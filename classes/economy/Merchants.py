"""Merchants, lodging and stashes (design/economy.md, phase 4).

A merchant is an NPC shop at one or more locations. It sells catalog items from its stock, each line with a quantity
(empty is unlimited), a chance to be there after a restock (100 is always) and its own price if staff set one. Prices
are the catalog (or the line's) price × the merchant's markup × Charisma × faction standing (the merchant's faction,
else the item's) × any haggled discount, never under 65% of price × markup. A merchant buys the kinds of gear it lists,
paying Charisma's sale value × its `pays`. Restocks come daily, weekly or when staff say so.

Haggling: once per item per restock, a character rolls Charisma against the merchant's haggle DC. A success takes 10%
off that item, a strong success or crit 20%; a failure changes nothing, and a bad failure or fumble means the merchant
won't deal with the character until the next restock.

Services: `repair` (the shop repair price × markup) and `lodging` (a room for a week at a time). A room opens the stash
at that location: items put there leave the inventory, weigh nothing and stay out of fights, and come back out at the
same location. Putting items in needs a paid room; taking them out only needs being there.

SHOP_MODE: `global` (the default; the catalog shop sells everything, merchants are extra), `both` (the catalog shop
sells only Common and Uncommon items, merchants the rest) or `merchants` (no catalog shop: buying, selling and repairs
go through merchants).
"""
import random
from datetime import datetime, timedelta, timezone

from classes.checks import Checks
from classes.gear import Carry, Condition, Pricing, Rarity
from classes.gear.Gear import Gear
from classes.kernel import RoleplaySettings
from database.database import CharacterGear, Characters, GearItems, Merchants, MerchantStock
from database.transactions.CharacterGearTransactions import CharacterGearTransactions, SOLD
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.MerchantTransactions import MerchantTransactions
from resources.configs.ConfigMapping import ConfigMapping

GLOBAL = "global"
BOTH = "both"
MERCHANTS = "merchants"
SHOP_MODES = [GLOBAL, MERCHANTS, BOTH]
REPAIR = "repair"
LODGING = "lodging"
IDENTIFY = "identify"
HEALING = "healing"
TRAINING = "training"
SERVICES = [REPAIR, LODGING, IDENTIFY, HEALING, TRAINING]
# What identifying an item costs: this share of its catalog price (at least 10), times the markup.
IDENTIFY_SHARE = 0.1
DAILY = "daily"
WEEKLY = "weekly"
MANUAL = "manual"
RESTOCKS = {DAILY : timedelta(days=1), WEEKLY : timedelta(days=7), MANUAL : None}
HAGGLE_DISCOUNT = {Checks.CRIT : 20, Checks.STRONG : 20, Checks.SUCCESS : 10}
STASHED = "stashed"
WEEK = timedelta(days=7)


# == shop mode ==

# ============================================================
def shop_mode(guild_id: int) -> str :
	mode = RoleplaySettings.text(guild_id, ConfigMapping.SHOP_MODE).lower()
	return mode if mode in SHOP_MODES else GLOBAL


# ============================================================
def global_shop_sells(item: GearItems) -> bool :
	"""Whether the catalog shop (/shop) sells this item under the server's shop mode."""
	mode = shop_mode(item.guild_id)
	if mode == MERCHANTS :
		return False
	if mode == BOTH :
		return Rarity.of(item) in (Rarity.COMMON, Rarity.UNCOMMON)
	return True


# ============================================================
def global_shop_problem(guild_id: int, what: str = "sells") -> str | None :
	"""Why the catalog shop is closed for this (merchants mode), or None."""
	if shop_mode(guild_id) == MERCHANTS :
		return f"This server has no catalog shop; the merchants {what} instead (/merchant browse in a location)."
	return None


# == where ==

# ============================================================
def trades_at(merchant: Merchants, location_id: int | None) -> bool :
	"""A merchant without locations trades anywhere; otherwise only at its locations."""
	return not merchant.location_ids or (location_id is not None and location_id in merchant.location_ids)


# ============================================================
def merchants_at(guild_id: int, location_id: int | None) -> list[Merchants] :
	return [merchant for merchant in MerchantTransactions().get_all(guild_id) if trades_at(merchant, location_id)]


# == prices ==

# ============================================================
def faction_multiplier(merchant: Merchants, character: Characters, item: GearItems) -> float :
	from classes.economy.FactionFlow import FactionFlow, PRICE, tier
	from database.transactions.EconomyTransactions import EconomyTransactions

	if merchant.faction_id :
		return PRICE[tier(EconomyTransactions().standing(character.id, merchant.faction_id))] or 1.0
	if item.price and getattr(item, "faction_id", None) :
		return FactionFlow.price_for(character, item, item.price) / item.price
	return 1.0


# ============================================================
def base_price(merchant: Merchants, line: MerchantStock, item: GearItems) -> int :
	return round((line.price if line.price is not None else item.price) * (merchant.markup or 1.0))


