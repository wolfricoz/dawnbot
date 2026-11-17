# Economy and equipment: design

Status: designed in the team proposal ("Dawnbot economy and equipment proposal" in Google Docs, 15 and 16 November
2026), with every open question answered by Rico. This file is the source of truth for what gets built, including the
choices made while building that the doc left open. Each phase adds its "as built" notes at the end.

## 1. Decisions

| Topic | Decision |
|---|---|
| Scope | Money balance and sinks; slots, carrying and repair; trading and merchants; magic items, loot and the other genre packs. |
| Pace | Saving is a hobby, not a job: an active player earns about 500 a day. Uncommon items take about 3 days to save for, Rare about a week, Very rare about a month. |
| Income | `CURRENCY_GAIN` 8 characters per unit (was 30; a 300-character post pays about 38), `WORK_PAY` 125 (was 50). Job rewards and bestiary loot are scaled to match. |
| Starting money | `STARTING_CURRENCY` 1,500 (was 3,000), plus the occupation's starter kit on top (phase 6). |
| Existing servers | Keep their current starting money, post pay and work pay: migration 0023 writes the old defaults (3,000, 30, 50) as explicit settings for every server that had none. Only servers added later get the new defaults. |
| Rarity | Common up to 1,000; Uncommon over 1,000 up to 1,500; Rare over 1,500 up to 3,500; Very rare over 3,500 (up to about 15,000); Legendary is never sold. An item without a set rarity takes it from its price; staff can set one. Legendary items show in the shop as unavailable and are only granted. |
| Charisma | The bartering stat. Buying costs 3% less per point of Charisma modifier (`stat − STAT_BASE`), at most 15% less, with no limit on the extra cost below 5. Selling returns 30% + 2% per point, between 20% and 40%. Faction prices multiply with it, but the total discount never passes 35%. |
| Selling | Based on the catalog price, not what was paid, so loot and granted gear sell too and there is no buy-low, sell-high loop. Masterwork sells for 50% more, cursed gear for nothing; an item removed from the catalog sells by what was paid. Free mode: selling returns nothing. |
| Price hints | `/armory add` and `/armory edit` suggest a price from the item's combat values; staff can ignore it. |
| Economy report | `/economy report` (staff): currency held by active characters, median, last week's income and spending by reason, top holders and earners. `/economy audit` shows one character's ledger. |
| Slots | Hands (main, off), readied, body, and worn slots (head, neck, back, hands, feet, two rings). Every owned weapon stays usable in fights for now; readied has no AP cost. |
| Carry weight | Off by default (`CARRY_WEIGHT`), kilograms when on: about 11 + 11 × Strength kg. |
| Ammunition | Off by default (`AMMO`: `off`, `die`, `counted`). |
| Condition | Good, Worn, Damaged, Broken. Rolled once per fight: every weapon used and the worn armor have a 1 in 20 chance to drop a step (1 in 40 masterwork). Worn does nothing; Damaged is −1 to hit or −1 DT; Broken does nothing at all. Broken items stay and can be repaired. |
| Repair | At a merchant with a repair service (5% / 15% / 40% of the catalog price), or by a character whose occupation staff marked as repairing that kind of gear (downtime, Agility or Intelligence against DC 10 / 13 / 16). Cursed items need a GM first. |
| Trading | `/trade` window with both sides accepting; `/currency pay`. Not between a player's own characters. Optional market forum with a 5% fee. |
| Merchants | NPC shops at locations with stock, restocks, markup, haggling and services. `SHOP_MODE` default `global`. |
| Magic items | Enchantments from the passive and effect catalogs; rarity sets the budget. 3 attuned at once (4 legendary). At most +2 from one item (masterwork + enchantment). Spell effects on items roll with the item's bonus: Uncommon +3, Rare +4, Very rare +5, Legendary set by staff. Players design enchanted items, staff review them like abilities, and they are crafted through an enchanting recipe. |
| Loot | Bestiary loot (currency dice, item drops). `LOOT_MODE` `gm` (default) or `claim`. |
| Spending | Healers remove injuries (350 / 1,000 / 3,500). Training raises proficiency with currency and downtime (1,500 / 5,000 / 14,000 + 10 days), from a trainer merchant or a fitting occupation; GMs keep `/gm gear proficiency`. Lodging and stash. Lifestyle built but off by default (weekly 0 / 70 / 250 / 700 / 1,750 / 5,000). Property later. |
| Packs | Post-apocalyptic, then modern, then sci-fi. Original names only. |

