---
layout: default
title: Combat
parent: Commands
nav_order: 6
---

<h1>Combat</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Fights in their own thread, PvP challenges, and quick attack rolls.


### `start`

**Usage:** `/combat start <title> <pacing> <lethal>`

> Starts a fight. Used in a channel it opens a new thread; used in a thread, the fight runs there. You become
> the fight's GM: add NPCs, start it and run it from the **GM** button on the board. Players join with
> **Join** and act with **Act**.
>
> `pacing` only counts when the server lets the starter choose (`combat_pacing` set to `choose`); otherwise
> the server's pacing is used. `lethal` fights can kill characters; whether you can start one depends on the
> server's `combat_lethal` setting.

---

### `challenge`

**Usage:** `/combat challenge <member> <character> <lethal>`

> Challenges another member's characters to a fight with one of yours. They accept (and pick their character)
> or decline with the buttons on the board. Others can join a side when someone on it invites them with
> `/combat invite`. You are the fight's GM and start it from the board.
>
> You'll both see a warning when a legendary character is involved. `lethal` needs the server's
> `combat_lethal` setting to allow it.

---

### `invite`

**Usage:** `/combat invite <member>`

> Lets a member join your side in the PvP fight running in this thread. Run it in the fight's thread.

---

### `board`

**Usage:** `/combat board`

> Posts the board of the fight in this thread again, for when it scrolled far up or was deleted.

---

### `attack`

**Usage:** `/combat attack <character> <weapon> <target_ac> <target_dt> <aimed> <hit_modifier> <damage_modifier> <title>`

> Rolls an attack outside a fight: one of your character's weapons against an AC you choose, with its stats,
> proficiency, armor and gear rules. `aimed` is -4 to hit, adds a damage die and ignores DT. Inside a fight's
> thread, use the board instead.

---