# ============================================================
def price(merchant: Merchants, line: MerchantStock, item: GearItems, character: Characters) -> int :
	if not Pricing.economy(merchant.guild_id) :
		return 0
	base = base_price(merchant, line, item)
	multiplier = Pricing.buy_multiplier(character) * faction_multiplier(merchant, character, item)
	multiplier *= 1 - discount_for(merchant, character, item.id) / 100
	return max(0, round(base * max(Pricing.LOWEST_PRICE, multiplier)))


# ============================================================
def sell_value(merchant: Merchants, entry: CharacterGear) -> int :
	return int(Gear.sell_value(entry) * (merchant.pays if merchant.pays is not None else 1.0))


# ============================================================
def repair_price(merchant: Merchants, entry: CharacterGear, item: GearItems | None, character: Characters) -> int :
	return round(Condition.shop_price(entry, item, character) * (merchant.markup or 1.0))


# ============================================================
def identify_price(merchant: Merchants, item: GearItems | None) -> int :
	if not Pricing.economy(merchant.guild_id) :
		return 0
	return max(10, round((item.price if item is not None else 0) * IDENTIFY_SHARE * (merchant.markup or 1.0)))


# == stock ==

# ============================================================
def in_stock(line: MerchantStock) -> bool :
	return bool(line.available) and (line.in_stock is None or line.in_stock > 0)


# ============================================================
def wares(merchant: Merchants) -> list[tuple[MerchantStock, GearItems]] :
	"""What the merchant has for sale right now."""
	lines = []
	for line in MerchantTransactions().stock(merchant.id) :
		item = GearItemTransactions().get(line.gear_item_id)
		if item is not None and in_stock(line) :
			lines.append((line, item))
	return lines


# ============================================================
def restocked_line(line: MerchantStock, rng: random.Random | None = None) -> tuple[bool, int | None] :
	"""(available, in stock) after a restock: there on a roll under its chance, with its full quantity."""
	available = (line.chance or 0) >= 100 or (rng or random).randint(1, 100) <= (line.chance or 0)
	return available, (line.quantity if available else 0)


# ============================================================
def restock(merchant: Merchants, now: datetime | None = None, rng: random.Random | None = None) -> Merchants | None :
	lines = [(line.id, *restocked_line(line, rng)) for line in MerchantTransactions().stock(merchant.id)]
	return MerchantTransactions().restock(merchant.id, lines, now or datetime.now(timezone.utc))


# ============================================================
def due(merchant: Merchants, now: datetime | None = None) -> bool :
	interval = RESTOCKS.get(merchant.restock)
	if interval is None :
		return False
	if merchant.last_restock is None :
		return True
	return (now or datetime.now(timezone.utc)) - merchant.last_restock >= interval


# ============================================================
def restock_due(now: datetime | None = None, rng: random.Random | None = None) -> list[Merchants] :
	"""Restocks every merchant whose time has come; returns them."""
	return [restock(merchant, now, rng) for merchant in MerchantTransactions().every_merchant() if due(merchant, now)]


# == haggling ==

# ============================================================
def refused(merchant: Merchants, character: Characters) -> bool :
	return any(haggle.refused for haggle in MerchantTransactions().haggles(merchant.id, character.id,
	                                                                       merchant.cycle or 0))


# ============================================================
def discount_for(merchant: Merchants, character: Characters, item_id: int) -> int :
	return max([haggle.discount for haggle in MerchantTransactions().haggles(merchant.id, character.id,
	                                                                         merchant.cycle or 0)
	            if haggle.gear_item_id == item_id] or [0])


# ============================================================
def haggle(merchant: Merchants, character: Characters, item: GearItems,
           rng: random.Random | None = None) -> tuple[str | None, list[str]] :
	"""Haggles over an item: (outcome, lines), or (None, [why not])."""
	from classes.characters.Special import Special

	if merchant.haggle_dc is None :
		return None, [f"{merchant.name} doesn't haggle."]
	if refused(merchant, character) :
		return None, [f"{merchant.name} won't deal with {character.name} until the next restock."]
	cycle = merchant.cycle or 0
	if any(haggle.gear_item_id == item.id for haggle in MerchantTransactions().haggles(merchant.id, character.id, cycle)) :
		return None, [f"{character.name} already haggled over {item.name}; try again after the next restock."]
	from classes.combat.Rules import Bonus
	from classes.economy import Lifestyle

	lifestyle = Lifestyle.haggle_bonus(character)
	extras = [Bonus("Lifestyle", lifestyle)] if lifestyle else []
	result = Checks.roll(Checks.stats_of(character), "charisma", merchant.haggle_dc,
	                     base=Special.rules(character.guild_id).base, extras=extras, rng=rng)
	discount = HAGGLE_DISCOUNT.get(result.outcome, 0)
	bad = result.outcome in (Checks.BAD, Checks.FUMBLE)
	MerchantTransactions().add_haggle(merchant.id, character.id, item.id, cycle, discount, False)
	if bad :
		MerchantTransactions().add_haggle(merchant.id, character.id, None, cycle, 0, True)
	lines = [f"🤝 {character.name} haggles with {merchant.name} over **{item.name}**: {result.breakdown()} on Charisma "
	         f"against {merchant.haggle_dc} · {Checks.OUTCOME_LABELS[result.outcome]}"]
	if discount :
		lines.append(f"{discount}% off {item.name} until the next restock.")
	elif bad :
		lines.append(f"{merchant.name} is offended and won't deal with {character.name} until the next restock.")
	else :
		lines.append("The price stays as it is.")
	return result.outcome, lines


