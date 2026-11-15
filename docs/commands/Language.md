---
layout: default
title: Language
parent: Commands
nav_order: 22
---

<h1>Language</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Languages characters speak; others see them scrambled until they understand.


### `add`

**Usage:** `/language add <name> <sound> <syllables> <description>`

> Adds a language characters can learn. Its scrambled text is built from the sound's pieces (or your own).
>
> **Permissions:**
> - `Manage Messages`

---

### `edit`

**Usage:** `/language edit <language> <name> <sound> <syllables> <description>`

> Changes a language's name, sound or description. Posts already made scramble with the new sound.
>
> **Permissions:**
> - `Manage Messages`

---

### `remove`

**Usage:** `/language remove <language>`

> Removes a language; characters forget it and its old posts can no longer be understood. The common language
> can't be removed.
>
> **Permissions:**
> - `Manage Messages`

---

### `list`

**Usage:** `/language list`

> Lists the languages with a sample of how each looks scrambled.

---

### `known`

**Usage:** `/language known <character>`

> Shows what your character speaks, the language its posts use, and how many starting picks it has left.

---

### `pick`

**Usage:** `/language pick <character> <language>`

> Gives your character one of its starting languages (fluently). A character gets LANGUAGE_SLOTS picks, plus 1
> per 2 Intelligence above 5.

---

### `speak`

**Usage:** `/language speak <character> <language>`

> Makes your character's posts use a language unless they switch with `{...}` markers. Pick the common language
> to go back.

---

### `grant`

**Usage:** `/language grant <member> <character> <language> <fluency>`

> Teaches a character a language (fluently unless you say partly), outside its starting picks.
>
> **Permissions:**
> - `Manage Messages`

---

### `take`

**Usage:** `/language take <member> <character> <language>`

> Takes a language away from a character (species languages stay).
>
> **Permissions:**
> - `Manage Messages`

---

### `species`

**Usage:** `/language species <species> <language>`

> Every character of the species speaks the language fluently. Using it again takes the language away.
>
> **Permissions:**
> - `Manage Messages`

---

