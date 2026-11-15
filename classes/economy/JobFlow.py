"""The job board (design/roleplay-tools.md, section 10): jobs posted to the JOB_BOARD forum, claimed by characters,
finished by the poster or staff with rewards paid at once, and failing at their deadline. Player jobs
(JOB_PLAYER_POSTS) hold their currency reward in escrow until they end."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord

from classes.kernel import RoleplaySettings
from classes.kernel.ConfigData import ConfigData
from database.database import Jobs
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import Option, pick, reply

OPEN = "open"
TAKEN = "taken"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"
CLAIMED = "claimed"
WAITING = "waiting"
WITHDRAWN = "withdrawn"
FINISHED = "done"
SUCCESS = "success"
PARTIAL = "partial"
FAILURE = "failure"
STATE_MARKS = {OPEN : "🟢", TAKEN : "🟡", DONE : "✅", FAILED : "❌", CANCELLED : "⚪"}
JOB_REASON = "job"
ESCROW_REASON = "escrow"
REFUND_REASON = "refund"


class JobFlow :
	_locks: dict[int, asyncio.Lock] = {}

	# ============================================================
	@staticmethod
	def lock(job_id: int) -> asyncio.Lock :
		return JobFlow._locks.setdefault(job_id, asyncio.Lock())

	# ============================================================
	@staticmethod
	def runs(job: Jobs, member) -> bool :
		permissions = getattr(member, "guild_permissions", None)
		return member.id == job.poster_uid or bool(permissions and permissions.manage_messages)

	# ============================================================
	@staticmethod
	def reward_text(job: Jobs) -> str :
		reward = job.reward or {}
		currency = ConfigData().get_key(job.guild_id, ConfigMapping.CURRENCY_NAME)
		parts = [f"{reward['currency']} {currency}" if reward.get("currency") else None,
		         f"{reward['xp']} XP" if reward.get("xp") else None] + list(reward.get("items") or [])
		if job.faction_id and job.rep_success :
			faction = EconomyTransactions().faction(job.faction_id)
			parts.append(f"+{job.rep_success} standing with {faction.name if faction else '?'}")
		return ", ".join(part for part in parts if part) or "Nothing but gratitude"

	# ============================================================
	@staticmethod
	def embed(job: Jobs) -> discord.Embed :
		embed = discord.Embed(title=f"{STATE_MARKS.get(job.state, '')} {job.title}"[:256],
		                      description=job.description[:4096], colour=discord.Colour.dark_orange())
		embed.add_field(name="Reward (each)", value=JobFlow.reward_text(job)[:1024], inline=False)
		claims = EconomyTransactions().claims(job.id)
		names = []
		for claim in claims :
			character = CharacterTransactions().get_by_id(claim.character_id)
			mark = "⏳ " if claim.state == WAITING else ""
			names.append(f"{mark}{character.name if character else '?'} (<@{claim.uid}>)")
		embed.add_field(name=f"Taken ({sum(claim.state == CLAIMED for claim in claims)} of {job.slots})",
		                value="\n".join(names)[:1024] or "Nobody yet: press **Claim**.", inline=False)
		details = []
		if job.min_level > 1 :
			details.append(f"Level {job.min_level}+")
		if job.deadline :
			details.append(f"Deadline <t:{int(job.deadline.timestamp())}:R>")
		if job.location_id :
			from database.transactions.WorldTransactions import WorldTransactions

			location = WorldTransactions().location(job.location_id)
			if location is not None :
				details.append(f"📍 {location.name}")
		if job.poster_character_id :
			poster = CharacterTransactions().get_by_id(job.poster_character_id)
			details.append(f"Posted by {poster.name if poster else 'a character'}")
		if details :
			embed.add_field(name="Details", value=" · ".join(details), inline=False)
		embed.set_footer(text=f"Job #{job.id} · {job.state}")
		return embed

	# ============================================================
	@staticmethod
	async def refresh(bot: discord.Client, job_id: int) -> None :
		from views.economy.JobButtons import job_view

		job = EconomyTransactions().job(job_id)
		if job is None or job.thread_id is None :
			return
		try :
			thread = bot.get_channel(job.thread_id) or await bot.fetch_channel(job.thread_id)
			await thread.get_partial_message(job.message_id or job.thread_id).edit(embed=JobFlow.embed(job),
			                                                                       view=job_view(job))
			name = f"{STATE_MARKS.get(job.state, '')} {job.title}"[:100]
			if isinstance(thread, discord.Thread) and thread.name != name :
				await thread.edit(name=name, locked=job.state in (DONE, FAILED, CANCELLED),
				                  archived=job.state in (DONE, FAILED, CANCELLED))
		except discord.HTTPException as e :
			logging.warning(f"Could not update job {job_id}: {e}")

	# == posting ==

	# ============================================================
	@staticmethod
	async def post(interaction: discord.Interaction, title: str, description: str, currency: int, xp: int,
	               items_text: str | None, slots: int, min_level: int, faction_name: str | None, rep_success: int,
	               rep_failure: int, deadline_hours: int | None, location_channel, as_character: str | None) -> None :
		from classes.gear.Gear import Gear
		from classes.world.WorldFlow import WorldFlow
		from views.economy.JobButtons import job_view

		guild = interaction.guild
		board = await ConfigData().get_channel(guild, ConfigMapping.JOB_BOARD, optional=True)
		if not isinstance(board, discord.ForumChannel) :
			return await reply(interaction, "This server has no job board; staff set a forum with /config "
			                                "singlechannels job_board.")
		staff = interaction.user.guild_permissions.manage_messages
		poster_character = None
		if as_character or not staff :
			if not RoleplaySettings.toggle(guild.id, ConfigMapping.JOB_PLAYER_POSTS) and not staff :
				return await reply(interaction, "Only staff post jobs on this server.")
			poster_character = CharacterTransactions().get(interaction.user.id, guild.id, as_character or "")
			if poster_character is None or poster_character.state != APPROVED :
				return await reply(interaction, "Player jobs are posted as one of your approved characters "
				                                "(`as_character`).")
		items = []
		for name in [part.strip() for part in (items_text or "").split(",") if part.strip()] :
			item = GearItemTransactions().find(guild.id, name)
			if item is None :
				return await reply(interaction, f"The catalog has no item called {name}.")
			items.append(item.name)
		if poster_character is not None and (items or xp) and not staff :
			return await reply(interaction, "Player jobs can only pay currency.")
		faction = None
		if faction_name :
			faction = EconomyTransactions().find_faction(guild.id, faction_name)
			if faction is None :
				return await reply(interaction, f"There is no faction called {faction_name}.")
		escrow = 0
		if poster_character is not None and currency :
			escrow = currency * slots
			updated, problem = Gear.change_currency(poster_character, -escrow, ESCROW_REASON, interaction.user.id,
			                                        note=f"Job: {title}")
			if problem :
				return await reply(interaction, f"The reward is held up front ({escrow} for {slots} slots). {problem}")
		location = WorldFlow.location_here(location_channel) if location_channel else None
		deadline = datetime.now(timezone.utc) + timedelta(hours=deadline_hours) if deadline_hours else None
		job = EconomyTransactions().add_job(guild.id, poster_uid=interaction.user.id,
		                                    poster_character_id=poster_character.id if poster_character else None,
		                                    title=title[:100], description=description,
		                                    reward={"currency" : currency, "xp" : xp, "items" : items}, slots=slots,
		                                    min_level=min_level, faction_id=faction.id if faction else None,
		                                    rep_success=rep_success, rep_failure=rep_failure,
		                                    location_id=location.id if location else None, deadline=deadline,
		                                    state=OPEN, escrow=escrow)
		try :
			created = await board.create_thread(name=f"{STATE_MARKS[OPEN]} {job.title}"[:100], embed=JobFlow.embed(job),
			                                    view=job_view(job))
		except discord.HTTPException as e :
			logging.warning(f"Could not post job {job.id}: {e}")
			return await reply(interaction, "I couldn't post on the job board; check my permissions there.")
		EconomyTransactions().update_job(job.id, thread_id=created.thread.id, message_id=created.message.id)
		await reply(interaction, f"📋 Posted: {created.thread.mention}")

	# == claiming ==

	# ============================================================
	@staticmethod
	async def start_claim(interaction: discord.Interaction, job_id: int) -> None :
		job = EconomyTransactions().job(job_id)
		if job is None or job.state not in (OPEN, TAKEN) :
			return await reply(interaction, "This job isn't open.")
		if any(claim.uid == interaction.user.id for claim in EconomyTransactions().claims(job.id)) :
			return await reply(interaction, "You're already on this job.")
		characters = [character for character in
		              CharacterTransactions().get_all(interaction.user.id, interaction.guild_id, states=[APPROVED])
		              if character.level >= job.min_level and character.id != job.poster_character_id]
		if not characters :
			return await reply(interaction, f"You need an approved character of level {job.min_level} or higher.")
		if len(characters) == 1 :
			return await JobFlow.claim(interaction, job.id, characters[0].id)
		await pick(interaction, "Take the job with which character?",
		           [Option(character.name, character.id, f"Level {character.level}") for character in characters],
		           "Pick a character", lambda next_interaction, values : JobFlow.claim(next_interaction, job.id,
		                                                                              int(values[0])))

	# ============================================================
	@staticmethod
	async def claim(interaction: discord.Interaction, job_id: int, character_id: int) -> None :
		async with JobFlow.lock(job_id) :
			job = EconomyTransactions().job(job_id)
			character = CharacterTransactions().get_by_id(character_id)
			if job is None or job.state not in (OPEN, TAKEN) or character is None :
				return await reply(interaction, "This job isn't open.")
			claimed = sum(claim.state == CLAIMED for claim in EconomyTransactions().claims(job.id))
			state = CLAIMED if claimed < job.slots else WAITING
			EconomyTransactions().add_claim(job.id, character.id, interaction.user.id, state)
			EconomyTransactions().update_job(job.id, state=TAKEN)
		await JobFlow.refresh(interaction.client, job_id)
		await reply(interaction, f"{character.name} {'took the job' if state == CLAIMED else 'is on the waiting list'}.")

	# ============================================================
	@staticmethod
	async def withdraw(interaction: discord.Interaction, job_id: int) -> None :
		async with JobFlow.lock(job_id) :
			job = EconomyTransactions().job(job_id)
			claims = EconomyTransactions().claims(job_id) if job else []
			mine = next((claim for claim in claims if claim.uid == interaction.user.id), None)
			if mine is None :
				return await reply(interaction, "You aren't on this job.")
			EconomyTransactions().update_claim(mine.id, state=WITHDRAWN)
			if mine.state == CLAIMED :
				waiting = next((claim for claim in claims if claim.state == WAITING), None)
				if waiting is not None :
					EconomyTransactions().update_claim(waiting.id, state=CLAIMED)
			if not [claim for claim in EconomyTransactions().claims(job_id)] :
				EconomyTransactions().update_job(job_id, state=OPEN)
		await JobFlow.refresh(interaction.client, job_id)
		await reply(interaction, "You left the job.")

	# == finishing ==

	# ============================================================
	@staticmethod
	async def start_complete(interaction: discord.Interaction, job_id: int) -> None :
		job = EconomyTransactions().job(job_id)
		if job is None or job.state not in (OPEN, TAKEN) :
			return await reply(interaction, "This job is already over.")
		if not JobFlow.runs(job, interaction.user) :
			return await reply(interaction, "Only the job's poster (or staff) can finish it.")
		claims = [claim for claim in EconomyTransactions().claims(job.id) if claim.state == CLAIMED]
		if not claims :
			return await reply(interaction, "Nobody took this job; cancel it with /job cancel instead.")
		options = []
		for claim in claims :
			character = CharacterTransactions().get_by_id(claim.character_id)
			options.append(Option(character.name if character else "?", claim.id))

		async def chosen(next_interaction: discord.Interaction, values: list[str]) :
			outcomes = [Option("Success: full reward", SUCCESS), Option("Partial: half the reward", PARTIAL),
			            Option("Failure: no reward", FAILURE)]
			await pick(next_interaction, "How did it go?", outcomes, "Pick the outcome",
			           lambda last, picked : JobFlow.complete(last, job_id, [int(value) for value in values],
			                                                  picked[0]))

		await pick(interaction, "Who took part?", options, "Pick the characters", chosen, max_values=len(options))

	# ============================================================
	@staticmethod
	def pay_out(job: Jobs, claim_ids: list[int], outcome: str, actor_uid: int) -> list[str] :
		"""Pays the characters that took part. Returns lines saying what each got."""
		from classes.characters.Special import Special
		from classes.economy.FactionFlow import FactionFlow
		from classes.gear.Gear import Gear

		reward = job.reward or {}
		share = {SUCCESS : 1.0, PARTIAL : 0.5, FAILURE : 0.0}[outcome]
		faction = EconomyTransactions().faction(job.faction_id)
		lines, paid_currency = [], 0
		for claim in EconomyTransactions().claims(job.id) :
			part = claim.id in claim_ids and claim.state == CLAIMED
			EconomyTransactions().update_claim(claim.id, state=FINISHED if part else WITHDRAWN,
			                                   outcome=outcome if part else None)
			character = CharacterTransactions().get_by_id(claim.character_id)
			if not part or character is None :
				continue
			got = []
			currency = int((reward.get("currency") or 0) * share)
			if currency :
				Gear.change_currency(character, currency, JOB_REASON, actor_uid, note=f"Job: {job.title}")
				paid_currency += currency
				got.append(f"{currency} currency")
			xp = int((reward.get("xp") or 0) * share)
			if xp :
				Special.add_xp(character, xp)
				got.append(f"{xp} XP")
			if outcome == SUCCESS :
				for name in reward.get("items") or [] :
					item = GearItemTransactions().find(job.guild_id, name)
					if item is not None :
						Gear.grant(character, item, actor_uid)
						got.append(item.name)
			if faction is not None :
				change = job.rep_success if outcome == SUCCESS else (job.rep_success // 2 if outcome == PARTIAL else
				                                                      -job.rep_failure)
				if change :
					got += FactionFlow.change(character, faction, change, f"job {job.id}", actor_uid)
			lines.append(f"**{character.name}**: {', '.join(got) or 'nothing'}")
		if job.escrow :
			JobFlow.refund(job, job.escrow - paid_currency, actor_uid)
		return lines

	# ============================================================
	@staticmethod
	def refund(job: Jobs, amount: int, actor_uid: int | None) -> None :
		from classes.gear.Gear import Gear

		poster = CharacterTransactions().get_by_id(job.poster_character_id) if job.poster_character_id else None
		if poster is not None and amount > 0 :
			Gear.change_currency(poster, amount, REFUND_REASON, actor_uid, note=f"Job: {job.title}")
		EconomyTransactions().update_job(job.id, escrow=0)

	# ============================================================
	@staticmethod
	async def complete(interaction: discord.Interaction, job_id: int, claim_ids: list[int], outcome: str) -> None :
		async with JobFlow.lock(job_id) :
			job = EconomyTransactions().job(job_id)
			if job is None or job.state not in (OPEN, TAKEN) :
				return await reply(interaction, "This job is already over.")
			lines = JobFlow.pay_out(job, claim_ids, outcome, interaction.user.id)
			EconomyTransactions().update_job(job_id, state=FAILED if outcome == FAILURE else DONE)
		await JobFlow.say(interaction.client, job, f"📋 The job is over: **{outcome}**.\n" + "\n".join(lines))
		await JobFlow.refresh(interaction.client, job_id)
		await reply(interaction, "Job finished and rewards paid.")

	# ============================================================
	@staticmethod
	async def cancel(interaction: discord.Interaction, job_id: int) -> None :
		job = EconomyTransactions().job(job_id)
		if job is None or job.guild_id != interaction.guild_id or job.state not in (OPEN, TAKEN) :
			return await reply(interaction, "There is no open job with that number.")
		if not JobFlow.runs(job, interaction.user) :
			return await reply(interaction, "Only the job's poster (or staff) can cancel it.")
		JobFlow.refund(job, job.escrow, interaction.user.id)
		EconomyTransactions().update_job(job.id, state=CANCELLED)
		await JobFlow.say(interaction.client, job, "📋 This job was cancelled.")
		await JobFlow.refresh(interaction.client, job.id)
		await reply(interaction, "Job cancelled.")

	# ============================================================
	@staticmethod
	async def deadlines(bot: discord.Client, now: datetime | None = None) -> None :
		"""Fails jobs past their deadline, refunding escrow."""
		for job in EconomyTransactions().overdue_jobs(now or datetime.now(timezone.utc)) :
			JobFlow.refund(job, job.escrow, None)
			EconomyTransactions().update_job(job.id, state=FAILED)
			mentions = " ".join(f"<@{claim.uid}>" for claim in EconomyTransactions().claims(job.id))
			await JobFlow.say(bot, job, f"⌛ The deadline passed; the job failed. {mentions}", ping=True)
			await JobFlow.refresh(bot, job.id)

	# ============================================================
	@staticmethod
	async def say(bot: discord.Client, job: Jobs, text: str, ping: bool = False) -> None :
		if not job.thread_id :
			return
		try :
			thread = bot.get_channel(job.thread_id) or await bot.fetch_channel(job.thread_id)
			await thread.send(text[:2000], allowed_mentions=discord.AllowedMentions(users=ping))
		except discord.HTTPException :
			pass

	# ============================================================
	@staticmethod
	async def start_scene(interaction: discord.Interaction, job_id: int) -> None :
		from classes.scenes import Scenes
		from classes.scenes.SceneFlow import SceneFlow
		from database.transactions.SceneTransactions import SceneTransactions

		job = EconomyTransactions().job(job_id)
		claims = [claim for claim in EconomyTransactions().claims(job_id) if claim.state == CLAIMED] if job else []
		if job is None or not (JobFlow.runs(job, interaction.user) or
		                       any(claim.uid == interaction.user.id for claim in claims)) :
			return await reply(interaction, "Only the poster, staff or the characters on the job can start its scene.")
		if interaction.channel_id != job.thread_id :
			return await reply(interaction, "Press it in the job's thread.")
		await SceneFlow.start(interaction, job.title, Scenes.ORDER)
		scene = SceneTransactions().open_in(job.thread_id)
		if scene is None :
			return
		for position, claim in enumerate(claims, start=1) :
			SceneTransactions().add_participant(scene.id, claim.character_id, claim.uid, position)
		SceneTransactions().update(scene.id, turn_started_at=datetime.now(timezone.utc))
		await SceneFlow.refresh(interaction.client, scene.id)
