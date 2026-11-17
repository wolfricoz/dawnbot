---
layout: default
title: School
parent: Commands
nav_order: 34
---

<h1>School</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Magic schools that spells belong to.


### `create`

**Usage:** `/school create <name> <casting_stat> <description>`

> Proposes a magic school. Spells of a school use its casting stat (Intelligence or Charisma) for their rolls.
> Staff review it before spells can use it. Every server also has the standard schools (see /school list).

---

### `edit`

**Usage:** `/school edit <name> <new_name> <casting_stat> <description>`

> Changes a magic school you proposed (staff can change any, including the standard ones). A member's change
> sends the school back to staff for review. Changing the casting stat changes it for every spell of the
> school too.

---

### `list`

**Usage:** `/school list`

> Lists the server's magic schools and their casting stats.

---

### `view`

**Usage:** `/school view <name>`

> Shows a magic school and the approved spells that belong to it.

---

