"""The chronicle (design/roleplay-tools.md, section 3): a finished scene (or a stretch of older roleplay) written up as
a transcript in the CHRONICLE forum, with a summary card, an HTML and a Markdown file, and per-character counts."""
import html
import io
import logging
import re
from datetime import datetime, timezone

import discord

from classes.kernel import RoleplaySettings
from classes.proxy.Compose import Compose
from classes.scenes import Scenes
from database.database import Chronicles, Scenes as SceneRecord
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from database.transactions.SceneTransactions import SceneTransactions
from resources.configs.ConfigMapping import ConfigMapping

CARD_PREFIXES = ("🎯", "⚔️", "🎲", "👁️")
# The scene card, chronicles and location cards aren't part of the story.
SKIPPED_PREFIXES = ("🎭", "📜", "📍")
CHRONICLE_COLOUR = discord.Colour.dark_gold()
LINK = re.compile(r"https?://(?:\w+\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)")
STYLE = """body{background:#313338;color:#dbdee1;font-family:'gg sans','Segoe UI',sans-serif;margin:0;padding:24px}
h1{color:#f2f3f5}.meta{color:#949ba4;margin-bottom:24px}.post{display:flex;gap:16px;margin:16px 0}
.avatar{width:40px;height:40px;border-radius:50%;flex:none;background:#5865f2}.name{color:#f2f3f5;font-weight:600}
.time{color:#949ba4;font-size:12px;margin-left:8px}.text{white-space:pre-wrap;line-height:1.4}
.note{color:#b5bac1;font-style:italic;margin:8px 0 8px 56px}.lang{color:#c9a0ff;font-size:12px}"""


# ============================================================
def snowflake(moment: datetime, high: bool = False) -> int :
	return discord.utils.time_snowflake(moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc), high=high)


# ============================================================
def card_note(message: discord.Message) -> str | None :
	"""A check, dice or table card as a one-line note."""
	for embed in message.embeds :
		title = embed.title or ""
		if title.startswith(SKIPPED_PREFIXES) :
			continue
		# Check and table cards start with an emoji; dice cards have an author line ("Ayla · Perception check").
		if not title.startswith(CARD_PREFIXES) and not (embed.author and embed.author.name) :
			continue
		parts = [title]
		if embed.author and embed.author.name :
			parts.insert(0, embed.author.name)
		result = next((field.value for field in embed.fields if field.name in ("Result", "Rewards", "Encounter")),
		              None)
		total = re.search(r"# 🎲 (-?\d+)", embed.description or "")
		if total :
			parts.append(f"rolled {total.group(1)}")
		if result :
			parts.append(result.replace("\n", " "))
		return " · ".join(part for part in parts if part)[:300]
	return None


# ============================================================
def inline_markdown(text: str) -> str :
	"""Escapes text for HTML, keeping bold and italics."""
	text = html.escape(text)
	text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
	text = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", text)
	return re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<i>\1</i>", text)


# ============================================================
def render_html(title: str, meta: str, entries: list[dict]) -> str :
	rows = []
	for entry in entries :
		if entry["kind"] == "note" :
			rows.append(f'<div class="note">{html.escape(entry["text"])}</div>')
			continue
		avatar = f'<img class="avatar" src="{html.escape(entry["avatar"])}">' if entry.get("avatar") else \
			'<div class="avatar"></div>'
		rows.append(f'<div class="post">{avatar}<div><span class="name">{html.escape(entry["name"])}</span>'
		            f'<span class="time">{entry["time"]:%Y-%m-%d %H:%M}</span>'
		            f'<div class="text">{inline_markdown(entry["text"])}</div></div></div>')
	return (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
	        f'<style>{STYLE}</style></head><body><h1>{html.escape(title)}</h1><div class="meta">{html.escape(meta)}</div>'
	        + "".join(rows) + "</body></html>")


