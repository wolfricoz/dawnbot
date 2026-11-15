# Combat: design

Status: built on branch `feature/combat` from the team proposal ("Dawnbot combat system proposal" in Google Docs,
15 November 2026). Migrations `0011_combat` (new tables and columns), `0012_bestiary_special` (bestiary entries built
from SPECIAL), `0013_passive_abilities` (active and passive abilities), `0014_bad_streak` (bad-roll protection),
`0015_ability_effects` (abilities built from catalog effects) and `0022_drop_legacy_combat` (drops the old global armor,
weapon, NPC and monster tables; import them first with `/armory import legacy` and `/bestiary import legacy`).

The Google Doc holds the reasoning and the open questions. This file is the source of truth for what was built,
including the choices made while building that the doc left open.

## 1. Decisions

| Topic | Decision |
|---|---|
| Fights | Each fight is an instance bound to one thread. `/combat start` in a channel opens a thread; run inside a thread it uses that thread. One active fight per thread. |
| Board | A pinned message in the thread shows the sides, HP, AP, AC, conditions, whose turn it is and the timer. Its buttons (Join, Act, Autopilot, GM) keep working after a restart. |
| Sides | Two by default (`Party` / `Enemies`, or the two challengers' names in PvP). The GM can add and rename sides. |
| GM | The person who started the fight, plus co-GMs they add, plus anyone with `manage_messages`. The GM can hand the role over. |
| PvE | Anyone can start a fight and becomes its GM. NPCs come from the server's bestiary or from a difficulty preset. |
| PvP | `/combat challenge`; the other player accepts or declines and picks a character. Joining a PvP side needs an invite from someone on that side (`/combat invite`). PvP can be turned off (`COMBAT_PVP`). A challenge warns both players when a legendary character is involved. |
| One fight per character | A character can be in only one fight that has not ended. |
| Pacing | `COMBAT_PACING`: `async` (default), `live`, or `choose` (the starter picks). Async uses side phases with a timer (`COMBAT_ASYNC_TIMER`, default 12 hours); live uses individual turns in Sequence order (`COMBAT_LIVE_TIMER`, default 3 minutes). |
| Actions | Action points (option B in the doc). A turn has `5 + AGI ÷ 2` AP (at least 2). AP left at the end of the turn becomes +1 AC each until the next turn. |
| Missed turns | When the timer runs out, characters that have not acted get an automatic move from their autopilot setting; NPCs act from their behavior. After 3 automatic moves in a row the GM is pinged. |
| Rolls | d20 + attack stat modifier + proficiency + weapon hit modifier + armor hit modifier + level bonus (optional, `COMBAT_LEVEL_BONUS`) + situational modifiers, against AC. Meeting the AC is a hit. |
| Stat modifier | `stat − STAT_BASE` (5 by default): each point is +1. Formulas such as HP use the stat itself. |
| Crits | Read from the natural die only. Crit range from Luck: one number wider for every 2 points of Luck above 5 (20 at Luck 6 or less, 19-20 at 7, 18-20 at 9, 16-20 at 13, 13-20 at a legendary 20, 10-20 at 26). Excellent proficiency and the `keen` property each widen it by one. A crit counts the dice at their maximum, adds one more roll of the dice and ignores DT. |
| Fumbles | Natural 1 always misses; Luck 1 to 2 fumbles on 1 to 2, Luck 0 or below on 1 to 3. A fumble leaves the attacker at −2 AC until their next turn. |
| Strong hit | The attack beats AC by 5 or more, the target fails a save by 5 or more, or a crit. Damage type effects only trigger on a strong hit (Restoration, for healing, always applies). |
| HP | `15 + STR + (2 × END)`, plus `2 + END modifier` (at least 1, none when END is 0 or below) per level after the first. At least 5. |
| AC | `10 + armor bonus + shield (+2) + AGI modifier`. Agility adds at most +2; a negative modifier counts in full. Armor, shield and stats together are capped at 18; temporary bonuses (unspent AP, Defend) can go above. |
| Sequence | `2 × PER`, ties by Agility. Slowed combatants and those with Perception 0 or below act last. |
| Proficiency | Stored on the character's own weapon record (`character_gear.proficiency`): Excellent +1 and a crit range one wider, Good +1, Average 0, Poor −1, Awful −2. No tier counts as Awful. At most two records at Good or Excellent. Players set a tier once; changing it afterwards is `/gm gear proficiency`. |
| Armor proficiency | `characters.armor_proficiency` (clothing, light, medium, heavy). Unset means it is read from a sheet answer labelled "Armor proficiency" (Unarmored, Light, Medium, Heavy) and otherwise gives no penalty. Armor heavier than the proficiency gives −2 to hit per step. |
| Unmet requirements | −1 to hit per missing point of a weapon's SPECIAL requirements, at most −5. |
| Shields | A catalog weapon with the `shield` property. While it is equipped: +2 AC and −2 to attack. |
| Crippled stats | A stat at 0 or below adds the effects in section 4. |
| Downed | At 0 HP a combatant is downed and cannot act until revived. A side with no one standing loses. Automatic moves and NPCs never target downed combatants. |
| Lethal | `COMBAT_LETHAL`: `off`, `gm` (default; staff can start a fight as lethal) or `agreed` (each player confirms when joining). In a lethal fight a downed combatant rolls `d20 + END modifier` against 10 (12 when END is 0 or below) at the start of each of its turns: 3 successes is stable, 3 failures is dying, and the GM confirms the death. A dead character gets the `dead` status (doc section 11): it stops proxying, frees its place under the cap and in its occupation, and its forum post is locked and archived. Staff bring it back with `/gm resurrect`. |
| After the fight | HP is not carried over. The GM gives the winning characters (not the ones that fled) XP, currency and catalog items, with XP and currency suggested from the defeated bestiary entries; PvP fights suggest nothing. From the GM panel ("Injuries / broken gear") the GM adds an injury to a character's sheet (an `Injuries` field, one line per injury with the fight's title) or marks one of its items broken. |
| Legendary | `characters.legendary`, set with `/gm legendary grant` and `/gm legendary take`: stat limits double (10 → 20, species 13 → 26), `LEGENDARY_POINTS` extra points (default 5) and one extra ability slot. Removing the status lowers stats above the normal limit, returns those points, then takes the legendary points back (from unspent points first, then from the highest stats). There is no cap on how many: servers keep only a few legendary characters for now (Rico, 2026-11-15), so staff judgement is the limit. |
| Only through the bot | Weapons, abilities and magic can only come from the bot's own systems: weapons, armor and shields from the gear catalog (shop, GM grants), abilities and spells from the effect catalog with `/ability`. Players can't write rules of their own. The default sheet no longer asks Magics, Abilities, Weapon proficiencies, Shield or Magic school; `/sheet add`, `/sheet edit` and `/character add_info` refuse those labels, a pasted sheet leaves them out (the interview says why and lists what was written), and old answers under them are hidden on cards and posts. The "Flavor the GM handles" box on abilities stays (Rico's call). |
| Old sheet answers | `/ability import_sheets` (Manage Server) removes the old questions from a server's sheet and turns each name written under Magics or Abilities into a **blank ability** (state `draft`, no effects, the line as its description) linked to the character. Its owner builds it with `/ability edit` or `/ability passive_edit`, which sends it to review; until then it does nothing in fights. Weapon lists can't become gear, so the owner's DM lists them and points to the shop and `/gear proficiency`. The answers are kept, renamed `<label> (old)`, so a second run skips them. Rico chose blank abilities or a warning over deleting them. |
| Abilities | Built from catalog effects (section 4): a kind, a tier, a stat (a spell's comes from its school) and 1 to 5 effects, plus a damage type for effects that take the ability's own. Every effect is **magic or physical**: spells only take magic effects, abilities only physical ones. Reviewed by staff in `CHARACTER_REVIEW`, posted to `ABILITY_FORUM` when set. Created with `/ability create` (effect options with autocomplete filtered by kind and tier, then a modal). Every ability is active (used on a turn) or passive (always on, `/ability passive`). |
| Ability AP | An active ability costs its tier's base AP (Cantrip 1, Weak 1, Normal 2, Strong 3) plus the cost of each effect: modifiers such as area add to it, drawbacks take 1 off. At least 1, at most 12. A character can't learn an active ability that costs more AP than it has. |
| Passive AP | A passive permanently lowers the character's AP each turn by the cost of its effects (one more per effect at Strong). It still takes 2 ability slots (Rico's call: slots **and** AP). A character can't learn a passive that would leave it under 3 AP; in a fight AP never drops below the usual minimum of 2. Event-granted passives cost AP too. |
| Magic schools | A standard set per server plus player-made schools reviewed by staff. A school sets the casting stat (Intelligence or Charisma). |
| Ability slots | Spellcasters: 6 spells (1 Cantrip, 2 Weak, 2 Normal, 1 Strong). Others: 3 ability slots, where an active ability takes 1 and a passive 2, with at most 1 Strong (active or passive). Spellcasters can take passive spells built from magic effects; each takes one spell slot of its tier (Rico's call). Not both spells and abilities, unless event-granted. Legendary characters get one extra slot of any tier. Event-granted abilities (`/gm ability grant`) do not count. |
| Damage types | One table per server (`damage_types`), filled with the defaults the first time it is used; staff edit it with `/damagetype`. Weapons name their type in `combat.type`; abilities pick one. Defaults added later (Acid, Necrotic, Sonic) reach every server automatically: at start-up for servers that already have a table, otherwise when it is first used. Each default is offered once (`DAMAGE_TYPE_DEFAULTS` config row), so a type staff delete stays deleted. |
| Bad-roll protection | `characters.bad_streak` counts a character's failed rolls in a row: fight rolls (attacks, ability attacks, saves, revive, flee, death rolls), `/combat attack`, and `/dice` rolls made as the character (Poor or Critical failure counts as failed). After 3, its next failed roll is made again once and the better result counts; any success resets the count. It carries across fights, undo puts it back, and the board shows when it is ready. NPCs don't have it. |
| Quick roll | `/combat attack` stays for rolls outside a fight: one of the character's weapons against an AC you type. In a fight thread it points to the board. |
| Use item | Consumables are a third catalog kind (doc open question 11). Use item costs 2 AP and uses the item up (`character_gear.status = used`; undo gives it back). Heal items revive a downed ally automatically, so a character crippled in Intelligence can still bring someone back. The fantasy pack has seven. |
| Bestiary | An entry has its own stat block from a difficulty preset, or SPECIAL (with a level) plus catalog weapons and armor, derived like a character with Average proficiency and no armor penalty. `/bestiary import` copies a pack's bestiary (the fantasy pack has six entries) or the old `npcs` and `monsters` tables (HP × 0.3 for the new scale, to hit from the old attack, dice from the old damage). |
| Weapon proficiency | Buying a weapon asks for its tier straight away; it can also be set later with `/gear proficiency`. |

## 2. Data model (migration 0011)

- `combat_instances` (rebuilt): `guild_id`, `channel_id`, `thread_id`, `board_message_id`, `gm_uid`, `co_gms` (JSON),
  `kind` (`pve`, `pvp`), `state` (`pending`, `setup`, `active`, `paused`, `ended`), `pacing`, `lethal`, `round`,
  `order` (JSON: side ids for async, combatant ids for live), `turn_index`, `deadline`, `paused_seconds`, `title`,
  `winner_side_id`, `late_join`, `invites` (JSON), `pending` (JSON: unsettled "Other" actions), `challenge` (JSON).
- `combat_sides`: `instance_id`, `name`, `position`.
- `combat_entities` (replaces `combat_instance_entities`): `instance_id`, `side_id`, `kind` (`character`, `npc`),
  `character_id`, `uid`, `bestiary_id`, `name`, `controller` (`player`, `gm`, `auto`), `behavior`, `stats` (JSON
  snapshot taken at join), `hp`, `hp_max`, `ap`, `ap_max`, `ac`, `dt`, `sequence`, `conditions` (JSON),
  `ability_uses` (JSON), `acted`, `idle_turns`, `state` (`active`, `downed`, `stable`, `dying`, `fled`, `dead`,
  `removed`), `death_successes`, `death_failures`, `last_attacker_id`, `weapon_key`, `position`, `lethal_ok`.
- `combat_log` (replaces `combat_instance_log`): `instance_id`, `round`, `actor_id`, `target_id`, `action`, `text`,
  `details` (JSON), `snapshot` (JSON, for undo).
- `bestiary`: `guild_id`, `name`, `description`, `avatar_url`, `preset`, `hp`, `ac`, `dt`, `to_hit`, `damage`,
  `damage_type`, `ap`, `sequence`, `behavior`, `ability_ids` (JSON), `reward_xp`, `reward_currency`, `creator_uid`;
  migration 0012 adds `special` (JSON), `level`, `weapon_ids` (JSON) and `armor_id`.
- `damage_types`: `guild_id`, `name`, `trigger` (`strong_hit`, `always`), `effect` (JSON), `description`, `pack`.
- `magic_schools`: `guild_id`, `name`, `description`, `casting_stat`, `creator_uid`, `state`, `standard`,
  `review_message_id`.
- `abilities`: `guild_id`, `creator_uid`, `name`, `description`, `flavor`, `kind` (`spell`, `ability`), `school_id`,
  `stat`, `tier`, `effects` (JSON list of `{"key"}`, passives may add `"target"` and `"limit"`), `damage_type` (for
  effects that take the ability's own), `activation` (`active`, `passive`), `state` (`draft`, `pending`, `approved`,
  `denied`), `review_message_id`, `forum_thread_id`, `forum_message_id`, `tag_ids`. Migration 0015 replaced `effect`,
  `condition`, `area`, `secondary` and `passive` with `effects`, converting existing abilities to the nearest catalog
  effects.
- `character_abilities`: `character_id`, `ability_id`, `event`, `granted_by`.
- `characters`: `legendary`, `legendary_points`, `legendary_by`, `legendary_at`, `armor_proficiency`.
- `character_gear`: `proficiency`; `status` can also be `used` (a consumable used in a fight).
- `characters.state` can also be `dead`; migration 0014 adds `characters.bad_streak`.

Migration 0016 drops `armors`, `weapons`, `npcs` and `monsters`. Nothing reads them any more except the legacy imports;
run `/armory import legacy` and `/bestiary import legacy` first, and confirm before running it against a real database.

### Combat values on catalog items

- Weapon: `{"type": "slashing", "dice": "2d6", "attack_stat": "strength", "damage_stat": "strength", "hit_mod": 0,
  "range": "melee", "properties": ["two_handed"]}`. Properties: `light`, `heavy`, `two_handed`, `reach`, `thrown`,
  `loading`, `keen`, `focus`, `shield`. AP cost: 5 with `loading`, 4 with `heavy` or `two_handed`, 2 with `light`,
  otherwise 3; an `ap` value overrides it.
- Armor: `{"armor_class": "medium", "ac": 2, "dt": 2, "hit_mod": 0, "ability_hit_mod": 0}`.
- Consumable: `{"use": "heal", "dice": "2d4", "condition": null, "turns": 2}`. `use` is `heal`, `cure` (removes
  `condition`, or the first harmful one), `boost` (gives Inspired, Regenerating or Shielded for `turns`; a shield
  absorbs the dice) or `none` (the GM settles it).
- In a pack, `"damage_stat": null` means no damage stat (bows and crossbows).
- Items with the old shape (`modifier`, `hitmodifier`, `hp`, `ap`, `hitchance`) are read through a converter, and
  `/armory import <pack> refresh:true` rewrites pack items with the pack's current values.

## 3. Settings

| Key | Default | Values |
|---|---|---|
| `COMBAT_PACING` | `async` | `async`, `live`, `choose` |
| `COMBAT_ASYNC_TIMER` | 12 | hours per phase (1 to 168) |
| `COMBAT_LIVE_TIMER` | 3 | minutes per turn (1 to 60) |
| `COMBAT_PVP` | on | toggle |
| `COMBAT_LETHAL` | `gm` | `off`, `gm`, `agreed` |
| `COMBAT_LEVEL_BONUS` | off | toggle: +1 to hit at levels 4, 8, 12 and 16 |
| `ABILITY_CREATION` | `everyone` | `everyone`, `staff`, `off` |
| `ABILITY_FORUM` | none | a forum channel |
| `LEGENDARY_POINTS` | 5 | 0 to 50 |

## 4. Rules reference

### Actions and AP

| Action | AP | Notes |
|---|---|---|
| Attack | weapon cost | Switching to another weapon first costs 1 more. |
| Aimed attack | weapon cost + 1 | −4 to hit; a hit adds one damage die and ignores DT. |
| Ability | tier base + effects | Base 1 (Cantrip, Weak), 2 (Normal), 3 (Strong), plus each effect's cost. Uses per fight: unlimited, 3, 2, 1. |
| Help | 2 | An ally gets +2 on their next roll. |
| Revive | 3 | A downed ally returns at 1 HP on `d20 + INT modifier` of 10 or more. |
| Use item | 2 | A consumable on yourself or an ally; a heal item on a downed ally revives them. |
| Flee | all | `d20 + AGI modifier` against 10 + standing enemies; success leaves the fight. |
| Other | all | Free text the GM settles; unsettled, it counts as defending with the AP. |
| End turn | 0 | Unspent AP becomes AC. |

### Crippled stats

| Stat at 0 or below | Effect |
|---|---|
| Strength | Can't use two-handed weapons or heavy armor. |
| Perception | Ranged attacks roll twice and keep the lower. Acts last. |
| Endurance | No HP from levels; death rolls need 12. |
| Charisma | Charisma abilities roll twice and keep the lower; can't Help. |
| Intelligence | Intelligence abilities roll twice and keep the lower; can't Revive without a healing item. |
| Agility | Flee fails unless the character was helped this turn. |
| Luck | A natural 20 must be confirmed by a second roll that also hits; fumbles on 1 to 3. |

### Conditions

Harmful: Stunned (loses its next turn; can't be stunned two turns in a row), Weakened (−2 to hit and damage), Slowed
(acts last, −2 AC), Burning, Bleeding and Poisoned (1d4 at the start of each of its turns; poisoned also −1 to hit),
Blinded (−4 to hit), Marked (attacks against it get +2), Silenced (can't use abilities), Prone (−2 to hit, −2 AC),
Frightened (−2 to hit and saves), Confused (half its attacks and abilities go to a random combatant), Charmed (can't
target whoever charmed it), Taunted (attacks must go to its taunter while that one stands), Asleep (loses its turns
until damaged), Restrained (can't flee, −2 to hit, attacks against it +2), Vulnerable (takes extra damage per hit),
Corroded (−2 DT), Withered (can't be healed), Drained (fewer AP next turn), Cursed (attacks and saves roll twice, keep
the lower), Doomed (takes the stored damage when it runs out), Disarmed (only unarmed or natural attacks), Banished
(loses its turns and can't be targeted).

Helpful: Shielded (absorbs damage), Inspired (+2 to hit), Regenerating (heals 1d4 each turn), Empowered (+2 damage),
Fortified (+2 AC), Hasted (extra AP each turn), Evasive (the next attack against it misses), Hidden (attacks against it
−4, ends when it attacks), Intangible (weapons and physical abilities can't hurt it), Warded (half damage from spells),
Reflecting (the next spell that hurts it hits the caster for half), Vampiric (its hits heal it for half), Focused (+2
to hit and DC), Blessed (+2 on saves), Riposte (melee attackers that miss take damage), Companion (a summon attacks at
the start of each of its turns), Thorns (melee attackers that hit take damage), Undying (the next downing hit leaves
1 HP).

Durations count the affected combatant's own turns. The GM panel picks harmful or helpful first, since Discord menus
hold 25 options; the armory's item options only offer the conditions from before the effect catalog.

**Control immunity** (Rico's call): when a control condition ends (Stunned, Asleep, Charmed, Restrained, Cursed,
Confused, Silenced, Disarmed, Taunted, Banished), whether it runs out, is cleansed, ends with a caster's concentration
or a sleeper is woken by damage, the combatant can't get that same condition again until the end of its next turn, so
a fight can't be locked down by re-applying it. Stunned already worked this way. GM tools ignore the immunity.

**Concentration** (Rico's call, as in D&D): a spell that keeps something going on someone (a boost on another, a
summon, a condition from a save, a doom) needs concentration, and a caster holds one at a time. Casting another such
spell ends the first, and so does going down; taking damage calls for an END save against the higher of 10 and half
the damage. When it ends, what that spell keeps going stops (and control conditions it held give the usual immunity).
Physical abilities and boosts only on the caster never need it. The board shows "🧠 concentrating on …".

**Weapon techniques**: 657 physical effects need a weapon (`requires` on the effect): a weapon kind (sword, spear,
crossbow, claw...), or a ranged weapon, a thrown weapon or a shield for the generic archery and shield tricks; fists,
kicks and elbows need nothing. In a fight the ability only works while the character can use a matching weapon (being
disarmed counts), and the weapon's proficiency, hit modifier and unmet requirements are added to the roll. A catalog
weapon names its kind in `combat.kind` (`/armory add|edit weapon_kind`, set on the fantasy pack); without one it is read
from the name (Hedge Knife is a dagger, Riverglass Sabre a scimitar). A greatsword or sabre also does sword techniques,
a hatchet axe ones. Natural weapons (claws, fangs, horns, tail, wings, tentacles) are catalog items staff grant, for
example to a clawed species; an NPC's own natural attack counts as any of them. `/ability learn` warns when the
character owns no matching weapon.

### Abilities and the effect catalog

| Tier | Uses | Dice | Condition turns | Save DC bonus | Base AP | Effects |
|---|---|---|---|---|---|---|
| Cantrip | unlimited | 1d8 | 1 | +0 | 1 | up to 2 |
| Weak | 3 | 2d6 | 1 | +1 | 1 | up to 3 |
| Normal | 2 | 3d6 | 2 | +2 | 2 | up to 4 |
| Strong | 1 | 4d8 | 3 | +3 | 3 | up to 5 |

The catalog holds 2,005 active effects (1,188 magic, 817 physical) in 34 categories, each magic or physical, drawn
from the Superpower Wiki's categories, lists of spells and D&D. About 280 are written by hand
(`classes/combat/EffectCatalog.py`: the well-known powers and spells by name); the rest come from
`classes/combat/GeneratedEffects.py`, which crosses 49 magic themes (fire, crystal, blood, dreams, cards, runes...) and
38 weapons and natural weapons (sword, whip, crossbow, claws, tail...) with technique templates (bolt, lance, nova,
hex, ward, summon; crippling, disarming, flurry, parry...). Many share a mechanic and differ in damage type, rider and
cost, so players find the power they mean by name. Some need a minimum tier (stuns at Weak, mass effects at Normal).
Generated keys (`<theme>_<template>`) are stored on abilities, so they must not be renamed.

Everything is pitched at a party of about 5th level in D&D terms (Rico's call): spells up to roughly 3rd level and the
tricks of a seasoned fighter, ranger or rogue. Nothing stops time, banishes, disintegrates, polymorphs, takes over a
mind, makes the user intangible or summons golems and demons; summons are small helpers (sprites, hounds, wisps). The
banished and intangible conditions stay for GMs to apply by hand.

**Balance pass 1** (2026-11-15, from the simulator's first report, see `classes/combat/Balance.py`): blasts roll one die
step below the tier's; Cantrip dice went from 1d6 to 1d8, so a 3 AP Cantrip attack matches a 3 AP weapon swing (a base
AP of 0 was tried and overshot: three Cantrips a turn won 64% to 88%); Precise and Dart effects give +2 to hit and cost
3 (at cost 2 the accuracy came free); self Armor, Guard, Iron Skin and Grit Teeth last two turns longer, since unspent AP
already becomes AC. The latest report is `design/balance-report.md`.

| Mechanic | What it does |
|---|---|
| attack | `d20 + stat modifier` against AC; a hit deals dice + modifier − DT. Options: fixed damage type, extra hits (one dice step lower each), ignores DT, drain (heals the user half), a condition on a hit, execute (+1 die at half HP or less), accuracy, wider crits. |
| blast | The target saves (`d20 + stat`) against `10 + modifier + DC bonus`; a failed save takes the dice (one step below the tier's, since a blast always does something), a passed one half. Can add a condition on a failed save. |
| afflict | Save or the condition for the tier's turns. A save failed by 5 or more also triggers the ability's damage type. |
| doom | Save or doomed: takes the dice when it runs out. |
| dispel / cleanse | Removes helpful conditions from an enemy / harmful ones from an ally. |
| heal / shield / revive | Dice + modifier as HP, as a shield, or to bring a downed ally back. Heals reach downed allies. |
| boost | A helpful condition for the tier's turns. Boosts that only work on the user cost 1 less. |
| companion | A summon attacks a random enemy at the start of the user's turns for the tier's turns + 1. |
| escape | The user leaves the fight. |
| modifier | Area (up to 3 targets, dice a step lower, +2 AP), mass (up to 5, two steps, +4, Normal+), empowered (+1 dice step, +2), precise (+2 to hit and DC, +1), lingering (conditions +1 turn, +1). |
| drawback | −1 AP each, at most 2: blood price (user takes half the base dice), exhausting (drained 2 AP), reckless (−2 AC), backlash (hurts when every roll fails), weakening, once per fight. |

An ability's effects aim at enemies or allies (never both); effects on the user can join either. Self-only abilities
need no target. Spells count as magic for passives and wards; physical abilities count as physical, like weapons.

### Passive abilities

Always on, never used on a turn. Tier Weak (1 effect), Normal (2) or Strong (3); built from 443 passive effects
(`classes/combat/PassiveCatalog.py` by hand, plus each theme's affinity, attunement, resistance, absorption, immunity
and infusion and each weapon's mastery and training), each magic or physical. An ability passive takes 2 ability slots and physical
effects; a spell passive takes one spell slot of its tier and magic effects (and needs a school). Every passive lowers
the character's AP each turn by the cost of its effects (+1 per effect at Strong), and can't leave it under 3 AP.

| Type | What it does | Weak / Normal / Strong |
|---|---|---|
| Bonus | +to hit, damage, AC (within the cap of 18), DT, max HP or Sequence. To hit and damage can be limited to melee, ranged, magic, physical or one damage type. | +1/+2/+3; HP +5/10/15; Sequence +2/4/6 |
| Resistance | Hits from a damage type, magic or physical attacks do less damage (at least 1). Damage over time isn't resisted. | 2/4/6 |
| Immunity | One harmful condition never takes hold. | Normal only |
| Trigger: regenerate | Heals at the start of each of its turns. | 1d4/1d6/1d8 |
| Trigger: last stand | Drops to 1 HP instead of going down. | Normal once, Strong twice per fight |
| Trigger: on a strong hit | Its strong hits (attacks and damage abilities) add a harmful condition. | 1/2/3 turns |
| Trigger: counter | A melee attacker that misses it takes damage, once per round. | 1d4/1d6/1d8 |
| Aura | Standing allies (not itself) get a bonus to to hit, damage or AC; only the best aura per bonus counts. | +1/+1/+2 |
| Stacks | Each hit it takes from a source (any, magic, physical or a damage type) adds a stack of +1 to hit, damage or AC, for the rest of the fight. Shown on the board. Each stacks passive can set its own limit (`stack_limit`, 1 to 30), so staff can approve ones that go into the 20s. | its own limit, or 2/3/5 stacks |
| Trigger: second wind | Heals once per fight when it drops to half HP or less. | 1d6/2d6/3d6 |
| Lifesteal | Its hits heal it for part of the damage. | 1/4, 1/3, 1/2 |
| Berserk | More damage at half HP or less. | +2/+3/+4 |
| Crit | Wider crit range. | 1/1/2 |
| DC | Higher DC for its abilities. | +1/+2/+3 |
| Save | Bonus on its saves. | +1/+2/+3 |
| Heal power | Its heals heal more. | +2/+3/+4 |
| Thorns | Melee attackers that hit it take damage. | 2/3/4 |

"Magic" means spells; "physical" means weapon attacks and physical abilities. HP, AC, DT and Sequence bonuses and the
AP cost are applied when the combatant joins; the rest during the fight. The AP bonus is gone (a passive that costs AP
to give AP made no sense). Bestiary entries can have passives too (their `abilities` option).

### Damage types (defaults)

| Type | Trigger | Effect |
|---|---|---|
| Slashing | strong hit | Bleeding, 2 turns |
| Piercing | strong hit | Ignores DT for that hit |
| Blunt | strong hit | Stunned |
| Fire | strong hit | Burning, 2 turns |
| Frost | strong hit | Slowed, 1 turn |
| Lightning | strong hit | Arcs to another enemy for half the damage |
| Arcane | strong hit | Marked, 2 turns |
| Poison | strong hit | Weakened, 2 turns |
| Radiant | strong hit | Blinded, 1 turn |
| Mental | strong hit | Silenced, 1 turn |
| Acid | strong hit | Corroded, 2 turns |
| Necrotic | strong hit | Withered, 2 turns |
| Sonic | strong hit | Prone, 1 turn |
| Restoration | always | Healing also removes one condition |

### Bestiary presets

| Preset | HP | AC | DT | To hit | Damage | AP |
|---|---|---|---|---|---|---|
| Minion | 8 | 10 | 0 | +1 | 1d6 | 7 |
| Standard | 20 | 12 | 1 | +2 | 2d6 | 7 |
| Elite | 40 | 14 | 2 | +4 | 2d8 | 7 |
| Miniboss | 75 + 75 × 0.25 per player | 14 | 2 | +4 | 2d8 | 10 |
| Boss | 75 + 75 × 0.5 per player | 15 | 3 | +5 | 3d8 | 14 (acts twice) |

**Minibosses and bosses** (Rico's formula): HP = 75 + 75 × 0.25 (miniboss) or 0.5 (boss) × the number of player
characters on the other sides, so 150 and 225 against 4 players (at least one player counts). It is set when the fight
starts (the log says "👑 Boss … has 225 HP against 4 players"), again whenever someone joins during setup, and when a
boss joins a running fight; HP passives add on top. Quick NPCs offer both presets, a bestiary entry with either preset
is one, and the GM can make any bestiary NPC a miniboss or boss when adding it (the "Miniboss or boss?" field). Roll
tables that start fights keep the entry's own rank.

NPC behaviors: aggressive (lowest HP), vengeful (whoever hit it last), random, cautious (defends below 30% HP, flees
below 15%), support (revives and heals allies first). Player autopilot: weakest, revenge, defend, support.

## 5. Commands

- `/combat start [title] [pacing] [lethal]`, `/combat challenge <member> <character> [lethal]`,
  `/combat invite <member>`, `/combat attack` (quick roll), `/combat board` (posts the board again).
- `/bestiary add | edit | remove | list | view | import` (Manage Messages).
- `/ability create | edit | passive | passive_edit | effects | list | view | learn | forget | import_sheets`,
  `/school create | edit | list | view`.
- `/damagetype add | edit | remove | list | reset` (Manage Server).
- `/armory add | edit` take consumables (`use`, `condition`); `/armory import legacy` copies the old armors and weapons.
- `/gear proficiency`, `/character armor_proficiency` (staff).
- `/gm gear proficiency`, `/gm ability grant | take`, `/gm legendary grant | take`, `/gm resurrect`.

## 6. Code map

- `classes/combat/Rules.py`: modifiers, derived stats, weapon and armor values, attack and damage rolls.
- `classes/combat/Conditions.py`, `DamageTypes.py`, `Abilities.py`: conditions, damage types, ability rules.
- `classes/combat/Effects.py`, `EffectCatalog.py`, `PassiveCatalog.py`, `GeneratedEffects.py`: effect mechanics,
  checks and AP costs, the hand-written catalogs and the themed bulk of them. `classes/combat/Resolver.py`: resolving abilities and their effects in a fight (a mixin of the engine).
- `classes/combat/SheetAbilities.py`: reserved sheet labels and turning old free-text answers into blank abilities.
- `classes/combat/Balance.py`: the balance simulator. `python -m classes.combat.Balance [fights] [path]` plays each
  effect in simulated duels (a hero with it against one that only attacks) and writes `design/balance-report.md` with
  the outliers per tier (too strong, too weak, worse than attacking). It needs no database or Discord.
- `classes/combat/Loadout.py`: a character or bestiary entry as a combatant.
- `classes/combat/Passives.py`: passive abilities. `classes/combat/Fortune.py`: bad-roll protection. `classes/combat/Items.py`: consumables. `classes/combat/BestiaryFlow.py`: bestiary values and imports.
- `classes/gear/Legacy.py`: reads the old global tables. `classes/characters/Death.py`: the dead status.
- `classes/combat/State.py`, `Engine.py`, `Autopilot.py`: the fight state and every rule that changes it. No Discord.
- `classes/combat/Board.py`, `CombatFlow.py`: the board embed and the Discord side (threads, logs, locks, PvP).
- `classes/combat/Legendary.py`: granting and removing legendary status.
- `views/combat/`: board buttons, the action panel, the GM panel, challenge and review buttons.
- `tasks/CombatTask.py`: checks timers every 30 seconds.
