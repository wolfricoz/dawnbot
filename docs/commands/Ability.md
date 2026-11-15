---
layout: default
title: Ability
parent: Commands
nav_order: 1
---

<h1>Ability</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Build spells and abilities, and teach them to your characters.


### `create`

**Usage:** `/ability create <name> <kind> <tier> <effect> <damage_type> <stat> <school> <condition> <secondary> <area>`

> Builds a spell or ability from parts, which the bot then resolves in fights:
>
> - `kind`: a spell needs a magic `school`, and uses the school's stat; an ability uses the `stat` you pick.
> - `tier`: Cantrip (1d6, unlimited), Weak (2d6, 3 uses), Normal (3d6, 2 uses) or Strong (4d8, 1 use) per fight.
> - `effect`: damage (an attack roll), heal, a `condition` on an enemy (they save against it), a shield, or a
>   boost (Inspired or Regenerating).
> - `damage_type`: its effect triggers on a strong hit (see /damagetype list). Healing uses Restoration.
> - `area`: up to 3 targets with half the dice. `secondary`: a damage ability also applies a condition on a
>   hit, for one dice step less.
>
> After the options, a form asks for the description and any flavor the GM handles. Staff review it in the
> review channel.

---

### `edit`

**Usage:** `/ability edit <name> <new_name> <tier> <effect> <damage_type> <stat> <school> <condition> <secondary> <area> <clear_condition> <clear_secondary>`

> Changes an ability you created (staff can change any). Options you leave out stay as they are; a form lets
> you change the description and flavor. The ability goes back to staff for review, and can't be used in
> fights until it is approved again.

---

### `list`

**Usage:** `/ability list <mine>`

> Lists the approved abilities and spells anyone can learn (tags on their forum posts can restrict them).
> With `mine`, lists the ones you created, whatever their review state.

---

### `view`

**Usage:** `/ability view <name>`

> Shows an ability: its rules, school, description and flavor.

---

### `learn`

**Usage:** `/ability learn <character> <ability>`

> Teaches your character an approved ability. Spellcasters know at most 6 spells (1 Cantrip, 2 Weak, 2 Normal,
> 1 Strong); other characters at most 3 abilities (1 Strong). A character can't have both spells and abilities,
> unless an event granted them. Legendary characters get one extra slot.

---

### `forget`

**Usage:** `/ability forget <character> <ability>`

> Removes an ability from your character, freeing its slot. Event abilities can only be taken away by a GM.

---

