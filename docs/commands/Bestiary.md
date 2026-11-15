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

**Usage:** `/bestiary add <name> <preset> <description> <hp> <ac> <dt> <to_hit> <damage> <damage_type> <attack_name> <ap> <sequence> <behavior> <abilities> <avatar_url> <reward_xp> <reward_currency>`

> Adds an NPC or monster to the bestiary. The `preset` (minion, standard, elite, boss) fills in its numbers;
> the options you fill in replace them. A boss has 14 AP, so it acts about twice as much. GMs add bestiary
> entries to a fight from the board's GM tools.
>
> **Permissions:**
> - `Manage Messages`

---

### `edit`

**Usage:** `/bestiary edit <name> <new_name> <description> <hp> <ac> <dt> <to_hit> <damage> <damage_type> <attack_name> <ap> <sequence> <behavior> <abilities> <avatar_url> <reward_xp> <reward_currency>`

> Changes a bestiary entry; options you leave out keep their value. Type `none` as `abilities` or
> `damage_type` to clear them. NPCs already in a fight keep the numbers they joined with.
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

### `list`

**Usage:** `/bestiary list`

> Lists the bestiary.

---

### `view`

**Usage:** `/bestiary view <name>`

> Shows a bestiary entry.

---

