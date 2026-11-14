---
layout: default
title: Occupation
parent: Commands
nav_order: 10
---

<h1>Occupation</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

The roles and occupations characters can hold. Each can have a limit on how many characters hold it, and can
need a server level, a role, or be given out by staff only.


### `add`

**Usage:** `/occupation add <name> <limit> <description> <min_level> <role> <staff_only>`

> Adds an occupation. Leave out `limit` for no limit on how many characters can hold it. `min_level` is the
server level a member needs (the number of level roles they have reached), `role` a role they need;
`staff_only` ones are only given out with /occupation assign.

**Permissions:**
- `Manage Server`

---

### `edit`

**Usage:** `/occupation edit <name> <new_name> <limit> <no_limit> <description> <min_level> <role> <no_role> <staff_only>`

> Changes an occupation; options you leave out keep their value. Use `no_limit` or `no_role` to remove the
limit or the role, and min_level 0 to remove the level. Lowering the limit below the number of holders takes
nobody's occupation away; it only stops new characters from picking it.

**Permissions:**
- `Manage Server`

---

### `remove`

**Usage:** `/occupation remove <name>`

> Removes an occupation. Characters that hold it are left without an occupation.

**Permissions:**
- `Manage Server`

---

### `move`

**Usage:** `/occupation move <name> <position>`

> Moves an occupation to another position in the list; position 1 shows first.

**Permissions:**
- `Manage Server`

---

### `list`

**Usage:** `/occupation list`

> Lists the occupations, how many characters hold each and how many can, and which ones you cannot pick.

---

### `assign`

**Usage:** `/occupation assign <member> <character> <occupation>`

> Gives a member's character an occupation, or takes it away when you leave `occupation` out. This applies at
once, without a review, and works for staff-only occupations and full ones too.

**Permissions:**
- `Manage Messages`

---

