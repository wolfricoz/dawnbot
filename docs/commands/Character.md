---
layout: default
title: Character
parent: Commands
nav_order: 3
---

<h1>Character</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Create and manage your combat characters.


### `create`

**Usage:** `/character create <name> <armor> <strength> <perception> <endurance> <charisma> <intelligence> <agility> <extra_points> <prefix>`

> Creates a character. You can divide 12 points (plus any extra points) over the stats.

---

### `delete`

**Usage:** `/character delete <name>`

> Deletes one of your characters.

---

### `list`

**Usage:** `/character list`

> Lists your characters and their stats.

---

### `edit`

**Usage:** `/character edit <name> <armor> <strength> <perception> <endurance> <charisma> <intelligence> <agility> <extra_points> <prefix>`

> Edits one of your characters; options you leave out keep their value.

---

### `profile`

**Usage:** `/character profile <name>`

> Shows one of your characters.

---

### `show`

**Usage:** `/character show <member> <name>`

> Shows another member's character.

---

### `add_info`

**Usage:** `/character add_info <name> <key> <value>`

> Adds a field to one of your characters; fields show on /character profile in their own order.

---

### `edit_info`

**Usage:** `/character edit_info <name> <key> <value>`

> Changes the value of one of your character's fields.

---

### `remove_info`

**Usage:** `/character remove_info <name> <key>`

> Removes one of your character's fields.

---

### `move_info`

**Usage:** `/character move_info <name> <key> <position>`

> Moves one of your character's fields to another position; position 1 shows first.

---

