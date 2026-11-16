"""Factions: characters gain and lose standing (-100 to 100) through jobs, GMs and their deeds.

Tiers: Vilified, Disliked, Neutral, Liked, Idolized. Gains grow with Charisma, and gaining standing with a faction costs
half as much with its rivals. A catalog item can belong to a faction: standing changes its price, a tier can be
needed to buy it, and Vilified characters can't buy it at all. Hidden factions only show once a character's standing
with them isn't 0. See design/roleplay-tools.md, section 11.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.kernel.GMRole import gm_only, is_gm
from classes.combat.AutoComplete import AutoComplete
from classes.economy import FactionFlow as Rules
from classes.economy.FactionFlow import FactionFlow
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from views.combat.Pickers import reply

TIER_CHOICES = [Choice(name=tier.capitalize(), value=tier) for tier in Rules.TIERS]


# ============================================================
async def faction_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	staff = is_gm(interaction.user)
	return [Choice(name=faction.name[:100], value=faction.name[:100])
	        for faction in EconomyTransactions().factions(interaction.guild_id)
	        if (staff or not faction.hidden) and current.lower() in faction.name.lower()][:25]


# ============================================================
async def member_characters(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	member = interaction.namespace.member
	if member is None :
		return []
	return [Choice(name=character.name[:100], value=character.name[:100])
	        for character in CharacterTransactions().get_in_guild(interaction.guild_id, member.id)
	        if current.lower() in character.name.lower()][:25]


# ============================================================
async def item_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=item.name[:100], value=item.name[:100])
	        for item in GearItemTransactions().get_all(interaction.guild_id) if current.lower() in item.name.lower()][:25]


# ============================================================
async def occupation_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	from database.transactions.OccupationTransactions import OccupationTransactions

	return [Choice(name=occupation.name[:100], value=occupation.name[:100])
	        for occupation in OccupationTransactions().get_all(interaction.guild_id)
	        if current.lower() in occupation.name.lower()][:25]


# ============================================================
def parse_colour(text: str | None) -> int | None :
	try :
		return int((text or "").strip().lstrip("#"), 16) if text else None
	except ValueError :
		return None


@app_commands.guild_only()
class Faction(commands.GroupCog, name="Faction", group_name="faction") :
	"""Factions and the standing characters have with them."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	def _rivals(self, guild_id: int, text: str | None, own_id: int | None = None) -> tuple[list[int] | None, str | None] :
		ids = []
		for name in [part.strip() for part in (text or "").split(",") if part.strip()] :
			rival = EconomyTransactions().find_faction(guild_id, name)
			if rival is None :
				return None, f"There is no faction called {name}."
			if rival.id != own_id :
				ids.append(rival.id)
		return ids, None

	# ============================================================
	@app_commands.command(name="add", description="Adds a faction")
	@gm_only()
	@app_commands.describe(name="Its name", description="What it is", emoji="An emoji for it",
	                       colour="A colour, like #aa3322", hidden="Only shown to characters with standing",
	                       rivals="Rival factions, separated by commas")
	async def add(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100],
	              description: app_commands.Range[str, 1, 1000] = None, emoji: app_commands.Range[str, 1, 64] = None,
	              colour: str = None, hidden: bool = False, rivals: str = None) :
		"""
		Adds a faction. Rivals lose half of what a character gains with this one.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		rival_ids, problem = self._rivals(interaction.guild_id, rivals)
		if problem :
			return await reply(interaction, problem)
		faction = EconomyTransactions().add_faction(interaction.guild_id, name.strip(), description=description,
		                                            emoji=emoji, colour=parse_colour(colour), hidden=hidden,
		                                            rivals=rival_ids)
		if faction is None :
			return await reply(interaction, f"There already is a faction called {name}.")
		await reply(interaction, f"Added **{faction.name}**.")

	# ============================================================
	@app_commands.command(name="edit", description="Changes a faction")
	@gm_only()
	@app_commands.autocomplete(faction=faction_autocomplete)
	async def edit(self, interaction: discord.Interaction, faction: str, name: app_commands.Range[str, 1, 100] = None,
	               description: app_commands.Range[str, 1, 1000] = None, emoji: app_commands.Range[str, 1, 64] = None,
	               colour: str = None, hidden: bool = None, rivals: str = None) :
		"""
		Changes a faction. `rivals` replaces its rival list.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = EconomyTransactions().find_faction(interaction.guild_id, faction)
		if record is None :
			return await reply(interaction, f"There is no faction called {faction}.")
		changes = {key : value for key, value in (("name", name), ("description", description), ("emoji", emoji),
		                                          ("colour", parse_colour(colour)), ("hidden", hidden))
		           if value is not None}
		if rivals is not None :
			rival_ids, problem = self._rivals(interaction.guild_id, rivals, record.id)
			if problem :
				return await reply(interaction, problem)
			changes["rivals"] = rival_ids
		EconomyTransactions().update_faction(record.id, **changes)
		await reply(interaction, f"Saved **{name or record.name}**.")

	# ============================================================
	@app_commands.command(name="remove", description="Removes a faction")
	@gm_only()
	@app_commands.autocomplete(faction=faction_autocomplete)
	async def remove(self, interaction: discord.Interaction, faction: str) :
		"""
		Removes a faction and everyone's standing with it.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = EconomyTransactions().find_faction(interaction.guild_id, faction)
		if record is None :
			return await reply(interaction, f"There is no faction called {faction}.")
		EconomyTransactions().delete_faction(record.id)
		await reply(interaction, f"Removed **{record.name}**.")

	# ============================================================
	@app_commands.command(name="list", description="Lists the factions")
	async def list_factions(self, interaction: discord.Interaction) :
		"""
		Lists the factions (staff also see hidden ones).
		"""
		staff = is_gm(interaction.user)
		factions = [faction for faction in EconomyTransactions().factions(interaction.guild_id)
		            if staff or not faction.hidden]
		if not factions :
			return await reply(interaction, "There are no factions yet.")
		lines = [f"{faction.emoji or '⚑'} **{faction.name}**{' (hidden)' if faction.hidden else ''}"
		         f"{f' · {faction.description[:80]}' if faction.description else ''}" for faction in factions]
		await reply(interaction, "\n".join(lines)[:2000])

	# ============================================================
	@app_commands.command(name="standing", description="Shows a character's standing with the factions")
	@app_commands.autocomplete(character=AutoComplete().character)
	async def standing(self, interaction: discord.Interaction, character: str) :
		"""
		Shows your character's standing with every faction it knows.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None :
			return await reply(interaction, f"You have no character called {character}.")
		entries = FactionFlow.visible(record)
		if not entries :
			return await reply(interaction, "There are no factions yet.")
		lines = [f"{faction.emoji or '⚑'} **{faction.name}**: {Rules.tier_text(value)}" for faction, value in entries]
		await reply(interaction, f"**{record.name}'s standing**\n" + "\n".join(lines))

	# ============================================================
	@app_commands.command(name="give", description="Raises or lowers a character's standing (staff)")
	@gm_only()
	@app_commands.autocomplete(character=member_characters, faction=faction_autocomplete)
	@app_commands.describe(amount="How much; negative lowers it", reason="Why, for the log")
	async def give(self, interaction: discord.Interaction, member: discord.Member, character: str, faction: str,
	               amount: app_commands.Range[int, -200, 200], reason: app_commands.Range[str, 1, 32] = None) :
		"""
		Changes a character's standing. Gains grow with Charisma and cost the faction's rivals half; losses are taken
		as they are.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = CharacterTransactions().get(member.id, interaction.guild_id, character)
		target = EconomyTransactions().find_faction(interaction.guild_id, faction)
		if record is None or target is None :
			return await reply(interaction, "Pick one of the member's characters and a faction.")
		lines = FactionFlow.change(record, target, amount, reason or "gm", interaction.user.id)
		await reply(interaction, f"**{record.name}**\n" + "\n".join(lines))

	# ============================================================
	@app_commands.command(name="item", description="Makes a catalog item a faction's (staff)")
	@gm_only()
	@app_commands.autocomplete(item=item_autocomplete, faction=faction_autocomplete)
	@app_commands.choices(tier=TIER_CHOICES)
	@app_commands.describe(faction="The faction (leave empty to make it no faction's)",
	                       tier="The standing needed to buy it")
	async def item(self, interaction: discord.Interaction, item: str, faction: str = None,
	               tier: Choice[str] = None) :
		"""
		Ties a catalog item to a faction: characters pay 20% less at Idolized, 10% less at Liked and 25% more at
		Disliked; Vilified characters can't buy it, and a tier can be required.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = GearItemTransactions().find(interaction.guild_id, item)
		if record is None :
			return await reply(interaction, f"The catalog has no item called {item}.")
		target = EconomyTransactions().find_faction(interaction.guild_id, faction) if faction else None
		if faction and target is None :
			return await reply(interaction, f"There is no faction called {faction}.")
		GearItemTransactions().update(record.id, faction_id=target.id if target else None,
		                              faction_tier=tier.value if tier and target else None)
		await reply(interaction, f"{record.name} now belongs to {target.name}" + (f" (needs {tier.value})" if tier else "")
		                         + "." if target else f"{record.name} belongs to no faction now.")


	# ============================================================
	@app_commands.command(name="occupation", description="Makes an occupation need standing with a faction (staff)")
	@gm_only()
	@app_commands.autocomplete(occupation=occupation_autocomplete, faction=faction_autocomplete)
	@app_commands.choices(tier=TIER_CHOICES)
	@app_commands.describe(faction="The faction (leave empty to remove the requirement)",
	                       tier="The standing needed at least")
	async def occupation(self, interaction: discord.Interaction, occupation: str, faction: str = None,
	                     tier: Choice[str] = None) :
		"""
		A character needs at least this standing with the faction to take the occupation. New characters are Neutral
		everywhere, so a higher tier can only be reached by changing occupation later.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		from database.transactions.OccupationTransactions import OccupationTransactions

		record = OccupationTransactions().find(interaction.guild_id, occupation)
		if record is None :
			return await reply(interaction, f"There is no occupation called {occupation}.")
		if not faction :
			OccupationTransactions().update(record.id, faction_id=None, faction_tier=None)
			return await reply(interaction, f"{record.name} needs no faction standing now.")
		target = EconomyTransactions().find_faction(interaction.guild_id, faction)
		if target is None or tier is None :
			return await reply(interaction, "Pick a faction and a tier.")
		OccupationTransactions().update(record.id, faction_id=target.id, faction_tier=tier.value)
		await reply(interaction, f"{record.name} needs {tier.name} standing with {target.name}.")


async def setup(bot) :
	await bot.add_cog(Faction(bot))
