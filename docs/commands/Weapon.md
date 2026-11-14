---
layout: default
title: Weapon
parent: Commands
nav_order: 18
---

<h1>Weapon</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Weapon types used for attack rolls.


### `create`

**Usage:** `/weapon create <name> <dice> <modifier> <hitmodifier>`

> Creates a weapon type. Dice look like 2d6; the modifier is dice:<stat>, damage:<stat> or none.

**Permissions:**
- `Manage Server`

---

### `delete`

**Usage:** `/weapon delete <name>`

> Deletes a weapon type.

**Permissions:**
- `Manage Server`

---

### `list`

**Usage:** `/weapon list`

> Lists all weapon types.

---

### `edit`

**Usage:** `/weapon edit <name> <dice> <modifier> <hitmodifier>`

> Edits a weapon type; options you leave out keep their value.

**Permissions:**
- `Manage Server`

---

