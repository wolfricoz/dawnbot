"""The rumor mill (design/roleplay-tools.md, section 6): anonymous rumors, GM-planted ones (marked true, false or
partly true, and maybe secret), overhearing them, spreading and fading.

In `board` mode (the default) a rumor is posted anonymously to RUMOR_CHANNEL straight away. In `whisper` mode rumors
stay in a pool characters overhear; one heard 3 times spreads and is posted. Secret rumors are never posted. Every
rumor is logged with its author in MODLOG, since anonymous text needs moderation. Listening (once a real day per
character) rolls d20 + the better of the Perception or Charisma modifier against Average (12): success hears one
rumor, a strong success two and a hint about a marked one, a bad failure a false rumor when there is one.
"""
import logging
import random
from datetime import datetime, timedelta, timezone

import discord

from classes.checks import Checks
from classes.characters.Special import Special
from classes.kernel import RoleplaySettings
from classes.kernel.ConfigData import ConfigData
from database.database import Characters, Rumors
from database.transactions.FlavorTransactions import FlavorTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import reply

BOARD = "board"
WHISPER = "whisper"
UNKNOWN = "unknown"
TRUE = "true"
FALSE = "false"
PARTIAL = "partial"
TRUTHS = [UNKNOWN, TRUE, FALSE, PARTIAL]
SPREAD_AT = 3
HINTS = {TRUE : "This one rings true.", PARTIAL : "There is something to this one.",
         FALSE : "Something about this one smells off."}
RUMOR_COLOUR = discord.Colour.dark_purple()


