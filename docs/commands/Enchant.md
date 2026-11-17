---
layout: default
title: Enchant
parent: Commands
nav_order: 16
---

<h1>Enchant</h1>
<h6>version: 1.0: Restructure</h6>
<h6>Documentation automatically generated from docstrings.</h6>

Design magic items for staff to approve.


### `design`

**Usage:** `/enchant design <character> <base> <name> <rarity> <activation> <effect> <second_effect> <charges> <recharge> <bonus> <description>`

> Designs a magic item: a catalog weapon, armor or accessory with an enchantment built from catalog effects,
> within its rarity's budget (Uncommon: one effect up to Weak; Rare: one up to Normal or two up to Weak; Very
> rare: one up to Strong or two up to Normal). Staff review it in the review channel. Once approved it joins
> the catalog (it is never sold) with an enchanting recipe: spellcasters, or characters with the occupation
> staff set, make it with /craft make, using the base item.

---

### `designs`

**Usage:** `/enchant designs`

> Lists your magic item designs and whether they were approved. Staff see everyone's.

---

