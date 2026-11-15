"""The Discord side of fights: starting them in a thread, running engine calls one at a time per fight, saving and
logging the result, posting it in the thread, pinging whoever is up next, and keeping the board current.

Every change to a fight goes through CombatFlow.run: it loads the fight, runs one engine call under the fight's lock,
saves it, logs it (with a snapshot for undo) and posts what happened.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

import discord

from classes.combat import Board
from classes.combat.DamageTypes import DamageTypes
from classes.combat.Engine import CombatError, Engine, Outcome
from classes.combat.Loadout import Loadout
from classes.combat.State import ACTIVE, ENDED, Fight, LIVE, PAUSED, PENDING, PVE, PVP, SETUP
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.CombatTransactions import CombatTransactions
from resources.configs.ConfigMapping import ConfigMapping, defaults
from views.combat.Pickers import reply

# The sheet field injuries are written to, and how long it may get.
INJURIES = "Injuries"
INJURY_LIMIT = 2000

MESSAGE_LIMIT = 2000
THREAD_ARCHIVE_MINUTES = 10080
DEFAULT_SIDES = ["Party", "Enemies"]
LETHAL_OFF = "off"
LETHAL_GM = "gm"
LETHAL_AGREED = "agreed"


class CombatFlow :
	# One lock per fight, so two members acting at once never overwrite each other.
	locks: dict[int, asyncio.Lock] = {}

	# == settings ==

	# ============================================================
	@staticmethod
	def timers(guild_id: int) -> tuple[int, int] :
		"""Seconds per async phase and per live turn."""
		config = ConfigData()
		hours = config.get_int(guild_id, ConfigMapping.COMBAT_ASYNC_TIMER) or defaults[ConfigMapping.COMBAT_ASYNC_TIMER]
		minutes = config.get_int(guild_id, ConfigMapping.COMBAT_LIVE_TIMER) or defaults[ConfigMapping.COMBAT_LIVE_TIMER]
		return max(1, hours) * 3600, max(1, minutes) * 60

	# ============================================================
	@staticmethod
	def engine(fight: Fight, now: datetime | None = None) -> Engine :
		async_seconds, live_seconds = CombatFlow.timers(fight.guild_id)
		return Engine(fight, DamageTypes.table(fight.guild_id), now=now or datetime.now(timezone.utc),
		              async_seconds=async_seconds, live_seconds=live_seconds)

	# ============================================================
	@staticmethod
	def pacing(guild_id: int, chosen: str | None) -> str :
		"""The pacing a new fight gets: the server's, or the starter's pick when the server lets them choose."""
		setting = str(ConfigData().get_key(guild_id, ConfigMapping.COMBAT_PACING) or "async").lower()
		if setting in ("async", LIVE) :
			return setting
		return chosen if chosen in ("async", LIVE) else "async"

	# ============================================================
	@staticmethod
	def lethal_mode(guild_id: int) -> str :
		mode = str(ConfigData().get_key(guild_id, ConfigMapping.COMBAT_LETHAL) or LETHAL_GM).lower()
		return mode if mode in (LETHAL_OFF, LETHAL_GM, LETHAL_AGREED) else LETHAL_GM

	# ============================================================
	@staticmethod
	def lethal_problem(guild_id: int, staff: bool) -> str | None :
		"""Why this member can't start a lethal fight, or None."""
		mode = CombatFlow.lethal_mode(guild_id)
		if mode == LETHAL_OFF :
			return "Lethal fights are turned off on this server."
		if mode == LETHAL_GM and not staff :
			return "Only staff can start lethal fights on this server."
		return None

	# == threads and the board ==

	# ============================================================
	@staticmethod
	async def thread(bot: discord.Client, fight: Fight) -> discord.Thread | None :
		if not fight.thread_id :
			return None
		channel = bot.get_channel(fight.thread_id)
		if channel is None :
			try :
				channel = await bot.fetch_channel(fight.thread_id)
			except discord.HTTPException :
				return None
		if isinstance(channel, discord.Thread) and channel.archived :
			try :
				await channel.edit(archived=False)
			except discord.HTTPException :
				pass
		return channel

	# ============================================================
	@staticmethod
	async def update_board(bot: discord.Client, fight: Fight) -> None :
		"""Edits the board, or posts (and pins) a new one when it is gone."""
		from views.combat.BoardButtons import board_view

		thread = await CombatFlow.thread(bot, fight)
		if thread is None :
			return
		embed = Board.embed(fight, CombatFlow.engine(fight))
		view = board_view(fight)
		if fight.board_message_id :
			try :
				message = thread.get_partial_message(fight.board_message_id)
				await message.edit(embed=embed, view=view)
				return
			except discord.NotFound :
				pass
			except discord.HTTPException as e :
				logging.warning(f"Could not update the board of fight {fight.id}: {e}")
				return
		try :
			message = await thread.send(embed=embed, view=view)
		except discord.HTTPException as e :
			logging.warning(f"Could not post the board of fight {fight.id}: {e}")
			return
		try :
			await message.pin()
		except discord.HTTPException :
			pass
		fight.board_message_id = message.id
		CombatTransactions().set_fields(fight.id, board_message_id=message.id)

	# ============================================================
	@staticmethod
	def chunks(lines: list[str]) -> list[str] :
		messages, current = [], ""
		for line in lines :
			line = line[:MESSAGE_LIMIT]
			if current and len(current) + 1 + len(line) > MESSAGE_LIMIT :
				messages.append(current)
				current = line
			else :
				current = f"{current}\n{line}" if current else line
		if current :
			messages.append(current)
		return messages

	# ============================================================
	@staticmethod
	async def post(bot: discord.Client, fight: Fight, outcome: Outcome) -> None :
		"""Posts what happened in the thread, then pings whoever has to act and the GM when needed."""
		thread = await CombatFlow.thread(bot, fight)
		if thread is None :
			return
		try :
			for text in CombatFlow.chunks(outcome.lines) :
				await thread.send(text, allowed_mentions=discord.AllowedMentions.none())
			if outcome.pings and fight.state == ACTIVE :
				mentions = " ".join(f"<@{uid}>" for uid in outcome.pings)
				await thread.send(f"{mentions} it's your turn: press **Act** on the board.",
				                  allowed_mentions=discord.AllowedMentions(users=True))
			if outcome.gm_pings :
				gms = " ".join(f"<@{uid}>" for uid in [fight.gm_uid] + list(fight.co_gms or []))
				await thread.send(f"{gms} " + " ".join(outcome.gm_pings),
				                  allowed_mentions=discord.AllowedMentions(users=True))
		except discord.HTTPException as e :
			logging.warning(f"Could not post in the thread of fight {fight.id}: {e}")

	# == running engine calls ==

	# ============================================================
	@staticmethod
	def lock(fight_id: int) -> asyncio.Lock :
		return CombatFlow.locks.setdefault(fight_id, asyncio.Lock())

	# ============================================================
	@staticmethod
	async def run(bot: discord.Client, fight_id: int, action: Callable[[Engine], Outcome | None],
	              interaction: discord.Interaction | None = None, label: str = "action", undoable: bool = True,
	              actor_id: int | None = None, target_id: int | None = None) -> Outcome | None :
		"""Runs one engine call on a fight. A CombatError is shown to the member and changes nothing.

		@return: the outcome, or None when the action was refused or the fight is gone.
		"""
		async with CombatFlow.lock(fight_id) :
			fight = CombatTransactions().load(fight_id)
			if fight is None :
				if interaction is not None :
					await reply(interaction, "That fight no longer exists.")
				return None
			CombatFlow.refresh_streaks(fight)
			engine = CombatFlow.engine(fight)
			snapshot = fight.snapshot() if undoable else None
			try :
				outcome = action(engine) or engine.outcome
			except CombatError as e :
				if interaction is not None :
					await reply(interaction, str(e))
				return None
			CombatTransactions().save(fight)
			CombatFlow.use_up(outcome.used_items)
			CombatFlow.save_streaks(outcome.streaks)
			if outcome.lines :
				CombatTransactions().log(fight.id, fight.round, label, "\n".join(outcome.lines), actor_id, target_id,
				                         snapshot=snapshot)
		await CombatFlow.post(bot, fight, outcome)
		await CombatFlow.after_deaths(bot, outcome)
		await CombatFlow.update_board(bot, fight)
		return outcome

	# ============================================================
	@staticmethod
	async def after_deaths(bot: discord.Client, outcome: Outcome) -> None :
		"""Marks characters whose death the GM confirmed as dead: they stop posting and their post is locked."""
		from classes.characters.Death import Death
		from classes.characters.ForumPost import ForumPost

		for character_id in outcome.deaths.values() :
			character = CharacterTransactions().get_by_id(character_id)
			if character is None :
				continue
			updated, _ = Death.die(character)
			if updated is not None :
				logging.info(f"Character {character.id} died in combat")
				await ForumPost.retire(bot, updated, lock=True)

	# ============================================================
	@staticmethod
	def refresh_streaks(fight: Fight) -> None :
		"""Reads the characters' bad-roll streaks into the fight, as /dice rolls may have changed them."""
		for combatant in fight.combatants :
			if combatant.character_id :
				character = CharacterTransactions().get_by_id(combatant.character_id)
				if character is not None :
					combatant.stats["bad_streak"] = int(getattr(character, "bad_streak", 0) or 0)

	# ============================================================
	@staticmethod
	def save_streaks(streaks: dict) -> None :
		for character_id, streak in streaks.items() :
			CharacterTransactions().update(character_id, bad_streak=int(streak))

	# ============================================================
	@staticmethod
	def used_items(fight: Fight) -> set[int] :
		return {entry_id for combatant in fight.combatants for entry_id in combatant.stats.get("used_items") or []}

	# ============================================================
	@staticmethod
	def use_up(entry_ids: list[int]) -> None :
		"""Marks consumables used in a fight as used on the characters' gear."""
		from classes.gear.Gear import Gear

		for entry_id in entry_ids :
			Gear.use_up(entry_id)

	# ============================================================
	@staticmethod
	def give_back(entry_ids: set[int]) -> None :
		"""Gives back consumables whose use the GM undid."""
		from classes.gear.Gear import Gear

		for entry_id in entry_ids :
			Gear.restore(entry_id)

	# ============================================================
	@staticmethod
	async def undo(bot: discord.Client, fight_id: int, interaction: discord.Interaction) -> None :
		async with CombatFlow.lock(fight_id) :
			fight = CombatTransactions().load(fight_id)
			entry = CombatTransactions().last_undoable(fight_id) if fight else None
			if fight is None or entry is None :
				return await reply(interaction, "There is nothing to undo.")
			used_before = CombatFlow.used_items(fight)
			fight.restore(entry.snapshot)
			CombatTransactions().save(fight)
			CombatFlow.save_streaks({combatant.character_id : int(combatant.stats.get("bad_streak") or 0)
			                         for combatant in fight.combatants if combatant.character_id})
			CombatFlow.give_back(used_before - CombatFlow.used_items(fight))
			CombatTransactions().delete_logs_from(fight_id, entry.id)
		first_line = (entry.text or entry.action).splitlines()[0][:200]
		await CombatFlow.post(bot, fight, Outcome(lines=[f"↩️ The GM undid: {first_line}"]))
		await CombatFlow.update_board(bot, fight)
		await reply(interaction, "Undone.")

	# ============================================================
	@staticmethod
	async def tick(bot: discord.Client) -> None :
		"""Gives automatic moves in fights whose timer ran out."""
		now = datetime.now(timezone.utc)
		for fight_id in CombatTransactions().with_deadlines() :
			fight = CombatTransactions().load(fight_id)
			if fight is None or fight.deadline is None or fight.deadline > now :
				continue
			try :
				await CombatFlow.run(bot, fight_id, lambda engine : engine.timeout(), label="timeout", undoable=False)
			except Exception as e :
				logging.error(f"The timer of fight {fight_id} failed: {e}", exc_info=True)

	# == starting fights ==

	# ============================================================
	@staticmethod
	async def open_thread(interaction: discord.Interaction, title: str) -> discord.Thread | None :
		"""The thread a new fight runs in: the current one, or a new thread in the current channel."""
		channel = interaction.channel
		if isinstance(channel, discord.Thread) :
			if CombatTransactions().load_by_thread(channel.id) is not None :
				await reply(interaction, "This thread already has a fight that has not ended.")
				return None
			return channel
		if not isinstance(channel, discord.TextChannel) :
			await reply(interaction, "Start a fight in a text channel or a thread.")
			return None
		try :
			return await channel.create_thread(name=title[:100], type=discord.ChannelType.public_thread,
			                                   auto_archive_duration=THREAD_ARCHIVE_MINUTES,
			                                   reason=f"Fight started by {interaction.user}")
		except discord.HTTPException as e :
			logging.warning(f"Could not create a fight thread in #{channel.name}: {e}")
			await reply(interaction, "I could not create a thread here. I need the Create Public Threads and Send "
			                         "Messages in Threads permissions.")
			return None

	# ============================================================
	@staticmethod
	async def start(interaction: discord.Interaction, title: str, pacing: str | None, lethal: bool) -> None :
		guild_id = interaction.guild_id
		if lethal :
			problem = CombatFlow.lethal_problem(guild_id, interaction.user.guild_permissions.manage_messages)
			if problem :
				return await reply(interaction, problem)
		await interaction.response.defer(ephemeral=True)
		thread = await CombatFlow.open_thread(interaction, title)
		if thread is None :
			return
		parent = thread.parent_id if isinstance(thread, discord.Thread) else interaction.channel_id
		fight = CombatTransactions().create(guild_id, interaction.user.id, DEFAULT_SIDES, title=title[:100],
		                                    channel_id=parent, thread_id=thread.id, kind=PVE, state=SETUP,
		                                    pacing=CombatFlow.pacing(guild_id, pacing), lethal=lethal)
		if fight is None :
			return await reply(interaction, "Something went wrong creating the fight; please try again.")
		logging.info(f"{interaction.user.name} started fight {fight.id} in {interaction.guild.name}")
		await CombatFlow.update_board(interaction.client, fight)
		lethal_note = " It is **lethal**." if lethal else ""
		await reply(interaction, f"The fight is ready in {thread.mention}.{lethal_note} Players press **Join** on "
		                         f"the board; as GM you add NPCs and start it from **GM**.")

	# == joining ==

	# ============================================================
	@staticmethod
	def joinable_characters(fight: Fight, user_id: int) -> list :
		return [character for character in CharacterTransactions().get_all(user_id, fight.guild_id, states=[APPROVED])
		        if CombatTransactions().open_fight_of(character.id) is None]

	# ============================================================
	@staticmethod
	def joinable_sides(fight: Fight, user_id: int) -> list :
		engine = CombatFlow.engine(fight)
		return [side for side in fight.sides if engine.join_problem(side.id, user_id, None) is None]

	# ============================================================
	@staticmethod
	async def join(bot: discord.Client, interaction: discord.Interaction, fight_id: int, character_id: int,
	               side_id: int, lethal_ok: bool = False) -> None :
		async with CombatFlow.lock(fight_id) :
			fight = CombatTransactions().load(fight_id)
			if fight is None :
				return await reply(interaction, "That fight no longer exists.")
			engine = CombatFlow.engine(fight)
			character = CharacterTransactions().get_by_id(character_id)
			if character is None or character.uid != interaction.user.id or character.state != APPROVED :
				return await reply(interaction, "That character can't join.")
			problem = engine.join_problem(side_id, interaction.user.id, character.id)
			if problem is None and CombatTransactions().open_fight_of(character.id) is not None :
				problem = f"{character.name} is already in another fight."
			if problem :
				return await reply(interaction, problem)
			position = max([combatant.position for combatant in fight.combatants] + [0]) + 1
			combatant = Loadout.for_character(character, side_id, position)
			combatant.lethal_ok = lethal_ok
			CombatTransactions().add_combatant(fight.id, combatant)
			fight.combatants.append(combatant)
			engine.joined(combatant)
			CombatTransactions().save(fight)
			CombatTransactions().log(fight.id, fight.round, "join", "\n".join(engine.outcome.lines), combatant.id)
		logging.info(f"{interaction.user.name} joined fight {fight.id} with character {character.id}")
		await CombatFlow.post(bot, fight, engine.outcome)
		await CombatFlow.update_board(bot, fight)
		await reply(interaction, f"{character.name} joined {fight.side(side_id).name}. HP {combatant.hp_max}, "
		                         f"AP {combatant.ap_max}, AC {combatant.ac}, DT {combatant.dt}.")

	# ============================================================
	@staticmethod
	async def add_npcs(bot: discord.Client, fight_id: int, make, count: int, side_id: int, base_name: str,
	                   interaction: discord.Interaction | None = None) -> None :
		"""Adds count NPCs; make(name, side_id, position) builds one. Several get numbers (Bandit 1, Bandit 2)."""
		async with CombatFlow.lock(fight_id) :
			fight = CombatTransactions().load(fight_id)
			if fight is None or fight.state == ENDED :
				if interaction is not None :
					await reply(interaction, "That fight is over.")
				return
			engine = CombatFlow.engine(fight)
			taken = {combatant.name.lower() for combatant in fight.combatants}
			number = 1
			for _ in range(count) :
				name = base_name
				if count > 1 or name.lower() in taken :
					while f"{base_name} {number}".lower() in taken :
						number += 1
					name = f"{base_name} {number}"
				taken.add(name.lower())
				position = max([combatant.position for combatant in fight.combatants] + [0]) + 1
				combatant = make(name, side_id, position)
				CombatTransactions().add_combatant(fight.id, combatant)
				fight.combatants.append(combatant)
				engine.joined(combatant)
			if fight.state == ACTIVE :
				engine.settle()
			CombatTransactions().save(fight)
			CombatTransactions().log(fight.id, fight.round, "add", "\n".join(engine.outcome.lines))
		await CombatFlow.post(bot, fight, engine.outcome)
		await CombatFlow.update_board(bot, fight)
		if interaction is not None :
			await reply(interaction, f"Added {count} × {base_name}.")

	# == PvP ==

	# ============================================================
	@staticmethod
	async def challenge(interaction: discord.Interaction, member: discord.Member, character_name: str,
	                    lethal: bool) -> None :
		guild_id = interaction.guild_id
		if not ConfigData().get_toggle(guild_id, ConfigMapping.COMBAT_PVP, default="ENABLED") :
			return await reply(interaction, "PvP challenges are turned off on this server.")
		if member.bot or member.id == interaction.user.id :
			return await reply(interaction, "Challenge another member.")
		character = CharacterTransactions().get(interaction.user.id, guild_id, character_name)
		if character is None or character.state != APPROVED :
			return await reply(interaction, f"You have no approved character called {character_name}.")
		if CombatTransactions().open_fight_of(character.id) is not None :
			return await reply(interaction, f"{character.name} is already in a fight.")
		theirs = CharacterTransactions().get_all(member.id, guild_id, states=[APPROVED])
		if not theirs :
			return await reply(interaction, f"{member.display_name} has no approved characters.")
		if lethal :
			mode = CombatFlow.lethal_mode(guild_id)
			if mode == LETHAL_OFF :
				return await reply(interaction, "Lethal fights are turned off on this server.")
			if mode == LETHAL_GM and not interaction.user.guild_permissions.manage_messages :
				return await reply(interaction, "Only staff can make a PvP fight lethal on this server.")
		await interaction.response.defer(ephemeral=True)
		title = f"{character.name} vs {member.display_name}"
		thread = await CombatFlow.open_thread(interaction, title)
		if thread is None :
			return
		legendary = character.legendary or any(other.legendary for other in theirs)
		fight = CombatTransactions().create(guild_id, interaction.user.id, [character.name, member.display_name[:50]],
		                                    title=title[:100], channel_id=getattr(thread, "parent_id", None),
		                                    thread_id=thread.id, kind=PVP, state=PENDING,
		                                    pacing=CombatFlow.pacing(guild_id, None), lethal=lethal,
		                                    challenge={"challenger_uid" : interaction.user.id,
		                                               "target_uid" : member.id, "character_id" : character.id,
		                                               "legendary" : legendary})
		await CombatFlow.update_board(interaction.client, fight)
		text = f"⚔️ {member.mention}, {interaction.user.mention} challenges you with **{character.name}**."
		if lethal :
			text += " ☠️ **This fight is lethal: characters can die.**"
		if legendary :
			text += " 🌟 **A legendary character is involved**, with doubled stats."
		text += " Answer with the buttons on the board."
		try :
			await thread.send(text, allowed_mentions=discord.AllowedMentions(users=[member]))
		except discord.HTTPException :
			pass
		await reply(interaction, f"Challenge sent in {thread.mention}.")

	# ============================================================
	@staticmethod
	async def accept(bot: discord.Client, interaction: discord.Interaction, fight_id: int, character_id: int) -> None :
		async with CombatFlow.lock(fight_id) :
			fight = CombatTransactions().load(fight_id)
			challenge = (fight.challenge or {}) if fight else {}
			if fight is None or fight.state != PENDING :
				return await reply(interaction, "This challenge is no longer open.")
			if interaction.user.id != challenge.get("target_uid") :
				return await reply(interaction, "Only the challenged member can answer.")
			challenger = CharacterTransactions().get_by_id(challenge.get("character_id"))
			defender = CharacterTransactions().get_by_id(character_id)
			if challenger is None or challenger.state != APPROVED :
				return await reply(interaction, "The challenger's character can no longer fight.")
			if defender is None or defender.uid != interaction.user.id or defender.state != APPROVED :
				return await reply(interaction, "That character can't fight.")
			for character in (challenger, defender) :
				if CombatTransactions().open_fight_of(character.id) is not None :
					return await reply(interaction, f"{character.name} is already in another fight.")
			fight.sides[1].name = defender.name[:50]
			fight.state = SETUP
			engine = CombatFlow.engine(fight)
			for position, (character, side) in enumerate(((challenger, fight.sides[0]), (defender, fight.sides[1])),
			                                             start=1) :
				combatant = Loadout.for_character(character, side.id, position)
				combatant.lethal_ok = fight.lethal
				CombatTransactions().add_combatant(fight.id, combatant)
				fight.combatants.append(combatant)
				engine.joined(combatant)
			engine.say("Allies can join a side when someone on it invites them with `/combat invite`. The challenger "
			           "starts the fight from **GM**.")
			CombatTransactions().save(fight)
			CombatTransactions().log(fight.id, 0, "accept", "\n".join(engine.outcome.lines))
		await CombatFlow.post(bot, fight, engine.outcome)
		await CombatFlow.update_board(bot, fight)
		await reply(interaction, f"Challenge accepted with {defender.name}.")

	# ============================================================
	@staticmethod
	async def decline(bot: discord.Client, interaction: discord.Interaction, fight_id: int) -> None :
		async with CombatFlow.lock(fight_id) :
			fight = CombatTransactions().load(fight_id)
			challenge = (fight.challenge or {}) if fight else {}
			if fight is None or fight.state != PENDING :
				return await reply(interaction, "This challenge is no longer open.")
			if interaction.user.id not in (challenge.get("target_uid"), challenge.get("challenger_uid")) :
				return await reply(interaction, "Only the two members can answer this challenge.")
			fight.state = ENDED
			CombatTransactions().save(fight)
		who = "withdrawn" if interaction.user.id == challenge.get("challenger_uid") else "declined"
		await CombatFlow.post(bot, fight, Outcome(lines=[f"The challenge was {who}."]))
		await CombatFlow.update_board(bot, fight)
		await reply(interaction, f"Challenge {who}.")

	# == rewards ==

	# ============================================================
	@staticmethod
	def suggested_rewards(fight: Fight) -> tuple[int, int] :
		"""XP and currency per winning character: the defeated NPCs' rewards, shared."""
		winners = [combatant for combatant in fight.combatants
		           if combatant.side_id == fight.winner_side_id and combatant.character_id and combatant.state != "fled"]
		if not winners :
			return 0, 0
		losers = [combatant for combatant in fight.combatants if combatant.side_id != fight.winner_side_id]
		xp = sum(int((combatant.stats.get("rewards") or {}).get("xp") or 0) for combatant in losers)
		currency = sum(int((combatant.stats.get("rewards") or {}).get("currency") or 0) for combatant in losers)
		return xp // len(winners), currency // len(winners)

	# ============================================================
	@staticmethod
	async def give_rewards(bot: discord.Client, interaction: discord.Interaction, fight_id: int, xp: int,
	                       currency: int, gear: str | None = None) -> None :
		"""Gives every winning character (not the ones that fled) the XP, currency and catalog items (names
		separated by commas)."""
		from classes.characters.ForumPost import ForumPost
		from classes.characters.Special import Special
		from classes.gear.Gear import Gear
		from database.transactions.GearItemTransactions import GearItemTransactions

		fight = CombatTransactions().load(fight_id)
		if fight is None or fight.state != ENDED :
			return await reply(interaction, "Rewards are given once the fight is over.")
		items = []
		for name in [part.strip() for part in (gear or "").split(",") if part.strip()] :
			item = GearItemTransactions().find(fight.guild_id, name)
			if item is None :
				return await reply(interaction, f"The catalog has no item called {name}; nothing was given.")
			items.append(item)
		names = []
		for combatant in fight.combatants :
			if combatant.side_id != fight.winner_side_id or not combatant.character_id or combatant.state == "fled" :
				continue
			character = CharacterTransactions().get_by_id(combatant.character_id)
			if character is None :
				continue
			if xp > 0 :
				character, _ = Special.add_xp(character, xp)
			if currency > 0 :
				Gear.give_currency(character, currency, interaction.user.id, note=f"Fight: {fight.title}")
			for item in items :
				Gear.grant(character, item, interaction.user.id)
			names.append(character.name)
			updated = CharacterTransactions().get_by_id(character.id)
			if updated is not None and updated.state == APPROVED :
				await ForumPost.sync(bot, updated)
		if not names :
			return await reply(interaction, "No winning characters to reward.")
		text = f"🎁 The GM rewards {', '.join(names)}: {xp} XP and {currency} " \
		       f"{ConfigData().get_key(fight.guild_id, ConfigMapping.CURRENCY_NAME)} each"
		text += f", plus {', '.join(item.name for item in items)}." if items else "."
		CombatTransactions().log(fight.id, fight.round, "rewards", text,
		                         details={"xp" : xp, "currency" : currency, "gear" : [item.id for item in items]})
		await CombatFlow.post(bot, fight, Outcome(lines=[text]))
		await reply(interaction, "Rewards given.")

	# == after the fight ==

	# ============================================================
	@staticmethod
	async def break_gear(bot: discord.Client, interaction: discord.Interaction, fight_id: int, entry_id: int) -> None :
		"""Marks a fighter's gear broken (the GM's call after the fight)."""
		from classes.gear.Gear import Gear
		from database.transactions.CharacterGearTransactions import BROKEN, CharacterGearTransactions

		fight = CombatTransactions().load(fight_id)
		entry = CharacterGearTransactions().get(entry_id)
		character_ids = {combatant.character_id for combatant in fight.combatants} if fight else set()
		if fight is None or entry is None or entry.character_id not in character_ids :
			return await reply(interaction, "That gear isn't carried by anyone in this fight.")
		updated, problem = Gear.set_status(entry, BROKEN, interaction.user.id)
		if updated is None :
			return await reply(interaction, problem)
		character = CharacterTransactions().get_by_id(entry.character_id)
		text = f"💥 {character.name}'s **{entry.name}** is broken."
		CombatTransactions().log(fight.id, fight.round, "broken", text, details={"entry_id" : entry.id})
		await CombatFlow.post(bot, fight, Outcome(lines=[text]))
		await CombatFlow.refresh_post(bot, character.id)
		await reply(interaction, "Marked broken.")

	# ============================================================
	@staticmethod
	async def refresh_post(bot: discord.Client, character_id: int) -> None :
		"""Updates an approved character's forum post after its sheet or gear changed."""
		from classes.characters.ForumPost import ForumPost

		character = CharacterTransactions().get_by_id(character_id)
		if character is not None and character.state == APPROVED :
			await ForumPost.sync(bot, character)

	# ============================================================
	@staticmethod
	def injury_text(current: str | None, title: str, text: str) -> str :
		"""The character's Injuries field with a new line added."""
		line = f"{text.strip()} ({title})"
		return f"{current.rstrip()}\n{line}" if current and current.strip() else line

	# ============================================================
	@staticmethod
	async def add_injury(bot: discord.Client, interaction: discord.Interaction, fight_id: int, character_id: int,
	                     text: str) -> None :
		"""Adds an injury to a fighter's sheet (the Injuries field), as free text the GM writes."""
		from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions

		fight = CombatTransactions().load(fight_id)
		if fight is None or character_id not in {combatant.character_id for combatant in fight.combatants} :
			return await reply(interaction, "That character isn't in this fight.")
		character = CharacterTransactions().get_by_id(character_id)
		infos = CharacterInfoTransactions()
		current = next((info.value for info in infos.get_all(character_id) if info.key == INJURIES), None)
		value = CombatFlow.injury_text(current, fight.title, text)[:INJURY_LIMIT]
		if current is None :
			infos.add(character_id, INJURIES, value)
		else :
			infos.edit(character_id, INJURIES, value)
		line = f"🩸 {character.name} is injured: {text.strip()}"
		CombatTransactions().log(fight.id, fight.round, "injury", line)
		await CombatFlow.post(bot, fight, Outcome(lines=[line]))
		await CombatFlow.refresh_post(bot, character_id)
		await reply(interaction, f"Added to {character.name}'s sheet under {INJURIES}.")

	# == NPC voices ==

	# ============================================================
	@staticmethod
	async def speak(bot: discord.Client, interaction: discord.Interaction, fight_id: int, combatant_id: int,
	                text: str) -> None :
		"""Posts text in the fight's thread as an NPC, with its name and avatar."""
		from classes.proxy.WebhookManager import WebhookManager

		fight = CombatTransactions().load(fight_id)
		combatant = fight.combatant(combatant_id) if fight else None
		thread = await CombatFlow.thread(bot, fight) if fight else None
		if combatant is None or thread is None :
			return await reply(interaction, "I could not find that NPC or the fight's thread.")
		try :
			webhook = await WebhookManager().get(bot, thread)
			await webhook.send(text[:MESSAGE_LIMIT], username=combatant.name[:80],
			                   avatar_url=combatant.stats.get("avatar_url") or discord.utils.MISSING, thread=thread,
			                   allowed_mentions=discord.AllowedMentions.none())
		except discord.HTTPException as e :
			logging.warning(f"Could not speak as NPC {combatant.id} in fight {fight.id}: {e}")
			return await reply(interaction, "I could not post as the NPC; I need the Manage Webhooks permission.")
		await reply(interaction, "Posted.")

	# ============================================================
	@staticmethod
	def is_gm(fight: Fight, member: discord.Member) -> bool :
		return fight.is_gm(member.id, staff=member.guild_permissions.manage_messages)

	# ============================================================
	@staticmethod
	def paused_or_active(fight: Fight) -> bool :
		return fight.state in (ACTIVE, PAUSED)
