---
layout: default
title: Sheet
parent: Commands
nav_order: 36
---

<h1>Sheet</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

The server's character sheet: the questions members answer when they create a character.


### `add`

**Usage:** `/sheet add <label> <type> <section> <required> <help> <choices> <max_length> <min_value> <max_value> <position>`

> Adds a question to the character sheet. Types: short (a line of text), long (paragraphs), number, choice
> (members pick one of the options you give in `choices`, separated by commas) and info (asks nothing; its
> `help` text is shown as a note before the next question). `section` is the heading the question is grouped
> under, `help` a hint shown with the question. Existing characters are asked a new required question the next
> time they are edited.
>
> **Permissions:**
> - `Manage Server`

---

### `edit`

**Usage:** `/sheet edit <label> <new_label> <section> <required> <help> <choices> <max_length> <min_value> <max_value>`

> Changes a question on the character sheet; options you leave out keep their value. The type cannot be
> changed: remove the question and add a new one instead. Answers characters already gave are kept.
>
> **Permissions:**
> - `Manage Server`

---

### `remove`

**Usage:** `/sheet remove <label>`

> Removes a question from the character sheet. Answers characters already gave stay on their sheets, as
> fields of their own.
>
> **Permissions:**
> - `Manage Server`

---

### `move`

**Usage:** `/sheet move <label> <position>`

> Moves a question to another position on the sheet; position 1 is asked first.
>
> **Permissions:**
> - `Manage Server`

---

### `view`

**Usage:** `/sheet view`

> Shows the server's character sheet: every question in the order it is asked, with its type and limits.

---

### `template`

**Usage:** `/sheet template`

> Gives you the server's character sheet as blank text to copy. Fill it in wherever you like, then paste it into
> the DM from `/character create` (or `/character edit`) in one message: the bot fills in what it can and only
> asks what is missing. Questions marked with * are required.

---

### `reset`

**Usage:** `/sheet reset`

> Replaces the whole character sheet with the default one. Answers characters already gave stay on their
> sheets, as fields of their own.
>
> **Permissions:**
> - `Manage Server`

---

