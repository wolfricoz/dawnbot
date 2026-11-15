---
layout: default
title: Scene
parent: Commands
nav_order: 29
---

<h1>Scene</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Scenes with a post order, reminders and a chronicle when they end.


### `start`

**Usage:** `/scene start <title> <mode>`

> Posts and pins the scene card here. You host the scene; players press **Join** to take part with one of their
> characters. The card shows the location and its weather, the in-world date, the participants and whose turn it
> is.

---

### `end`

**Usage:** `/scene end <summary> <date>`

> Ends the scene: the card freezes, the chronicle is written in the chronicle channel (when set) and the timeline
> gets an entry (when set). Only the host or staff can end it.

---

### `join`

**Usage:** `/scene join`

> Joins the scene in this channel; the same as the card's **Join** button.

---

### `leave`

**Usage:** `/scene leave`

> Leaves the scene in this channel; the same as the card's **Leave** button.

---

### `pass`

**Usage:** `/scene pass`

> Passes your turn to the next participant. The host or staff can pass anyone's turn.

---

### `away`

**Usage:** `/scene away <days>`

> Marks you as away in every scene: no reminders, and your turns are passed over without counting as skips,
> until the date or until you use /scene back.

---

### `back`

**Usage:** `/scene back`

> Ends your away time; reminders and turns work for you again.

---

### `add`

**Usage:** `/scene add <member> <character>`

> Adds another member's approved character to the scene. Host or staff.

---

### `remove`

**Usage:** `/scene remove <member>`

> Removes a member's character from the scene. Host or staff.

---

### `move`

**Usage:** `/scene move <member> <position>`

> Moves a participant to another place in the post order. Host or staff.

---

### `host`

**Usage:** `/scene host <member>`

> Makes another member the scene's host. Host or staff.

---

### `pause`

**Usage:** `/scene pause`

> Pauses the scene. Host or staff.

---

### `resume`

**Usage:** `/scene resume`

> Resumes a paused scene; the current turn starts over. Host or staff.

---

### `card`

**Usage:** `/scene card`

> Posts the scene's card again (and pins it), for when it scrolled far up.

---

