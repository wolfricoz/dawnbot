---
layout: default
title: Location
parent: Commands
nav_order: 24
---

<h1>Location</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Places in the world, bound to channels, grouped in regions and joined by routes.


### `set`

**Usage:** `/location set <name> <region> <climate> <indoor> <danger> <encounters> <image>`

> Makes the channel (or thread) you use it in a location, or changes the one it is. A form asks for the
> description and hazards. Options you leave out keep their value.
>
> **Permissions:**
> - `Manage Messages`

---

### `view`

**Usage:** `/location view <channel>`

> Shows a location: its description, weather, region, danger, hazards and who is there.

---

### `who`

**Usage:** `/location who <channel>`

> Lists the characters whose last post was at this location, within the last PRESENCE_DAYS days.

---

### `list`

**Usage:** `/location list`

> Lists every location with its region and channel.

---

### `remove`

**Usage:** `/location remove`

> Removes the location of this channel, with its routes.
>
> **Permissions:**
> - `Manage Messages`

---

### `region add`

**Usage:** `/location region add <name> <climate> <description>`

> Adds a region. Its locations share its climate (unless they set their own) and its weather.
>
> **Permissions:**
> - `Manage Messages`

---

### `region edit`

**Usage:** `/location region edit <region> <name> <climate> <description>`

> Changes a region's name, climate or description.
>
> **Permissions:**
> - `Manage Messages`

---

### `region remove`

**Usage:** `/location region remove <region>`

> Removes a region; its locations keep existing without one.
>
> **Permissions:**
> - `Manage Messages`

---

### `region list`

**Usage:** `/location region list`

> Lists the regions with their climates.

---

### `route add`

**Usage:** `/location route add <start> <end> <hours> <danger> <encounters> <one_way>`

> Adds a route. /travel along it takes its time (when in-world time flows) and rolls for encounters by its
> danger.
>
> **Permissions:**
> - `Manage Messages`

---

### `route remove`

**Usage:** `/location route remove <start> <end>`

> Removes a route.
>
> **Permissions:**
> - `Manage Messages`

---

### `route list`

**Usage:** `/location route list`

> Lists every route with its travel time and danger.

---

