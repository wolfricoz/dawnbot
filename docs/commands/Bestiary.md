---
layout: default
title: Bestiary
parent: Commands
nav_order: 4
---

<h1>Bestiary</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

NPCs and monsters for fights.


### `add`

**Usage:** `/bestiary add <name> <preset> <description> <hp> <ac> <dt> <to_hit> <damage> <damage_type> <attack_name> <ap> <sequence> <behavior> <abilities> <avatar_url> <reward_xp> <reward_currency> <special> <level> <weapons> <armor>`

> Adds an NPC or monster to the bestiary. The `preset` (minion, standard, elite, miniboss, boss) fills in its
> numbers; a miniboss or boss gets 75 HP + 18.75 (miniboss) or 37.5 (boss) per player character it faces, set
> when the fight starts;
> the options you fill in replace them. A boss has 14 AP, so it acts about twice as much. GMs add bestiary
> entries to a fight from the board's GM tools.
>
> Give it `special` instead (seven numbers, or like `str 6, agi 7`) to build it like a character: HP, AC, AP
> and Sequence come from SPECIAL and `level`, and it fights with catalog `weapons` (Average proficiency) and
> `armor`. Its own attack options are then not used.
>
> **Permissions:**
> - `Manage Messages`

---

### `edit`

**Usage:** `/bestiary edit <name> <new_name> <description> <hp> <ac> <dt> <to_hit> <damage> <damage_type> <attack_name> <ap> <sequence> <behavior> <abilities> <avatar_url> <reward_xp> <reward_currency> <special> <level> <weapons> <armor>`

> Changes a bestiary entry; options you leave out keep their value. Type `none` as `abilities`,
> `damage_type`, `special`, `weapons` or `armor` to clear them; clearing `special` turns it back into a stat
> block. NPCs already in a fight keep the numbers they joined with.
>
> **Permissions:**
> - `Manage Messages`

---

### `remove`

**Usage:** `/bestiary remove <name>`

> Removes an entry from the bestiary. NPCs already in a fight stay in it.
>
> **Permissions:**
> - `Manage Messages`

---

### `loot`

**Usage:** `/bestiary loot <name> <currency> <items> <clear>`

> Sets what an entry drops when it is defeated: currency (dice or a number) and catalog items, each with a
> chance (100% when left out) and an amount. After a fight, the GM presses Loot on the GM panel to roll it,
> winners claim items, and the GM settles who gets what. Options you leave out keep their value.
>
> **Permissions:**
> - `Manage Messages`

---

### `list`

**Usage:** `/bestiary list`

> Lists the bestiary.

---

### `view`

**Usage:** `/bestiary view <name>`

> Shows a bestiary entry.

---

### `import`

**Usage:** `/bestiary import <source>`

> Copies NPCs and monsters into the bestiary: a genre pack's ready-made bestiary (import the pack's gear with
> /armory import first, so its fighters get their weapons), or `legacy`, the old global npcs and monsters
> tables. Names the bestiary already has are skipped, so importing again only adds what is missing.
>
> Old NPCs had HP on the old scale (about 100 for a character), so their HP is scaled down to the new rules;
> check the imported numbers with /bestiary view.
>
> **Permissions:**
> - `Manage Messages`

---