# == buying and selling ==

# ============================================================
def buy(merchant: Merchants, line: MerchantStock, item: GearItems, character: Characters, access,
        actor_uid: int) -> tuple[CharacterGear | None, str | None] :
	from classes.economy.FactionFlow import FactionFlow

	if refused(merchant, character) :
		return None, f"{merchant.name} won't deal with {character.name} until the next restock."
	locked = Gear.lock_reason(item, access.for_character(character.id))
	if locked :
		return None, f"{item.name} {locked}."
	problem = FactionFlow.buy_problem(character, item) or Carry.too_heavy(character, item)
	if problem :
		return None, problem
	cost = price(merchant, line, item, character)
	return MerchantTransactions().buy(line.id, character.id, cost, actor_uid, f"{item.name} from {merchant.name}")


# ============================================================
def sell(merchant: Merchants, entry: CharacterGear, actor_uid: int) -> tuple[int | None, str | None] :
	"""Sells an owned item to the merchant, if it buys that kind."""
	if entry.kind not in (merchant.buys or []) :
		return None, f"{merchant.name} doesn't buy {entry.kind} gear."
	if entry.status != "owned" :
		return None, f"{entry.name} is {entry.status}."
	if Gear.stuck(entry) :
		return None, f"The cursed {entry.name} won't come off."
	from database.transactions.CharacterTransactions import CharacterTransactions
	from database.transactions.CurrencyTransactions import SELL

	character = CharacterTransactions().get_by_id(entry.character_id)
	value = sell_value(merchant, entry)
	CharacterGearTransactions().update(entry.id, status=SOLD, equipped=False, slot=None, changed_by=actor_uid)
	if value :
		Gear.change_currency(character, value, SELL, actor_uid, note=f"{entry.name} to {merchant.name}")
	return value, None


# == lodging and stashes ==

# ============================================================
def lodging_active(character: Characters, location_id: int, now: datetime | None = None) -> bool :
	lodging = MerchantTransactions().lodging(character.id, location_id)
	return lodging is not None and lodging.paid_until > (now or datetime.now(timezone.utc))


# ============================================================
def rent(merchant: Merchants, character: Characters, location_id: int, weeks: int, actor_uid: int,
         now: datetime | None = None) :
	"""Rents a room at the location for some weeks (adding to time already paid)."""
	if LODGING not in (merchant.services or []) :
		return None, f"{merchant.name} has no rooms."
	now = now or datetime.now(timezone.utc)
	current = MerchantTransactions().lodging(character.id, location_id)
	start = current.paid_until if current is not None and current.paid_until > now else now
	cost = (merchant.lodging_price or 0) * weeks if Pricing.economy(merchant.guild_id) else 0
	return MerchantTransactions().rent(character.id, location_id, merchant.id, start + WEEK * weeks, cost, actor_uid,
	                                   f"{weeks} week(s) at {merchant.name}")


# ============================================================
def stash(character: Characters, entry: CharacterGear, location_id: int, now: datetime | None = None) -> str | None :
	"""Puts an item in the stash at the location; returns why it can't, or None."""
	if not lodging_active(character, location_id, now) :
		return f"{character.name} needs a paid room here to use the stash (/merchant lodge)."
	if entry.character_id != character.id or entry.status != "owned" :
		return f"{entry.name} isn't in {character.name}'s inventory."
	if entry.equipped :
		return f"{entry.name} is equipped; put it away first with /gear unequip."
	CharacterGearTransactions().update(entry.id, status=STASHED, stash_location_id=location_id)
	return None


# ============================================================
def unstash(character: Characters, entry: CharacterGear, location_id: int) -> str | None :
	"""Takes an item out of the stash at the location; returns why it can't, or None."""
	if entry.character_id != character.id or entry.status != STASHED or entry.stash_location_id != location_id :
		return f"{entry.name} isn't in {character.name}'s stash here."
	item = GearItemTransactions().get(entry.gear_item_id)
	if item is not None :
		heavy = Carry.too_heavy(character, item, max(1, entry.quantity or 1))
		if heavy :
			return heavy
	CharacterGearTransactions().update(entry.id, status="owned", stash_location_id=None)
	return None


# ============================================================
def stashed(character: Characters, location_id: int | None = None) -> list[CharacterGear] :
	return [entry for entry in CharacterGearTransactions().get_all(character.id, include_gone=True)
	        if entry.status == STASHED and (location_id is None or entry.stash_location_id == location_id)]
