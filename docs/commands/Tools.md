---
layout: default
title: Tools
parent: Commands
nav_order: 39
---

<h1>Tools</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Roleplay tools: dice, coin flips, scene endings and translation.


### `endscene`

**Usage:** `/endscene <rpenddate> <title>`

> Ends the scene in this channel and posts a summary entry in the timeline channel. When a scene from /scene start
> is open here, this ends it like /scene end (host or staff), writing its chronicle too. The in-world date
> defaults to the server's calendar.

---

### `dice`

**Usage:** `/dice <dicetype> <modifier> <title> <amount> <character> <stat> <dc> <secret>`

> Rolls one or more dice and posts the result with a line of story text that depends on how the roll went.
>
> Pick one of your approved characters to roll as them, and a SPECIAL stat to add its modifier: the stat minus the
> server's starting stat value (5 by default), so 5 adds nothing, 10 adds +5 and 1 adds -4. The modifier option
> comes on top. Modifiers are added once to the total, and dice of 100 sides or more triple them. Rolling every die
> on its highest side is a critical success; every die on 1 is a critical failure.
>
> Rolling as a character counts toward its bad luck: after 3 rolls in a row that come out Poor or worse (or fail
> in a fight), its next bad roll is made again once and the better result counts.
>
> With a `dc`, the card also says whether the total reached it (a critical success always does, a critical failure
> never), and a roll as a character counts as bad when it falls short. A `secret` roll only shows you the result,
> with a **Show** button to post it later, and is copied to the GM roll log when the server has one.

---

### `coinflip`

**Usage:** `/coinflip`

> Flips a coin.

---

### `purge`

**Usage:** `/purge <role>`

> Kicks every member who has the given (inactivity) role, after DMing them a one-time invite back.
>
> **Permissions:**
> - `Manage Server`

---

### `translate`

**Usage:** `/translate <text> <from_language> <target_language>`

> Translates text between languages using the MyMemory translation service.

---