## 2. Build order

1. **Money:** new defaults (existing servers keep theirs), rarity, Charisma pricing, catalog-based selling, price hints, `/economy report` and `/economy audit`.
2. **Equipment:** slots, condition, wear and repair (with repairing occupations), optional ammunition, carry weight.
3. **Trading:** the trade window, `/currency pay` and the market.
4. **Merchants:** stock, restocks, haggling, services, stashes and the shop modes.
5. **Magic items and loot:** enchantments, attunement, enchanting recipes and player designs, identification, bestiary loot.
6. **Spending:** healers, training, starter kits, lifestyle.
7. **Packs:** post-apocalyptic, modern, sci-fi.

Migrations start at `0023`; the legacy combat drop is renumbered so it stays last.

## 3. Settings

| Key | Default | Values |
|---|---|---|
| `STARTING_CURRENCY` | 1500 (existing servers keep theirs) | 0 and up |
| `CURRENCY_GAIN` | 8 (existing servers keep theirs) | characters of a post per unit |
| `WORK_PAY` | 125 (existing servers keep theirs) | 0 to 100000 |
| `STARTER_KITS` | on | toggle |
| `SHOP_MODE` | global | global, merchants, both |
| `CARRY_WEIGHT` | off | off, kg, lb |
| `AMMO` | off | off, die, counted |
| `GEAR_WEAR` | on | toggle |
| `MARKET` | none | a forum channel |
| `MARKET_FEE` | 5 | percent, 0 to 50 |
| `MARKET_DAYS` | 14 | 1 to 90 |
| `TRADING` | on | toggle |
| `ATTUNEMENT_SLOTS` | 3 | 1 to 10 |
| `IDENTIFY` | off | toggle |
| `LOOT_MODE` | gm | gm, claim |
| `LIFESTYLE` | off | toggle |

## 4. Phase 1 as built

Migration `0023_economy_money` (the legacy drop is now `0029_drop_legacy_combat`).

| Topic | As built |
|---|---|
| Defaults | `STARTING_CURRENCY` 1500, `CURRENCY_GAIN` 8, `WORK_PAY` 125 in `ConfigMapping.defaults`. The migration writes 3000, 30 and 50 for every existing server that had no setting of its own (keys compared without case); a downgrade leaves those rows. |
| Rarity | `gear_items.rarity` (empty means "from the price"), `classes/gear/Rarity.py`. `/armory add` and `/armory edit` take a `rarity` option ("From the price" clears it); packs may give `"rarity"`. Lines and cards show it: `**Plate** (armor, Rare) · 2000 caps`. `Gear.lock_reason` refuses Legendary items ("is legendary and only given out by staff"); `/gm gear grant` still gives them. |
| Pricing | `classes/gear/Pricing.py`: `buy_price` (Charisma × faction, floor 65%, 0 in free mode), `sell_rate`, `sell_value`. `Gear.buy` charges `buy_price`, except starting gear (`source = creation`), which costs the catalog price it was picked against in the interview. `/shop view` lists what the item costs each of the member's approved characters. |
| Selling | `Gear.sell_value(entry)` (one argument now) reads the entry's character and catalog item. Cursed 0, masterwork ×1.5, a stack counts every unit, an item gone from the catalog uses `price_paid`. |
| Price hints | `Pricing.suggest(kind, combat, requirements)`, fitted to the fantasy pack (most of its weapons within ±40%, armor within about 30%). Weapons: `65 × 1.45^(highest requirement) × √(average damage ÷ 6) × (1 + 0.2 × hit_mod)`; armor: `100 + 50 × (AC + DT)² + 300 per hit modifier`; heal consumables `1.5 × average²`, boosts `60 × turns`, cures 35. The reply to `/armory add` and `/armory edit` gives a ±25% range and says when the price is below or above it. |
| Report | `/economy report [days]` and `/economy audit <member> <character>` (Manage Messages), `classes/economy/Report.py`, `modules/Economy.py`. The report counts approved characters only; the ledger totals split each reason into money in and money out. |

