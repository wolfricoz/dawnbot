"""The rules for gear and currency: what a character may buy, buying, selling, granting, losing and equipping.

This is the one place that changes a character's gear or currency; commands and the interview call it. In free mode
(ECONOMY = free) everything costs nothing and selling returns nothing.
"""
from dataclasses import dataclass

from classes.characters.Access import Access
from classes.characters.Special import STATS
from classes.kernel.ConfigData import ConfigData
from database.database import CharacterGear, Characters, GearItems
from database.transactions.CharacterGearTransactions import BROKEN, CharacterGearTransactions, LOST, OWNED, SOLD, \
	USED
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.CurrencyTransactions import BUY, CurrencyTransactions, GM_GIVE, GM_TAKE, SELL
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping

WEAPON = "weapon"
ARMOR = "armor"
# Used up in a fight with the Use item action (see classes/combat/Items.py).
CONSUMABLE = "consumable"
KINDS = [WEAPON, ARMOR, CONSUMABLE]
KIND_LABELS = {WEAPON : "Weapon", ARMOR : "Armor", CONSUMABLE : "Consumable", "material" : "Material"}
# Crafted quality (see classes/economy/Crafting.py).
MASTERWORK = "masterwork"
CURSED = "cursed"
MASTERWORK_SELL = 1.5

# Where a character's gear came from.
CREATION = "creation"
SHOP = "shop"
GRANTED = "granted"

# Selling returns this share of what the character paid.
SELL_RATE = 0.3
ECONOMY = "economy"
FREE = "free"


@dataclass
class ShopItem :
	item: GearItems
	# What it costs this server (0 in free mode).
	price: int
	# Why the member cannot buy it, or None.
	locked: str | None


