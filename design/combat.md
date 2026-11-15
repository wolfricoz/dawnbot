# Combat: design

Status: built on branch `feature/combat` from the team proposal ("Dawnbot combat system proposal" in Google Docs,
15 November 2026). Migrations `0011_combat` (new tables and columns), `0012_bestiary_special` (bestiary entries built
from SPECIAL), `0013_passive_abilities` (active and passive abilities), `0014_bad_streak` (bad-roll protection) and `0015_drop_legacy_combat` (drops the old global armor, weapon, NPC and monster tables; import them
first with `/armory import legacy` and `/bestiary import legacy`).

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
| Legendary | `characters.legendary`, set with `/gm legendary grant` and `/gm legendary take`: stat limits double (10 → 20, species 13 → 26), `LEGENDARY_POINTS` extra points (default 5) and one extra ability slot. Removing the status lowers stats above the normal limit, returns those points, then takes the legendary points back (from unspent points first, then from the highest stats). |
| Abilities | Built from parts (kind, tier, stat, effect, damage type, optional area and second condition), reviewed by staff in `CHARACTER_REVIEW`, posted to `ABILITY_FORUM` when set. Created with `/ability create` (slash options and a modal) rather than a DM interview. Every ability is active (used on a turn) or passive (always on, `/ability passive`; see section 4). |
| Magic schools | A standard set per server plus player-made schools reviewed by staff. A school sets the casting stat (Intelligence or Charisma). |
| Ability slots | Spellcasters: 6 spells (1 Cantrip, 2 Weak, 2 Normal, 1 Strong). Others: 3 ability slots, where an active ability takes 1 and a passive 2, with at most 1 Strong (active or passive). Spellcasters can't take passives (they are abilities). Not both, unless event-granted. Legendary characters get one extra slot of any tier. Event-granted abilities (`/gm ability grant`) do not count. |
| Damage types | One table per server (`damage_types`), filled with the defaults the first time it is used; staff edit it with `/damagetype`. Weapons name their type in `combat.type`; abilities pick one. |
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
- `abilities` (migration 0013 adds `activation` (`active`, `passive`) and `passive` (JSON: `type`, `field`, `scope`,
  `trigger`, `condition`, `limit`)): `guild_id`, `creator_uid`, `name`, `description`, `flavor`, `kind` (`spell`, `ability`), `school_id`,
  `stat`, `tier`, `effect` (`damage`, `heal`, `condition`, `shield`, `boost`), `damage_type`, `condition`, `area`,
  `secondary`, `state`, `review_message_id`, `forum_thread_id`, `forum_message_id`, `tag_ids`.
- `character_abilities`: `character_id`, `ability_id`, `event`, `granted_by`.
- `characters`: `legendary`, `legendary_points`, `legendary_by`, `legendary_at`, `armor_proficiency`.
- `character_gear`: `proficiency`; `status` can also be `used` (a consumable used in a fight).
- `characters.state` can also be `dead`; migration 0014 adds `characters.bad_streak`.

Migration 0015 drops `armors`, `weapons`, `npcs` and `monsters`. Nothing reads them any more except the legacy imports;
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
| Ability | 3 (Cantrip, Weak), 4 (Normal), 5 (Strong) | Uses per fight: unlimited, 3, 2, 1. |
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

