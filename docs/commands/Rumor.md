---
layout: default
title: Rumor
parent: Commands
nav_order: 32
---

<h1>Rumor</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Rumors: post them anonymously, overhear them, and plant some as a GM.


### `post`

**Usage:** `/rumor post <text> <location> <character>`

> Spreads a rumor. Other players never see who started it; staff can, for moderation.

---

### `listen`

**Usage:** `/rumor listen <character>`

> Rolls d20 + the better of your character's Perception or Charisma modifier against 12, once a day. A success
> hears a rumor (secret ones and the ones from where the character is first), a strong success two and a hint
> about whether one is true; a bad failure hears a false one.

---

### `plant`

**Usage:** `/rumor plant <text> <truth> <secret> <location>`

> Plants a rumor. Characters who overhear it with a strong success get a hint about its truth.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `mark`

**Usage:** `/rumor mark <rumor> <truth>`

> Marks whether a rumor is true; players only learn it from hints.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `pin`

**Usage:** `/rumor pin <rumor> <pinned>`

> Pinned rumors never fade.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `block`

**Usage:** `/rumor block <member> <blocked>`

> Blocks (or unblocks) a member from /rumor post.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `list`

**Usage:** `/rumor list`

> Lists live rumors with their number, author, truth and how often they were overheard.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

