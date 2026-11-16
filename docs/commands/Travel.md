---
layout: default
title: Travel
parent: Commands
nav_order: 40
---

<h1>Travel</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Travel between locations, with encounters on dangerous roads.


### `travel`

**Usage:** `/travel <character> <destination>`

> Sends a character from this channel's location (or where it last posted) to another. A departure line is
> posted here and an arrival line there: right away with manual time, or after the route's travel time when
> in-world time flows. On a dangerous route (or to a dangerous place) the character rolls d20 + Luck modifier
> against 8 + 2 x danger; a failure rolls the route's (or destination's) encounter table at the destination.
> Characters can still post anywhere while on the road.

---

