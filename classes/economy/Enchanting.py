"""Player-designed magic items (design/economy.md, phase 5).

A player designs an enchanted item from a catalog item and catalog effects, within its rarity's budget
(classes/gear/Magic.py). The design waits for staff in the review channel. Approval adds a crafted-only catalog item
(the base item's values with the enchantment) and an enchanting recipe: the base item as its ingredient, Intelligence
against 12 / 15 / 18 / 20 by rarity, and 0 / 2 / 5 / 7 days. Only spellcasters, or characters with an occupation staff
put on the recipe, can make it. Crafting it: a crit adds a charge (and makes weapons and armor masterwork); a bad
failure curses it. Who may design follows ABILITY_CREATION.
"""
import logging

import discord

from classes.gear import Magic, Rarity
from classes.kernel.ConfigData import ConfigData
from database.database import EnchantDesigns, GearItems
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.DatabaseTransactions import DatabaseTransactions
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping

PENDING = "pending"
APPROVED = "approved"
DENIED = "denied"
RECIPE_DC = {Rarity.UNCOMMON : 12, Rarity.RARE : 15, Rarity.VERY_RARE : 18, Rarity.LEGENDARY : 20}
RECIPE_DAYS = {Rarity.UNCOMMON : 0, Rarity.RARE : 2, Rarity.VERY_RARE : 5, Rarity.LEGENDARY : 7}
# What the finished item is worth on top of its base item (selling goes by the catalog price).
ADDED_VALUE = {Rarity.UNCOMMON : 1250, Rarity.RARE : 2500, Rarity.VERY_RARE : 9000, Rarity.LEGENDARY : 20000}
DESIGN_RARITIES = [Rarity.UNCOMMON, Rarity.RARE, Rarity.VERY_RARE]


class DesignTransactions(DatabaseTransactions) :

	# ============================================================
	def add(self, **fields) -> EnchantDesigns :
		with self.createsession() as session :
			design = EnchantDesigns(state=PENDING, **fields)
			session.add(design)
			self.commit(session)
			return design

	# ============================================================
	def get(self, design_id: int) -> EnchantDesigns | None :
		from sqlalchemy import Select

		with self.createsession() as session :
			return session.scalar(Select(EnchantDesigns).where(EnchantDesigns.id == design_id))

	# ============================================================
	def update(self, design_id: int, **fields) -> EnchantDesigns | None :
		from sqlalchemy import Select

		with self.createsession() as session :
			design = session.scalar(Select(EnchantDesigns).where(EnchantDesigns.id == design_id))
			if design is None :
				return None
			for key, value in fields.items() :
				setattr(design, key, value)
			self.commit(session)
			return design

	# ============================================================
	def of_user(self, guild_id: int, uid: int | None = None) -> list[EnchantDesigns] :
		from sqlalchemy import Select

		with self.createsession() as session :
			query = Select(EnchantDesigns).where(EnchantDesigns.guild_id == guild_id)
			if uid is not None :
				query = query.where(EnchantDesigns.creator_uid == uid)
			return list(session.scalars(query.order_by(EnchantDesigns.id.desc()).limit(25)).all())


# ============================================================
def creation_problem(member) -> str | None :
	who = str(ConfigData().get_key(member.guild.id, ConfigMapping.ABILITY_CREATION) or "everyone").lower()
	if who == "off" :
		return "Designing magic items is off on this server."
	if who == "staff" and not member.guild_permissions.manage_messages :
		return "Only staff can design magic items on this server."
	return None


# ============================================================
def design_problem(guild_id: int, name: str, base: GearItems | None, rarity: str, data: dict) -> str | None :
	if base is None :
		return "Pick a catalog item to enchant."
	if base.kind not in ("weapon", "armor", "accessory") :
		return "Only weapons, armor and accessories can be enchanted."
	if Magic.enchanted(base) :
		return f"{base.name} is already a magic item."
	if GearItemTransactions().find(guild_id, name) is not None :
		return f"The catalog already has an item called {name}."
	if rarity not in DESIGN_RARITIES :
		return "A design is Uncommon, Rare or Very rare; Legendary items are made by staff."
	return Magic.check(rarity, data)


# ============================================================
def embed(design: EnchantDesigns) -> discord.Embed :
	base = GearItemTransactions().get(design.base_item_id)
	character = CharacterTransactions().get_by_id(design.character_id) if design.character_id else None
	preview = GearItems(kind=base.kind if base else "weapon", enchantments=design.enchantments, price=0,
	                    rarity=design.rarity)
	colour = {PENDING : discord.Colour.blurple(), APPROVED : discord.Colour.green(), DENIED : discord.Colour.red()}
	result = discord.Embed(title=f"✨ {design.name}", description=(design.description or "")[:4000],
	                       colour=colour.get(design.state))
	result.add_field(name="Base item", value=base.name if base else "gone")
	result.add_field(name="Rarity", value=Rarity.label(design.rarity))
	result.add_field(name="Designer", value=f"<@{design.creator_uid}>" + (f" ({character.name})" if character else ""))
	result.add_field(name="Enchantment", value=Magic.describe(preview) or "none", inline=False)
	result.set_footer(text=f"Design {design.id} · {design.state}")
	return result


# ============================================================
def approve(design: EnchantDesigns, reviewer_uid: int) -> tuple[GearItems | None, str | None] :
	"""Adds the catalog item and its enchanting recipe."""
	base = GearItemTransactions().get(design.base_item_id)
	if base is None :
		return None, "The base item is no longer in the catalog."
	problem = design_problem(design.guild_id, design.name, base, design.rarity, design.enchantments)
	if problem :
		return None, problem
	item = GearItemTransactions().add(design.guild_id, base.kind, design.name, price=base.price +
	                                  ADDED_VALUE.get(design.rarity, 0), description=design.description,
	                                  requirements=base.requirements, combat=base.combat, weight=base.weight,
	                                  slot=base.slot, rarity=design.rarity, enchantments=design.enchantments,
	                                  crafted_only=True, salvage=base.salvage)
	if item is None :
		return None, f"The catalog already has an item called {design.name}."
	recipe = EconomyTransactions().add_recipe(design.guild_id, design.name, result_item_id=item.id, result_amount=1,
	                                          ingredients=[{"item_id" : base.id, "amount" : 1}],
	                                          stat="intelligence", dc=RECIPE_DC.get(design.rarity, 15),
	                                          days=RECIPE_DAYS.get(design.rarity, 0), enchanting=True)
	DesignTransactions().update(design.id, state=APPROVED, result_item_id=item.id,
	                            recipe_id=recipe.id if recipe else None)
	logging.info(f"Enchant design {design.id} approved by {reviewer_uid}: item {item.id}")
	return item, None


# ============================================================
def spellcaster(character_id: int) -> bool :
	from classes.combat.Abilities import SPELL
	from database.transactions.AbilityTransactions import AbilityTransactions

	return any(ability.kind == SPELL for _, ability in AbilityTransactions().known(character_id))
