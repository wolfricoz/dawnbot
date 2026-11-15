---
layout: default
title: Letter
parent: Commands
nav_order: 23
---

<h1>Letter</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

In-character letters between characters, delivered after a while.


### `write`

**Usage:** `/letter write <sender> <recipient> <language> <express> <sealed>`

> Opens a form for the letter's subject and text. It arrives in the recipient player's DMs (or, with DMs closed,
> with a ping in the letter channel), with Reply and Report buttons, and stays in /letter inbox.

---

### `inbox`

**Usage:** `/letter inbox <character>`

> Lists the latest letters your character received; read one with /letter read.

---

### `read`

**Usage:** `/letter read <letter>`

> Shows a letter your character received (or sent), as your character understands its language.

---

### `transit`

**Usage:** `/letter transit`

> Lists letters in transit: who wrote to whom and when they arrive. Subjects show only when interception is on;
> the text never shows here.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `intercept`

**Usage:** `/letter intercept <letter> <action>`

> An in-game intercept, only when LETTER_INTERCEPT is on. Reading a sealed letter breaks its seal, which the
> recipient sees.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

