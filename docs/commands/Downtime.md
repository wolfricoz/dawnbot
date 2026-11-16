---
layout: default
title: Downtime
parent: Commands
nav_order: 14
---

<h1>Downtime</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Once a day: work, study, craft, carouse or repair gear.


### `spend`

**Usage:** `/downtime spend <character> <activity> <language> <project> <stat>`

> Spends the character's downtime for the day. The result is posted here (or only shown to you with
> DOWNTIME_PRIVATE on).
>
> - **Work** rolls the occupation's stat against 12 and pays by how it went: nothing on a bad failure, half on a
>   failure, all on a success, 1.5x on a strong success and double (plus a roll on the occupation's table) on a
>   crit. Without an occupation it is odd jobs at half pay.
> - **Study** rolls Intelligence against 12: +1 on a success, +2 on a strong one. STUDY_DAYS points teach the
>   language partly, twice that fluently.
> - **Craft** works a day on a crafting project (see /craft).
> - **Carouse** costs CAROUSE_COST and overhears a rumor at +2.

---

### `repair`

**Usage:** `/downtime repair <character> <item> <member> <owner>`

> Spends the character's downtime for the day repairing an item, its own or another character's. Its occupation
> has to repair that kind of gear (staff set it with /downtime occupation). It rolls the better of Agility and
> Intelligence against 10 (Worn), 13 (Damaged) or 16 (Broken); a success makes the item good as new. When the
> item has a salvage list, the repair uses one of those materials from the repairer (lost on a bad failure too).

---

### `occupation`

**Usage:** `/downtime occupation <occupation> <pay> <stat> <table> <seer> <repairs>`

> Sets an occupation's downtime work: its pay, the stat it rolls and a roll table for a crit. `seer` lets its
> characters read omens for others (/omen read). `repairs` lists the gear its characters can repair with
> /downtime repair, like `weapon, medium, heavy` for a blacksmith (armor goes by its class); `none` clears it.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `flavor`

**Usage:** `/downtime flavor <occupation> <outcome> <line>`

> Adds a flavor line shown when a character of this occupation has that result at work; one is picked at random.
> Without a line, that result's lines are cleared and the default line is used again.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

