---
layout: default
title: Shop
parent: Commands
nav_order: 33
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

> Shows an item's details: its rarity, price, SPECIAL requirements and effects, and for each of your approved
> characters what it would cost them (Charisma and faction standing change it) and whether they meet the
> requirements. Gear can be used without meeting them, but with a penalty.

---

### `buy`

**Usage:** `/shop buy <character> <item>`

> Buys an item for one of your approved characters, paid with that character's currency. Charisma changes the
> price: each point above 5 takes 3% off (at most 15%), each point below adds 3%. You can buy gear your
> character doesn't have the SPECIAL for; it still works, but with a penalty. Selling it back later returns
> about 30% of the catalog price.

---

### `repair`

**Usage:** `/shop repair <character> <item>`

> Has the shop's smith repair one of your character's items back to good condition, for 5% of its catalog
> price when Worn, 15% when Damaged and 40% when Broken (Charisma changes it like any purchase). Cursed gear
> needs a GM to lift the curse first. A character whose occupation repairs gear can do it with /downtime repair
> instead.

---

### `refill`

**Usage:** `/shop refill <character> <item>`

> Refills a ranged weapon's ammunition back to a full d12, for 20 for each step it ran down (only on servers
> that use ammunition).

---

