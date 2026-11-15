---
layout: default
title: Config
parent: Commands
nav_order: 10
---

<h1>Config</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Server settings: XP (roleplay) channels, level roles, characters, currency and the channels the bot posts in.


### `setup`

**Usage:** `/config setup <mode>`

> Sets up the roleplay features: the character review, bot log, characters, species, gear, level-up and
> timeline channels, the roleplay channels and the main character, species and gear settings.
>
> `guided` walks you through it one step at a time: for each channel you pick one, let the bot create it, or
> skip; then you choose the settings and can import a ready-made gear pack. Every answer is saved straight away.
>
> `auto` creates every channel that is not set yet, in a hidden **Roleplay Staff** category, a read-only
> **Roleplay Info** category and a **Roleplay** category. Channels that are already set, or that already exist
> under the default name, are kept. Settings keep their values.
>
> Both end with what is still missing (such as permissions) and what to do next.
>
> **Permissions:**
> - `Manage Server`

---

### `roles`

**Usage:** `/config roles <option> <role> <xp_required>`

> Adds, removes or updates a level role and the XP needed to reach it.
>
> **Permissions:**
> - `Manage Server`

---

### `announcement`

**Usage:** `/config announcement <channel>`

> Sets the channel where level-ups are announced.
>
> **Permissions:**
> - `Manage Server`

---

### `xp_gain`

**Usage:** `/config xp_gain <amount_of_characters>`

> Sets how many characters a message needs per point of XP.
>
> **Permissions:**
> - `Manage Server`

---

### `currency_gain`

**Usage:** `/config currency_gain <amount_of_characters>`

> Sets how many characters a post made as a character needs per unit of currency for that character.
>
> **Permissions:**
> - `Manage Server`

---

### `currency_name`

**Usage:** `/config currency_name <name>`

> Sets the name of the server's currency.
>
> **Permissions:**
> - `Manage Server`

---

### `channel`

**Usage:** `/config channel <option> <channel>`

> Adds or removes a text channel where messages earn XP (a roleplay channel). Posts made as a character there
> also earn the character currency.
>
> **Permissions:**
> - `Manage Server`

---

### `singlechannels`

**Usage:** `/config singlechannels <option> <channel>`

> Sets one of the channels the bot posts in. Approved characters and species are posted in the character channel
> and the species forum (a forum gives each its own thread); new and edited characters and species wait for staff
> in the character review channel. The GM roll log gets a copy of every secret roll. The chronicle gets finished
> scenes, the job board (a forum) jobs, the letter channel notices for members with DMs closed, and the rumor
> channel rumors.
>
> **Permissions:**
> - `Manage Server`

---

### `characters`

**Usage:** `/config characters <option> <value>`

> Sets one of the numbers for characters: the character cap, the SPECIAL rules (stat_base, stat_bonus,
> stat_min, stat_max), how fast characters level (level_base, points_per_level) or the starting currency.
> Existing characters keep the stats they have.
>
> **Permissions:**
> - `Manage Server`

---

### `stat_method`

**Usage:** `/config stat_method <method>`

> Sets how members set their SPECIAL stats when creating a character: both (the member chooses), point_buy
> or rolled.
>
> **Permissions:**
> - `Manage Server`

---

### `proxy_outside_rp`

**Usage:** `/config proxy_outside_rp <enabled>`

> Sets whether members can post as their characters outside the XP (roleplay) channels. Posts there earn no
> XP and have no minimum length. Off by default.
>
> **Permissions:**
> - `Manage Server`

---

### `species_creation`

**Usage:** `/config species_creation <who>`

> Sets who can create species with /species create: everyone, staff (Manage Messages) or off.
>
> **Permissions:**
> - `Manage Server`

---

### `economy`

**Usage:** `/config economy <mode>`

> Sets whether gear costs currency: economy (characters buy gear and sell it for 30% of what they paid) or
> free (all gear costs nothing and selling returns nothing).
>
> **Permissions:**
> - `Manage Server`

---

### `retire_thread`

**Usage:** `/config retire_thread <mode>`

> Sets what happens to a retired character's post: lock (the forum thread is locked and archived, and opened
> again if the character returns) or delete.
>
> **Permissions:**
> - `Manage Server`

---

### `reapproval`

**Usage:** `/config reapproval <mode>`

> Sets which edits to an approved character need a new staff review: none, lore (name, picture and sheet
> answers) or all (also prefix, suffix and the member's own extra fields). A respec is always reviewed.
>
> **Permissions:**
> - `Manage Server`

---

### `category`

**Usage:** `/config category <category>`

> Adds every text channel and forum in a category to the XP channels.
>
> **Permissions:**
> - `Manage Server`

---

### `forum`

**Usage:** `/config forum <option> <channel>`

> Adds or removes a forum whose posts earn XP (a roleplay forum). Posts made as a character there also earn
> the character currency.
>
> **Permissions:**
> - `Manage Server`

---

### `roleplay`

**Usage:** `/config roleplay <setting> <value>`

> Sets one of the roleplay tools' settings: in-world time and weather, travel, scenes, languages, letters, jobs,
> downtime, rumors and omens. Start typing to see them all with their current values; /config view lists them
> too.
>
> **Permissions:**
> - `Manage Server`

---

### `gmrole`

**Usage:** `/config gmrole <role>`

> Sets the role of the server's game masters. Members with it run the roleplay tools as staff do (roll tables,
> calendar and time, weather, locations, languages, letters in transit, factions, jobs, recipes, rumors), and
> the role is pinged when an encounter on the road needs a GM. It doesn't give /gm or fight GM powers.
>
> **Permissions:**
> - `Manage Server`

---

### `view`

**Usage:** `/config view`

> Shows the server's current settings.
>
> **Permissions:**
> - `Manage Server`

---

