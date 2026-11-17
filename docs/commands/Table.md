---
layout: default
title: Table
parent: Commands
nav_order: 40
---

<h1>Table</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Roll tables for loot, encounters, names and plot hooks; staff make them, anyone rolls.


### `create`

**Usage:** `/table create <name> <luck> <visibility> <file> <deck>`

> Creates a table. Without a file, a form asks for the description and the entries (up to 4000 characters).
>
> Entries go one per line:
> - `01-05: A rusty key` gives an entry a range; the table rolls 1dN up to the highest number. Ranges must cover
>   every number without overlapping.
> - `3x A rusty key` gives it a weight; plain lines weigh 1. Ranges and weights can't be mixed.
> - `{2d6}` is rolled when the entry comes up; `[[Other table]]` rolls that table in its place (3 deep at most).
> - `| item: Arming Sword`, `| currency: 2d6`, `| xp: 50` and `| npc: 1d4 Grey Wolf` after the text add actions:
>   staff press **Grant** to give the rewards to a character, and **Start fight** opens a fight with the NPCs.
> - Lines starting with `#` are skipped.
>
> Luck-touched tables (`luck`) put the best results at the high end: rolling as a character moves the roll by
> twice their Luck modifier. A `deck` is drawn from with /omen draw instead (one card per entry, `Name: meaning`).
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `edit`

**Usage:** `/table edit <table> <name> <luck> <visibility> <file>`

> Opens the table's description and entries in a form to change them, and applies the options. A table whose
> entries don't fit the form (4000 characters) can be changed with a file: get it with /table export, change it
> and upload it here.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `remove`

**Usage:** `/table remove <table>`

> Deletes a table after asking. Tables that roll it with [[name]] show its name instead from then on.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `list`

**Usage:** `/table list`

> Lists the tables you can roll, with how many entries each has. Staff also see staff-only tables (🔒).

---

### `view`

**Usage:** `/table view <table>`

> Shows a table's description and entries, written the way /table create reads them.

---

### `roll`

**Usage:** `/table roll <table> <character> <secret>`

> Rolls on a table and posts the result. Rewards in the result get a **Grant** button (staff give them to a
> character) and NPCs a **Start fight** button, which opens a fight with them from the bestiary. A secret roll
> only shows you the result, and is copied to the GM roll log when the server has one.

---

### `import`

**Usage:** `/table import <pack>`

> Copies a ready-made pack of tables into this server. Tables whose names the server already has are skipped.
> The fantasy pack's loot and encounters use the fantasy gear pack's items and bestiary; import those with
> /armory import and /bestiary import.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `export`

**Usage:** `/table export <table>`

> Sends you the table's entries as a .txt file, written the way /table create reads them: a backup, a way to copy
> a table to another server, or a way to edit a long table with /table edit file:.

---