## 5. Phase 2 as built

Migration `0024_economy_equipment` (the legacy drop is now `0029_drop_legacy_combat`).

| Topic | As built |
|---|---|
| Data | `gear_items.weight` (kg) and `gear_items.slot` (an accessory's slot); `character_gear.slot`, `condition` (default `good`) and `ammo_die`; `occupations.repairs` (JSON list). Broken stops being a status: the migration turns broken items into owned items in Broken condition. Equipped armor gets the body slot, the first equipped shield the off hand and the first other equipped weapon the main hand; other equipped weapons are put away (they stay usable in fights). |
| Accessories | A fifth catalog kind, `accessory`, with no combat values (enchantments come in phase 5). `/armory add` needs `worn_slot` for one; packs need `"slot"`. |
| Slots | `classes/gear/Slots.py`, `Gear.equip(entry, slot=None)`. Weapons fill the main hand, then the off hand, then readied; a two-handed weapon holds both hands; a shield goes in the off hand and puts a two-hander away; rings take the free ring slot, else the first. Whatever was in the slot is put away; cursed armor and accessories don't come off. `/gear equip` has a `slot` option (hands, readied, rings). |
| Fights | Every owned weapon is still usable. The main-hand weapon is the one a fighter starts holding (`Loadout.default_weapon`); an equipped shield still gives +2 AC. Weapons carry their `slot`; worn armor carries its `entry_id` for wear. |
| Condition | `classes/gear/Condition.py`. `Condition.adjust` runs after masterwork/cursed: Damaged −1 `hit_mod` or −1 DT (never below 0); Broken weapons are left out of the fight and broken armor counts as no armor. `/gear break`, `/gm gear break` and the GM panel's "broken gear" set the condition instead of a status, and the item stays worn. |
| Wear | `CombatFlow.run` calls `Condition.after_fight` when an outcome ends the fight (every ending goes through it: actions, the GM's finish, timeouts). It wears the weapon each character was holding at the end (`weapon_key`) and its worn armor: 1 in 20, masterwork 1 in 40, posted in the thread. `GEAR_WEAR` (toggle, on). Undoing the last action doesn't undo wear. |
| Repairs | `/shop repair` (the global shop's smith, until merchants): 5% / 15% / 40% of the catalog price × the Charisma buy multiplier, ledger reason `repair`. `/downtime repair <character> <item> [member] [owner]` uses the day's downtime: the repairer's occupation must list the kind (`weapon`, `clothing`, `light`, `medium`, `heavy`, `accessory`; armor by its class), set with `/downtime occupation repairs:`. Better of Agility and Intelligence against 10 / 13 / 16; success or better restores Good. When the item has a salvage list, the repairer needs one of those materials: used on a success, a bad failure or a fumble. `/gm gear repair` restores for free. Cursed items need the curse lifted first. |
| Carry weight | `classes/gear/Carry.py`, `CARRY_WEIGHT` (`off`, `kg`, `lb`). Capacity `11 + 11 × Strength` kg (at least 11). Over capacity: −2 AP when joining a fight (`stats.overloaded`) and travel time ×1.5 (`TravelFlow`). `Gear.buy` refuses an item that would pass 150%; grants are never refused. `/gear inventory` shows the load in its footer. The fantasy pack items have weights; `/armory import fantasy refresh:true` fills them into catalogs imported before. |
| Ammunition | `AMMO` (`off`, `die`); counted shots are not built. A ranged weapon that isn't a focus or thrown uses ammunition (the sling too). The held weapon's die is rolled after each fight (d12 → d10 → d8 → d6 → d4 → empty on a 1 or 2); an empty weapon is left out of fights. `/shop refill` costs 20 per step back to d12 (ledger reason `refill`). |
| Settings | `GEAR_WEAR`, `CARRY_WEIGHT` and `AMMO` are set with `/config roleplay`, like the roleplay tools' settings (the `/config` group has no room for more commands). |

## 6. Phase 3 as built

Migration `0025_economy_trading` (the legacy drop is now `0029_drop_legacy_combat`).

| Topic | As built |
|---|---|
| Data | `trades` (both characters and players, `offers` JSON per side, `accepted`, `state`: open, done, cancelled, expired) and `market_listings` (the item, seller, price, fee, thread, `state`: open, sold, withdrawn, expired, buyer, `expires_at`). A listed item has `character_gear.status = listed`. |
| Transfers | `TradeTransactions.transfer` moves items and makes ledger payments in one database transaction, locking the rows; any problem (an item gone or equipped, a balance below 0) changes nothing. Items that change hands lose their slot and proficiency, and get `source` `traded` or `market`. `buy_listing` closes the listing in the same transaction. |
| Rules | `classes/economy/Trading.py`: never between one player's own characters; both approved; equipped items can't be offered; no currency in free mode; the receiver's carry limit (150%) is checked. `TRADING` (toggle, on) turns trades, payments and the market off. |
| Trade window | `/trade <character> <member> <theirs>` (`modules/Trade.py`, `classes/economy/TradeFlow.py`, `views/economy/TradeView.py`). Buttons: Offer items (a private multi-select of tradable items; the pick replaces the side's items), Offer currency (a modal), Clear my offer, Accept, Cancel. Any change clears both accepts; the swap runs when both accepted, after `Trading.check` passes again. The view isn't kept across restarts: it expires after 10 minutes without a press, and an open trade more than an hour old is expired when either character starts a new one. A character can be in one open trade at a time. Ledger reasons `trade_out` / `trade_in`, noted with the other character. |
| Payments | `/currency pay <character> <member> <theirs> <amount> [note]` after a confirmation; ledger reason `pay` on both sides; the payee's player gets a DM. |
| Market | `MARKET` (a forum, `/config singlechannels`), `MARKET_FEE` (5) and `MARKET_DAYS` (14) in `/config roleplay`. `/market sell` lists an item (it leaves the inventory) and posts it; `/market browse`; `/market withdraw` (seller or staff). Each post has Buy and Withdraw buttons that survive restarts (`MarketButton`, registered in `setup_hook`). Buying: the buyer picks a character (not the seller's player), pays the price (`market`), the seller gets the price (`market`) minus the fee (`market_fee`, rounded down) and a DM. Posts are renamed (🟢 open, ✅ sold, ⚪ withdrawn, ⌛ expired) and locked when they end. `tasks/MarketTask.py` ends expired listings every 10 minutes. No market in free mode. |
| Histories | `/currency history` and `/economy audit` show the note for trades, payments, market sales and fees, repairs and refills; the report labels them. |

## 7. Phase 4 as built

Migration `0026_economy_merchants` (the legacy drop is now `0029_drop_legacy_combat`).

| Topic | As built |
|---|---|
| Data | `merchants` (name, description, avatar, `location_ids`, faction, `markup`, `buys` kinds, `pays`, `services`, `lodging_price`, `haggle_dc`, `restock`, `last_restock`, `cycle`), `merchant_stock` (item, `quantity` (empty unlimited), `chance` %, own `price`, `in_stock`, `available`), `merchant_haggles` (per character, item and restock cycle: discount, or a refusal), `lodgings` (character, location, merchant, `paid_until`), and `character_gear.stash_location_id` (status `stashed`). |
| Rules | `classes/economy/Merchants.py`. A merchant without locations trades anywhere, otherwise only in channels of its locations. Price: (line price or catalog price) × markup × Charisma × faction (the merchant's faction, else the item's) × haggle discount, at least 65% of price × markup; free mode 0. Buying runs in one transaction (`MerchantTransactions.buy`: stock count, currency, ledger `buy` noted "item from merchant", materials stack, `source = merchant`) after lock, faction and carry checks. Selling: `Gear.sell_value` × `pays`, only kinds the merchant buys. Legendary items can't be stocked. |
| Restocks | `daily`, `weekly` (default) or `manual`. A restock sets every line to its quantity, rolls rotating lines against their chance, and starts a new cycle (haggles and refusals are per cycle). `tasks/MerchantTask.py` checks every 15 minutes; `/merchant restock` does it now. Stock added or changed with `/merchant stock` is in stock straight away. |
| Haggling | `/merchant haggle`: Charisma against `haggle_dc`, once per item per cycle: success 10% off that item, strong success or crit 20%, failure nothing, bad failure or fumble a refusal until the next restock. Posted publicly. |
| Services | `repair` (`/merchant repair`: the shop repair price × markup, ledger `repair`) and `lodging` (`/merchant lodge [weeks]`: `lodging_price` per week, added to time already paid, ledger `lodging`). Healing, training and enchanting come with phases 5 and 6. Merchants are shown as embeds with their name and avatar, not through webhooks; travelling merchants are moved by hand with `/merchant place`. |
| Stashes | `/stash put` (needs a paid room at this location; not equipped items), `/stash take` (only needs being at the location, even after the rent ran out), `/stash list`. Stashed items leave the inventory, don't weigh anything and stay out of fights. |
| Shop mode | `SHOP_MODE` in `/config roleplay`: `global` (default), `both` (`/shop` lists and sells only Common and Uncommon items), `merchants` (`/shop browse`, `/shop buy`, `/shop repair` and `/gear sell` point to the merchants). Starting gear in the interview always comes from the catalog. `/shop refill` works in every mode. |
| Commands | `/merchant browse | buy | sell | haggle | repair | lodge` for players; `/merchant add | edit | remove | place | stock | restock` for staff and the GM role. |

## 8. Phase 5 as built

Migration `0027_economy_magic` (the legacy drop is now `0029_drop_legacy_combat`).

| Topic | As built |
|---|---|
| Data | `gear_items.enchantments` (`activation`, `effects`, `charges`, `recharge`, `bonus`, `item_bonus`, `damage_type`), `unidentified_name`, `crafted_only`; `character_gear.attuned`, `charges_left`, `charges_day`, `extra_charges`, `identified`; `bestiary.loot`; `recipes.enchanting`; tables `enchant_designs` and `fight_loot`. |
| Enchantments | `classes/gear/Magic.py`. One enchantment per item: active (effect catalog) or passive (passive catalog), plus an optional +1 (`bonus`: +1 to hit for weapons, +1 DT for armor; with masterwork at most +2). Budgets by rarity as decided; effect tiers are each effect's minimum tier, and the catalogs top out at Normal, so Very rare means one effect of any tier or two up to Normal. Common items can't be enchanted. `/armory enchant` (Manage Server) sets or clears it; cards show it. |
| Fights | `Loadout.character_stats` adds a working item's active enchantment as an ability (id `item:<entry id>`, the item's tier by rarity, `fixed_bonus` = Uncommon 3 / Rare 4 / Very rare 5 / Legendary `item_bonus` or 6, `uses` = its charges) and passive entries with no AP cost. `Resolver.ability_mod` uses `fixed_bonus` instead of the stat everywhere abilities add a stat (attack, DC, damage, healing); a crippled stat doesn't give an item disadvantage. Daily charges used in a fight are counted when it ends (`Condition.after_fight`). |
| Attunement | An enchantment works only when the item is attuned and identified, and armor and accessories also worn. `ATTUNEMENT_SLOTS` (3, `/config roleplay`), legendary characters +1. `/gear attune` spends the day's downtime; `/gm gear attune` is free; `/gear unattune` (cursed items hold on). Attuning identifies. |
| Identification | `IDENTIFY` (toggle, off). Enchanted loot arrives unidentified (shown by `unidentified_name`, does nothing). Identify by attuning, `/gear identify` (downtime, Intelligence against 12 / 14 / 16 / 18 by rarity) or a merchant's `identify` service (10% of the catalog price, at least 10, × markup; ledger `service`). |
| Designs | `/enchant design` (follows `ABILITY_CREATION`): a weapon, armor or accessory from the catalog, Uncommon to Very rare, one or two effects. Posted to `CHARACTER_REVIEW` with Approve / Deny buttons that survive restarts (`EnchantButton`); the player gets a DM. Approval (`classes/economy/Enchanting.py`) adds a crafted-only catalog item (base values + enchantment, price = base + 1,250 / 2,500 / 9,000) and an enchanting recipe (the base item; DC 12 / 15 / 18; 0 / 2 / 5 days). `/enchant designs` lists them. |
| Crafting | An enchanting recipe needs a spellcaster (a character knowing a spell) or the recipe's occupation. A crit on an enchanted item adds a charge (weapons and armor are also masterwork); a bad failure curses enchanted accessories too. Crafted-only items are never bought (`Gear.lock_reason`). |
| Loot | `/bestiary loot <entry> [currency] [items] [clear]` (`3d10`, `Healing Draught 50%, Hedge Knife 10% x2`). After a fight the GM presses **Loot** on the GM panel: `classes/economy/Loot.py` rolls each defeated bestiary enemy's loot once per fight and posts it with **Claim** and **Settle (GM)** buttons (`LootButton`). Winning players claim items; on Settle, a single claimant gets the item, contested items go to the GM's pick (`LOOT_MODE` `gm`, default) or the highest d20 (`claim`, ties reroll); unclaimed items are left behind; currency splits evenly among the winners (ledger `loot`). `reward_currency` stays as the GM's suggested reward. |

## 9. Phase 6 as built

Migration `0028_economy_spending` (the legacy drop is now `0029_drop_legacy_combat`). Property stays for later.

| Topic | As built |
|---|---|
| Data | `occupations.kit` (catalog item ids) and `occupations.trains`; `characters.lifestyle` and `lifestyle_paid_until`; the `trainings` table (character, weapon entry, target tier, days done and needed, paid, trainer, state). |
| Healers | `classes/economy/Spending.py`. Injury lines may start with `[serious]` or `[grave]` (minor otherwise); the GM panel's injury form has a "How bad?" field. A merchant with the `healing` service: `/merchant heal` removes one injury for 350 / 1,000 / 3,500 × markup × Charisma (ledger `healing`); the Injuries field goes away with its last line. |
| Starter kits | `STARTER_KITS` (toggle, on). `/downtime occupation kit:` sets an occupation's kit (catalog names, `none` clears). A new character gets it when its interview is submitted, with the starting gear, as `source = kit`; kit items sell for nothing (`Pricing.sell_value`). |
| Training | One step per training: Awful → Poor 500 / 1 day, Poor → Average 1,500 / 2, Average → Good 5,000 / 5, Good → Excellent 14,000 / 10. Paid up front with `/merchant train` (service `training`; × markup × Charisma; ledger `training`) or in `/downtime train ... member: trainer:` to another player's character whose occupation `trains` (paid to that character in one transfer; never between one player's own characters). Every `/downtime train` spends the day; the last day sets the proficiency through `Proficiency.set_weapon(staff=True)`. One open training per weapon; the two-at-Good-or-Excellent limit is checked when it starts. |
| Lifestyle | `classes/economy/Lifestyle.py`, `LIFESTYLE` (toggle, off). Weekly costs as decided; no choice means Modest. `/lifestyle set` pays the first week; `/lifestyle view`. `tasks/LifestyleTask.py` charges every approved character whose week is due (hourly check), dropping to the best tier it can afford. Destitute −2 and Poor −1 to haggling; Comfortable and up restore Worn gear each week; Wealthy and Aristocratic +2 to haggling and to `/rumor listen`. Ledger `lifestyle`. |
