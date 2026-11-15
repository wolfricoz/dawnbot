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

### `passive`

**Usage:** `/ability passive <name> <tier> <type> <field> <target> <trigger> <condition> <stack_limit>`

> Builds a passive ability: always on, never used on a turn. It takes 2 of a character's 3 ability slots (an
> active ability takes 1), and spellcasters can't learn passives unless an event grants one. The tier sets its
> size: Weak +1, Normal +2, Strong +3.
>
> - `bonus`: +to hit, damage, AC (within the cap of 18), DT, max HP (+5/10/15), AP (+1/1/2) or Sequence
>   (+2/4/6). To hit and damage can be limited with `target` (melee, ranged, magic or a damage type).
> - `resistance`: hits from `target` (a damage type, magic or physical) do 2/4/6 less damage, at least 1.
> - `immunity` (Normal): the `condition` never takes hold.
> - `trigger`: regenerate (1d4/1d6/1d8 each turn), last stand (Normal once, Strong twice per fight), on a strong
>   hit (adds `condition` for 1/2/3 turns) or counter (1d4/1d6/1d8 to a melee attacker that misses, once a round).
> - `aura`: standing allies get +1/+1/+2 to hit, damage or AC.
> - `stacks`: each hit it takes from `target` (any, magic, physical or a damage type) adds +1 to hit, damage or
>   AC for the rest of the fight, up to `stack_limit` stacks (1 to 30; without it 2/3/5 by tier).

---

### `passive_edit`

**Usage:** `/ability passive_edit <name> <new_name> <tier> <type> <field> <target> <trigger> <condition> <stack_limit>`

> Changes a passive ability you created (staff can change any). Options you leave out stay as they are; a form
> lets you change the description and flavor. It goes back to staff for review and doesn't work in fights
> until it is approved again. Type `none` as `target` to remove its limit, and set `stack_limit` to 0 to go back
> to the tier's stack limit.

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
> 1 Strong); other characters have 3 ability slots, where an active ability takes 1 and a passive 2 (at most 1
> Strong). A character can't have both spells and abilities, unless an event granted them. Legendary characters
> get one extra slot.

---

### `forget`

**Usage:** `/ability forget <character> <ability>`

> Removes an ability from your character, freeing its slot. Event abilities can only be taken away by a GM.

---

