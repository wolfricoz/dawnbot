---
layout: default
title: Time
parent: Commands
nav_order: 41
---

<h1>Time</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

In-world time: see the date and time, and move it forward or back.


### `now`

**Usage:** `/time now`

> Shows the in-world date and time of day, the season, the moon, and the weather where this channel is.

---

### `advance`

**Usage:** `/time advance <amount> <unit>`

> Moves in-world time. Events and birthdays on the days passed (up to a week of them) are announced in the
> announcement channel.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `set`

**Usage:** `/time set <year> <month> <day> <part>`

> Jumps to a date without announcing the events in between.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

