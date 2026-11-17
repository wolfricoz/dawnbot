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

**Usage:** `/armory add <kind> <name> <price> <description> <requirements> <effect> <effect_met> <effect_unmet> <dice> <damage_type> <attack_stat> <damage_stat> <hit_mod> <range> <properties> <ap_cost> <armor_class> <ac> <dt> <ability_hit_mod> <use> <condition> <weapon_kind> <rarity> <weight> <worn_slot>`

> Adds a weapon, armor set, consumable or accessory to the catalog. `requirements` are SPECIAL minimums written like
> `strength 8, agility 4` (short names like `str 8` work too); they never stop a character from owning or using
> the item, but each missing point is -1 to hit, and they decide whether `effect_met` (a bonus) or `effect_unmet`
> (a penalty) applies. `effect` is something the item always does.
>
> Combat values are optional. Weapons use `dice` (like 2d6), `damage_type`, `attack_stat` and `damage_stat`
> (the stats added to attack and damage rolls), `hit_mod`, `range`, `properties` (like `light, thrown`; a
> `shield` gives +2 AC while equipped), `ap_cost` and `weapon_kind` (sword, spear, bow, claw...: which weapon
> techniques it allows; without it the kind is read from the name). Armor uses `armor_class`, `ac` (added to
> AC), `dt` (taken
> off every hit), `hit_mod` and `ability_hit_mod`. Consumables use `use` (heal, cure, boost or nothing
> automatic), `dice` (healing or a shield) and `condition` (what a cure removes or a boost gives); they cost 2 AP
> in a fight and are used up. When a gear forum is set, the item is posted there.
>
> An accessory needs `worn_slot` (head, neck, back, hands, feet or ring) and has no combat values; `weight` (in
> kilograms) matters on servers with a carry limit.
>
> `rarity` is taken from the price unless you set it (Common up to 1,000, Uncommon up to 1,500, Rare up to 3,500,
> Very rare above); Legendary items are never sold, only granted. The reply suggests a price for the item's
> combat values, which you are free to ignore.
>
> **Permissions:**
> - `Manage Server`

---

### `edit`

**Usage:** `/armory edit <name> <new_name> <price> <description> <requirements> <clear_requirements> <effect> <effect_met> <effect_unmet> <dice> <damage_type> <attack_stat> <damage_stat> <hit_mod> <range> <properties> <ap_cost> <armor_class> <ac> <dt> <ability_hit_mod> <use> <condition> <weapon_kind> <rarity> <weight> <worn_slot>`

> Changes a catalog item; options you leave out keep their value. `requirements` replaces all of the item's
> requirements, and `clear_requirements` removes them. Type `-` in description or one of the effects to clear
> it. An item's kind cannot change: remove it and add it again instead.
>
> Characters who own the item keep it under the name it had when they got it. The item's post in the gear forum
> is updated. Pick `rarity` From the price to let the price decide it again. The reply suggests a price for the
> item's combat values.
>
> **Permissions:**
> - `Manage Server`

---

### `enchant`

**Usage:** `/armory enchant <name> <activation> <effect> <second_effect> <third_effect> <charges> <recharge> <bonus> <item_bonus> <damage_type> <unidentified_name> <clear>`

> Makes a catalog item a magic item, built from the same effects as abilities: `active` effects are used in a
> fight for AP like an ability (with `charges` that come back after each fight or each day), `passive` ones are
> always on. `bonus` adds +1 to hit (weapons) or +1 DT (armor). The item's rarity sets the budget: Uncommon one
> effect up to Weak; Rare one up to Normal or two up to Weak; Very rare one up to Strong or two up to Normal;
> Legendary up to three of any tier. Its effects roll with the item's own bonus (Uncommon +3, Rare +4, Very rare
> +5, Legendary `item_bonus`). A magic item only works for an attuned character.
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

> Copies a ready-made genre pack (like Fantasy or Post-apocalyptic) into the catalog. Items whose name the
> catalog already has are skipped, so importing again only adds what is missing and never overwrites your
> changes. When a gear forum is set, every new item is posted there. You can edit or remove imported items like
> any other. Occupations named like the pack's get its starter kits when they have none; the reply suggests the
> pack's currency name. Import its recipes with /craft recipe import, its bestiary with /bestiary import and its
> merchants with /merchant import.
>
> With `refresh`, items that came from the pack instead get the pack's current combat values (for catalogs
> imported before the combat rework); nothing else about them changes.
>
> Pick `legacy` to copy the old global armors and weapons tables instead, with their values converted to the
> new combat rules and a price of 0 (set prices with /armory edit). Do this before migration 0015 drops them.
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

