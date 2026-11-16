"""Where equipped gear goes (design/economy.md, phase 2).

A character has a main hand and an off hand, one readied weapon (on the belt or back), a body for armor, and worn slots
for accessories: head, neck, back, hands, feet and two rings. A two-handed weapon fills both hands, a shield goes in
the off hand. Equipping into a taken slot puts the old item away; cursed gear never comes off that way.

Slots decide what a character wears and what its card shows. Every owned weapon can still be used in a fight, as
before; the main-hand weapon is the one a character starts a fight holding, and an equipped shield gives its AC.
"""
from database.database import CharacterGear, GearItems

MAIN_HAND = "main_hand"
OFF_HAND = "off_hand"
READIED = "readied"
BODY = "body"
HEAD = "head"
NECK = "neck"
BACK = "back"
HANDS = "hands"
FEET = "feet"
RING = "ring"
RING_1 = "ring_1"
RING_2 = "ring_2"
WEAPON_SLOTS = [MAIN_HAND, OFF_HAND, READIED]
# Where an accessory can be worn (gear_items.slot); a ring takes either ring slot.
ACCESSORY_SLOTS = [HEAD, NECK, BACK, HANDS, FEET, RING]
SLOTS = WEAPON_SLOTS + [BODY, HEAD, NECK, BACK, HANDS, FEET, RING_1, RING_2]
LABELS = {MAIN_HAND : "main hand", OFF_HAND : "off hand", READIED : "readied", BODY : "body", HEAD : "head",
          NECK : "neck", BACK : "back", HANDS : "hands", FEET : "feet", RING : "ring", RING_1 : "ring",
          RING_2 : "ring"}


# ============================================================
def label(slot: str | None) -> str :
	return LABELS.get(slot, str(slot or "").replace("_", " "))


# ============================================================
def properties(item: GearItems | None) -> set[str] :
	return set(((item.combat or {}) if item is not None else {}).get("properties") or [])


# ============================================================
def two_handed(item: GearItems | None) -> bool :
	return "two_handed" in properties(item)


# ============================================================
def shield(item: GearItems | None) -> bool :
	return "shield" in properties(item)


# ============================================================
def occupied(worn: list[tuple[CharacterGear, GearItems | None]]) -> dict[str, CharacterGear] :
	"""{slot: entry} for equipped gear; a two-handed weapon in the main hand also holds the off hand."""
	slots = {}
	for entry, item in worn :
		if not entry.equipped or not entry.slot :
			continue
		slots[entry.slot] = entry
		if entry.slot == MAIN_HAND and two_handed(item) :
			slots[OFF_HAND] = entry
	return slots


# ============================================================
def place(kind: str, item: GearItems | None, wanted: str | None,
          worn: list[tuple[CharacterGear, GearItems | None]]) -> tuple[str | None, list[str], str | None] :
	"""Where an item goes and which slots it clears: (slot, slots to clear, problem).

	worn is the character's other owned gear with its catalog items. wanted is the slot the player asked for, or None
	for the usual one.
	"""
	taken = occupied(worn)
	if kind == "armor" :
		return BODY, [BODY], None
	if kind == "accessory" :
		home = getattr(item, "slot", None) if item is not None else None
		if home not in ACCESSORY_SLOTS :
			return None, [], "That accessory has no slot to be worn in; staff can set one with /armory edit."
		if home == RING :
			if wanted in (RING_1, RING_2) :
				return wanted, [wanted], None
			free = next((slot for slot in (RING_1, RING_2) if slot not in taken), RING_1)
			return free, [free], None
		return home, [home], None
	if kind != "weapon" :
		return None, [], "Only weapons, armor and accessories can be equipped."
	if wanted is not None and wanted not in WEAPON_SLOTS :
		return None, [], "A weapon goes in the main hand, the off hand or the readied slot."
	if shield(item) :
		if wanted not in (None, OFF_HAND) :
			return None, [], "A shield goes in the off hand."
		return OFF_HAND, [OFF_HAND] + ([MAIN_HAND] if taken.get(MAIN_HAND) is not None and
		                                taken.get(OFF_HAND) is taken.get(MAIN_HAND) else []), None
	if two_handed(item) :
		if wanted == READIED :
			return READIED, [READIED], None
		if wanted == OFF_HAND :
			return None, [], "A two-handed weapon goes in the main hand (it takes both hands) or the readied slot."
		return MAIN_HAND, [MAIN_HAND, OFF_HAND], None
	if wanted is None :
		wanted = next((slot for slot in WEAPON_SLOTS if slot not in taken), MAIN_HAND)
	clears = [wanted]
	# A two-handed weapon held in the main hand is put away when a hand is needed.
	main = taken.get(MAIN_HAND)
	if wanted == OFF_HAND and main is not None and taken.get(OFF_HAND) is main :
		clears.append(MAIN_HAND)
	return wanted, clears, None
