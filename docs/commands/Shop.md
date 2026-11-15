---
layout: default
title: Shop
parent: Commands
nav_order: 20
---

<h1>Shop</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

The server's gear shop. Browse the weapons and armor your characters can buy, look at an item, and buy it
with a character's currency. Some items need a server level or a role and show as unavailable until you have it;
event and staff items aren't sold and are only given out by staff.


### `browse`

**Usage:** `/shop browse <kind>`

> Lists the gear in the shop, optionally only weapons or only armor, with prices and SPECIAL requirements.
> Items you can't buy yet are marked with the reason. Use /shop view for an item's details and /shop buy to
> buy it.

---

### `view`

**Usage:** `/shop view <item>`

> Shows an item's details: its price, SPECIAL requirements and effects, and whether each of your approved
> characters meets the requirements. Gear can be used without meeting them, but with a penalty.

---

### `buy`

**Usage:** `/shop buy <character> <item>`

> Buys an item for one of your approved characters, paid with that character's currency. You can buy gear
> your character doesn't have the SPECIAL for; it still works, but with a penalty. Selling it back later
> returns 30% of the price.

---

