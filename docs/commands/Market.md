---
layout: default
title: Market
parent: Commands
nav_order: 28
---

<h1>Market</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Sell items to other players' characters at a fixed price.


### `sell`

**Usage:** `/market sell <character> <item> <price>`

> Puts an item up for sale in the market forum at a fixed price. While it is listed it is out of your
> character's inventory and fights. When another player's character buys it, your character gets the price
> minus the market's fee (MARKET_FEE, 5% by default). Unsold items come back after MARKET_DAYS (14 by
> default); withdraw a listing sooner with its Withdraw button or /market withdraw.

---

### `browse`

**Usage:** `/market browse`

> Lists everything for sale on the market, cheapest first, with a link to each post. Buy with the Buy button
> on the post.

---

### `withdraw`

**Usage:** `/market withdraw <listing>`

> Takes one of your listings off the market; the item goes back to your character. Staff can withdraw any
> listing.

---

