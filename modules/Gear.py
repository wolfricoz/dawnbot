"""Player commands for the gear their characters own: the inventory, equipping, selling, and marking gear lost or
broken. The rules live in classes/gear/Gear.py."""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.CharacterFlow import CharacterFlow
from classes.characters.ForumPost import ForumPost
from classes.combat import Rules
from classes.combat.AutoComplete import AutoComplete
from classes.combat.Proficiency import Proficiency
from classes.gear import Carry, Condition, Pricing, Slots
from classes.gear.Gear import ARMOR, Gear as GearRules
from database.database import CharacterGear, Characters, GearItems
from database.transactions.CharacterGearTransactions import BROKEN, CharacterGearTransactions, LOST, OWNED
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from modules.Currency import balance_text, find_own_character
from views.buttons.Confirm import ask

SLOT_CHOICES = [Choice(name="Main hand", value=Slots.MAIN_HAND), Choice(name="Off hand", value=Slots.OFF_HAND),
                Choice(name="Readied", value=Slots.READIED), Choice(name="First ring", value=Slots.RING_1),
                Choice(name="Second ring", value=Slots.RING_2)]
PROFICIENCY_CHOICES = [Choice(name=f"{tier.capitalize()} ({Rules.proficiency_bonus(tier):+d})", value=tier)
                       for tier in Rules.PROFICIENCY_ORDER]


# ============================================================
def find_entry(entries: list[CharacterGear], text: str) -> CharacterGear | None :
	"""The entry an item option points at: autocomplete sends the entry id, a typed name matches by name."""
	text = (text or "").strip()
	if text.isdigit() :
		for entry in entries :
			if entry.id == int(text) :
				return entry
	for entry in entries :
		if entry.name.lower() == text.lower() :
			return entry
	return None


# ============================================================
def entry_label(entry: CharacterGear, entries: list[CharacterGear]) -> str :
	"""`Sword`, `Sword #2` when the character has more than one, and `(equipped)` when it is."""
	same = [other.id for other in entries if other.name.lower() == entry.name.lower()]
	label = entry.name if len(same) < 2 else f"{entry.name} #{same.index(entry.id) + 1}"
	return f"{label} (equipped)" if entry.equipped else label


# ============================================================
def entry_choices(entries: list[CharacterGear], current: str) -> list[Choice[str]] :
	"""Autocomplete choices for owned gear; the value is the entry id, so duplicates stay apart."""
	choices = []
	for entry in entries :
		label = entry_label(entry, entries)
		if current.lower() in label.lower() :
			choices.append(Choice(name=label[:100], value=str(entry.id)))
	return choices[:25]


# ============================================================
def unmet_warning(character: Characters, item: GearItems | None) -> str :
	"""A warning when the character misses the item's SPECIAL requirements, or an empty string."""
	if item is None :
		return ""
	unmet = GearRules.unmet_requirements(GearRules.stats_of(character), item)
	if not unmet :
		return ""
	return (f"\n-# {character.name} doesn't meet {', '.join(unmet)} yet. The item still works, but with the penalty "
	        f"for unmet requirements.")


# ============================================================
def equipped_text(entry: CharacterGear) -> str :
	"""How an equipped item is carried: `worn`, `main hand`, `readied`, `worn (neck)`."""
	if entry.kind == ARMOR :
		return "worn"
	if entry.kind == "accessory" :
		return f"worn ({Slots.label(entry.slot)})" if entry.slot else "worn"
	return Slots.label(entry.slot) if entry.slot else "equipped"


# ============================================================
def inventory_lines(character: Characters, inventory: list[tuple[CharacterGear, GearItems | None]]) -> list[str] :
	"""One line per item: equipped items first, then the rest, then lost, sold and used items."""
	stats = GearRules.stats_of(character)
	owned = [pair for pair in inventory if pair[0].status == OWNED]
	gone = [pair for pair in inventory if pair[0].status != OWNED]
	owned.sort(key=lambda pair : (not pair[0].equipped, Slots.SLOTS.index(pair[0].slot)
	                              if pair[0].slot in Slots.SLOTS else len(Slots.SLOTS)))
	lines = []
	for entry, item in owned :
		parts = [f"**{entry.name}** ({entry.kind})"]
		if entry.kind == "weapon" :
			parts.append(Proficiency.label(entry))
		if entry.equipped :
			parts.append(equipped_text(entry))
		if Condition.of(entry) != Condition.GOOD :
			parts.append(Condition.label(Condition.of(entry)).lower())
		if item is not None and Carry.ammo_on(character.guild_id) and Carry.uses_ammo(item.combat) :
			die = Carry.die_of(entry)
			parts.append("out of ammunition" if die == Carry.EMPTY else f"ammunition {die}")
		unmet = GearRules.unmet_requirements(stats, item) if item is not None else []
		if unmet :
			parts.append(f"misses {', '.join(unmet)}")
		lines.append(" · ".join(parts))
	for entry, item in gone :
		lines.append(f"~~{entry.name}~~ ({entry.kind}) · {entry.status}")
	return lines


