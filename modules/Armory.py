import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Access import Access
from classes.characters.CharacterFlow import CharacterFlow
from classes.characters.Special import STATS
from classes.combat import Conditions, Items, Rules
from classes.combat.DamageTypes import DamageTypes
from classes.gear import Magic, Pricing, Rarity, Slots
from classes.gear.Gear import ACCESSORY, ARMOR, CONSUMABLE, Gear, WEAPON
from classes.gear.GearCard import GearCard
from classes.gear.GearPost import GearPost
from classes.gear.Legacy import Legacy
from classes.gear.Packs import LEGACY_PACK, Packs
from database.database import GearItems
from database.transactions.GearItemTransactions import GearItemTransactions
from views.buttons.Confirm import ask

DESCRIPTION_LIMIT = 4000
EMBEDS_PER_MESSAGE = 10
# Discord refuses a message whose embeds hold more than 6000 characters together.
MESSAGE_EMBED_LIMIT = 6000
# Typed into a text option of /armory edit, this clears the text.
CLEAR = "-"
TEXT_LIMIT = 1000

KIND_CHOICES = [Choice(name="Weapon", value=WEAPON), Choice(name="Armor", value=ARMOR),
                Choice(name="Consumable", value=CONSUMABLE), Choice(name="Accessory", value=ACCESSORY)]
WORN_SLOT_CHOICES = [Choice(name=Slots.label(slot).capitalize(), value=slot) for slot in Slots.ACCESSORY_SLOTS]
USE_CHOICES = [Choice(name="Heal (revives a downed ally)", value=Items.HEAL),
               Choice(name="Cure a condition", value=Items.CURE), Choice(name="Boost an ally", value=Items.BOOST),
               Choice(name="Nothing automatic (the GM settles it)", value=Items.NONE)]
ITEM_CONDITION_CHOICES = [Choice(name="None", value="none")] + [Choice(name=Conditions.label(name), value=name)
                                                                for name in Items.BOOST_CHOICES + Items.CURE_CHOICES]
STAT_CHOICES = [Choice(name=stat.capitalize(), value=stat) for stat in STATS]
DAMAGE_STAT_CHOICES = [Choice(name="None", value="none")] + STAT_CHOICES
RANGE_CHOICES = [Choice(name=value.capitalize(), value=value) for value in Rules.RANGES]
ARMOR_CLASS_CHOICES = [Choice(name=value.capitalize(), value=value) for value in Rules.ARMOR_CLASSES]
RARITY_CHOICES = [Choice(name="From the price", value="auto")] + [Choice(name=Rarity.label(value), value=value)
                                                                  for value in Rarity.RARITIES]
OPTION_HELP = {
	"rarity"          : "Leave out (or From the price) to take it from the price; Legendary items are never sold",
	"weight"          : "In kilograms, for servers with a carry limit (CARRY_WEIGHT)",
	"worn_slot"       : "Accessory: where it is worn (head, neck, back, hands, feet or ring)",
	"requirements"    : "SPECIAL minimums, like: strength 8, agility 4",
	"dice"            : "Weapon damage dice, like 1d8 or 2d6",
	"damage_type"     : "Weapon: its damage type (see /damagetype list), or none",
	"attack_stat"     : "Weapon: the stat added to attack rolls",
	"damage_stat"     : "Weapon: the stat added to damage, or none",
	"hit_mod"         : "Weapon or armor: added to attack rolls",
	"range"           : "Weapon: melee or ranged",
	"properties"      : "Weapon: like light, thrown (light, heavy, two_handed, reach, loading, keen, focus, shield)",
	"ap_cost"         : "Weapon: AP per attack, if not the usual (light 2, normal 3, heavy 4, loading 5)",
	"weapon_kind"     : "Weapon: sword, spear, bow, claw... (which weapon techniques it allows), or none",
	"armor_class"     : "Armor: clothing, light, medium or heavy",
	"ac"              : "Armor: added to the wearer's AC (0 to 10)",
	"dt"              : "Armor: damage threshold, taken off every hit (0 to 10)",
	"ability_hit_mod" : "Armor: added to attack rolls with abilities",
	"use"             : "Consumable: what using it does in a fight (uses dice for healing and shields)",
	"condition"       : "Consumable: the condition a cure removes or a boost gives",
}


