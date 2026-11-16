"""Scene summaries drafted by a local model (Ollama on the bot's own server). See design/roleplay-tools.md, section 3.

Every summary goes through the bot's Queue, so only one is written at a time and two scenes ending together never
split the CPU between them.

- **When a scene ends** without a summary, the job reads the scene's posts, asks the model for a short summary and
  saves it as the scene's (and its chronicle's) summary. It is posted as a draft in the chronicle thread (or the
  scene's channel when there is no chronicle), added to the chronicle card and written into the timeline entry.
  Players fix it with the chronicle's **Add summary** button. A summary someone wrote meanwhile is never replaced.
- **`/scene summary`** asks for the story so far of an open scene; the answer is sent only to whoever asked.

Set OLLAMA_URL in .env to turn it on; SUMMARY_MODEL and SUMMARY_THREADS tune it. A server switches it off with
`/config roleplay SCENE_AI_SUMMARY off`.
"""
import asyncio
import logging
import re

import aiohttp
import discord

from classes.kernel import RoleplaySettings
from classes.kernel.Queue import Queue
from data.env.loader import env
from database.database import Scenes as SceneRecord
from database.transactions.SceneTransactions import SceneTransactions
from resources.configs.ConfigMapping import ConfigMapping

DEFAULT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
DEFAULT_THREADS = 4
# One request may take a long scene several minutes on a CPU; past this it is given up.
TIMEOUT_SECONDS = 20 * 60
# About 10-13k tokens. Longer transcripts are summarised in parts, then the parts merged.
PART_CHARS = 40_000
MAX_SUMMARY = 1500  # the Add summary form's limit
DRAFTING = "(Being drafted…)"
NO_SUMMARY = "(Post below!)"
TIMELINE_LINE = "Brief summary of what happened: "

SYSTEM = (
	"You summarise roleplay scenes for a Discord server's timeline. Write one or two short paragraphs, third person, "
	"past tense, about 150 words. Say who was there, where it happened and what changed: decisions, fights and their "
	"outcomes, discoveries, promises, injuries, items gained or lost. Use the character names exactly as written. "
	"Only state what the transcript shows; never invent events, motives or names. No headings, no lists, no preamble."
)
OOC = re.compile(r"^\s*(\(\(.*\)\)|//.*|ooc\s*:.*)\s*$", re.IGNORECASE)
THINKING = re.compile(r"<think>.*?</think>", re.DOTALL)

# Open requests per scene: {scene id: [interactions waiting for the story so far]}. A second request for the same
# scene joins the first instead of queueing another job.
_waiting: dict[int, list[discord.Interaction]] = {}
# Scenes whose end-of-scene summary is queued or being written.
_ending: set[int] = set()


# ============================================================
def configured() -> bool :
	return bool(env("OLLAMA_URL"))


# ============================================================
def available(guild_id: int) -> bool :
	return configured() and RoleplaySettings.toggle(guild_id, ConfigMapping.SCENE_AI_SUMMARY)


# ============================================================
def threads() -> int :
	try :
		return max(1, int(env("SUMMARY_THREADS", DEFAULT_THREADS)))
	except ValueError :
		return DEFAULT_THREADS


# ============================================================
def transcript(entries: list[dict]) -> str :
	"""The posts as 'Name: text' lines and check, dice and table cards as [notes], without blank or OOC lines."""
	lines = []
	for entry in entries :
		if entry["kind"] == "note" :
			lines.append(f"[{entry['text']}]")
			continue
		for line in entry["text"].splitlines() :
			if line.strip() and not OOC.match(line) :
				lines.append(f"{entry['name']}: {line.strip()}")
	return "\n".join(lines)


# ============================================================
def parts(text: str, size: int = PART_CHARS) -> list[str] :
	"""Splits a transcript on line breaks into pieces of at most `size` characters (a longer line is cut)."""
	pieces, current = [], ""
	for line in text.splitlines() :
		while len(line) > size :
			if current :
				pieces.append(current)
				current = ""
			pieces.append(line[:size])
			line = line[size:]
		if current and len(current) + 1 + len(line) > size :
			pieces.append(current)
			current = ""
		current = f"{current}\n{line}" if current else line
	if current :
		pieces.append(current)
	return pieces


# ============================================================
def context_for(characters: int) -> int :
	"""A context window that fits the text (about 3 characters a token, to be safe) plus the answer."""
	needed = characters // 3 + 1024
	window = 4096
	while window < needed and window < 32768 :
		window *= 2
	return window


