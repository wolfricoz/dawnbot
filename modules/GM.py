"""Game master tools: giving and taking characters' gear, currency, abilities and legendary status. GMs are staff
(Manage Messages)."""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Death import Death
from classes.combat.Legendary import Legendary
from classes.kernel.ConfigData import ConfigData
from classes.combat.Proficiency import Proficiency
from classes.gear import Condition, Magic
from classes.gear.Gear import Gear
from database.database import CharacterGear, Characters, GearItems
from database.transactions.CharacterGearTransactions import BROKEN, CharacterGearTransactions, LOST
from database.transactions.AbilityTransactions import AbilityTransactions
from database.transactions.CharacterTransactions import CharacterTransactions, DEAD
from database.transactions.GearItemTransactions import GearItemTransactions
from modules.Currency import balance_text
from resources.configs.ConfigMapping import ConfigMapping
from modules.Gear import PROFICIENCY_CHOICES, entry_choices, find_entry, refresh_post, unmet_warning
from views.buttons.Confirm import ask


@app_commands.guild_only()
@app_commands.default_permissions(manage_messages=True)
class GM(commands.GroupCog, name="GM", group_name="gm") :

	gear = app_commands.Group(name="gear", description="Give or take characters' gear")
	currency = app_commands.Group(name="currency", description="Give or take characters' currency")
	ability = app_commands.Group(name="ability", description="Grant or take characters' abilities")
	legendary = app_commands.Group(name="legendary", description="Grant or take characters' legendary status")

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# == autocomplete ==

	# ============================================================
	async def _characters(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		member = interaction.namespace.member
		if member is None :
			return []
		return [Choice(name=character.name, value=character.name)
		        for character in CharacterTransactions().get_all(member.id, interaction.guild_id)
		        if current.lower() in character.name.lower()][:25]

	# ============================================================
	async def _catalog(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=item.name[:100], value=item.name[:100])
		        for item in GearItemTransactions().get_all(interaction.guild_id)
		        if current.lower() in item.name.lower()][:25]

	# ============================================================
	async def _owned(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		member, name = interaction.namespace.member, interaction.namespace.character
		if member is None or not name :
			return []
		character = CharacterTransactions().get(member.id, interaction.guild_id, name)
		if character is None :
			return []
		return entry_choices(CharacterGearTransactions().get_all(character.id), current)

	# == helpers ==

	# ============================================================
	async def _character(self, interaction: discord.Interaction, member: discord.Member,
	                     character: str) -> Characters | None :
		record = CharacterTransactions().get(member.id, interaction.guild_id, character)
		if record is None :
			await interaction.followup.send(f"{member.display_name} has no character called {character}.",
			                                ephemeral=True)
		return record

	# ============================================================
	async def _entry(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                 item: str) -> tuple[Characters | None, CharacterGear | None] :
		record = await self._character(interaction, member, character)
		if record is None :
			return None, None
		entry = find_entry(CharacterGearTransactions().get_all(record.id), item)
		if entry is None :
			await interaction.followup.send(f"{record.name} doesn't own {item}.", ephemeral=True)
		return record, entry

	# ============================================================
	async def _mark(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str,
	                status: str) -> None :
		await interaction.response.defer(ephemeral=True)
		record, entry = await self._entry(interaction, member, character, item)
		if entry is None :
			return
		_, problem = Gear.set_status(entry, status, interaction.user.id)
		if problem :
			return await interaction.followup.send(problem, ephemeral=True)
		logging.info(f"GM {interaction.user.name} marked gear {entry.id} ({entry.name}) of character {record.id} "
		             f"{status} in {interaction.guild.name}")
		await interaction.followup.send(f"{record.name}'s **{entry.name}** is now {status}.", ephemeral=True)
		await refresh_post(self.bot, record.id)

	# == gear ==

	# ============================================================
	@gear.command(name="grant")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_catalog)
	async def gear_grant(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Gives a member's character an item from the catalog for free, including event and staff-only items that
		aren't sold in the shop. Requirements like server level or roles don't apply.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		catalog_item: GearItems | None = GearItemTransactions().find(interaction.guild_id, item)
		if catalog_item is None :
			return await interaction.followup.send(f"The catalog has no item called {item}.", ephemeral=True)
		entry = Gear.grant(record, catalog_item, interaction.user.id)
		if entry is None :
			return await interaction.followup.send("Something went wrong, please try again.", ephemeral=True)
		logging.info(f"GM {interaction.user.name} granted {catalog_item.name} to character {record.id} "
		             f"in {interaction.guild.name}")
		await interaction.followup.send(f"Gave {record.name} **{catalog_item.name}**."
		                                + unmet_warning(record, catalog_item), ephemeral=True)
		await refresh_post(self.bot, record.id)

	# ============================================================
	@gear.command(name="take")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_owned)
	async def gear_take(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Removes an item from a member's character entirely, as if it never had it, for fixing mistakes. Nothing is
		refunded. To take gear away in the story, use /gm gear lose or /gm gear break instead.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record, entry = await self._entry(interaction, member, character, item)
		if entry is None :
			return
		Gear.take(entry)
		logging.info(f"GM {interaction.user.name} took gear {entry.id} ({entry.name}) from character {record.id} "
		             f"in {interaction.guild.name}")
		await interaction.followup.send(f"Removed **{entry.name}** from {record.name}.", ephemeral=True)
		await refresh_post(self.bot, record.id)

	# ============================================================
	@gear.command(name="lose")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_owned)
	async def gear_lose(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Marks an item of a member's character as lost. It leaves the inventory but stays in its history.

		**Permissions:**
		- `Manage Messages`
		"""
		await self._mark(interaction, member, character, item, LOST)

	# ============================================================
	@gear.command(name="break")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_owned)
	async def gear_break(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Marks an item of a member's character as broken. It stays in the inventory but does nothing in a fight until
		it is repaired.

		**Permissions:**
		- `Manage Messages`
		"""
		await self._mark(interaction, member, character, item, BROKEN)

	# ============================================================
	@gear.command(name="attune")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_owned)
	async def gear_attune(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Attunes a member's character to a magic item on the spot, without a day of downtime (a short pause in a
		scene). The attunement limit still applies.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record, entry = await self._entry(interaction, member, character, item)
		if entry is None :
			return
		problem = Magic.attune_problem(record, entry, GearItemTransactions().get(entry.gear_item_id))
		if problem :
			return await interaction.followup.send(problem, ephemeral=True)
		Magic.attune(entry)
		logging.info(f"GM {interaction.user.name} attuned gear {entry.id} of character {record.id}")
		await interaction.followup.send(f"{record.name} is attuned to **{entry.name}**.", ephemeral=True)

	# ============================================================
	@gear.command(name="repair")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_owned)
	async def gear_repair(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Repairs an item of a member's character back to good condition, for free. Cursed items keep their curse; lift
		it with /craft uncurse.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record, entry = await self._entry(interaction, member, character, item)
		if entry is None :
			return
		if Condition.of(entry) == Condition.GOOD :
			return await interaction.followup.send(f"{entry.name} is in good condition already.", ephemeral=True)
		Condition.restore(entry, interaction.user.id)
		logging.info(f"GM {interaction.user.name} repaired gear {entry.id} of character {record.id}")
		await interaction.followup.send(f"{record.name}'s **{entry.name}** is repaired.", ephemeral=True)
		await refresh_post(self.bot, record.id)

	# ============================================================
	@gear.command(name="proficiency")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, item=_owned)
	@app_commands.choices(tier=PROFICIENCY_CHOICES)
	async def gear_proficiency(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                           item: str, tier: Choice[str]) :
		"""
		Sets or changes how well a member's character handles one of its weapons. The limit of two Good or Excellent
		weapons still applies.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record, entry = await self._entry(interaction, member, character, item)
		if entry is None :
			return
		updated, text = Proficiency.set_weapon(entry, tier.value, staff=True)
		if updated is not None :
			logging.info(f"GM {interaction.user.name} set proficiency {tier.value} on gear {entry.id} of character "
			             f"{record.id} in {interaction.guild.name}")
		await interaction.followup.send(text, ephemeral=True)

	# == currency ==

	# ============================================================
	@currency.command(name="give")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters)
	async def currency_give(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                        amount: app_commands.Range[int, 1, 1000000000],
	                        note: app_commands.Range[str, 1, 200] = None) :
		"""
		Gives a member's character currency, for example as an event reward. The optional `note` shows in the
		character's /currency history.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		updated, problem = Gear.give_currency(record, amount, interaction.user.id, note)
		if problem :
			return await interaction.followup.send(problem, ephemeral=True)
		guild_id = interaction.guild_id
		logging.info(f"GM {interaction.user.name} gave {amount} currency to character {record.id} "
		             f"in {interaction.guild.name}: {note or ''}")
		await interaction.followup.send(f"Gave {record.name} {balance_text(guild_id, amount)}; it now has "
		                                f"{balance_text(guild_id, updated.currency)}.", ephemeral=True)
		await refresh_post(self.bot, record.id)

	# ============================================================
	@currency.command(name="take")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters)
	async def currency_take(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                        amount: app_commands.Range[int, 1, 1000000000],
	                        note: app_commands.Range[str, 1, 200] = None) :
		"""
		Takes currency from a member's character, for example as a fine. A character can't go below 0. The optional
		`note` shows in the character's /currency history.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		updated, problem = Gear.take_currency(record, amount, interaction.user.id, note)
		if problem :
			return await interaction.followup.send(problem, ephemeral=True)
		guild_id = interaction.guild_id
		logging.info(f"GM {interaction.user.name} took {amount} currency from character {record.id} "
		             f"in {interaction.guild.name}: {note or ''}")
		await interaction.followup.send(f"Took {balance_text(guild_id, amount)} from {record.name}; it now has "
		                                f"{balance_text(guild_id, updated.currency)}.", ephemeral=True)
		await refresh_post(self.bot, record.id)


	# == deaths ==

	# ============================================================
	@app_commands.command(name="resurrect")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters)
	async def resurrect(self, interaction: discord.Interaction, member: discord.Member, character: str) :
		"""
		Brings back a character that died in a lethal fight. It is approved again straight away, can post again, and
		its forum post is reopened. It needs a free place under the character cap.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		cap = ConfigData().get_int(interaction.guild_id, ConfigMapping.CHARACTER_CAP)
		if record.state == DEAD and CharacterTransactions().count_active(record.uid, record.guild_id) >= cap :
			return await interaction.followup.send(f"{member.display_name} already has {cap} characters here, which "
			                                       f"is this server's limit.", ephemeral=True)
		updated, problem = Death.resurrect(record)
		if updated is None :
			return await interaction.followup.send(problem, ephemeral=True)
		logging.info(f"GM {interaction.user.name} resurrected character {record.id} in {interaction.guild.name}")
		await interaction.followup.send(f"{updated.name} is back.", ephemeral=True)
		await refresh_post(self.bot, updated.id)

	# == abilities ==

	# ============================================================
	async def _all_abilities(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=ability.name[:100], value=ability.name[:100])
		        for ability in AbilityTransactions().get_all(interaction.guild_id)
		        if current.lower() in ability.name.lower()][:25]

	# ============================================================
	@ability.command(name="grant")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, ability=_all_abilities)
	async def ability_grant(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                        ability: str) :
		"""
		Grants a member's character an ability as an event reward. Event abilities skip the slot limits and the rule
		against mixing spells and abilities, and work even if the ability hasn't been approved.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		found = AbilityTransactions().find(interaction.guild_id, ability)
		if found is None :
			return await interaction.followup.send(f"There is no ability called {ability}.", ephemeral=True)
		if AbilityTransactions().learn(record.id, found.id, event=True, granted_by=interaction.user.id) is None :
			return await interaction.followup.send(f"{record.name} already knows {found.name}.", ephemeral=True)
		logging.info(f"GM {interaction.user.name} granted ability {found.id} to character {record.id} in "
		             f"{interaction.guild.name}")
		await interaction.followup.send(f"{record.name} now knows **{found.name}** (event).", ephemeral=True)
		await refresh_post(self.bot, record.id)

	# ============================================================
	@ability.command(name="take")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, ability=_all_abilities)
	async def ability_take(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                       ability: str) :
		"""
		Takes an ability away from a member's character, event or not.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		found = AbilityTransactions().find(interaction.guild_id, ability)
		if found is None or not AbilityTransactions().forget(record.id, found.id) :
			return await interaction.followup.send(f"{record.name} doesn't know {ability}.", ephemeral=True)
		await interaction.followup.send(f"{record.name} no longer knows **{found.name}**.", ephemeral=True)
		await refresh_post(self.bot, record.id)

	# == legendary ==

	# ============================================================
	@legendary.command(name="grant")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters)
	async def legendary_grant(self, interaction: discord.Interaction, member: discord.Member, character: str) :
		"""
		Makes a member's character legendary. Legendary characters have doubled stat limits (20, or 26 with a species
		that allows 13), get extra points to spend (`LEGENDARY_POINTS`, 5 by default) and one extra ability slot.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		updated, text = Legendary.grant(record, interaction.user.id)
		if updated is not None :
			logging.info(f"GM {interaction.user.name} made character {record.id} legendary in {interaction.guild.name}")
			await refresh_post(self.bot, record.id)
		await interaction.followup.send(text, ephemeral=True)

	# ============================================================
	@legendary.command(name="take")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters)
	async def legendary_take(self, interaction: discord.Interaction, member: discord.Member, character: str) :
		"""
		Takes legendary status away from a member's character. Stats above the normal limits are lowered and those
		points returned, then the extra legendary points are taken back: from unspent points first, then from the
		highest stats. You'll see exactly what changes before you confirm.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = await self._character(interaction, member, character)
		if record is None :
			return
		if not record.legendary :
			return await interaction.followup.send(f"{record.name} is not legendary.", ephemeral=True)
		question = f"Take legendary status from **{record.name}**? {Legendary.preview(record)}"
		if not await ask(interaction, question, "Take legendary status") :
			return
		# Read it again: the character may have changed while the question was open.
		updated, text = Legendary.remove(CharacterTransactions().get_by_id(record.id))
		if updated is not None :
			logging.info(f"GM {interaction.user.name} took legendary status from character {record.id} in "
			             f"{interaction.guild.name}")
			await refresh_post(self.bot, record.id)
		await interaction.followup.send(text, ephemeral=True)

async def setup(bot) :
	await bot.add_cog(GM(bot))