@app_commands.guild_only()
class Armory(commands.GroupCog, name="Armory", group_name="armory") :

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@staticmethod
	def hidden(item: GearItems) -> bool :
		"""True for event items, which only staff see."""
		return Access.hidden(Access.for_gear(item))

	# ============================================================
	async def _names(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""Catalog items; event items only for staff."""
		staff = interaction.user.guild_permissions.manage_messages
		return [Choice(name=item.name, value=item.name)
		        for item in GearItemTransactions().get_all(interaction.guild_id)
		        if current.lower() in item.name.lower() and (staff or not self.hidden(item))][:25]

	# ============================================================
	async def _packs(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		choices = [Choice(name=title, value=name) for name, title in Packs.available()]
		if Legacy.exists("armors") or Legacy.exists("weapons") :
			choices.append(Choice(name="The old armors and weapons tables", value=LEGACY_PACK))
		return [choice for choice in choices
		        if current.lower() in choice.name.lower() or current.lower() in choice.value][:25]

	# ============================================================
	@staticmethod
	def text_update(value: str | None) -> tuple[bool, str | None] :
		"""What a text option of /armory edit asks for: (False, None) to leave it, (True, None) to clear it with `-`,
		(True, text) to set it."""
		if value is None :
			return False, None
		value = value.strip()
		return True, None if value in ("", CLEAR) else value

	# ============================================================
	@staticmethod
	def combat_changes(dice=None, damage_type=None, attack_stat=None, damage_stat=None, hit_mod=None, range=None,
	                   properties=None, ap_cost=None, armor_class=None, ac=None, dt=None, ability_hit_mod=None,
	                   use=None, condition=None, weapon_kind=None) -> dict :
		"""The combat options that were filled in, as combat values."""
		values = {"dice" : dice, "type" : damage_type, "attack_stat" : attack_stat, "damage_stat" : damage_stat,
		          "hit_mod" : hit_mod, "range" : range, "properties" : properties, "ap" : ap_cost, "kind" : weapon_kind,
		          "armor_class" : armor_class, "ac" : ac, "dt" : dt, "ability_hit_mod" : ability_hit_mod,
		          "use" : use, "condition" : condition}
		values = {key : value.value if isinstance(value, Choice) else value for key, value in values.items()}
		return {key : value for key, value in values.items() if value is not None}

	# ============================================================
	@staticmethod
	def check_type(guild_id: int, changes: dict) -> None :
		"""Raises ValueError when a weapon names a damage type the server doesn't have."""
		name = changes.get("type")
		if name is None or str(name).strip().lower() in ("", "none", "-") :
			return
		names = DamageTypes.names(guild_id)
		match = next((known for known in names if known.lower() == str(name).strip().lower()), None)
		if match is None :
			raise ValueError(f"The server has no damage type called {name}; see /damagetype list.")
		changes["type"] = match

	# ============================================================
	async def _weapon_kinds(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=kind, value=kind) for kind in ["none"] + Rules.WEAPON_KINDS
		        if current.lower() in kind][:25]

	# ============================================================
	async def _types(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=name, value=name) for name in DamageTypes.names(interaction.guild_id)
		        if current.lower() in name.lower()][:25]

	# ============================================================
	@staticmethod
	def pages(title: str, lines: list[str], limit: int = DESCRIPTION_LIMIT) -> list[discord.Embed] :
		"""The lines as embeds, as many as it takes to keep each description under the limit."""
		embeds, current = [], ""
		for line in lines :
			line = line[:limit]
			if current and len(current) + 1 + len(line) > limit :
				embeds.append(current)
				current = line
			else :
				current = f"{current}\n{line}" if current else line
		if current :
			embeds.append(current)
		return [discord.Embed(title=title if number == 0 else f"{title} (continued)", description=text,
		                      color=discord.Color.dark_gold()) for number, text in enumerate(embeds)]

	# ============================================================
	@staticmethod
	def batches(embeds: list[discord.Embed]) -> list[list[discord.Embed]] :
		"""The embeds grouped into messages Discord accepts: at most 10 per message and 6000 characters together."""
		batches, current, size = [], [], 0
		for embed in embeds :
			if current and (len(current) >= EMBEDS_PER_MESSAGE or size + len(embed) > MESSAGE_EMBED_LIMIT) :
				batches.append(current)
				current, size = [], 0
			current.append(embed)
			size += len(embed)
		if current :
			batches.append(current)
		return batches

	# ============================================================
	async def _post(self, item: GearItems) -> str :
		"""Posts or updates the item in the gear forum when there is one; returns a note for staff when it failed."""
		if not GearPost.configured(item.guild_id) :
			return ""
		if await GearPost.sync(self.bot, GearItemTransactions().get(item.id)) :
			return ""
		return " I could not post it in the gear forum; check that I can create posts there, and that posts there " \
		       "do not need a tag."

	# ============================================================
	@app_commands.command(name="add")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(use=USE_CHOICES, condition=ITEM_CONDITION_CHOICES)
	@app_commands.choices(kind=KIND_CHOICES, attack_stat=STAT_CHOICES, damage_stat=DAMAGE_STAT_CHOICES,
	                      range=RANGE_CHOICES, armor_class=ARMOR_CLASS_CHOICES, rarity=RARITY_CHOICES,
	                      worn_slot=WORN_SLOT_CHOICES)
	@app_commands.autocomplete(damage_type=_types, weapon_kind=_weapon_kinds)
	@app_commands.describe(**OPTION_HELP)
	async def add(self, interaction: discord.Interaction, kind: Choice[str], name: app_commands.Range[str, 1, 100],
	              price: app_commands.Range[int, 0, 10000000], description: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	              requirements: app_commands.Range[str, 1, 200] = None,
	              effect: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	              effect_met: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	              effect_unmet: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	              dice: app_commands.Range[str, 3, 7] = None, damage_type: app_commands.Range[str, 1, 50] = None,
	              attack_stat: Choice[str] = None, damage_stat: Choice[str] = None,
	              hit_mod: app_commands.Range[int, -10, 10] = None, range: Choice[str] = None,
	              properties: app_commands.Range[str, 1, 200] = None, ap_cost: app_commands.Range[int, 1, 10] = None,
	              armor_class: Choice[str] = None, ac: app_commands.Range[int, 0, 10] = None,
	              dt: app_commands.Range[int, 0, 10] = None, ability_hit_mod: app_commands.Range[int, -10, 10] = None,
	              use: Choice[str] = None, condition: Choice[str] = None, weapon_kind: str = None,
	              rarity: Choice[str] = None, weight: app_commands.Range[float, 0, 1000] = None,
	              worn_slot: Choice[str] = None) :
		"""
		Adds a weapon, armor set, consumable or accessory to the catalog. `requirements` are SPECIAL minimums written like
		`strength 8, agility 4` (short names like `str 8` work too); they never stop a character from owning or using
		the item, but each missing point is -1 to hit, and they decide whether `effect_met` (a bonus) or `effect_unmet`
		(a penalty) applies. `effect` is something the item always does.

		Combat values are optional. Weapons use `dice` (like 2d6), `damage_type`, `attack_stat` and `damage_stat`
		(the stats added to attack and damage rolls), `hit_mod`, `range`, `properties` (like `light, thrown`; a
		`shield` gives +2 AC while equipped), `ap_cost` and `weapon_kind` (sword, spear, bow, claw...: which weapon
		techniques it allows; without it the kind is read from the name). Armor uses `armor_class`, `ac` (added to
		AC), `dt` (taken
		off every hit), `hit_mod` and `ability_hit_mod`. Consumables use `use` (heal, cure, boost or nothing
		automatic), `dice` (healing or a shield) and `condition` (what a cure removes or a boost gives); they cost 2 AP
		in a fight and are used up. When a gear forum is set, the item is posted there.

		An accessory needs `worn_slot` (head, neck, back, hands, feet or ring) and has no combat values; `weight` (in
		kilograms) matters on servers with a carry limit.

		`rarity` is taken from the price unless you set it (Common up to 1,000, Uncommon up to 1,500, Rare up to 3,500,
		Very rare above); Legendary items are never sold, only granted. The reply suggests a price for the item's
		combat values, which you are free to ignore.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		if kind.value == ACCESSORY and worn_slot is None :
			return await interaction.followup.send("An accessory needs a `worn_slot`.")
		try :
			needs = Packs.parse_requirements(requirements)
			changes = self.combat_changes(dice, damage_type, attack_stat, damage_stat, hit_mod, range, properties,
			                              ap_cost, armor_class, ac, dt, ability_hit_mod, use, condition, weapon_kind)
			self.check_type(interaction.guild_id, changes)
			combat = Packs.combat_for(kind.value, None, changes)
		except ValueError as e :
			return await interaction.followup.send(str(e))
		item = GearItemTransactions().add(interaction.guild_id, kind.value, name.strip(), price=price,
		                                  description=description, requirements=needs, effect=effect,
		                                  effect_met=effect_met, effect_unmet=effect_unmet, combat=combat,
		                                  rarity=Rarity.parse(rarity.value) if rarity else None, weight=weight,
		                                  slot=worn_slot.value if worn_slot and kind.value == ACCESSORY else None)
		if item is None :
			return await interaction.followup.send(f"The catalog already has an item called {name}.")
		logging.info(f"{interaction.user.name} added gear item {item.name} in {interaction.guild.name}")
		note = await self._post(item)
		hint = Pricing.suggestion_text(item.kind, item.combat, item.requirements, item.price, interaction.guild_id)
		await interaction.followup.send(f"Added the {kind.value} **{item.name}** "
		                                f"({Rarity.label(Rarity.of(item))}).{note}{hint}")

	# ============================================================
	@app_commands.command(name="edit")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=_names)
	@app_commands.choices(attack_stat=STAT_CHOICES, damage_stat=DAMAGE_STAT_CHOICES, range=RANGE_CHOICES,
	                      armor_class=ARMOR_CLASS_CHOICES, use=USE_CHOICES, condition=ITEM_CONDITION_CHOICES,
	                      rarity=RARITY_CHOICES, worn_slot=WORN_SLOT_CHOICES)
	@app_commands.autocomplete(damage_type=_types, weapon_kind=_weapon_kinds)
	@app_commands.describe(**OPTION_HELP)
	async def edit(self, interaction: discord.Interaction, name: str, new_name: app_commands.Range[str, 1, 100] = None,
	               price: app_commands.Range[int, 0, 10000000] = None,
	               description: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	               requirements: app_commands.Range[str, 1, 200] = None, clear_requirements: bool = False,
	               effect: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	               effect_met: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	               effect_unmet: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	               dice: app_commands.Range[str, 3, 7] = None, damage_type: app_commands.Range[str, 1, 50] = None,
	               attack_stat: Choice[str] = None, damage_stat: Choice[str] = None,
	               hit_mod: app_commands.Range[int, -10, 10] = None, range: Choice[str] = None,
	               properties: app_commands.Range[str, 1, 200] = None, ap_cost: app_commands.Range[int, 1, 10] = None,
	               armor_class: Choice[str] = None, ac: app_commands.Range[int, 0, 10] = None,
	               dt: app_commands.Range[int, 0, 10] = None,
	               ability_hit_mod: app_commands.Range[int, -10, 10] = None, use: Choice[str] = None,
	               condition: Choice[str] = None, weapon_kind: str = None, rarity: Choice[str] = None,
	               weight: app_commands.Range[float, 0, 1000] = None, worn_slot: Choice[str] = None) :
		"""
		Changes a catalog item; options you leave out keep their value. `requirements` replaces all of the item's
		requirements, and `clear_requirements` removes them. Type `-` in description or one of the effects to clear
		it. An item's kind cannot change: remove it and add it again instead.

		Characters who own the item keep it under the name it had when they got it. The item's post in the gear forum
		is updated. Pick `rarity` From the price to let the price decide it again. The reply suggests a price for the
		item's combat values.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		item = GearItemTransactions().find(interaction.guild_id, name)
		if item is None :
			return await interaction.followup.send(f"The catalog has no item called {name}.")
		updates = {}
		if new_name and new_name.strip() != item.name :
			other = GearItemTransactions().find(interaction.guild_id, new_name.strip())
			if other is not None and other.id != item.id :
				return await interaction.followup.send(f"The catalog already has an item called {new_name}.")
			updates["name"] = new_name.strip()
		if price is not None :
			updates["price"] = price
		if rarity is not None :
			updates["rarity"] = Rarity.parse(rarity.value)
		if weight is not None :
			updates["weight"] = weight or None
		if worn_slot is not None :
			if item.kind != ACCESSORY :
				return await interaction.followup.send("Only accessories have a worn slot.")
			updates["slot"] = worn_slot.value
		for field, value in (("description", description), ("effect", effect), ("effect_met", effect_met),
		                     ("effect_unmet", effect_unmet)) :
			change, text = self.text_update(value)
			if change :
				updates[field] = text
		try :
			if clear_requirements :
				if requirements :
					return await interaction.followup.send("Use either `requirements` or `clear_requirements`, not "
					                                       "both.")
				updates["requirements"] = {}
			elif requirements is not None :
				updates["requirements"] = Packs.parse_requirements(requirements)
			changes = self.combat_changes(dice, damage_type, attack_stat, damage_stat, hit_mod, range, properties,
			                              ap_cost, armor_class, ac, dt, ability_hit_mod, use, condition, weapon_kind)
			self.check_type(interaction.guild_id, changes)
			if changes :
				updates["combat"] = Packs.combat_for(item.kind, item.combat, changes)
		except ValueError as e :
			return await interaction.followup.send(str(e))
		if not updates :
			return await interaction.followup.send("Nothing to change: fill in at least one option.")
		updated = GearItemTransactions().update(item.id, **updates)
		logging.info(f"{interaction.user.name} edited gear item {item.name} in {interaction.guild.name}: "
		             f"{', '.join(updates)}")
		note = await self._post(item)
		hint = Pricing.suggestion_text(updated.kind, updated.combat, updated.requirements, updated.price,
		                               interaction.guild_id)
		await interaction.followup.send(f"Updated **{updated.name}** ({Rarity.label(Rarity.of(updated))}).{note}{hint}")

	# ============================================================
	async def _enchant_effects(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		from classes.combat import EffectCatalog, PassiveCatalog
		from modules.Ability import effect_choice

		activation = getattr(interaction.namespace, "activation", None) or Magic.ACTIVE
		catalog = PassiveCatalog if activation == Magic.PASSIVE else EffectCatalog
		return [effect_choice(effect) for effect in catalog.search(current, None)[:25]]

	# ============================================================
	@app_commands.command(name="enchant")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=_names, effect=_enchant_effects, second_effect=_enchant_effects,
	                           third_effect=_enchant_effects, damage_type=_types)
	@app_commands.choices(activation=[Choice(name="Active (used as an action)", value=Magic.ACTIVE),
	                                  Choice(name="Passive (always on)", value=Magic.PASSIVE)],
	                      recharge=[Choice(name="After each fight", value=Magic.FIGHT),
	                                Choice(name="Each day", value=Magic.DAY)])
	@app_commands.describe(bonus="+1 to hit (weapon) or +1 DT (armor)", charges="Active: uses (empty: the tier's usual)",
	                       item_bonus="Legendary: the bonus its effects roll with (default 6)",
	                       unidentified_name="What an unidentified copy is called", clear="Make it a plain item again")
	async def enchant(self, interaction: discord.Interaction, name: str, activation: Choice[str] = None,
	                  effect: str = None, second_effect: str = None, third_effect: str = None,
	                  charges: app_commands.Range[int, 1, 10] = None, recharge: Choice[str] = None,
	                  bonus: bool = False, item_bonus: app_commands.Range[int, 0, 10] = None,
	                  damage_type: str = None, unidentified_name: app_commands.Range[str, 1, 100] = None,
	                  clear: bool = False) :
		"""
		Makes a catalog item a magic item, built from the same effects as abilities: `active` effects are used in a
		fight for AP like an ability (with `charges` that come back after each fight or each day), `passive` ones are
		always on. `bonus` adds +1 to hit (weapons) or +1 DT (armor). The item's rarity sets the budget: Uncommon one
		effect up to Weak; Rare one up to Normal or two up to Weak; Very rare one up to Strong or two up to Normal;
		Legendary up to three of any tier. Its effects roll with the item's own bonus (Uncommon +3, Rare +4, Very rare
		+5, Legendary `item_bonus`). A magic item only works for an attuned character.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		item = GearItemTransactions().find(interaction.guild_id, name)
		if item is None :
			return await interaction.followup.send(f"The catalog has no item called {name}.")
		if clear :
			GearItemTransactions().update(item.id, enchantments=None, unidentified_name=None)
			await self._post(item)
			return await interaction.followup.send(f"**{item.name}** is a plain item again.")
		data, problem = Magic.build(activation.value if activation else Magic.ACTIVE,
		                            [effect, second_effect, third_effect], charges,
		                            recharge.value if recharge else None, bonus, item_bonus, damage_type)
		problem = problem or Magic.check(Rarity.of(item), data)
		if problem :
			return await interaction.followup.send(problem)
		updated = GearItemTransactions().update(item.id, enchantments=data,
		                                        unidentified_name=unidentified_name or item.unidentified_name)
		note = await self._post(updated)
		await interaction.followup.send(f"✨ **{item.name}** ({Rarity.label(Rarity.of(item))}): "
		                                f"{Magic.describe(updated)}.{note}")

	# ============================================================
	@app_commands.command(name="remove")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=_names)
	async def remove(self, interaction: discord.Interaction, name: str) :
		"""
		Removes an item from the catalog, and its post from the gear forum. Characters who own it keep their copy, and
		it can no longer be bought or granted.

		**Permissions:**
		- `Manage Server`
		"""
		item = GearItemTransactions().find(interaction.guild_id, name)
		if item is None :
			return await CharacterFlow.respond(interaction, f"The catalog has no item called {name}.")
		if not await ask(interaction, f"Remove **{item.name}** from the catalog? Characters who own it keep their copy.",
		                 "Remove") :
			return
		await GearPost.remove(self.bot, item)
		GearItemTransactions().delete(item.id)
		logging.info(f"{interaction.user.name} removed gear item {item.name} in {interaction.guild.name}")
		await interaction.followup.send(f"Removed {item.name} from the catalog.", ephemeral=True)

	# ============================================================
	@app_commands.command(name="list")
	@app_commands.choices(kind=KIND_CHOICES)
	async def list_items(self, interaction: discord.Interaction, kind: Choice[str] = None) :
		"""
		Lists the catalog with prices and SPECIAL requirements, marking the items you cannot buy and why. Pick a
		`kind` to see only weapons, armor or consumables. Staff also see event items, which are hidden from members.
		"""
		await interaction.response.defer(ephemeral=True)
		kind = kind.value if isinstance(kind, Choice) else kind
		entries = Gear.shop_items(interaction.guild_id, Access.of(interaction.user), kind)
		if not entries :
			return await interaction.followup.send("The catalog is empty." if kind is None else
			                                       f"The catalog has no {Packs.KIND_WORDS[kind][0]}.")
		embeds = []
		for section, title in ((WEAPON, "Weapons"), (ARMOR, "Armor"), (CONSUMABLE, "Consumables"),
		                       (ACCESSORY, "Accessories")) :
			lines = []
			for entry in entries :
				if entry.item.kind != section :
					continue
				line = GearCard.line(entry.item, entry.locked)
				if entry.item.forum_thread_id :
					line += f" · <#{entry.item.forum_thread_id}>"
				lines.append(line)
			embeds += self.pages(title, lines)
		for batch in self.batches(embeds) :
			await interaction.followup.send(embeds=batch, ephemeral=True)

	# ============================================================
	@app_commands.command(name="view")
	@app_commands.autocomplete(name=_names)
	async def view(self, interaction: discord.Interaction, name: str) :
		"""
		Shows a catalog item: its description, price, SPECIAL requirements, effects and combat values, and whether you
		can buy it.
		"""
		await interaction.response.defer(ephemeral=True)
		item = GearItemTransactions().find(interaction.guild_id, name)
		access = Access.of(interaction.user)
		if item is None or (self.hidden(item) and not access.staff) :
			return await interaction.followup.send(f"The catalog has no item called {name}.")
		embed = GearPost.card(item)
		if item.forum_thread_id :
			embed.add_field(name="Post", value=f"<#{item.forum_thread_id}>")
		locked = Gear.lock_reason(item, access)
		if locked :
			embed.set_footer(text=f"Not for sale to you: it {locked}."[:2048])
		await interaction.followup.send(embed=embed)

	# ============================================================
	@app_commands.command(name="import")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(pack=_packs)
	async def import_pack(self, interaction: discord.Interaction, pack: str, refresh: bool = False) :
		"""
		Copies a ready-made genre pack (like Fantasy or Post-apocalyptic) into the catalog. Items whose name the
		catalog already has are skipped, so importing again only adds what is missing and never overwrites your
		changes. When a gear forum is set, every new item is posted there. You can edit or remove imported items like
		any other. Occupations named like the pack's get its starter kits when they have none; the reply suggests the
		pack's currency name. Import its recipes with /craft recipe import, its bestiary with /bestiary import and its
		merchants with /merchant import.

		With `refresh`, items that came from the pack instead get the pack's current combat values (for catalogs
		imported before the combat rework); nothing else about them changes.

		Pick `legacy` to copy the old global armors and weapons tables instead, with their values converted to the
		new combat rules and a price of 0 (set prices with /armory edit). Do this before migration 0015 drops them.

		**Permissions:**
		- `Manage Server`
		"""
		if pack == LEGACY_PACK :
			return await self._import_legacy(interaction)
		try :
			data = Packs.load(pack)
		except ValueError as e :
			return await CharacterFlow.respond(interaction, str(e))
		if refresh :
			if not await ask(interaction, f"Give every item from the **{data['title']}** pack its current combat "
			                              f"values? Other changes you made to those items stay.", "Refresh") :
				return
			updated = Packs.refresh_into(interaction.guild_id, pack)
			logging.info(f"{interaction.user.name} refreshed gear pack {pack} in {interaction.guild.name}: "
			             f"{len(updated)} updated")
			for item in updated :
				await self._post(item)
			return await interaction.followup.send(f"Updated the combat values of {len(updated)} item"
			                                       f"{'s' if len(updated) != 1 else ''} from the {data['title']} pack.",
			                                       ephemeral=True)
		catalog = {item.name.lower() for item in GearItemTransactions().get_all(interaction.guild_id)}
		new = [item for item in data["items"] if item["name"].lower() not in catalog]
		if not new :
			return await CharacterFlow.respond(interaction, f"The catalog already has every item of the "
			                                                f"{data['title']} pack.")
		posting = GearPost.configured(interaction.guild_id)
		question = f"Import the **{data['title']}** pack? This adds {len(new)} item{'s' if len(new) != 1 else ''}"
		if len(new) < len(data["items"]) :
			question += f" ({len(data['items']) - len(new)} already in the catalog are skipped)"
		question += " and posts each in the gear forum." if posting else "."
		if not await ask(interaction, question, "Import") :
			return
		added, skipped = Packs.import_into(interaction.guild_id, pack)
		logging.info(f"{interaction.user.name} imported gear pack {pack} in {interaction.guild.name}: "
		             f"{len(added)} added, {len(skipped)} skipped")
		text = f"Imported the {data['title']} pack: {len(added)} added, {len(skipped)} skipped."
		if posting and added :
			failed = 0
			for item in added :
				if not await GearPost.sync(self.bot, item) :
					failed += 1
			if failed :
				text += f" {failed} could not be posted in the gear forum; check that I can create posts there, then " \
				        f"use /armory post."
		kits = Packs.apply_kits(interaction.guild_id, data)
		if kits :
			text += "\nStarter kits for your occupations: " + "; ".join(kits) + "."
		if data.get("kits") :
			text += "\nOccupations named like the pack's (" + ", ".join(data["kits"]) + ") get its starter kits when " \
			        "they have none."
		if data.get("currency_name") :
			text += f"\nThe pack suggests calling the currency **{data['currency_name']}** (/config currency_name)."
		if data.get("merchants") :
			text += "\nIt also has merchants: add them with /merchant import."
		await interaction.followup.send(text[:2000], ephemeral=True)

	# ============================================================
	async def _import_legacy(self, interaction: discord.Interaction) -> None :
		if not (Legacy.exists("armors") or Legacy.exists("weapons")) :
			return await CharacterFlow.respond(interaction, "The old armors and weapons tables are gone (migration "
			                                                "0015 dropped them).")
		items, _ = Packs.legacy_items()
		if not await ask(interaction, f"Copy {len(items)} item{'s' if len(items) != 1 else ''} from the old armors and "
		                              f"weapons tables into the catalog? Names the catalog already has are skipped.",
		                 "Import") :
			return
		added, skipped, problems = Packs.import_legacy(interaction.guild_id)
		logging.info(f"{interaction.user.name} imported the legacy armors and weapons in {interaction.guild.name}: "
		             f"{len(added)} added, {len(skipped)} skipped")
		for item in added :
			await self._post(item)
		lines = [f"Imported {len(added)} item{'s' if len(added) != 1 else ''} at price 0; {len(skipped)} skipped."]
		if problems :
			lines.append("Could not convert: " + "; ".join(problems))
		await interaction.followup.send("\n".join(lines)[:2000], ephemeral=True)

	# ============================================================
	@app_commands.command(name="post")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def post(self, interaction: discord.Interaction) :
		"""
		Posts every catalog item in the gear forum, or updates its post when it already has one. Use it after setting
		the gear forum, or when posts were deleted. Items keep the tags they had, so their restrictions stay.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		if not GearPost.configured(interaction.guild_id) :
			return await interaction.followup.send("This server has no gear forum. Set one with "
			                                       "`/config singlechannels` (option `gear_forum`).")
		items = GearItemTransactions().get_all(interaction.guild_id)
		if not items :
			return await interaction.followup.send("The catalog is empty.")
		posted = 0
		for item in items :
			if await GearPost.sync(self.bot, item) :
				posted += 1
		text = f"Posted or updated {posted} of {len(items)} item{'s' if len(items) != 1 else ''}."
		if posted < len(items) :
			text += " Check that I can create posts in the gear forum, and that posts there do not need a tag."
		await interaction.followup.send(text)


async def setup(bot) :
	await bot.add_cog(Armory(bot))
