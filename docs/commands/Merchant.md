---
layout: default
title: Merchant
parent: Commands
nav_order: 29
---

<h1>Merchant</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Trade with the merchants at your location.


### `browse`

**Usage:** `/merchant browse <merchant> <character>`

> Lists the merchants at this location, or what one of them sells: each item with its price (for `character`,
> after its Charisma, standing and haggling), what is left of it, the kinds of gear the merchant buys, and its
> services.

---

### `buy`

**Usage:** `/merchant buy <character> <merchant> <item>`

> Buys an item from a merchant at this location, paid with your character's currency. The price is the
> merchant's, changed by Charisma, faction standing and anything you haggled.

---

### `sell`

**Usage:** `/merchant sell <character> <merchant> <item>`

> Sells one of your character's items to a merchant at this location, if it buys that kind of gear. It pays
> your Charisma's share of the catalog price, times how generous the merchant is.

---

### `haggle`

**Usage:** `/merchant haggle <character> <merchant> <item>`

> Haggles over one item, once per item until the merchant restocks: Charisma against the merchant's DC. A
> success takes 10% off, a strong success 20%; a bad failure offends the merchant, who won't deal with your
> character until the next restock.

---

### `repair`

**Usage:** `/merchant repair <character> <merchant> <item>`

> Has a merchant with a repair service fix one of your character's items: 5%, 15% or 40% of its catalog price
> (Worn, Damaged, Broken) times the merchant's markup, changed by Charisma.

---

### `identify`

**Usage:** `/merchant identify <character> <merchant> <item>`

> Has a merchant with an identify service tell your character what an unidentified item is, for 10% of its
> catalog price (at least 10) times the merchant's markup.

---

### `heal`

**Usage:** `/merchant heal <character> <merchant> <injury>`

> Has a merchant with the healing service treat one of your character's injuries, taking it off its sheet:
> 350 for a minor injury, 1,000 for a serious one and 3,500 for a grave one, times the merchant's markup and
> changed by Charisma.

---

### `train`

**Usage:** `/merchant train <character> <merchant> <weapon>`

> Pays a merchant with the training service to raise your character's proficiency with a weapon one step:
> Awful to Poor 500, Poor to Average 1,500, Average to Good 5,000, Good to Excellent 14,000 (times the markup,
> changed by Charisma). Then spend the days with /downtime train: 1, 2, 5 or 10.

---

### `lodge`

**Usage:** `/merchant lodge <character> <merchant> <weeks>`

> Rents a room at this location for some weeks (added to time already paid). A room opens the stash here:
> /stash put and /stash take keep items safe, weightless and out of fights.

---

### `add`

**Usage:** `/merchant add <name> <description> <avatar_url> <markup> <buys> <pays> <services> <lodging_price> <haggle_dc> <restock> <here> <faction>`

> Adds a merchant. With `here` (the default) it trades at this channel's location; add more locations with
> /merchant place, or none to let it trade anywhere. Fill its stock with /merchant stock.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `edit`

**Usage:** `/merchant edit <merchant> <name> <description> <avatar_url> <markup> <buys> <pays> <services> <lodging_price> <haggle_dc> <restock> <faction>`

> Changes a merchant; options you leave out keep their value. Type `-` in description or avatar_url to clear
> it.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `remove`

**Usage:** `/merchant remove <merchant>`

> Removes a merchant and its stock. Rooms rented from it stay paid, and stashes stay where they are.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `place`

**Usage:** `/merchant place <merchant> <remove>`

> Lets a merchant trade at this channel's location too, or with `remove` stops it trading here. A merchant
> without any location trades everywhere. Move a travelling merchant by placing it somewhere new and removing it
> from where it was.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `stock`

**Usage:** `/merchant stock <merchant> <item> <quantity> <chance> <price> <remove>`

> Puts a catalog item in a merchant's stock, or changes it: how many a restock brings, the chance it is there
> at all (rotating stock) and its own price. It is in stock straight away. Legendary items are never sold.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

### `restock`

**Usage:** `/merchant restock <merchant>`

> Restocks a merchant now: every line comes back to its quantity, rotating items roll their chance, and
> haggles and grudges are forgotten.
>
> **Permissions:**
> - `Manage Messages`, or the GM role

---

