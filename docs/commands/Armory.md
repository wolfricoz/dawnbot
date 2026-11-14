---
layout: default
title: Armory
parent: Commands
nav_order: 3
---

<h1>Armory</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

The server's gear catalog: the weapons and armor characters can buy in /shop or be given by staff. Staff add
items by hand or import a ready-made genre pack. When a gear forum is set (/config singlechannels), every item gets
its own post there, and tags on that post can restrict who may buy it (see /tagrule).


### `add`

**Usage:** `/armory add <kind> <name> <price> <description> <requirements> <effect> <effect_met> <effect_unmet> <dice> <modifier> <hitmodifier> <hp> <ap> <ac> <hitchance>`

> Adds a weapon or armor set to the catalog. `requirements` are SPECIAL minimums written like
`strength 8, agility 4` (short names like `str 8` work too); they never stop a character from owning or using
the item, they decide whether `effect_met` (a bonus) or `effect_unmet` (a penalty) applies. `effect` is
something the item always does.

Combat values are optional. Weapons use `dice` (like 1d8), `modifier` (a stat added to the damage, or half a
stat as extra dice) and `hitmodifier`. Armor uses `hp`, `ap`, `ac` and `hitchance`; values you leave out are
those of a character without armor (75 HP, 25 AP, 12 AC, 0 hit chance). When a gear forum is set, the item is
posted there.

**Permissions:**
- `Manage Server`

---

### `edit`

**Usage:** `/armory edit <name> <new_name> <price> <description> <requirements> <clear_requirements> <effect> <effect_met> <effect_unmet> <dice> <modifier> <hitmodifier> <hp> <ap> <ac> <hitchance>`

> Changes a catalog item; options you leave out keep their value. `requirements` replaces all of the item's
requirements, and `clear_requirements` removes them. Type `-` in description or one of the effects to clear
it. An item's kind cannot change: remove it and add it again instead.

Characters who own the item keep it under the name it had when they got it. The item's post in the gear forum
is updated.

**Permissions:**
- `Manage Server`

---

### `remove`

**Usage:** `/armory remove <name>`

> Removes an item from the catalog, and its post from the gear forum. Characters who own it keep their copy, and
it can no longer be bought or granted.

**Permissions:**
- `Manage Server`

---

### `list`

**Usage:** `/armory list <kind>`

> Lists the catalog with prices and SPECIAL requirements, marking the items you cannot buy and why. Pick a
`kind` to see only weapons or only armor. Staff also see event items, which are hidden from members.

---

### `view`

**Usage:** `/armory view <name>`

> Shows a catalog item: its description, price, SPECIAL requirements, effects and combat values, and whether you
can buy it.

---

### `import`

**Usage:** `/armory import <pack>`

> Copies a ready-made genre pack (like Fantasy) into the catalog. Items whose name the catalog already has are
skipped, so importing again only adds what is missing and never overwrites your changes. When a gear forum is
set, every new item is posted there. You can edit or remove imported items like any other.

**Permissions:**
- `Manage Server`

---

### `post`

**Usage:** `/armory post`

> Posts every catalog item in the gear forum, or updates its post when it already has one. Use it after setting
the gear forum, or when posts were deleted. Items keep the tags they had, so their restrictions stay.

**Permissions:**
- `Manage Server`

---