class Gear :

	# == settings ==

	# ============================================================
	@staticmethod
	def economy(guild_id: int) -> bool :
		"""True when gear costs currency; False in free mode."""
		return str(ConfigData().get_key(guild_id, ConfigMapping.ECONOMY)).lower() != FREE

	# ============================================================
	@staticmethod
	def price(item: GearItems) -> int :
		return item.price if Gear.economy(item.guild_id) else 0

	# ============================================================
	@staticmethod
	def sell_value(entry: CharacterGear, guild_id: int) -> int :
		"""30% of what was paid, for the whole stack of a material; masterwork sells for half as much again and
		cursed gear for nothing."""
		if not Gear.economy(guild_id) or getattr(entry, "quality", None) == CURSED :
			return 0
		value = entry.price_paid * SELL_RATE * max(1, getattr(entry, "quantity", 1) or 1)
		if getattr(entry, "quality", None) == MASTERWORK :
			value *= MASTERWORK_SELL
		return int(value)

	# == what a character may have ==

	# ============================================================
	@staticmethod
	def unmet_requirements(stats: dict[str, int], item: GearItems) -> list[str] :
		"""The SPECIAL requirements these stats do not meet, as text like "Strength 8"."""
		return [f"{stat.capitalize()} {minimum}" for stat, minimum in (item.requirements or {}).items()
		        if stat in STATS and stats.get(stat, 0) < minimum]

	# ============================================================
	@staticmethod
	def stats_of(character: Characters) -> dict[str, int] :
		return {stat : getattr(character, stat) for stat in STATS}

	# ============================================================
	@staticmethod
	def lock_reason(item: GearItems, access: Access) -> str | None :
		"""Why the member may not buy the item, or None. Event and staff-only items are never bought."""
		requirements = Access.for_gear(item)
		if Access.hidden(requirements) or any(requirement.kind == "staff_only" for requirement in requirements) :
			return "is only given out by staff"
		return access.check(requirements)

	# ============================================================
	@staticmethod
	def shop_items(guild_id: int, access: Access, kind: str | None = None) -> list[ShopItem] :
		"""The catalog as the member sees it: event items left out (staff see everything), locked items marked."""
		items = []
		for item in GearItemTransactions().get_all(guild_id, kind) :
			requirements = Access.for_gear(item)
			if Access.hidden(requirements) and not access.staff :
				continue
			items.append(ShopItem(item, Gear.price(item), Gear.lock_reason(item, access)))
		return items

	# == currency ==

	# ============================================================
	@staticmethod
	def change_currency(character: Characters, amount: int, reason: str, actor_uid: int | None = None,
	                    note: str | None = None, allow_negative: bool = False) -> tuple[Characters | None, str | None] :
		"""Changes a character's currency and writes it in the ledger.

		@return: the updated character, or None and why it was refused (not enough currency).
		"""
		updated, done = CharacterTransactions().change_currency(character.id, amount, allow_negative)
		if updated is None :
			return None, "That character no longer exists."
		if not done :
			name = ConfigData().get_key(character.guild_id, ConfigMapping.CURRENCY_NAME)
			return None, f"{character.name} has {updated.currency} {name}, which is not enough."
		if amount :
			CurrencyTransactions().log(character.id, character.guild_id, amount, reason, actor_uid, note)
		return updated, None

	# ============================================================
	@staticmethod
	def give_currency(character: Characters, amount: int, actor_uid: int, note: str | None = None) :
		return Gear.change_currency(character, amount, GM_GIVE, actor_uid, note)

	# ============================================================
	@staticmethod
	def take_currency(character: Characters, amount: int, actor_uid: int, note: str | None = None) :
		"""Takes currency, refusing to go below 0."""
		return Gear.change_currency(character, -amount, GM_TAKE, actor_uid, note)

	# == getting and losing gear ==

	# ============================================================
	@staticmethod
	def buy(character: Characters, item: GearItems, access: Access, actor_uid: int,
	        source: str = SHOP) -> tuple[CharacterGear | None, str | None] :
		"""Buys an item for a character: checks it may be bought, takes the price and adds it to the inventory.

		@return: the new inventory entry, or None and why it was refused.
		"""
		if item.guild_id != character.guild_id :
			return None, "That item is not sold on this server."
		# Reputation tags on the item's post read this character's standing.
		access = access.for_character(character.id)
		locked = Gear.lock_reason(item, access)
		if locked :
			return None, f"{item.name} {locked}."
		from classes.economy.FactionFlow import FactionFlow

		faction_problem = FactionFlow.buy_problem(character, item)
		if faction_problem :
			return None, faction_problem
		price = FactionFlow.price_for(character, item, Gear.price(item))
		if price :
			updated, problem = Gear.change_currency(character, -price, BUY, actor_uid, note=item.name)
			if problem :
				return None, problem
		entry = CharacterGearTransactions().add(character.id, item.id, item.name, item.kind, source, price, actor_uid)
		return entry, None

	# ============================================================
	@staticmethod
	def grant(character: Characters, item: GearItems, actor_uid: int) -> CharacterGear | None :
		"""Gives a character an item for free, whatever its restrictions (staff and event items)."""
		return CharacterGearTransactions().add(character.id, item.id, item.name, item.kind, GRANTED, 0, actor_uid)

	# ============================================================
	@staticmethod
	def sell(entry: CharacterGear, actor_uid: int) -> tuple[int | None, str | None] :
		"""Sells an owned item for 30% of what was paid (nothing in free mode).

		@return: the amount received, or None and why it was refused.
		"""
		if entry.status != OWNED :
			return None, f"{entry.name} is {entry.status}, so it cannot be sold."
		character = CharacterTransactions().get_by_id(entry.character_id)
		value = Gear.sell_value(entry, character.guild_id)
		CharacterGearTransactions().update(entry.id, status=SOLD, equipped=False, changed_by=actor_uid)
		if value :
			Gear.change_currency(character, value, SELL, actor_uid, note=entry.name)
		return value, None

	# ============================================================
	@staticmethod
	def set_status(entry: CharacterGear, status: str, actor_uid: int) -> tuple[CharacterGear | None, str | None] :
		"""Marks an owned item as lost or broken; it stays in the history."""
		if status not in (LOST, BROKEN) :
			return None, "Gear can only be marked lost or broken."
		if entry.status != OWNED :
			return None, f"{entry.name} is already {entry.status}."
		return CharacterGearTransactions().update(entry.id, status=status, equipped=False, changed_by=actor_uid), None

	# ============================================================
	@staticmethod
	def use_up(entry_id: int) -> CharacterGear | None :
		"""Marks a consumable as used (after a fight's Use item action)."""
		entry = CharacterGearTransactions().get(entry_id)
		if entry is None or entry.status != OWNED :
			return None
		return CharacterGearTransactions().update(entry.id, status=USED, equipped=False)

	# ============================================================
	@staticmethod
	def restore(entry_id: int) -> CharacterGear | None :
		"""Gives back a consumable whose use was undone."""
		entry = CharacterGearTransactions().get(entry_id)
		if entry is None or entry.status != USED :
			return None
		return CharacterGearTransactions().update(entry.id, status=OWNED)

	# ============================================================
	@staticmethod
	def take(entry: CharacterGear) -> bool :
		"""Removes an item from a character entirely, as if they never had it (for mistakes)."""
		return CharacterGearTransactions().delete(entry.id)

	# == equipping ==

	# ============================================================
	@staticmethod
	def equip(entry: CharacterGear) -> tuple[CharacterGear | None, str | None] :
		"""Equips an owned item. A character wears one armor set at a time; weapons can all be equipped."""
		if entry.status != OWNED :
			return None, f"{entry.name} is {entry.status}."
		if entry.kind == CONSUMABLE :
			return None, f"{entry.name} is used up in a fight, not equipped."
		if entry.kind not in (WEAPON, ARMOR) :
			return None, f"{entry.name} can't be equipped."
		if entry.kind == ARMOR :
			stuck = [worn for worn in CharacterGearTransactions().equipped(entry.character_id, ARMOR)
			         if worn.id != entry.id and getattr(worn, "quality", None) == CURSED]
			if stuck :
				return None, f"The cursed {stuck[0].name} won't come off; a GM has to lift the curse first."
		return CharacterGearTransactions().equip(entry.id, only_one_of_kind=entry.kind == ARMOR), None

	# ============================================================
	@staticmethod
	def unequip(entry: CharacterGear) -> CharacterGear | None :
		"""Takes an item off. Cursed armor doesn't come off (returns None)."""
		if Gear.stuck(entry) :
			return None
		return CharacterGearTransactions().update(entry.id, equipped=False)

	# ============================================================
	@staticmethod
	def stuck(entry: CharacterGear) -> bool :
		"""Cursed armor that is worn can't be taken off until a GM lifts the curse."""
		return entry.kind == ARMOR and entry.equipped and getattr(entry, "quality", None) == CURSED

	# ============================================================
	@staticmethod
	def inventory(character_id: int, include_gone: bool = False) -> list[tuple[CharacterGear, GearItems | None]] :
		"""The character's gear with its catalog entry (None when the catalog entry was removed)."""
		return [(entry, GearItemTransactions().get(entry.gear_item_id))
		        for entry in CharacterGearTransactions().get_all(character_id, include_gone)]

	# ============================================================
	@staticmethod
	def equipped_armor(character_id: int) -> tuple[CharacterGear, GearItems | None] | None :
		armor = CharacterGearTransactions().equipped(character_id, ARMOR)
		if not armor :
			return None
		return armor[0], GearItemTransactions().get(armor[0].gear_item_id)
