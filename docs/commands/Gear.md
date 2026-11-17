---
layout: default
title: Gear
parent: Commands
nav_order: 20
---

<h1>Gear</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Player commands for the gear their characters own: the inventory, equipping, selling, and marking gear lost or
broken. The rules live in classes/gear/Gear.py.


### `inventory`

**Usage:** `/gear inventory <character> <history> <member>`

> Shows what one of your characters owns: what it wears and holds in which slot, each item's condition when it
> isn't good, ammunition and carried weight when the server uses them, and any SPECIAL requirements it doesn't
> meet. Turn on `history` to include gear that was lost, sold or used up.
>
> Staff can look at another member's character with `member`.

---

### `equip`

**Usage:** `/gear equip <character> <item> <slot>`

> Equips an item in a slot: armor on the body, an accessory where it is worn (head, neck, back, hands, feet or
> one of two rings), a weapon in the main hand, the off hand or the readied slot. A two-handed weapon takes both
> hands and a shield goes in the off hand. Whatever was in the slot is put away. Every weapon your character
> owns can still be used in a fight; the one in the main hand is the one it starts holding. Gear works even when
> the character misses its SPECIAL requirements, but with a penalty.

---

### `unequip`

**Usage:** `/gear unequip <character> <item>`

> Takes off or puts away an equipped item. It stays in the character's inventory.

---

### `sell`

**Usage:** `/gear sell <character> <item>`

> Sells an item for a share of its catalog price: 30% at average Charisma, from 20% to 40% depending on your
> character's Charisma. Masterwork sells for half as much again and cursed gear for nothing. Nothing is paid in
> free mode. You are asked to confirm first.

---

### `attune`

**Usage:** `/gear attune <character> <item>`

> Spends the character's downtime for the day attuning to a magic item, so its enchantment works (armor and
> accessories also have to be worn). A character can be attuned to 3 items (ATTUNEMENT_SLOTS), a legendary one
> to one more. Attuning also identifies an unidentified item. A GM can attune it on the spot instead.

---

### `unattune`

**Usage:** `/gear unattune <character> <item>`

> Ends your character's attunement to a magic item, freeing the slot. A cursed item won't let go until a GM
> lifts the curse.

---

### `identify`

**Usage:** `/gear identify <character> <item>`

> Spends the character's downtime for the day studying an unidentified item: Intelligence against 10 plus 2 per
> rarity step (12 for Uncommon, 14 Rare, 16 Very rare, 18 Legendary). A success reveals what it is.

---

### `lose`

**Usage:** `/gear lose <character> <item>`

> Marks an item as lost, for when your character loses it in the story. It leaves the inventory but stays in
> its history (/gear inventory with `history`). You are asked to confirm first.

---

### `break`

**Usage:** `/gear break <character> <item>`

> Marks an item as broken, for when it breaks in the story. It stays in the inventory but does nothing in a fight
> until it is repaired at the shop (/shop repair) or by a character whose occupation repairs it (/downtime
> repair). You are asked to confirm first.

---

### `proficiency`

**Usage:** `/gear proficiency <character> <item> <tier>`

> Sets how well your character handles one of its weapons: Excellent (+1 to hit and a crit range one wider),
> Good (+1), Average (0), Poor (-1) or Awful (-2). A weapon without a tier counts as Awful. At most two weapons
> can be Good or Excellent. You set a weapon's tier once; after that a GM can change it.

---

