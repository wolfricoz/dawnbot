---
layout: default
title: Homepage
nav_order: 1
---
# Dawnbot

Dawnbot runs the roleplay side of a community: members earn XP and currency by writing in the roleplay channels,
level roles are handed out automatically, and characters, armor and weapons power dice-based combat.

---

## Features

### Progression
* **XP and currency:** messages in the configured XP channels and forums earn XP and currency based on their length.
* **Level roles:** members automatically receive the level role their XP has reached; level-ups are announced.
* **Quality control:** posts shorter than 300 characters are removed from XP channels, and the author gets a DM explaining why.

### Combat
* **Characters:** divide stat points over strength, perception, endurance, charisma, intelligence and agility.
* **Armor and weapons:** staff define armor sets and weapon types with their own dice and modifiers.
* **Attack rolls:** `/combat attack` rolls to hit and for damage, including advantage and critical hits.

### Roleplay tools
* `/dice`, `/coinflip`, and `/endscene` to log finished scenes in the timeline channel.

---

## Getting Started

1. **Permissions:** the bot needs View Channel, Read Message History, Send Messages, Embed Links, Manage Messages and
   Manage Roles. Its role must sit above the level roles it hands out.
2. **Setup:** use `/config channel` or `/config forum` to choose the XP channels, `/config roles` to add level roles and
   `/config announcement` for level-up messages. `/config view` shows the current settings.

See [Configuration](config.html) for every setting.
