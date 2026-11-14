---
layout: default
title: Gear
parent: Commands
nav_order: 10
---

<h1>Gear</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Your characters' gear. Buy gear with /shop; here you look at what a character owns, equip it, sell it, or mark
it lost or broken. A character wears one armor set at a time and can carry every weapon it owns.


### `inventory`

**Usage:** `/gear inventory <character> <history> <member>`

> Shows what one of your characters owns: what it wears and carries, and any SPECIAL requirements it doesn't
meet. Turn on `history` to include gear that was lost, broken or sold.

Staff can look at another member's character with `member`.

---

### `equip`

**Usage:** `/gear equip <character> <item>`

> Equips an item. A character wears one armor set at a time, so equipping armor takes off the armor it wore;
weapons can all be equipped together. Gear works even when the character misses its SPECIAL requirements,
but with a penalty.

---

### `unequip`

**Usage:** `/gear unequip <character> <item>`

> Takes off or puts away an equipped item. It stays in the character's inventory.

---

### `sell`

**Usage:** `/gear sell <character> <item>`

> Sells an item for 30% of what your character paid for it. Gear that was given to you or bought in free mode
sells for nothing. You are asked to confirm first.

---

### `lose`

**Usage:** `/gear lose <character> <item>`

> Marks an item as lost, for when your character loses it in the story. It leaves the inventory but stays in
its history (/gear inventory with `history`). You are asked to confirm first.

---

### `break`

**Usage:** `/gear break <character> <item>`

> Marks an item as broken, for when it breaks in the story. It leaves the inventory but stays in its history
(/gear inventory with `history`). You are asked to confirm first.

---

