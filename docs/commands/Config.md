---
layout: default
title: Config
parent: Commands
nav_order: 5
---

<h1>Config</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Server settings: XP channels, level roles, currency and the channels the bot posts in.


### `roles`

**Usage:** `/config roles <option> <role> <xp_required>`

> Adds, removes or updates a level role and the XP needed to reach it.

**Permissions:**
- `Manage Server`

---

### `announcement`

**Usage:** `/config announcement <channel>`

> Sets the channel where level-ups are announced.

**Permissions:**
- `Manage Server`

---

### `xp_gain`

**Usage:** `/config xp_gain <amount_of_characters>`

> Sets how many characters a message needs per point of XP.

**Permissions:**
- `Manage Server`

---

### `currency_gain`

**Usage:** `/config currency_gain <amount_of_characters>`

> Sets how many characters a message needs per unit of currency.

**Permissions:**
- `Manage Server`

---

### `currency_name`

**Usage:** `/config currency_name <name>`

> Sets the name of the server's currency.

**Permissions:**
- `Manage Server`

---

### `channel`

**Usage:** `/config channel <option> <channel>`

> Adds or removes a text channel where messages earn XP and currency.

**Permissions:**
- `Manage Server`

---

### `singlechannels`

**Usage:** `/config singlechannels <option> <channel>`

> Sets the character, character review, timeline or modlog channel. Approved characters are posted in the
character channel (a forum gives each its own thread); new and edited characters wait for staff in the
character review channel.

**Permissions:**
- `Manage Server`

---

### `characters`

**Usage:** `/config characters <option> <value>`

> Sets one of the numbers for characters: the character cap, the SPECIAL rules (stat_base, stat_bonus,
stat_min, stat_max), how fast characters level (level_base, points_per_level) or the starting currency.
Existing characters keep the stats they have.

**Permissions:**
- `Manage Server`

---

### `stat_method`

**Usage:** `/config stat_method <method>`

> Sets how members set their SPECIAL stats when creating a character: both (the member chooses), point_buy
or rolled.

**Permissions:**
- `Manage Server`

---

### `proxy_outside_rp`

**Usage:** `/config proxy_outside_rp <enabled>`

> Sets whether members can post as their characters outside the XP (roleplay) channels. Posts there earn no
XP and have no minimum length. Off by default.

**Permissions:**
- `Manage Server`

---

### `reapproval`

**Usage:** `/config reapproval <mode>`

> Sets which edits to an approved character need a new staff review: none, lore (name, picture and sheet
answers) or all (also prefix, suffix and the member's own extra fields). A respec is always reviewed.

**Permissions:**
- `Manage Server`

---

### `category`

**Usage:** `/config category <category>`

> Adds every text channel and forum in a category to the XP channels.

**Permissions:**
- `Manage Server`

---

### `forum`

**Usage:** `/config forum <option> <channel>`

> Adds or removes a forum whose posts earn XP and currency.

**Permissions:**
- `Manage Server`

---

### `view`

**Usage:** `/config view`

> Shows the server's current settings.

**Permissions:**
- `Manage Server`

---

