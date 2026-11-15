---
layout: default
title: Calendar
parent: Commands
nav_order: 5
---

<h1>Calendar</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

The in-world calendar: set it up, add holidays and set birthdays.


### `setup`

**Usage:** `/calendar setup <preset> <year> <month> <day> <era> <moon_cycle>`

> Sets up the calendar the server's in-world dates use, starting at the date given (at morning). A custom
> calendar opens a form for the months (`Name: days: season`, one per line; the season can be left out) and the
> weekday names. Setting it up again replaces the calendar and its date; events stay.
>
> **Permissions:**
> - `Manage Server`

---

### `view`

**Usage:** `/calendar view`

> Shows the calendar's months with their days and seasons, the weekdays and today's in-world date.

---

### `event add`

**Usage:** `/calendar event add <name> <month> <day> <year> <description>`

> Adds an event, announced in the announcement channel when the in-world date reaches it.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `event remove`

**Usage:** `/calendar event remove <name>`

> Removes an event.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `event list`

**Usage:** `/calendar event list`

> Lists the holidays and events on the calendar.

---

### `birthday`

**Usage:** `/calendar birthday <character> <month> <day>`

> Sets the in-world day your character was born; it is announced every year when that day comes.

---