Stunned (loses its next turn; can't be stunned two turns in a row), Weakened (−2 to hit and damage), Slowed (acts last,
−2 AC), Burning and Bleeding (1d4 at the start of each of its turns), Blinded (−4 to hit), Marked (attacks against it
get +2), Shielded (absorbs damage), Inspired (+2 to hit), Regenerating (heals 1d4 at the start of each of its turns),
Silenced (can't use abilities). Durations count the affected combatant's own turns.

### Abilities

| Tier | Uses | Dice | Condition turns | Save DC bonus | AP |
|---|---|---|---|---|---|
| Cantrip | unlimited | 1d6 | 1 | +0 | 3 |
| Weak | 3 | 2d6 | 1 | +1 | 3 |
| Normal | 2 | 3d6 | 2 | +2 | 4 |
| Strong | 1 | 4d8 | 3 | +3 | 5 |

Damage rolls `d20 + stat modifier` against AC and deals dice + stat modifier − DT. Conditions use a save:
`d20 + the condition's save stat` against `10 + stat modifier + DC bonus`. Area hits up to 3 targets with half the dice.
A second condition on a damage ability costs one dice step. Cantrips can't apply conditions as their main effect.

### Passive abilities

Always on, never used on a turn. Tier Weak, Normal or Strong (no Cantrip); each takes 2 ability slots.

| Type | What it does | Weak / Normal / Strong |
|---|---|---|
| Bonus | +to hit, damage, AC (within the cap of 18), DT, max HP, AP or Sequence. To hit and damage can be limited to melee, ranged, magic or one damage type. | +1/+2/+3; HP +5/10/15; AP +1/1/2; Sequence +2/4/6 |
| Resistance | Hits from a damage type, magic or physical attacks do less damage (at least 1). Damage over time isn't resisted. | 2/4/6 |
| Immunity | One harmful condition never takes hold. | Normal only |
| Trigger: regenerate | Heals at the start of each of its turns. | 1d4/1d6/1d8 |
| Trigger: last stand | Drops to 1 HP instead of going down. | Normal once, Strong twice per fight |
| Trigger: on a strong hit | Its strong hits (attacks and damage abilities) add a harmful condition. | 1/2/3 turns |
| Trigger: counter | A melee attacker that misses it takes damage, once per round. | 1d4/1d6/1d8 |
| Aura | Standing allies (not itself) get a bonus to to hit, damage or AC; only the best aura per bonus counts. | +1/+1/+2 |
| Stacks | Each hit it takes from a source (any, magic, physical or a damage type) adds a stack of +1 to hit, damage or AC, for the rest of the fight. Shown on the board. Each stacks passive can set its own limit (`stack_limit`, 1 to 30), so staff can approve ones that go into the 20s. | its own limit, or 2/3/5 stacks |

"Magic" means abilities and spells; "physical" means weapon attacks. HP, AP, AC, DT and Sequence bonuses are added when
the combatant joins; the rest during the fight. Bestiary entries can have passives too (their `abilities` option).

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
| Restoration | always | Healing also removes one condition |

### Bestiary presets

| Preset | HP | AC | DT | To hit | Damage | AP |
|---|---|---|---|---|---|---|
| Minion | 8 | 10 | 0 | +1 | 1d6 | 7 |
| Standard | 20 | 12 | 1 | +2 | 2d6 | 7 |
| Elite | 40 | 14 | 2 | +4 | 2d8 | 7 |
| Boss | 80 | 15 | 3 | +5 | 3d8 | 14 (acts twice) |

NPC behaviors: aggressive (lowest HP), vengeful (whoever hit it last), random, cautious (defends below 30% HP, flees
below 15%), support (revives and heals allies first). Player autopilot: weakest, revenge, defend, support.

## 5. Commands

- `/combat start [title] [pacing] [lethal]`, `/combat challenge <member> <character> [lethal]`,
  `/combat invite <member>`, `/combat attack` (quick roll), `/combat board` (posts the board again).
- `/bestiary add | edit | remove | list | view | import` (Manage Messages).
- `/ability create | edit | passive | passive_edit | list | view | learn | forget`, `/school create | edit | list |
  view`.
- `/damagetype add | edit | remove | list | reset` (Manage Server).
- `/armory add | edit` take consumables (`use`, `condition`); `/armory import legacy` copies the old armors and weapons.
- `/gear proficiency`, `/character armor_proficiency` (staff).
- `/gm gear proficiency`, `/gm ability grant | take`, `/gm legendary grant | take`, `/gm resurrect`.

## 6. Code map

- `classes/combat/Rules.py`: modifiers, derived stats, weapon and armor values, attack and damage rolls.
- `classes/combat/Conditions.py`, `DamageTypes.py`, `Abilities.py`: conditions, damage types, ability rules.
- `classes/combat/Loadout.py`: a character or bestiary entry as a combatant.
- `classes/combat/Passives.py`: passive abilities. `classes/combat/Fortune.py`: bad-roll protection. `classes/combat/Items.py`: consumables. `classes/combat/BestiaryFlow.py`: bestiary values and imports.
- `classes/gear/Legacy.py`: reads the old global tables. `classes/characters/Death.py`: the dead status.
- `classes/combat/State.py`, `Engine.py`, `Autopilot.py`: the fight state and every rule that changes it. No Discord.
- `classes/combat/Board.py`, `CombatFlow.py`: the board embed and the Discord side (threads, logs, locks, PvP).
- `classes/combat/Legendary.py`: granting and removing legendary status.
- `views/combat/`: board buttons, the action panel, the GM panel, challenge and review buttons.
- `tasks/CombatTask.py`: checks timers every 30 seconds.