class RumorFlow :

	# ============================================================
	@staticmethod
	def mode(guild_id: int) -> str :
		return RoleplaySettings.text(guild_id, ConfigMapping.RUMOR_MODE)

	# ============================================================
	@staticmethod
	def expiry(guild_id: int) -> datetime :
		return datetime.now(timezone.utc) + timedelta(days=RoleplaySettings.number(guild_id, ConfigMapping.RUMOR_DAYS))

	# ============================================================
	@staticmethod
	def where(rumor: Rumors) -> str :
		from database.transactions.WorldTransactions import WorldTransactions

		location = WorldTransactions().location(rumor.location_id)
		if location is not None :
			return f" in {location.name}"
		region = WorldTransactions().region(rumor.region_id)
		return f" around {region.name}" if region is not None else ""

	# ============================================================
	@staticmethod
	async def publish(bot: discord.Client, rumor: Rumors) -> None :
		"""Posts a rumor anonymously to the rumor channel."""
		guild = bot.get_guild(rumor.guild_id)
		channel = await ConfigData().get_channel(guild, ConfigMapping.RUMOR_CHANNEL, optional=True) if guild else None
		if channel is None :
			return
		embed = discord.Embed(title=f"🗣️ Overheard{RumorFlow.where(rumor)}", description=f"*{rumor.text}*"[:4096],
		                      colour=RUMOR_COLOUR)
		embed.set_footer(text=f"Rumor #{rumor.id}")
		try :
			message = await channel.send(embed=embed)
			FlavorTransactions().update_rumor(rumor.id, spread_message_id=message.id)
		except discord.HTTPException as e :
			logging.warning(f"Could not post rumor {rumor.id}: {e}")

	# ============================================================
	@staticmethod
	async def log(guild: discord.Guild, rumor: Rumors) -> None :
		channel = await ConfigData().get_channel(guild, ConfigMapping.MODLOG, optional=True)
		if channel is None :
			return
		kind = "planted" if rumor.planted else "posted"
		extra = f" · {rumor.truth}{' · secret' if rumor.secret else ''}" if rumor.planted else ""
		try :
			await channel.send(f"🗣️ Rumor #{rumor.id} {kind} by <@{rumor.author_uid}>{extra}: {rumor.text}"[:2000],
			                   allowed_mentions=discord.AllowedMentions.none())
		except discord.HTTPException :
			pass

	# ============================================================
	@staticmethod
	async def post(interaction: discord.Interaction, text: str, location_channel, character_name: str | None,
	               planted: bool = False, truth: str = UNKNOWN, secret: bool = False) -> None :
		from classes.world.WorldFlow import WorldFlow
		from database.transactions.CharacterTransactions import CharacterTransactions

		guild = interaction.guild
		if not planted and FlavorTransactions().blocked(guild.id, interaction.user.id) :
			return await reply(interaction, "You can't post rumors on this server.")
		character = CharacterTransactions().get(interaction.user.id, guild.id, character_name) if character_name \
			else None
		location = WorldFlow.location_here(location_channel) if location_channel else None
		rumor = FlavorTransactions().add_rumor(guild.id, interaction.user.id, text.strip()[:1000],
		                                       character_id=character.id if character else None,
		                                       location_id=location.id if location else None,
		                                       region_id=location.region_id if location else None, truth=truth,
		                                       secret=secret, planted=planted, heard=0,
		                                       expires_at=RumorFlow.expiry(guild.id))
		if rumor is None :
			return await reply(interaction, "Something went wrong; please try again.")
		await RumorFlow.log(guild, rumor)
		posted = RumorFlow.mode(guild.id) == BOARD and not secret
		if posted :
			await RumorFlow.publish(interaction.client, rumor)
		where = "It's on the rumor board." if posted else "It's going round; characters may overhear it."
		await reply(interaction, f"🗣️ Rumor #{rumor.id} is out. {where}")

	# == overhearing ==

	# ============================================================
	@staticmethod
	def candidates(character: Characters, location=None, now: datetime | None = None) -> list[Rumors] :
		"""Rumors the character hasn't heard, secret ones first, then the ones from where it is."""
		heard = FlavorTransactions().heard_by(character.id)
		pool = [rumor for rumor in FlavorTransactions().live(character.guild_id, now or datetime.now(timezone.utc))
		        if rumor.id not in heard and rumor.author_uid != character.uid]

		def rank(rumor: Rumors) :
			near = location is not None and (rumor.location_id == location.id or
			                                 (location.region_id and rumor.region_id == location.region_id))
			return (0 if rumor.secret else 1, 0 if near else 1, random.random())

		return sorted(pool, key=rank)

	# ============================================================
	@staticmethod
	def overhear(character: Characters, bonus: int = 0, location=None, rng: random.Random | None = None) -> tuple[
		str, list[str]] :
		"""Listens for rumors: returns the roll's outcome and what the character hears (with hints)."""
		stat = "perception" if character.perception >= character.charisma else "charisma"
		result = Checks.roll(Checks.stats_of(character), stat, Checks.DCS["average"],
		                     Special.rules(character.guild_id).base, bonus, None, rng)
		pool = RumorFlow.candidates(character, location)
		if result.outcome in (Checks.BAD, Checks.FUMBLE) :
			false = [rumor for rumor in pool if rumor.truth == FALSE]
			chosen = false[:1]
		elif result.outcome == Checks.FAILURE :
			chosen = []
		else :
			chosen = pool[:2 if result.outcome in (Checks.STRONG, Checks.CRIT) else 1]
		heard = []
		hinted = False
		for rumor in chosen :
			updated = FlavorTransactions().hear(rumor.id, character.id)
			line = rumor.text
			if result.outcome in (Checks.STRONG, Checks.CRIT) and not hinted and rumor.truth in HINTS :
				line += f" ({HINTS[rumor.truth]})"
				hinted = True
			heard.append(line)
			if updated is not None :
				RumorFlow._maybe_spread(updated)
		return result.outcome, heard

	# ============================================================
	@staticmethod
	def _maybe_spread(rumor: Rumors) -> None :
		"""Marks a whispered rumor heard often enough to spread; WorldTask posts it."""
		if RumorFlow.mode(rumor.guild_id) == WHISPER and not rumor.secret and not rumor.spread_message_id and \
				rumor.heard >= SPREAD_AT :
			RumorFlow._to_spread.add(rumor.id)

	_to_spread: set[int] = set()

	# ============================================================
	@staticmethod
	async def spread(bot: discord.Client) -> None :
		"""Posts the whispered rumors that spread."""
		while RumorFlow._to_spread :
			rumor = FlavorTransactions().rumor(RumorFlow._to_spread.pop())
			if rumor is not None and not rumor.spread_message_id :
				await RumorFlow.publish(bot, rumor)

	# ============================================================
	@staticmethod
	async def listen(interaction: discord.Interaction, character_name: str) -> None :
		from classes.world.WorldFlow import WorldFlow
		from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions

		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character_name)
		if character is None or character.state != APPROVED :
			return await reply(interaction, f"You have no approved character called {character_name}.")
		day = datetime.now(timezone.utc).date().isoformat()
		if FlavorTransactions().listened(character.id, day) :
			return await reply(interaction, f"{character.name} already listened for rumors today.")
		FlavorTransactions().mark_listen(interaction.guild_id, character.id, day)
		location = WorldFlow.where_is(interaction.guild, character.id)
		from classes.economy import Lifestyle

		outcome, heard = RumorFlow.overhear(character, Lifestyle.rumor_bonus(character), location)
		await RumorFlow.spread(interaction.client)
		lines = [f"👂 {character.name} keeps an ear out ({Checks.OUTCOME_LABELS[outcome]})."]
		lines += [f"• *{text}*" for text in heard] or ["Nothing worth repeating today."]
		await reply(interaction, "\n".join(lines)[:2000])