# ============================================================
def render_markdown(title: str, meta: str, entries: list[dict]) -> str :
	lines = [f"# {title}", "", meta, ""]
	for entry in entries :
		if entry["kind"] == "note" :
			lines += [f"> {entry['text']}", ""]
		else :
			lines += [f"**{entry['name']}** · {entry['time']:%Y-%m-%d %H:%M}", "", entry["text"], ""]
	return "\n".join(lines)


# ============================================================
def counts(entries: list[dict]) -> dict[int, tuple[int, int]] :
	"""{character_id: (posts, words)}"""
	found = {}
	for entry in entries :
		if entry["kind"] == "post" and entry.get("character_id") :
			posts, words = found.get(entry["character_id"], (0, 0))
			found[entry["character_id"]] = (posts + 1, words + Scenes.words(entry["text"]))
	return found


class ChronicleFlow :

	# ============================================================
	@staticmethod
	def original(first_message_id: int) -> str | None :
		"""The original text of a post written in a language (phase D), with ‹Language› markers."""
		try :
			from classes.language.LanguageFlow import LanguageFlow
		except ImportError :
			return None
		return LanguageFlow.chronicle_text(first_message_id)

	# ============================================================
	@staticmethod
	async def gather(bot: discord.Client, channel, first_id: int, last_id: int) -> list[dict] :
		"""The proxied posts (and check, dice and table cards as notes) between two message ids, oldest first."""
		logged = ProxyTransactions().in_range(channel.id, first_id, last_id)
		by_message = {entry.message_id : entry for entry in logged}
		entries, current_post = [], None
		async for message in channel.history(after=discord.Object(first_id - 1), before=discord.Object(last_id + 1),
		                                     limit=None, oldest_first=True) :
			entry = by_message.get(message.id)
			if entry is not None :
				_, text = Compose.strip_reply_line(message.content or "")
				if current_post is not None and current_post["first"] == entry.first_message_id :
					current_post["text"] += "\n" + text
					continue
				original = ChronicleFlow.original(entry.first_message_id)
				current_post = {"kind" : "post", "first" : entry.first_message_id, "time" : message.created_at,
				                "name" : message.author.display_name, "character_id" : entry.character_id,
				                "avatar" : message.author.display_avatar.url if message.author.avatar else None,
				                "text" : original if original is not None else text}
				entries.append(current_post)
				continue
			if bot.user is not None and message.author.id == bot.user.id :
				note = card_note(message)
				if note :
					entries.append({"kind" : "note", "text" : note, "time" : message.created_at})
		return entries

	# ============================================================
	@staticmethod
	async def write(bot: discord.Client, guild: discord.Guild, title: str, channel, first_id: int, last_id: int,
	                creator_uid: int | None, scene: SceneRecord | None = None) -> tuple[Chronicles | None, str | None] :
		"""Builds and posts a chronicle. Returns it, or None and why it wasn't written."""
		from classes.kernel.ConfigData import ConfigData

		target = await ConfigData().get_channel(guild, ConfigMapping.CHRONICLE, optional=True)
		if target is None :
			return None, "This server has no chronicle channel; staff set one with /config singlechannels."
		entries = await ChronicleFlow.gather(bot, channel, first_id, last_id)
		posts = [entry for entry in entries if entry["kind"] == "post"]
		if not posts :
			return None, "There are no posts made as characters in that stretch."
		tally = counts(entries)
		names = {}
		for character_id in tally :
			character = CharacterTransactions().get_by_id(character_id)
			names[character_id] = character.name if character else "?"
		started, ended = posts[0]["time"], posts[-1]["time"]
		world = ""
		if scene is not None and scene.world_start :
			end = scene.world_end.get("text") if scene.world_end else None
			world = f" · In-world: {scene.world_start.get('text')}{f' to {end}' if end and end != scene.world_start.get('text') else ''}"
		meta = f"{getattr(channel, 'name', 'roleplay')} · {started:%Y-%m-%d} to {ended:%Y-%m-%d}{world}"
		summary = discord.Embed(title=f"📜 {title}"[:256], colour=CHRONICLE_COLOUR,
		                        description=f"[Jump to the roleplay](https://discord.com/channels/{guild.id}/"
		                                    f"{channel.id}/{first_id})\n{meta}"[:4096])
		summary.add_field(name="Characters", value="\n".join(
			f"**{names[character_id]}** · {posts_} posts · {words} words"
			for character_id, (posts_, words) in sorted(tally.items(), key=lambda item : -item[1][1]))[:1024],
		                  inline=False)
		if scene is not None and scene.summary :
			summary.add_field(name="Summary", value=scene.summary[:1024], inline=False)
		safe = re.sub(r"[^\w-]+", "_", title)[:60] or "chronicle"
		files = [discord.File(io.BytesIO(render_html(title, meta, entries).encode("utf-8")), filename=f"{safe}.html"),
		         discord.File(io.BytesIO(render_markdown(title, meta, entries).encode("utf-8")), filename=f"{safe}.md")]
		record = SceneTransactions().add_chronicle(guild.id, title[:200], channel.id, scene_id=scene.id if scene else None,
		                                           first_message_id=first_id, last_message_id=last_id,
		                                           created_by=creator_uid, summary=scene.summary if scene else None)
		if record is None :
			return None, "Something went wrong saving the chronicle."
		from views.scenes.SceneButtons import chronicle_view

		view = chronicle_view(record.id)
		try :
			if isinstance(target, discord.ForumChannel) :
				created = await target.create_thread(name=title[:100], embed=summary, files=files, view=view)
				thread_id, message_id = created.thread.id, created.message.id
			else :
				message = await target.send(embed=summary, files=files, view=view)
				thread_id, message_id = None, message.id
				try :
					thread = await message.create_thread(name=title[:100])
					thread_id = thread.id
				except discord.HTTPException :
					pass
		except discord.HTTPException as e :
			logging.warning(f"Could not post a chronicle in {guild.name}: {e}")
			return None, "I couldn't post in the chronicle channel; check my permissions there."
		record = SceneTransactions().update_chronicle(record.id, thread_id=thread_id, message_id=message_id)
		SceneTransactions().set_chronicle_characters(record.id, tally)
		if scene is not None :
			SceneTransactions().update(scene.id, chronicle_id=record.id)
		if RoleplaySettings.toggle(guild.id, ConfigMapping.CHRONICLE_CHARACTER_POSTS) :
			await ChronicleFlow._tell_characters(bot, record, tally)
		return record, None

	# ============================================================
	@staticmethod
	async def _tell_characters(bot: discord.Client, record: Chronicles, tally: dict) -> None :
		link = f"<#{record.thread_id}>" if record.thread_id else record.title
		for character_id in tally :
			character = CharacterTransactions().get_by_id(character_id)
			if character is None or not character.forum_thread_id :
				continue
			thread = bot.get_channel(character.forum_thread_id)
			try :
				thread = thread or await bot.fetch_channel(character.forum_thread_id)
				await thread.send(f"📜 Appeared in **{record.title}**: {link}",
				                  allowed_mentions=discord.AllowedMentions.none())
			except discord.HTTPException :
				continue

	# ============================================================
	@staticmethod
	async def for_scene(bot: discord.Client, guild: discord.Guild, scene: SceneRecord,
	                    ender_uid: int | None) -> Chronicles | None :
		from classes.kernel.ConfigData import ConfigData

		if ConfigData().get_int(guild.id, ConfigMapping.CHRONICLE) is None :
			return None
		channel = guild.get_channel_or_thread(scene.channel_id)
		if channel is None :
			return None
		first = scene.card_message_id or snowflake(scene.started_at)
		last = snowflake(scene.ended_at or datetime.now(timezone.utc), high=True)
		record, problem = await ChronicleFlow.write(bot, guild, scene.title, channel, first, last, ender_uid, scene)
		if problem :
			logging.info(f"No chronicle for scene {scene.id}: {problem}")
		return record

	# ============================================================
	@staticmethod
	def parse_link(text: str) -> tuple[int, int, int] | None :
		"""A message link → (guild id, channel id, message id)."""
		match = LINK.search(text or "")
		return (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else None
