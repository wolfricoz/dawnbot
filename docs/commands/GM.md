---
layout: default
title: GM
parent: Commands
nav_order: 14
---

<h1>GM</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Game master tools: giving and taking characters' gear, currency, abilities and legendary status. GMs are staff
(Manage Messages).


### `gear grant`

**Usage:** `/gm gear grant <member> <character> <item>`

> Gives a member's character an item from the catalog for free, including event and staff-only items that
> aren't sold in the shop. Requirements like server level or roles don't apply.
>
> **Permissions:**
> - `Manage Messages`

---

### `gear take`

**Usage:** `/gm gear take <member> <character> <item>`

> Removes an item from a member's character entirely, as if it never had it, for fixing mistakes. Nothing is
> refunded. To take gear away in the story, use /gm gear lose or /gm gear break instead.
>
> **Permissions:**
> - `Manage Messages`

---

### `gear lose`

**Usage:** `/gm gear lose <member> <character> <item>`

> Marks an item of a member's character as lost. It leaves the inventory but stays in its history.
>
> **Permissions:**
> - `Manage Messages`

---

### `gear break`

**Usage:** `/gm gear break <member> <character> <item>`

> Marks an item of a member's character as broken. It leaves the inventory but stays in its history.
>
> **Permissions:**
> - `Manage Messages`

---

### `gear proficiency`

**Usage:** `/gm gear proficiency <member> <character> <item> <tier>`

> Sets or changes how well a member's character handles one of its weapons. The limit of two Good or Excellent
> weapons still applies.
>
> **Permissions:**
> - `Manage Messages`

---

### `currency give`

**Usage:** `/gm currency give <member> <character> <amount> <note>`

> Gives a member's character currency, for example as an event reward. The optional `note` shows in the
> character's /currency history.
>
> **Permissions:**
> - `Manage Messages`

---

### `currency take`

**Usage:** `/gm currency take <member> <character> <amount> <note>`

> Takes currency from a member's character, for example as a fine. A character can't go below 0. The optional
> `note` shows in the character's /currency history.
>
> **Permissions:**
> - `Manage Messages`

---

### `resurrect`

**Usage:** `/gm resurrect <member> <character>`

> Brings back a character that died in a lethal fight. It is approved again straight away, can post again, and
> its forum post is reopened. It needs a free place under the character cap.
>
> **Permissions:**
> - `Manage Messages`

---

### `ability grant`

**Usage:** `/gm ability grant <member> <character> <ability>`

> Grants a member's character an ability as an event reward. Event abilities skip the slot limits and the rule
> against mixing spells and abilities, and work even if the ability hasn't been approved.
>
> **Permissions:**
> - `Manage Messages`

---

### `ability take`

**Usage:** `/gm ability take <member> <character> <ability>`

> Takes an ability away from a member's character, event or not.
>
> **Permissions:**
> - `Manage Messages`

---

### `legendary grant`

**Usage:** `/gm legendary grant <member> <character>`

> Makes a member's character legendary. Legendary characters have doubled stat limits (20, or 26 with a species
> that allows 13), get extra points to spend (`LEGENDARY_POINTS`, 5 by default) and one extra ability slot.
>
> **Permissions:**
> - `Manage Messages`

---

### `legendary take`

**Usage:** `/gm legendary take <member> <character>`

> Takes legendary status away from a member's character. Stats above the normal limits are lowered and those
> points returned, then the extra legendary points are taken back: from unspent points first, then from the
> highest stats. You'll see exactly what changes before you confirm.
>
> **Permissions:**
> - `Manage Messages`

---

