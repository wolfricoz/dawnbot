---
layout: default
title: Ability
parent: Commands
nav_order: 1
---

<h1>Ability</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Build spells and abilities from the effect catalog, and teach them to your characters.


### `create`

**Usage:** `/ability create <name> <kind> <tier> <effect1> <effect2> <effect3> <effect4> <effect5> <damage_type> <stat> <school>`

> Builds a spell or ability from effects in the catalog (browse them with /ability effects). The bot resolves
> every effect itself in fights, so there are no free-text powers.
>
> - `kind`: a spell takes magic effects and needs a magic `school` (which sets its stat); an ability takes
>   physical effects and uses the `stat` you pick.
> - `tier`: Cantrip (1d8, unlimited, up to 2 effects), Weak (2d6, 3 uses, 3 effects), Normal (3d6, 2 uses, 4
>   effects) or Strong (4d8, 1 use, 5 effects). Some effects need a higher tier.
> - `effect1` to `effect5`: what it does. Its AP cost is the tier's base (1, 1, 2, 3) plus every effect's cost;
>   modifiers (area, empowered...) add to it, drawbacks (blood price, reckless...) take 1 off.
> - `damage_type`: for effects that take the ability's own type, like Bolt or Strike.
>
> A form then asks for the description and any flavor the GM handles. Staff review it in the review channel.

---

### `edit`

**Usage:** `/ability edit <name> <new_name> <kind> <tier> <effect1> <effect2> <effect3> <effect4> <effect5> <damage_type> <stat> <school>`

> Changes an ability you created (staff can change any), including the blank abilities made from old sheet
> answers. Options you leave out stay as they are. Giving any effect replaces the whole effect list with the
> ones you give. The kind can only change while the ability is still blank. A form lets you change the
> description and flavor. The ability goes back to staff for review, and can't be used in fights until it is
> approved again.

---

### `passive`

**Usage:** `/ability passive <name> <kind> <tier> <effect1> <effect2> <effect3> <target> <stack_limit> <school>`

> Builds a passive: always on, never used on a turn, built from passive effects (browse them with
> /ability effects passive:True). It lowers the character's AP every turn, for good, by the cost of its effects
> (one more each at Strong), and nobody can drop below 3 AP this way.
>
> - `kind`: an ability passive takes physical effects and 2 of a character's 3 ability slots; a spell passive
>   takes magic effects, one spell slot of its tier and a `school`.
> - `tier`: Weak (+1, one effect), Normal (+2, two effects) or Strong (+3, three effects).
> - `target`: for effects you aim, like Specialist or Resilient: a damage type, or melee, ranged, magic,
>   physical or any.
> - `stack_limit`: for stacks effects, how many stacks it can hold (1 to 30).

---

### `passive_edit`

**Usage:** `/ability passive_edit <name> <new_name> <tier> <effect1> <effect2> <effect3> <target> <stack_limit> <school>`

> Changes a passive you created (staff can change any), or turns a blank ability from an old sheet answer into a
> passive. Options you leave out stay as they are; giving any effect replaces the effect list. Type `none` as
> `target` to clear it, and set `stack_limit` to 0 to go back to the tier's. It goes back to staff for review
> and doesn't work in fights until it is approved again.

---

### `effects`

**Usage:** `/ability effects <realm> <category> <search> <passive>`

> Browses the effect catalog. Without a category or search it lists the categories and how many effects each
> has; pick one, or search for a word, to see the effects with their AP cost, the lowest tier that can use them
> and what they do. Spells take magic effects, abilities physical ones.

---

### `list`

**Usage:** `/ability list <mine>`

> Lists the approved abilities and spells anyone can learn (tags on their forum posts can restrict them).
> With `mine`, lists the ones you created, whatever their review state (blank ones need effects first).

---

### `view`

**Usage:** `/ability view <name>`

> Shows an ability: its rules (every effect and what it does), school, description and flavor.

---

### `learn`

**Usage:** `/ability learn <character> <ability>`

> Teaches your character an approved ability. Spellcasters know at most 6 spells (1 Cantrip, 2 Weak, 2 Normal,
> 1 Strong; a passive spell takes a slot of its tier); other characters have 3 ability slots, where an active
> ability takes 1 and a passive 2 (at most 1 Strong). A character can't have both spells and abilities, unless
> an event granted them. Legendary characters get one extra slot. An active ability can't cost more AP than the
> character has, and passives can't leave it with fewer than 3 AP. Weapon techniques (a Spear Thrust, a Crossbow
> Volley) only work in a fight while the character carries a weapon of that kind; you're told when it has none.

---

### `forget`

**Usage:** `/ability forget <character> <ability>`

> Removes an ability from your character, freeing its slot (and the AP a passive took). Event abilities can only
> be taken away by a GM.

---

### `import_sheets`

**Usage:** `/ability import_sheets`

> Abilities, spells and weapons can only come from the bot's own systems now. This removes the free-text
> Magics, Abilities, Weapon proficiencies, Shield and Magic school questions from the server's sheet, and goes
> through every character's old answers:
>
> - each spell or ability written there becomes a blank ability with that name, linked to the character. It
>   does nothing in fights until its owner builds it with `/ability edit` (or `/ability passive_edit`) and staff
>   approve it;
> - weapons written there can't be made automatically, so the owner is told to get them from the shop or a GM
>   and set their proficiency with `/gear proficiency`.
>
> Owners get a DM listing what was found. The old answers stay saved but no longer show on cards or posts.
> Running it again only handles answers it hasn't seen.

---