# ============================================================
async def refresh_post(bot: commands.Bot, character_id: int) -> None :
	"""Updates the character's forum post after its gear or currency changed (approved characters only)."""
	character = CharacterTransactions().get_by_id(character_id)
	if character is not None and character.state == APPROVED :
		await ForumPost.sync(bot, character)


@app_commands.guild_only()
class Gear(commands.GroupCog, name="Gear", group_name="gear") :


	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# == helpers ==

	# ============================================================
	async def _owned_items(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		name = interaction.namespace.character
		if not name :
			return []
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name)
		if character is None :
			return []
		return entry_choices(CharacterGearTransactions().get_all(character.id), current)

	# ============================================================
	async def _inventory_characters(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		member = interaction.namespace.member
		user_id = member.id if member is not None else interaction.user.id
		return [Choice(name=character.name, value=character.name)
		        for character in CharacterTransactions().get_all(user_id, interaction.guild_id)
		        if current.lower() in character.name.lower()][:25]

	# ============================================================
	async def _own_entry(self, interaction: discord.Interaction, character: str,
	                     item: str) -> tuple[Characters | None, CharacterGear | None, GearItems | None] :
		"""The member's approved character and the owned item; tells them when either is missing."""
		record = await find_own_character(interaction, character, approved=True)
		if record is None :
			return None, None, None
		entry = find_entry(CharacterGearTransactions().get_all(record.id), item)
		if entry is None :
			await CharacterFlow.respond(interaction, f"{record.name} doesn't own {item}.")
			return None, None, None
		return record, entry, GearItemTransactions().get(entry.gear_item_id)

	# == commands ==

	# ============================================================
	@app_commands.command(name="inventory")
	@app_commands.autocomplete(character=_inventory_characters)
	async def inventory(self, interaction: discord.Interaction, character: str, history: bool = False,
	                    member: discord.Member = None) :
		"""
		Shows what one of your characters owns: what it wears and holds in which slot, each item's condition when it
		isn't good, ammunition and carried weight when the server uses them, and any SPECIAL requirements it doesn't
		meet. Turn on `history` to include gear that was lost, sold or used up.

		Staff can look at another member's character with `member`.
		"""
		if member is not None and member.id != interaction.user.id :
			if not interaction.user.guild_permissions.manage_messages :
				return await CharacterFlow.respond(interaction, "Only staff can look at another member's gear.")
			record = CharacterTransactions().get(member.id, interaction.guild_id, character)
			if record is None :
				return await CharacterFlow.respond(interaction,
				                                   f"{member.display_name} has no character called {character}.")
		elif (record := await find_own_character(interaction, character)) is None :
			return
		lines = inventory_lines(record, GearRules.inventory(record.id, include_gone=history))
		embed = discord.Embed(title=f"{record.name}'s gear", description="\n".join(lines)[:4000] or "No gear yet.",
		                      color=discord.Color.dark_gold())
		footer = [Carry.load_text(record)]
		if GearRules.economy(interaction.guild_id) :
			footer.append(balance_text(interaction.guild_id, record.currency))
		if any(footer) :
			embed.set_footer(text=" · ".join(part for part in footer if part))
		await interaction.response.send_message(embed=embed, ephemeral=True)

	# ============================================================
	@app_commands.command(name="equip")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_owned_items)
	@app_commands.choices(slot=SLOT_CHOICES)
	@app_commands.describe(slot="Weapons and rings: where it goes (leave out for the usual place)")
	async def equip(self, interaction: discord.Interaction, character: str, item: str, slot: Choice[str] = None) :
		"""
		Equips an item in a slot: armor on the body, an accessory where it is worn (head, neck, back, hands, feet or
		one of two rings), a weapon in the main hand, the off hand or the readied slot. A two-handed weapon takes both
		hands and a shield goes in the off hand. Whatever was in the slot is put away. Every weapon your character
		owns can still be used in a fight; the one in the main hand is the one it starts holding. Gear works even when
		the character misses its SPECIAL requirements, but with a penalty.
		"""
		record, entry, catalog_item = await self._own_entry(interaction, character, item)
		if entry is None :
			return
		before = {other.id for other in CharacterGearTransactions().get_all(record.id)
		          if other.equipped and other.id != entry.id}
		updated, problem = GearRules.equip(entry, slot.value if slot else None)
		if problem or updated is None :
			return await CharacterFlow.respond(interaction, problem or "That item no longer exists.")
		put_away = [other.name for other in CharacterGearTransactions().get_all(record.id)
		            if other.id in before and not other.equipped]
		text = f"{record.name} now has **{entry.name}** ({equipped_text(updated)})."
		if put_away :
			text += f" Put away: {', '.join(put_away)}."
		await CharacterFlow.respond(interaction, text + unmet_warning(record, catalog_item))
		await refresh_post(self.bot, record.id)

	# ============================================================
	@app_commands.command(name="unequip")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_owned_items)
	async def unequip(self, interaction: discord.Interaction, character: str, item: str) :
		"""
		Takes off or puts away an equipped item. It stays in the character's inventory.
		"""
		record, entry, _ = await self._own_entry(interaction, character, item)
		if entry is None :
			return
		if not entry.equipped :
			return await CharacterFlow.respond(interaction, f"{entry.name} isn't equipped.")
		if GearRules.unequip(entry) is None :
			return await CharacterFlow.respond(interaction, f"The cursed {entry.name} won't come off; a GM has to "
			                                                f"lift the curse first (/craft uncurse).")
		await CharacterFlow.respond(interaction, f"{record.name} put away **{entry.name}**.")
		await refresh_post(self.bot, record.id)

	# ============================================================
	@app_commands.command(name="sell")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_owned_items)
	async def sell(self, interaction: discord.Interaction, character: str, item: str) :
		"""
		Sells an item for a share of its catalog price: 30% at average Charisma, from 20% to 40% depending on your
		character's Charisma. Masterwork sells for half as much again and cursed gear for nothing. Nothing is paid in
		free mode. You are asked to confirm first.
		"""
		record, entry, _ = await self._own_entry(interaction, character, item)
		if entry is None :
			return
		guild_id = interaction.guild_id
		value = GearRules.sell_value(entry)
		if value :
			rate = round(Pricing.sell_rate(record) * 100)
			worth = f"{record.name} gets {balance_text(guild_id, value)} ({rate}% of the catalog price)."
		else :
			worth = f"{record.name} gets nothing back for it."
		if not await ask(interaction, f"Sell **{entry.name}**? {worth}", "Sell") :
			return
		received, problem = GearRules.sell(entry, interaction.user.id)
		if problem :
			return await interaction.followup.send(problem, ephemeral=True)
		text = f"Sold **{entry.name}**."
		if received :
			balance = CharacterTransactions().get_by_id(record.id).currency
			text = (f"Sold **{entry.name}** for {balance_text(guild_id, received)}. "
			        f"{record.name} now has {balance_text(guild_id, balance)}.")
		logging.info(f"{interaction.user.name} sold gear {entry.id} ({entry.name}) of character {record.id} "
		             f"for {received}")
		await interaction.followup.send(text, ephemeral=True)
		await refresh_post(self.bot, record.id)

	# ============================================================
	async def _mark(self, interaction: discord.Interaction, character: str, item: str, status: str) -> None :
		record, entry, _ = await self._own_entry(interaction, character, item)
		if entry is None :
			return
		warning = "It stays with your character until it is repaired." if status == BROKEN else \
			"Only staff can give it back."
		if not await ask(interaction, f"Mark **{entry.name}** as {status}? {warning}", f"Mark {status}") :
			return
		_, problem = GearRules.set_status(entry, status, interaction.user.id)
		if problem :
			return await interaction.followup.send(problem, ephemeral=True)
		logging.info(f"{interaction.user.name} marked gear {entry.id} ({entry.name}) of character {record.id} {status}")
		where = "It does nothing until repaired (/shop repair)." if status == BROKEN else \
			f"It stays in {record.name}'s history."
		await interaction.followup.send(f"**{entry.name}** is now {status}. {where}",
		                                ephemeral=True)
		await refresh_post(self.bot, record.id)

	# ============================================================
	@app_commands.command(name="lose")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_owned_items)
	async def lose(self, interaction: discord.Interaction, character: str, item: str) :
		"""
		Marks an item as lost, for when your character loses it in the story. It leaves the inventory but stays in
		its history (/gear inventory with `history`). You are asked to confirm first.
		"""
		await self._mark(interaction, character, item, LOST)

	# ============================================================
	@app_commands.command(name="break")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_owned_items)
	async def break_gear(self, interaction: discord.Interaction, character: str, item: str) :
		"""
		Marks an item as broken, for when it breaks in the story. It stays in the inventory but does nothing in a fight
		until it is repaired at the shop (/shop repair) or by a character whose occupation repairs it (/downtime
		repair). You are asked to confirm first.
		"""
		await self._mark(interaction, character, item, BROKEN)


	# ============================================================
	@app_commands.command(name="proficiency")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_owned_items)
	@app_commands.choices(tier=PROFICIENCY_CHOICES)
	async def proficiency(self, interaction: discord.Interaction, character: str, item: str, tier: Choice[str]) :
		"""
		Sets how well your character handles one of its weapons: Excellent (+1 to hit and a crit range one wider),
		Good (+1), Average (0), Poor (-1) or Awful (-2). A weapon without a tier counts as Awful. At most two weapons
		can be Good or Excellent. You set a weapon's tier once; after that a GM can change it.
		"""
		record, entry, _ = await self._own_entry(interaction, character, item)
		if entry is None :
			return
		updated, text = Proficiency.set_weapon(entry, tier.value)
		if updated is not None :
			logging.info(f"{interaction.user.name} set proficiency {tier.value} on gear {entry.id} of character "
			             f"{record.id}")
		await CharacterFlow.respond(interaction, text)

async def setup(bot) :
	await bot.add_cog(Gear(bot))
