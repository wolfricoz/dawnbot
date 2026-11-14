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

> Sets the character, timeline or modlog channel.

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

