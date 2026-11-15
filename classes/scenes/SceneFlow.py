"""The Discord side of scenes (design/roleplay-tools.md, section 2): the pinned card, joining and leaving, counting
proxied posts, nudges and skips, pausing for fights, idle scenes and ending (with the chronicle and timeline)."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord

from classes.kernel import RoleplaySettings
from classes.scenes import Scenes
from classes.scenes.Scenes import ENDED, FREE, OPEN, ORDER, PAUSED
from database.database import Characters, Scenes as SceneRecord
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.SceneTransactions import SceneTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import Option, pick, reply

OPEN_COLOUR = discord.Colour.purple()
PAUSED_COLOUR = discord.Colour.orange()
ENDED_COLOUR = discord.Colour.dark_grey()


class SceneFlow :
	_locks: dict[int, asyncio.Lock] = {}

	# ============================================================
	@staticmethod
	def lock(scene_id: int) -> asyncio.Lock :
		return SceneFlow._locks.setdefault(scene_id, asyncio.Lock())

	# ============================================================
	@staticmethod
	def runs(scene: SceneRecord, member) -> bool :
		"""The host or staff."""
		permissions = getattr(member, "guild_permissions", None)
		return member.id == scene.host_uid or bool(permissions and permissions.manage_messages)

	# ============================================================
	@staticmethod
	def away_uids(participants: list, now: datetime | None = None) -> set[int] :
		now = now or datetime.now(timezone.utc)
		away = set()
		for participant in participants :
			until = Scenes.aware(SceneTransactions().away_until(participant.uid))
			if until is not None and until > now :
				away.add(participant.uid)
		return away

	# ============================================================
	@staticmethod
	def scene_here(channel) -> SceneRecord | None :
		return SceneTransactions().open_in(getattr(channel, "id", None))

	# == the card ==

	# ============================================================
	@staticmethod
	def embed(scene: SceneRecord) -> discord.Embed :
		from classes.world import Weather
		from classes.world.WorldFlow import WorldFlow
		from database.transactions.WorldTransactions import WorldTransactions

		participants = SceneTransactions().participants(scene.id)
		away = SceneFlow.away_uids(participants)
		colour = {OPEN : OPEN_COLOUR, PAUSED : PAUSED_COLOUR}.get(scene.state, ENDED_COLOUR)
		lines = []
		location = WorldTransactions().location(scene.location_id)
		if location is not None :
			climate, key = WorldFlow.weather(scene.guild_id, location)
			lines.append(f"📍 {location.name} · {Weather.text(climate, key)}")
		if scene.world_start :
			end = f" → {scene.world_end.get('text')}" if scene.world_end else ""
			lines.append(f"📅 {scene.world_start.get('text')}{end}")
		lines.append("🔁 Post order" if scene.mode == ORDER else "🕊️ Free order")
		if scene.state == PAUSED :
			lines.append(f"⏸️ Paused{' for a fight' if scene.paused_by_fight else ''}: no nudges or skips.")
		elif scene.state == ENDED :
			lines.append("🏁 This scene has ended.")
		turn = Scenes.current(participants, scene.turn_index) if scene.mode == ORDER and scene.state != ENDED else None
		rows = []
		for participant in participants :
			character = CharacterTransactions().get_by_id(participant.character_id)
			name = character.name if character else "?"
			mark = "▶️ " if turn is not None and participant.id == turn.id else ""
			sleeping = " 💤" if participant.uid in away else ""
			last = f" · last post <t:{int(Scenes.aware(participant.last_post_at).timestamp())}:R>" \
				if participant.last_post_at else ""
			rows.append(f"{mark}**{name}** (<@{participant.uid}>){sleeping} · {participant.posts} posts{last}")
		card = discord.Embed(title=f"🎭 {scene.title}"[:256], description="\n".join(lines)[:4096], colour=colour)
		card.add_field(name="Participants", value="\n".join(rows)[:1024] or "Nobody yet: press **Join**.",
		               inline=False)
		if turn is not None and scene.state == OPEN and scene.turn_started_at :
			card.add_field(name="Turn", value=f"<@{turn.uid}>'s turn since "
			                                  f"<t:{int(Scenes.aware(scene.turn_started_at).timestamp())}:R>",
			               inline=False)
		card.set_footer(text="Host and staff run the scene with /scene. Out-of-turn posts move their poster up.")
		card.add_field(name="Host", value=f"<@{scene.host_uid}>", inline=True)
		return card

	# ============================================================
	@staticmethod
	async def refresh(bot: discord.Client, scene_id: int) -> None :
		from views.scenes.SceneButtons import scene_view

		scene = SceneTransactions().get(scene_id)
		if scene is None or scene.card_message_id is None :
			return
		try :
			channel = bot.get_channel(scene.channel_id) or await bot.fetch_channel(scene.channel_id)
			await channel.get_partial_message(scene.card_message_id).edit(embed=SceneFlow.embed(scene),
			                                                              view=scene_view(scene))
		except discord.HTTPException as e :
			logging.warning(f"Could not update the card of scene {scene_id}: {e}")

	# == starting and joining ==

	# ============================================================
	@staticmethod
	async def start(interaction: discord.Interaction, title: str | None, mode: str) -> None :
		from classes.world.WorldFlow import WorldFlow
		from views.scenes.SceneButtons import scene_view

		channel = interaction.channel
		if SceneFlow.scene_here(channel) is not None :
			return await reply(interaction, "There already is an open scene here; end it with /scene end first.")
		location = WorldFlow.location_here(channel)
		title = (title or getattr(channel, "name", "A scene")).strip()[:200]
		scene = SceneTransactions().create(interaction.guild_id, channel.id, title, interaction.user.id, mode=mode,
		                                   state=OPEN, location_id=location.id if location else None,
		                                   world_start=WorldFlow.world_date(interaction.guild_id))
		if scene is None :
			return await reply(interaction, "Something went wrong saving the scene; please try again.")
		await interaction.response.send_message(embed=SceneFlow.embed(scene), view=scene_view(scene))
		message = await interaction.original_response()
		SceneTransactions().update(scene.id, card_message_id=message.id)
		try :
			await message.pin(reason=f"Scene card: {title}")
		except discord.HTTPException :
			pass
		logging.info(f"{interaction.user.name} started scene {scene.id} in {interaction.guild.name}")

	# ============================================================
	@staticmethod
	async def start_join(interaction: discord.Interaction, scene_id: int) -> None :
		scene = SceneTransactions().get(scene_id)
		if scene is None or scene.state == ENDED :
			return await reply(interaction, "This scene has ended.")
		participants = SceneTransactions().participants(scene.id)
		if any(participant.uid == interaction.user.id for participant in participants) :
			return await reply(interaction, "You already take part in this scene; each player joins with one "
			                                "character.")
		characters = CharacterTransactions().get_all(interaction.user.id, interaction.guild_id, states=[APPROVED])
		if not characters :
			return await reply(interaction, "You have no approved character to join with.")
		if len(characters) == 1 :
			return await SceneFlow.join(interaction, scene.id, characters[0])
		await pick(interaction, "Join with which character?",
		           [Option(character.name, character.id) for character in characters], "Pick a character",
		           lambda next_interaction, values : SceneFlow.join(
			           next_interaction, scene.id, CharacterTransactions().get_by_id(int(values[0]))))

	# ============================================================
	@staticmethod
	async def join(interaction: discord.Interaction, scene_id: int, character: Characters | None,
	               added_by_host: bool = False) -> None :
		async with SceneFlow.lock(scene_id) :
			scene = SceneTransactions().get(scene_id)
			if scene is None or scene.state == ENDED or character is None or character.state != APPROVED :
				return await reply(interaction, "That character can't join this scene.")
			participants = SceneTransactions().participants(scene.id)
			if any(participant.uid == character.uid for participant in participants) :
				return await reply(interaction, "That player already takes part in this scene.")
			position = max([participant.position for participant in participants] + [0]) + 1
			SceneTransactions().add_participant(scene.id, character.id, character.uid, position)
			if not participants :
				SceneTransactions().update(scene.id, turn_index=0, turn_started_at=datetime.now(timezone.utc))
		await SceneFlow.refresh(interaction.client, scene_id)
		await reply(interaction, f"{character.name} {'was added to' if added_by_host else 'joins'} **{scene.title}**.")

	# ============================================================
	@staticmethod
	async def leave(interaction: discord.Interaction, scene_id: int, uid: int, removed: bool = False) -> None :
		async with SceneFlow.lock(scene_id) :
			scene = SceneTransactions().get(scene_id)
			if scene is None or scene.state == ENDED :
				return await reply(interaction, "This scene has ended.")
			participants = SceneTransactions().participants(scene.id)
			leaving = next((participant for participant in participants if participant.uid == uid), None)
			if leaving is None :
				return await reply(interaction, "That member doesn't take part in this scene.")
			index = participants.index(leaving)
			was_turn = scene.mode == ORDER and Scenes.current(participants, scene.turn_index).id == leaving.id
			SceneTransactions().update_participant(leaving.id, state="removed" if removed else "left")
			remaining = [participant for participant in participants if participant.id != leaving.id]
			turn_index = scene.turn_index % len(participants)
			if index < turn_index :
				turn_index -= 1
			changes = {"turn_index" : (turn_index % len(remaining)) if remaining else 0}
			if was_turn :
				changes["turn_started_at"] = datetime.now(timezone.utc)
			SceneTransactions().update(scene.id, **changes)
		await SceneFlow.refresh(interaction.client, scene_id)
		await reply(interaction, "Removed from the scene." if removed else "You left the scene.")

	# ============================================================
	@staticmethod
	async def pass_turn(interaction: discord.Interaction, scene_id: int) -> None :
		async with SceneFlow.lock(scene_id) :
			scene = SceneTransactions().get(scene_id)
			if scene is None or scene.state == ENDED :
				return await reply(interaction, "This scene has ended.")
			if scene.mode != ORDER :
				return await reply(interaction, "This scene has no post order to pass in.")
			participants = SceneTransactions().participants(scene.id)
			turn = Scenes.current(participants, scene.turn_index)
			if turn is None or (turn.uid != interaction.user.id and not SceneFlow.runs(scene, interaction.user)) :
				return await reply(interaction, "It isn't your turn.")
			SceneTransactions().update(scene.id, turn_index=Scenes.next_index(participants, scene.turn_index,
			                                                                  SceneFlow.away_uids(participants)),
			                           turn_started_at=datetime.now(timezone.utc))
		await SceneFlow.refresh(interaction.client, scene_id)
		await reply(interaction, "Turn passed.")

	# == posts ==

	# ============================================================
	@staticmethod
	async def on_post(bot: discord.Client, channel, character: Characters, text: str) -> None :
		"""Counts a proxied post in a scene: the poster's numbers, the turn, and the card."""
		scene = SceneFlow.scene_here(channel)
		if scene is None :
			return
		async with SceneFlow.lock(scene.id) :
			scene = SceneTransactions().get(scene.id)
			participant = SceneTransactions().participant(scene.id, character.id)
			if participant is None or participant.state != "active" :
				return
			now = datetime.now(timezone.utc)
			SceneTransactions().update_participant(participant.id, posts=participant.posts + 1,
			                                       words=participant.words + Scenes.words(text), last_post_at=now)
			changes = {"last_post_at" : now}
			if scene.mode == ORDER :
				participants = SceneTransactions().participants(scene.id)
				order, turn_index, passed = Scenes.after_post(participants, scene.turn_index, participant.id,
				                                              SceneFlow.away_uids(participants, now))
				if [entry.id for entry in order] != [entry.id for entry in participants] :
					SceneTransactions().reorder([entry.id for entry in order])
				changes["turn_index"] = turn_index
				if passed :
					changes["turn_started_at"] = now
			SceneTransactions().update(scene.id, **changes)
		await SceneFlow.refresh(bot, scene.id)

	# == running ==

	# ============================================================
	@staticmethod
	async def move(interaction: discord.Interaction, scene: SceneRecord, uid: int, position: int) -> None :
		participants = SceneTransactions().participants(scene.id)
		mover = next((participant for participant in participants if participant.uid == uid), None)
		if mover is None :
			return await reply(interaction, "That member doesn't take part in this scene.")
		turn = Scenes.current(participants, scene.turn_index)
		order = [participant for participant in participants if participant.id != mover.id]
		order.insert(max(0, min(len(order), position - 1)), mover)
		SceneTransactions().reorder([participant.id for participant in order])
		if turn is not None :
			SceneTransactions().update(scene.id, turn_index=[entry.id for entry in order].index(turn.id))
		await SceneFlow.refresh(interaction.client, scene.id)
		await reply(interaction, "Order changed.")

	# ============================================================
	@staticmethod
	def pause_for_fight(channel_ids: list[int | None], fight_id: int) -> SceneRecord | None :
		"""Pauses the open scene in one of these channels when a fight starts from it."""
		for channel_id in channel_ids :
			scene = SceneTransactions().open_in(channel_id)
			if scene is not None and scene.state == OPEN :
				return SceneTransactions().update(scene.id, state=PAUSED, paused_by_fight=fight_id)
		return None

	# ============================================================
	@staticmethod
	async def tick(bot: discord.Client, now: datetime | None = None) -> None :
		"""Resumes scenes whose fight ended, nudges and skips, and handles idle scenes."""
		from database.transactions.CombatTransactions import CombatTransactions

		now = now or datetime.now(timezone.utc)
		for scene in SceneTransactions().open_scenes() :
			try :
				if scene.state == PAUSED :
					if scene.paused_by_fight :
						fight = CombatTransactions().load(scene.paused_by_fight)
						if fight is None or fight.state == "ended" :
							SceneTransactions().update(scene.id, state=OPEN, paused_by_fight=None,
							                           turn_started_at=now)
							await SceneFlow.refresh(bot, scene.id)
					continue
				await SceneFlow._idle(bot, scene, now)
				if SceneTransactions().get(scene.id).state != OPEN :
					continue
				if scene.mode == ORDER :
					await SceneFlow._turn_timers(bot, scene, now)
				else :
					await SceneFlow._free_nudges(bot, scene, now)
			except Exception as e :
				logging.error(f"Scene {scene.id} timers failed: {e}", exc_info=True)

	# ============================================================
	@staticmethod
	async def _turn_timers(bot: discord.Client, scene: SceneRecord, now: datetime) -> None :
		participants = SceneTransactions().participants(scene.id)
		if not participants :
			return
		away = SceneFlow.away_uids(participants, now)
		turn = Scenes.current(participants, scene.turn_index)
		if turn.uid in away :
			SceneTransactions().update(scene.id, turn_index=Scenes.first_present(participants, scene.turn_index, away),
			                           turn_started_at=now)
			return await SceneFlow.refresh(bot, scene.id)
		skip_hours = RoleplaySettings.number(scene.guild_id, ConfigMapping.SCENE_SKIP_HOURS)
		if Scenes.skip_due(scene.turn_started_at, skip_hours, now) and len(participants) > 1 :
			SceneTransactions().update_participant(turn.id, skips=turn.skips + 1)
			SceneTransactions().update(scene.id, turn_index=Scenes.next_index(participants, scene.turn_index, away),
			                           turn_started_at=now)
			await SceneFlow._say(bot, scene, f"⏭️ <@{turn.uid}>'s turn was skipped after {skip_hours} hours.")
			return await SceneFlow.refresh(bot, scene.id)
		nudge_hours = RoleplaySettings.number(scene.guild_id, ConfigMapping.SCENE_NUDGE_HOURS)
		if Scenes.nudge_due(scene.turn_started_at, turn.last_nudged_at, nudge_hours, now) :
			SceneTransactions().update_participant(turn.id, last_nudged_at=now)
			await SceneFlow._nudge(bot, scene, turn.uid, "It's your turn")

	# ============================================================
	@staticmethod
	async def _free_nudges(bot: discord.Client, scene: SceneRecord, now: datetime) -> None :
		participants = SceneTransactions().participants(scene.id)
		hours = RoleplaySettings.number(scene.guild_id, ConfigMapping.SCENE_NUDGE_HOURS)
		for participant in Scenes.free_nudges(participants, hours, now, SceneFlow.away_uids(participants, now)) :
			SceneTransactions().update_participant(participant.id, last_nudged_at=now)
			await SceneFlow._nudge(bot, scene, participant.uid, "Everyone else has posted since you")

	# ============================================================
	@staticmethod
	async def _idle(bot: discord.Client, scene: SceneRecord, now: datetime) -> None :
		days = RoleplaySettings.number(scene.guild_id, ConfigMapping.SCENE_IDLE_DAYS)
		state = Scenes.idle_state(scene.last_post_at or scene.started_at, scene.idle_warned_at, days, now)
		if state == "warn" :
			SceneTransactions().update(scene.id, idle_warned_at=now)
			await SceneFlow._say(bot, scene, f"💤 <@{scene.host_uid}>, **{scene.title}** has had no posts for {days} "
			                                 f"days. Post to keep it going, or end it with /scene end; it ends by "
			                                 f"itself in {Scenes.IDLE_GRACE_DAYS} days.", ping=True)
		elif state == "end" :
			await SceneFlow.finish(bot, scene.id, None, "Ended after going quiet.")

	# ============================================================
	@staticmethod
	async def _nudge(bot: discord.Client, scene: SceneRecord, uid: int, why: str) -> None :
		link = f"https://discord.com/channels/{scene.guild_id}/{scene.channel_id}"
		user = bot.get_user(uid)
		try :
			if user is None :
				user = await bot.fetch_user(uid)
			await user.send(f"🎭 {why} in **{scene.title}**: {link}")
		except discord.HTTPException :
			await SceneFlow._say(bot, scene, f"🎭 <@{uid}>, {why.lower()} in this scene.", ping=True)

	# ============================================================
	@staticmethod
	async def _say(bot: discord.Client, scene: SceneRecord, text: str, ping: bool = False) -> None :
		try :
			channel = bot.get_channel(scene.channel_id) or await bot.fetch_channel(scene.channel_id)
			await channel.send(text, allowed_mentions=discord.AllowedMentions(users=ping))
		except discord.HTTPException as e :
			logging.warning(f"Could not post in scene {scene.id}: {e}")

	# == ending ==

	# ============================================================
	@staticmethod
	async def finish(bot: discord.Client, scene_id: int, ender_uid: int | None, summary: str | None = None,
	                 world_date: str | None = None) -> tuple[SceneRecord | None, object | None] :
		"""Ends a scene: freezes the card, writes the chronicle (when CHRONICLE is set) and the timeline entry (when
		TIMELINE is set). Returns the scene and the chronicle (or None)."""
		from classes.scenes.ChronicleFlow import ChronicleFlow
		from classes.world.WorldFlow import WorldFlow

		async with SceneFlow.lock(scene_id) :
			scene = SceneTransactions().get(scene_id)
			if scene is None or scene.state == ENDED :
				return scene, None
			end = WorldFlow.world_date(scene.guild_id)
			if world_date :
				end = dict(end or {}, text=world_date)
			scene = SceneTransactions().update(scene_id, state=ENDED, ended_at=datetime.now(timezone.utc),
			                                   world_end=end, summary=summary)
		await SceneFlow.refresh(bot, scene_id)
		guild = bot.get_guild(scene.guild_id)
		chronicle = None
		if guild is not None :
			try :
				chronicle = await ChronicleFlow.for_scene(bot, guild, scene, ender_uid)
			except Exception as e :
				logging.error(f"Writing the chronicle of scene {scene_id} failed: {e}", exc_info=True)
			await SceneFlow._timeline(bot, guild, scene, ender_uid, chronicle)
		SceneFlow._locks.pop(scene_id, None)
		return scene, chronicle

	# ============================================================
	@staticmethod
	async def _timeline(bot: discord.Client, guild: discord.Guild, scene: SceneRecord, ender_uid: int | None,
	                    chronicle) -> None :
		from classes.kernel.ConfigData import ConfigData

		channel = await ConfigData().get_channel(guild, ConfigMapping.TIMELINE, optional=True)
		if channel is None :
			return
		link = f"https://discord.com/channels/{scene.guild_id}/{scene.channel_id}"
		lines = [f"# {scene.title}", f"Author: <@{ender_uid or scene.host_uid}>", f"Scene: {link}"]
		if scene.world_end :
			lines.append(f"In roleplay date: {scene.world_end.get('text')}")
		if chronicle is not None and chronicle.thread_id :
			lines.append(f"Chronicle: <#{chronicle.thread_id}>")
		lines.append(f"Brief summary of what happened: {scene.summary or '(Post below!)'}")
		try :
			await channel.send("\n".join(lines)[:2000], allowed_mentions=discord.AllowedMentions.none())
		except discord.HTTPException as e :
			logging.warning(f"Could not post the timeline entry of scene {scene.id}: {e}")
