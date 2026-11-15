---
layout: default
title: Check
parent: Commands
nav_order: 6
---

<h1>Check</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Checks players roll with a button: call one, oppose a character, or roll passively.


### `call`

**Usage:** `/check call <stat> <dc> <title> <kind> <visibility> <modifier> <npc_bonus> <npc_name> <role> <member> <hours>`

> Posts a check card in this channel. Each player presses **Roll** and picks a character; the bot rolls
> d20 + the stat's modifier (stat minus 5) + the modifier against the DC. The crit range widens with Luck and a
> natural 1 always fails. Each character rolls once. **Help** gives another member +2 on their roll, once per
> character. Whoever calls the check (or staff) can close it; it closes by itself after `hours`.
>
> - **Group** checks succeed when at least half of the rollers succeed.
> - **Opposed** checks are against an NPC: it rolls d20 + `npc_bonus` once, and players have to beat that total.
> - **Hidden DC** shows the rolls and outcomes but not the DC; **secret** shows only who rolled, while the caller
>   sees the results with the **Results** button.

---

### `oppose`

**Usage:** `/check oppose <member> <their_character> <character> <stat> <their_stat> <title> <hours>`

> Posts an opposed check: both players press **Roll**, each rolling d20 + their own stat's modifier. The higher
> total wins and a tie goes to the other member's character (the one defending). A critical success beats
> anything but another one; a fumble loses to anything but another fumble.

---

### `passive`

**Usage:** `/check passive <stat> <dc> <modifier> <title> <role> <member>`

> Rolls the check for every approved character that posted in this channel (or thread) in the last 7 days,
> without anyone pressing anything. Only you see the results; **Reveal to those who passed** lets you write what
> they notice, which the bot sends to those players in a DM. Passive rolls don't count toward bad-roll protection.

---

