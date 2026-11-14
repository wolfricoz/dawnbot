---
layout: default
title: Character
parent: Commands
nav_order: 4
---

<h1>Character</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Create and manage your characters. New characters and most changes are reviewed by staff.


### `create`

**Usage:** `/character create`

> Starts creating a character. The bot asks its questions in your DMs: a name, how you speak as the character,
a picture, the server's character sheet and your SPECIAL stats. There is no time limit. When you submit,
staff review the character before you can use it.

---

### `edit`

**Usage:** `/character edit <name>`

> Changes one of your characters: its name, prefix and suffix, picture or sheet answers. The bot shows the
current answers in your DMs and you pick what to change. Depending on the server's settings, changes to an
approved character wait for staff approval; until then the character stays as it was. A character that was
denied is sent back to staff when you submit.

---

### `respec`

**Usage:** `/character respec <name>`

> Divides all of a character's SPECIAL points again, including unspent ones. The bot asks for the new stats in
your DMs. Staff always review a respec before it applies.

---

### `spend`

**Usage:** `/character spend <name> <stat> <amount>`

> Spends points your character earned by levelling up. This needs no staff review.

---

### `delete`

**Usage:** `/character delete <name>`

> Deletes one of your characters, with its sheet, picture and post in the character channel. This cannot be
undone.

---

### `autoproxy`

**Usage:** `/character autoproxy <name>`

> Posts everything you type in this channel (or thread) as one of your approved characters, without a prefix
or suffix. Leave the name out to turn it off. A prefix or suffix still picks another character, and a message
starting with a backslash (\) is posted as yourself.

---

### `list`

**Usage:** `/character list`

> Lists your characters on this server with their review state, level and stats.

---

### `profile`

**Usage:** `/character profile <name>`

> Shows one of your characters: its sheet, SPECIAL stats, level and how you speak as it.

---

### `show`

**Usage:** `/character show <member> <name>`

> Shows another member's approved character. Staff (Manage Messages) can also see characters that are not
approved yet.

---

### `add_info`

**Usage:** `/character add_info <name> <key> <value>`

> Adds a field of your own to one of your characters, on top of the server's sheet. Your fields show after the
sheet, in their own order.

---

### `edit_info`

**Usage:** `/character edit_info <name> <key> <value>`

> Changes the value of a field you added yourself. Answers to the server's sheet are changed with
/character edit.

---

### `remove_info`

**Usage:** `/character remove_info <name> <key>`

> Removes a field you added yourself.

---

### `move_info`

**Usage:** `/character move_info <name> <key> <position>`

> Moves a field you added yourself to another position among your own fields; position 1 shows first.

---

