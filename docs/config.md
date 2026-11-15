---
layout: default
title: Configuration

nav_order: 2
---

<h1>Configuration</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>





<h2>Channel lists</h2>

### XP_CHANNELS
Text channels and forums where roleplay happens: messages earn XP there, and posts made as a character also earn that character currency. Threads count when their parent channel is listed. Messages shorter than 300 characters are removed there.
<h2>Channels</h2>

### ANNOUNCEMENT
The channel where level-up announcements are posted.

### TIMELINE
The channel where /endscene posts scene summaries.

### CHARACTER
The channel or forum where approved characters are posted.

### CHARACTER_REVIEW
The staff channel where new and edited characters wait for approval. Characters cannot be created until it is set.

### SPECIES_FORUM
The forum (or channel) where approved species are posted. Tags on a species' post can restrict who may pick it; see /tagrule.

### GEAR_FORUM
Optional: the forum where the gear catalog is posted, one post per item. Tags on an item's post can restrict who may buy it; see /tagrule.

### ABILITY_FORUM
Optional: the forum where approved abilities are posted. Tags on an ability's post can restrict who may learn it; see /tagrule.

### GM_ROLL_LOG
Optional: a channel where every secret roll is copied (secret and passive checks, secret /dice rolls and secret table rolls), so the server can audit them.

### MODLOG
The staff channel for bot notices, such as missing permissions.
<h2>Settings</h2>

### XP_GAIN
How many characters a message needs per point of XP (default 5).

### CURRENCY_GAIN
How many characters a post made as a character needs per unit of currency for that character (default 30).

### CURRENCY_NAME
The name shown for the server's currency (default 'currency').

### CHARACTER_CAP
How many characters a member can have (default 3). Retired characters do not count.

### REAPPROVAL_ON_EDIT
Which edits to an approved character need a new review: `none`, `lore` (name, avatar and sheet answers; the default) or `all` (also prefix, suffix and the member's own extra fields). Spending earned points never needs a review; a respec always does.

### STAT_METHOD
How members set their SPECIAL stats: `both` (the member chooses; the default), `point_buy` or `rolled`.

### STAT_BASE
The value every SPECIAL stat starts at with point-buy (default 5).

### STAT_BONUS
The extra points a new character can spend on top of the starting values (default 5).

### STAT_MIN
The lowest value a SPECIAL stat can have (default 1).

### STAT_MAX
The highest value a SPECIAL stat can have (default 10).

### LEVEL_BASE
How fast characters level: reaching level L takes this number x L(L-1)/2 XP (default 1000, so level 2 at 1000 XP and level 3 at 3000).

### POINTS_PER_LEVEL
How many SPECIAL points a character gets for each level (default 1).

### STARTING_CURRENCY
How much currency a new character starts with (default 3000).

### SPECIES_CREATION
Who can create species with /species create: `everyone` (the default), `staff` (Manage Messages) or `off`.

### ECONOMY
`economy` (the default): characters buy gear with their currency and sell it for 30% of what they paid. `free`: all gear costs nothing and selling returns nothing.

### RETIRE_THREAD
What happens to a retired character's post in the character channel: `lock` (the default; the forum thread is locked and archived, and opened again if the character returns) or `delete`.

### LEGENDARY_POINTS
How many extra SPECIAL points a character gets when staff make it legendary (default 5). Legendary characters also have doubled stat limits and one extra ability slot.

### COMBAT_PACING
How fights run: `async` (the default; each side gets a phase with a long timer), `live` (each combatant gets a short turn in Sequence order) or `choose` (whoever starts the fight picks).

### COMBAT_ASYNC_TIMER
Hours each side gets per phase in async fights (default 12). When it runs out, those who did not act get an automatic move.

### COMBAT_LIVE_TIMER
Minutes each combatant gets per turn in live fights (default 3).

### COMBAT_LETHAL
Whether fights can kill characters: `off`, `gm` (the default; staff can start a fight as lethal) or `agreed` (lethal fights need every player to accept when they join).

### ABILITY_CREATION
Who can create abilities, spells and magic schools: `everyone` (the default), `staff` (Manage Messages) or `off`.
<h2>Toggles</h2>

### PROXY_OUTSIDE_RP
Whether members can post as their characters outside the XP channels (default off). Posts there earn no XP and have no minimum length.

### COMBAT_PVP
Whether members can challenge each other with /combat challenge (default on).

### COMBAT_LEVEL_BONUS
Whether characters get +1 to hit at levels 4, 8, 12 and 16 (default off).