# ============================================================
async def ask(text: str, instruction: str) -> str | None :
	"""One request to the model. Returns its answer, or None when it couldn't be reached or said nothing."""
	body = {
		"model"      : env("SUMMARY_MODEL", DEFAULT_MODEL),
		"stream"     : False,
		"messages"   : [{"role" : "system", "content" : SYSTEM},
		                {"role" : "user", "content" : f"{instruction}\n\n{text}"}],
		"options"    : {"num_ctx" : context_for(len(text)), "num_thread" : threads(), "temperature" : 0.3},
	}
	url = f"{str(env('OLLAMA_URL')).rstrip('/')}/api/chat"
	try :
		async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)) as session :
			async with session.post(url, json=body) as response :
				if response.status != 200 :
					logging.warning(f"The summary model answered {response.status}: {(await response.text())[:300]}")
					return None
				data = await response.json()
	except (aiohttp.ClientError, asyncio.TimeoutError) as e :
		logging.warning(f"The summary model couldn't be reached at {url}: {e!r}")
		return None
	answer = THINKING.sub("", (data.get("message") or {}).get("content") or "").strip()
	return answer or None


# ============================================================
async def summarise(entries: list[dict], title: str, so_far: bool = False) -> str | None :
	"""A summary of the scene's posts, or None when there is nothing to summarise or the model didn't answer."""
	text = transcript(entries)
	if not text :
		return None
	what = f"the scene \"{title}\"" + (" so far (it is still going on)" if so_far else "")
	pieces = parts(text)
	if len(pieces) == 1 :
		answer = await ask(text, f"Summarise {what}.")
	else :
		summaries = []
		for number, piece in enumerate(pieces, 1) :
			summary = await ask(piece, f"This is part {number} of {len(pieces)} of {what}. Summarise just this part "
			                           f"in about 100 words.")
			if summary is None :
				return None
			summaries.append(f"Part {number}: {summary}")
		answer = await ask("\n\n".join(summaries), f"These are summaries of the consecutive parts of {what}, in order. "
		                                           f"Merge them into one summary.")
	return answer[:MAX_SUMMARY].strip() if answer else None


# ============================================================
async def scene_entries(bot: discord.Client, scene: SceneRecord) -> list[dict] :
	"""The scene's posts from its start to its end (or now), as the chronicle reads them."""
	from classes.scenes.ChronicleFlow import ChronicleFlow, scene_range

	channel = bot.get_channel(scene.channel_id)
	if channel is None :
		try :
			channel = await bot.fetch_channel(scene.channel_id)
		except discord.HTTPException :
			return []
	return await ChronicleFlow.gather(bot, channel, *scene_range(scene))


# == when a scene ends ==

# ============================================================
def queue_scene_end(bot: discord.Client, scene_id: int, chronicle_id: int | None,
                    timeline: discord.Message | None = None) -> bool :
	"""Queues the end-of-scene summary. False when one is already queued for the scene."""
	if scene_id in _ending :
		return False
	_ending.add(scene_id)
	Queue().add(scene_ended(bot, scene_id, chronicle_id, timeline), priority=1)
	return True


# ============================================================
def save(scene_id: int, chronicle_id: int | None, text: str) -> bool :
	"""Stores a drafted summary on the scene and its chronicle, unless someone wrote one meanwhile."""
	scene = SceneTransactions().get(scene_id)
	chronicle = SceneTransactions().chronicle(chronicle_id) if chronicle_id else None
	if scene is None or scene.summary or (chronicle is not None and chronicle.summary) :
		return False
	SceneTransactions().update(scene_id, summary=text)
	if chronicle is not None :
		SceneTransactions().update_chronicle(chronicle.id, summary=text)
	return True


# ============================================================
async def scene_ended(bot: discord.Client, scene_id: int, chronicle_id: int | None,
                      timeline: discord.Message | None) -> None :
	text = None
	try :
		scene = SceneTransactions().get(scene_id)
		if scene is None or scene.summary :
			return
		text = await summarise(await scene_entries(bot, scene), scene.title)
		if text is None or not save(scene_id, chronicle_id, text) :
			text = None
			return
		chronicle = SceneTransactions().chronicle(chronicle_id) if chronicle_id else None
		await _post_draft(bot, scene, chronicle, text)
		if chronicle is not None :
			await _add_to_card(bot, chronicle, text)
	finally :
		_ending.discard(scene_id)
		await _fill_timeline(timeline, text)


