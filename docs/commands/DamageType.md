---
layout: default
title: DamageType
parent: Commands
nav_order: 13
---

<h1>DamageType</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Damage types and what their strong hits do.


### `list`

**Usage:** `/damagetype list`

> Lists the server's damage types and what each adds. A strong hit beats the target's AC by 5 or more (or the
> target fails its save by 5 or more); a crit is always a strong hit.

---

### `add`

**Usage:** `/damagetype add <name> <effect> <condition> <turns> <trigger> <description>`

> Adds a damage type. `effect` is what a strong hit adds: a `condition` for some `turns`, ignoring DT, arcing to
> another enemy, or (for healing) removing a condition. `trigger` is usually a strong hit.
>
> **Permissions:**
> - `Manage Server`

---

### `edit`

**Usage:** `/damagetype edit <name> <effect> <condition> <turns> <trigger> <description>`

> Changes a damage type's effect, trigger or description. Renaming isn't possible, because weapons and
> abilities refer to types by name.
>
> **Permissions:**
> - `Manage Server`

---

### `remove`

**Usage:** `/damagetype remove <name>`

> Removes a damage type. Weapons and abilities that use it keep its name but get no effect.
>
> **Permissions:**
> - `Manage Server`

---

### `reset`

**Usage:** `/damagetype reset`

> Replaces the server's damage types with the default set.
>
> **Permissions:**
> - `Manage Server`

---

