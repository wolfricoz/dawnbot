"""How rare a catalog item is (design/economy.md).

An item without a rarity of its own takes it from its price: Common up to 1,000, Uncommon up to 1,500, Rare up to 3,500
and Very rare above that. Staff can set a rarity on an item. Legendary is never taken from a price and is never sold:
legendary items are only granted.
"""
from database.database import GearItems

COMMON = "common"
UNCOMMON = "uncommon"
RARE = "rare"
VERY_RARE = "very_rare"
LEGENDARY = "legendary"
RARITIES = [COMMON, UNCOMMON, RARE, VERY_RARE, LEGENDARY]
LABELS = {COMMON : "Common", UNCOMMON : "Uncommon", RARE : "Rare", VERY_RARE : "Very rare", LEGENDARY : "Legendary"}
# The highest price of each rarity that is read from a price; anything above the last is Very rare.
PRICE_BANDS = [(1000, COMMON), (1500, UNCOMMON), (3500, RARE)]


# ============================================================
def from_price(price: int) -> str :
	for highest, rarity in PRICE_BANDS :
		if (price or 0) <= highest :
			return rarity
	return VERY_RARE


# ============================================================
def of(item: GearItems) -> str :
	"""The item's own rarity, or the one its price gives."""
	rarity = getattr(item, "rarity", None)
	return rarity if rarity in RARITIES else from_price(item.price)


# ============================================================
def label(rarity: str) -> str :
	return LABELS.get(rarity, str(rarity).replace("_", " ").capitalize())


# ============================================================
def parse(value: str | None) -> str | None :
	"""A rarity typed by staff or written in a pack (`very rare`, `Very_Rare`...), or None for "from the price".
	Raises ValueError for anything else."""
	if value is None :
		return None
	text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
	if text in ("", "auto", "none") :
		return None
	if text not in RARITIES :
		raise ValueError(f"rarity must be one of {', '.join(LABELS.values())} (or auto), not {value!r}.")
	return text
