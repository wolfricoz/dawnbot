---
layout: default
title: TagRule
parent: Commands
nav_order: 39
---

<h1>TagRule</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Restrictions through forum tags. Link a tag in the species forum to a requirement, and every species whose
post has that tag follows it. Retag a post to change who may pick it.


### `add`

**Usage:** `/tagrule add <forum> <tag> <kind> <role> <level> <faction> <tier>`

> Links a forum tag to a requirement. Kinds: role (members need `role`), level (members need server `level`:
> the number of level roles they have reached), staff_only (only staff can give it out), event (hidden from
> members; only staff can give it out) and reputation (the character needs at least `tier` standing with
> `faction`; checked when a character buys the item or learns the ability, and against a new character's
> Neutral standing when a species is picked). A tag can have one rule of each kind.
>
> **Permissions:**
> - `Manage Server`

---

### `remove`

**Usage:** `/tagrule remove <forum> <tag> <kind>`

> Removes a tag's rule of one kind, or all its rules when you leave `kind` out.
>
> **Permissions:**
> - `Manage Server`

---

### `list`

**Usage:** `/tagrule list`

> Lists every tag rule on the server.

---

