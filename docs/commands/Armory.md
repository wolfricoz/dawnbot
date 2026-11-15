---
layout: default
title: Armory
parent: Commands
nav_order: 3
---

<h1>Armory</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>




### `add`

**Usage:** `/armory add <kind> <name> <price> <description> <requirements> <effect> <effect_met> <effect_unmet> <dice> <damage_type> <attack_stat> <damage_stat> <hit_mod> <range> <properties> <ap_cost> <armor_class> <ac> <dt> <ability_hit_mod> <use> <condition>`

> Adds a weapon, armor set or consumable to the catalog. `requirements` are SPECIAL minimums written like
> `strength 8, agility 4` (short names like `str 8` work too); they never stop a character from owning or using
> the item, but each missing point is -1 to hit, and they decide whether `effect_met` (a bonus) or `effect_unmet`
> (a penalty) applies. `effect` is something the item always does.
>
> Combat values are optional. Weapons use `dice` (like 2d6), `damage_type`, `attack_stat` and `damage_stat`
> (the stats added to attack and damage rolls), `hit_mod`, `range`, `properties` (like `light, thrown`; a
> `shield` gives +2 AC while equipped) and `ap_cost`. Armor uses `armor_class`, `ac` (added to AC), `dt` (taken
> off every hit), `hit_mod` and `ability_hit_mod`. Consumables use `use` (heal, cure, boost or nothing
> automatic), `dice` (healing or a shield) and `condition` (what a cure removes or a boost gives); they cost 2 AP
> in a fight and are used up. When a gear forum is set, the item is posted there.
>
> **Permissions:**
> - `Manage Server`

---

### `edit`

**Usage:** `/armory edit <name> <new_name> <price> <description> <requirements> <clear_requirements> <effect> <effect_met> <effect_unmet> <dice> <damage_type> <attack_stat> <damage_stat> <hit_mod> <range> <properties> <ap_cost> <armor_class> <ac> <dt> <ability_hit_mod> <use> <condition>`

> Changes a catalog item; options you leave out keep their value. `requirements` replaces all of the item's
> requirements, and `clear_requirements` removes them. Type `-` in description or one of the effects to clear
> it. An item's kind cannot change: remove it and add it again instead.
>
> Characters who own the item keep it under the name it had when they got it. The item's post in the gear forum
> is updated.
>
> **Permissions:**
> - `Manage Server`

---

### `remove`

**Usage:** `/armory remove <name>`

> Removes an item from the catalog, and its post from the gear forum. Characters who own it keep their copy, and
> it can no longer be bought or granted.
>
> **Permissions:**
> - `Manage Server`

---

### `list`

**Usage:** `/armory list <kind>`

> Lists the catalog with prices and SPECIAL requirements, marking the items you cannot buy and why. Pick a
> `kind` to see only weapons, armor or consumables. Staff also see event items, which are hidden from members.

---

### `view`

**Usage:** `/armory view <name>`

> Shows a catalog item: its description, price, SPECIAL requirements, effects and combat values, and whether you
> can buy it.

---

### `import`

**Usage:** `/armory import <pack> <refresh>`

> Copies a ready-made genre pack (like Fantasy) into the catalog. Items whose name the catalog already has are
> skipped, so importing again only adds what is missing and never overwrites your changes. When a gear forum is
> set, every new item is posted there. You can edit or remove imported items like any other.
>
> With `refresh`, items that came from the pack instead get the pack's current combat values (for catalogs
> imported before the combat rework); nothing else about them changes.
>
> Pick `legacy` to copy the old global armors and weapons tables instead, with their values converted to the
> new combat rules and a price of 0 (set prices with /armory edit). Do this before migration 0014 drops them.
>
> **Permissions:**
> - `Manage Server`

---

### `post`

**Usage:** `/armory post`

> Posts every catalog item in the gear forum, or updates its post when it already has one. Use it after setting
> the gear forum, or when posts were deleted. Items keep the tags they had, so their restrictions stay.
>
> **Permissions:**
> - `Manage Server`

---

