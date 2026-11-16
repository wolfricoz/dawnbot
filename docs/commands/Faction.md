---
layout: default
title: Faction
parent: Commands
nav_order: 17
---

<h1>Faction</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Factions and the standing characters have with them.


### `add`

**Usage:** `/faction add <name> <description> <emoji> <colour> <hidden> <rivals>`

> Adds a faction. Rivals lose half of what a character gains with this one.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `edit`

**Usage:** `/faction edit <faction> <name> <description> <emoji> <colour> <hidden> <rivals>`

> Changes a faction. `rivals` replaces its rival list.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `remove`

**Usage:** `/faction remove <faction>`

> Removes a faction and everyone's standing with it.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `list`

**Usage:** `/faction list`

> Lists the factions (staff also see hidden ones).

---

### `standing`

**Usage:** `/faction standing <character>`

> Shows your character's standing with every faction it knows.

---

### `give`

**Usage:** `/faction give <member> <character> <faction> <amount> <reason>`

> Changes a character's standing. Gains grow with Charisma and cost the faction's rivals half; losses are taken
> as they are.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `item`

**Usage:** `/faction item <item> <faction> <tier>`

> Ties a catalog item to a faction: characters pay 20% less at Idolized, 10% less at Liked and 25% more at
> Disliked; Vilified characters can't buy it, and a tier can be required.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `occupation`

**Usage:** `/faction occupation <occupation> <faction> <tier>`

> A character needs at least this standing with the faction to take the occupation. New characters are Neutral
> everywhere, so a higher tier can only be reached by changing occupation later.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

