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
Text channels and forums where messages earn XP and currency. Threads count when their parent channel is listed. Messages shorter than 300 characters are removed there.
<h2>Channels</h2>

### ANNOUNCEMENT
The channel where level-up announcements are posted.

### TIMELINE
The channel where /endscene posts scene summaries.

### CHARACTER
The channel or forum where approved characters are posted.

### CHARACTER_REVIEW
The staff channel where new and edited characters wait for approval. Characters cannot be created until it is set.

### MODLOG
The staff channel for bot notices, such as missing permissions.
<h2>Settings</h2>

### XP_GAIN
How many characters a message needs per point of XP (default 5).

### CURRENCY_GAIN
How many characters a message needs per unit of currency (default 30).

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
<h2>Toggles</h2>

### PROXY_OUTSIDE_RP
Whether members can post as their characters outside the XP channels (default off). Posts there earn no XP and have no minimum length.