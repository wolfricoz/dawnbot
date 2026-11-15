---
layout: default
title: Species
parent: Commands
nav_order: 21
---

<h1>Species</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Species for characters. Members make their own; staff review them, and approved ones are posted in the species
forum, where tags on a post can restrict who may pick it (see /tagrule).


### `create`

**Usage:** `/species create`

> Starts creating a species. The bot asks in your DMs for its name, description, benefits and drawbacks, and how
> it changes the SPECIAL stats: its own highest and lowest values per stat, which have to balance out, and
> changes to the starting stats. Staff review it; once approved, anyone can pick it for their characters.

---

### `edit`

**Usage:** `/species edit <name>`

> Changes a species you made (staff can change any species). The bot shows the current answers in your DMs.
> Changes to an approved species are reviewed before they apply. Characters keep the stats they have.

---

### `list`

**Usage:** `/species list`

> Lists the server's approved species, marking the ones that are restricted for you. Your own species that are
> waiting for review or were denied are listed too.

---

### `view`

**Usage:** `/species view <name>`

> Shows a species: its description, benefits, drawbacks and how it changes the SPECIAL stats.

---

### `delete`

**Usage:** `/species delete <name>`

> Deletes a species and its post. A species that characters are cannot be deleted.
>
> **Permissions:**
> - `Manage Messages`

---