# ============================================================
async def _post_draft(bot: discord.Client, scene: SceneRecord, chronicle, text: str) -> None :
	where = chronicle.thread_id if chronicle is not None and chronicle.thread_id else scene.channel_id
	fix = "fix it with **Add summary** on the chronicle" if chronicle is not None else "staff can correct it"
	try :
		channel = bot.get_channel(where) or await bot.fetch_channel(where)
		await channel.send(f"🤖 **Draft summary** of **{scene.title}** (written by the bot; {fix}):\n{text}"[:2000],
		                   allowed_mentions=discord.AllowedMentions.none())
	except discord.HTTPException as e :
		logging.warning(f"Could not post the drafted summary of scene {scene.id}: {e}")


# ============================================================
async def _add_to_card(bot: discord.Client, chronicle, text: str) -> None :
	"""Adds the summary to the chronicle's card. Forum posts keep the card in their thread; text channels don't."""
	from classes.kernel.ConfigData import ConfigData

	if not chronicle.message_id :
		return
	try :
		channel = bot.get_channel(chronicle.thread_id) if chronicle.thread_id else None
		message = None
		if channel is not None :
			try :
				message = await channel.fetch_message(chronicle.message_id)
			except discord.NotFound :
				message = None
		if message is None :
			guild = bot.get_guild(chronicle.guild_id)
			target = await ConfigData().get_channel(guild, ConfigMapping.CHRONICLE, optional=True) if guild else None
			if target is None or isinstance(target, discord.ForumChannel) :
				return
			message = await target.fetch_message(chronicle.message_id)
		if not message.embeds :
			return
		embed = message.embeds[0]
		if any(field.name == "Summary" for field in embed.fields) :
			return
		embed.add_field(name="Summary", value=text[:1024], inline=False)
		await message.edit(embed=embed)
	except discord.HTTPException as e :
		logging.warning(f"Could not add the summary to chronicle {chronicle.id}'s card: {e}")


# ============================================================
async def _fill_timeline(timeline: discord.Message | None, text: str | None) -> None :
	"""Swaps the timeline entry's 'being drafted' placeholder for the summary, or for the usual 'post below'."""
	if timeline is None or f"{TIMELINE_LINE}{DRAFTING}" not in (timeline.content or "") :
		return
	content = timeline.content.replace(f"{TIMELINE_LINE}{DRAFTING}", f"{TIMELINE_LINE}{text or NO_SUMMARY}")
	try :
		await timeline.edit(content=content[:2000], allowed_mentions=discord.AllowedMentions.none())
	except discord.HTTPException as e :
		logging.warning(f"Could not fill in the timeline entry {timeline.id}: {e}")


# == on request ==

# ============================================================
async def request(interaction: discord.Interaction, scene: SceneRecord) -> None :
	"""/scene summary: queues the story so far of an open scene, sent only to whoever asked."""
	from views.combat.Pickers import reply

	if not configured() :
		return await reply(interaction, "Scene summaries aren't set up on this bot.")
	if not RoleplaySettings.toggle(interaction.guild_id, ConfigMapping.SCENE_AI_SUMMARY) :
		return await reply(interaction, "Scene summaries are switched off on this server.")
	waiting = _waiting.get(scene.id)
	if waiting is not None :
		waiting.append(interaction)
		return await reply(interaction, "A summary of this scene is already being written; you'll get it here too.")
	_waiting[scene.id] = [interaction]
	ahead = len(Queue().high_priority_queue)
	Queue().add(story_so_far(interaction.client, scene.id), priority=2)
	await reply(interaction, "📝 Writing a summary of the scene so far; it can take a few minutes"
	                         + (f" ({ahead} ahead of it)" if ahead else "") + ". I'll send it here.")


# ============================================================
async def story_so_far(bot: discord.Client, scene_id: int) -> None :
	text, scene = None, None
	try :
		scene = SceneTransactions().get(scene_id)
		if scene is not None :
			text = await summarise(await scene_entries(bot, scene), scene.title, so_far=bool(scene.state != "ended"))
	finally :
		message = f"📝 **The story so far** in **{scene.title}**:\n{text}" if text and scene else \
			"I couldn't write a summary of that scene; try again later."
		for interaction in _waiting.pop(scene_id, []) :
			await _answer(interaction, message[:2000])


# ============================================================
async def _answer(interaction: discord.Interaction, text: str) -> None :
	"""Sends the answer privately: as a follow-up while the command's token lasts (15 minutes), else by DM."""
	try :
		await interaction.followup.send(text, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
		return
	except discord.HTTPException :
		pass
	try :
		await interaction.user.send(text, allowed_mentions=discord.AllowedMentions.none())
	except discord.HTTPException as e :
		logging.info(f"Could not send a scene summary to {interaction.user.id}: {e}")
