# Roleplay tools: design

Status: proposal, 15 November 2026; Rico answered the open questions the same day (section 16). **All six phases are
built** on branch `feature/combat`: phase A (migration `0016_checks_tables`, section 20) and phases B to F (migrations
`0017_world` to `0021_rumors_omens`, section 21), and the pieces first left out (migration `0022_roleplay_extras`,
section 22). `0025_drop_legacy_combat` was renumbered so it stays last. The doc
covers the 15 tools picked from the idea list: languages, scenes and post order, the chronicle, calendar and weather,
locations and travel, rumors, GM checks, secret rolls, roll tables, the job board, faction reputation, downtime,
crafting, letters and omens. Not picked: idle-channel prompts, the memorial wall and the relationship web.

Every tool builds on systems that already exist: proxying (`classes/proxy/`), SPECIAL and the stat modifier
(`stat − STAT_BASE`), the Luck crit range and bad-roll protection (`classes/combat/Fortune.py`), the gear catalog and
shop, character currency and its ledger, occupations, the bestiary and `/combat start`, tag requirements, genre packs
and `ConfigData`. Section 16 records Rico's answers to the open questions.

## 0. Shared rules

| Topic | Decision |
|---|---|
| GM | Staff (`manage_messages`), as in `/gm`. In a scene its host also counts as GM for tables in that scene, and in a fight thread the fight's GMs do. Checks are different: anyone can call one, and whoever calls it runs it (Rico's call). |
| Character picker | Buttons that act "as a character" use the player's character in the current scene when there is one; otherwise a select of their approved characters (skipped when they have one). |
| Check roll | `d20 + stat modifier + modifiers` against a DC. Crits and fumbles use the combat rules: the crit range from Luck (20 at Luck 6 or less, wider by one per 2 points above 5) and fumbles on a natural 1 (1 to 2 at Luck 1 to 2, 1 to 3 at Luck 0 or below). A crit always succeeds, a fumble always fails. Rolls made as a character count toward bad-roll protection. |
| DC names | Easy 8, Average 12, Hard 15, Very hard 18, Heroic 22. Commands offer the names and accept a number. |
| Strong result | Beating the DC by 5 or more, or a crit; failing by 5 or more, or a fumble, is a bad failure. Several tools give extra outcomes on these (the same rule as a strong hit in combat). |
| Buttons | Persistent `DynamicItem` buttons with the record id in the custom id, like the combat board, so they keep working after a restart. |
| In-world date | When a server has a calendar (section 4), anything that shows a date shows the in-world date, with the real date in a tooltip line. |
| Packs | The pack format (`classes/gear/Packs.py`) gains tables, recipes, materials, omen decks, language presets and a calendar preset. The fantasy pack gets content for each first. |
| Ledger | New `currency_transactions.reason` values: `job`, `work`, `craft`, `courier`, `escrow`, `refund`. |
| Docstrings | Cog and group class docstrings stay at 100 characters or fewer (Discord limit); longer text goes in the module docstring. |

## 1. Languages

Characters speak languages; readers whose characters don't know the language see it scrambled and press a button to
understand it.

| Topic | Decision |
|---|---|
| Server languages | Staff manage a list per server (`/language add | edit | remove | list`). Each has a name, a description, a sound (how its scramble looks) and an optional script. One language is common (`COMMON_LANGUAGE`, default "Common") and every character knows it. |
| Sounds | Presets: flowing (`ae, el, ith, ri, on, la…`), harsh (`gr, uk, dak, zug, kr…`), clipped (`ka, ti, po, ne…`), sibilant (`ss, ith, sa, zh…`), runes (Unicode runes `ᚠ ᚢ ᚦ ᚨ…`) and glyphs (`⟟ ⏃ ⌇ ⟒…`). Staff can type their own syllables. |
| Knowing | `character_languages`: a character knows a language **fluently** or **partly**. Starting languages: common plus `LANGUAGE_SLOTS` (default 1), plus 1 per 2 points of Intelligence above 5 (INT 7 gives 2, INT 9 gives 3). Picked in the interview as a built-in step. A species can grant languages for free (`species.language_ids`). More come from `/gm language grant` or studying in downtime (section 12). |
| Speaking | `{Elvish}` in a proxied message switches to that language for the rest of the message, or until `{}` switches back. `/language speak <character> <language>` sets a sticky default for that character, so plain messages are in that language until it is changed. A character can only speak languages it knows; otherwise the message is not posted and the player gets a DM. |
| What gets scrambled | `LANGUAGE_SCRAMBLE`: `speech` (default) scrambles only quoted text (`"…"`, `“…”`, `«…»`) inside a language part, so the narration stays readable; `all` scrambles the whole part. |
| Scrambling | Word by word and deterministic: the same word always comes out the same in a language (seeded by language id and word), so players can learn to recognize words. Word length, capitals, punctuation, Markdown and mentions are kept. |
| Understanding | The post gets an "🗣 Understand (Elvish)" button. Pressing it answers privately: the full text for a fluent character, about half the words for a partial one (the same words every time), or "None of your characters speak Elvish." Staff always see the full text. A message context menu "Understand" does the same, as a fallback. |
| Stored text | The original text is stored (`proxy_languages`) so the button, edits, the ❓ lookup (staff see the original) and the chronicle work. Edits re-scramble. The 300-character minimum counts the original. |
| Letters | Letters (section 14) can be written in a language too. |

Data: `languages` (`guild_id`, `name`, `description`, `sound`, `syllables` JSON, `common`, `pack`),
`character_languages` (`character_id`, `language_id`, `fluency`, `source`: `start`, `species`, `study`, `granted`),
`proxy_languages` (`message_id`, `original`, `language_ids` JSON), `characters.speaking_language_id`,
`species.language_ids` (JSON).

Build check: webhooks the bot created are application-owned, so they can send buttons (`webhook.send(view=…)`).
Confirm this early; if it fails, the context menu is the only way in.

## 2. Scenes and post order

A scene is a tracked roleplay in one channel or thread, with a pinned card, a post order and nudges for whoever's turn
it is.

| Topic | Decision |
|---|---|
| Starting | `/scene start [title] [mode] [location]` in a roleplay channel or thread. One open scene per channel or thread. The starter is the host. The card shows the title, location and weather, the in-world date, the participants (character and player), the order, whose turn it is and when the last post was. |
| Joining | Join button (pick a character) or the host adds people. Each player takes part with one character per scene. Leave button. The host and staff can remove someone, move them in the order and hand over the host role. |
| Modes | `order` (default): a fixed rotation; a post by the character whose turn it is passes the turn on. A post out of turn is allowed and moves its poster into the current spot, so the order adapts to how people actually post: with A B C D and B to post, a post by D makes the order A D B C and it is still B's turn (Rico's call). `free`: no turns; the bot only nudges participants who haven't posted since everyone else has. |
| What counts as a post | A proxied post by the participant's scene character in that channel or thread that meets the roleplay minimum length. |
| Nudges | After `SCENE_NUDGE_HOURS` (default 24) the player whose turn it is gets a DM with a link (a ping in the channel when DMs are closed). After `SCENE_SKIP_HOURS` (default 72, 0 = never) the turn passes on and the card notes the skip. Pass button to skip yourself. |
| Away | `/scene away [until]` pauses nudges and auto-skips for that player in all scenes until the date or `/scene back`. The card shows them as away. |
| Pausing | The host can pause a scene (no nudges). A fight started from the scene's channel pauses it until the fight ends; the fight is linked on the scene card and in the chronicle. |
| Ending | `/scene end [summary]` (host or staff) closes it: the card is frozen, the chronicle is built (section 3) and, when `TIMELINE` is set, the timeline entry is posted as `/endscene` does now. `/endscene` stays as a shortcut that ends the open scene, or makes a one-off timeline entry when there isn't one. The in-world date comes from the calendar when there is one. |
| Idle scenes | A scene with no posts for `SCENE_IDLE_DAYS` (default 14) asks the host whether to end it; after another 7 days it ends by itself. |

Data: `scenes` (`guild_id`, `channel_id`, `thread_id`, `title`, `host_uid`, `mode`, `state`: `open`, `paused`,
`ended`, `location_id`, `turn_index`, `turn_started_at`, `card_message_id`, `started_at`, `ended_at`,
`world_start` / `world_end` JSON, `chronicle_thread_id`, `summary`), `scene_participants` (`scene_id`, `character_id`,
`uid`, `position`, `state`: `active`, `left`, `removed`, `last_post_at`, `posts`, `words`, `skips`,
`last_nudged_at`), `users.away_until`. `tasks/SceneTask.py` checks nudges every 5 minutes.

## 3. Chronicle

When a scene ends, its posts become a transcript in a chronicle forum, and each character keeps a list of the scenes
it was in.

| Topic | Decision |
|---|---|
| Where | `CHRONICLE` (a forum channel). Without it, scenes still end but no transcript is made. |
| What | The proxied posts in the scene's channel or thread between its start and end, read from Discord (one history pass, keeping messages whose ids are in `proxy_messages`), so edits and deletions are respected. Check, table and dice results in the scene become one-line notes ("🎲 Aria: Perception 17, success"). Language parts show the original text with a `‹Elvish›` marker: the chronicle is an out-of-character record. |
| The post | One forum thread per scene named after its title. The first message is a summary embed: location, in-world and real dates, participants, posts and words per character, and a link to the scene's first message. Then the transcript as an HTML file (avatars, names, timestamps, styled like Discord) and a plain `.md` file. An "Add summary" button lets participants write the short summary that `/endscene` used to ask for. |
| Older roleplay | `/chronicle make <first message link> <last message link> [title]` (staff, or anyone whose characters posted in that range) builds one without a scene. |
| Characters | `/character scenes <character>` lists its scenes with links. With `CHRONICLE_CHARACTER_POSTS` on (default off), each scene also adds a line to the character's forum thread. |

Data: `scenes.chronicle_thread_id` and `chronicles` (`guild_id`, `scene_id` nullable, `thread_id`, `title`,
`first_message_id`, `last_message_id`, `created_by`) plus `chronicle_characters` (`chronicle_id`, `character_id`,
`posts`, `words`).

## 4. Calendar, time and weather

| Topic | Decision |
|---|---|
| Calendar | One per server, set up with `/calendar setup` (Manage Server): a preset (Gregorian, or one from a pack) or custom months (name, days, season), weekday names, the era label ("4E") and the starting date. Optional moon with a cycle length, for moon phases. |
| Time of day | Six parts: dawn, morning, midday, afternoon, dusk, night. |
| Moving time | `/time advance <amount> <unit>` (staff) or `/time set`. `TIME_FLOW`: `manual` (default) or a real-time ratio (`1:1`, `1:2`… in-world days per real day), moved by a task. |
| Showing it | `/time` shows the date, time of day, season, moon phase and the weather where you are (the channel's location). Scene cards, the chronicle, letters, jobs and timeline entries use it. |
| Holidays | `/calendar event add` (name, date, description, recurring). On the day, the bot posts it to `ANNOUNCEMENT`. |
| Birthdays | `/character birthday <character> <month> <day>`; announced on that in-world date. Optional. |
| Weather | Rolled per **climate** (temperate, arid, arctic, tropical, coastal, none for indoors and underground) and season, from a weighted table. It changes when the in-world day changes, or every `WEATHER_HOURS` real hours (default 12) with manual time. The next weather is usually one step from the current one (clear → cloudy → rain → storm), so it doesn't jump from blizzard to heatwave. Staff can force weather with `/weather set`. |
| Weather effects | `WEATHER_EFFECTS` (default on): some weather adds a modifier to outdoor checks (section 7). Fog and heavy rain −2 Perception, storm −2 Agility, blizzard −2 Endurance and Perception, heatwave −2 Endurance. Indoor locations ignore it. |

Data: `calendars` (`guild_id` unique, `months` JSON, `weekdays` JSON, `era`, `year`, `month`, `day`, `part`,
`moon_cycle`, `flow`, `last_tick`), `calendar_events` (`guild_id`, `name`, `month`, `day`, `year` nullable,
`description`), `characters.birthday` JSON, `weather_state` (`guild_id`, `climate`, `region`, `weather`, `since`).

## 5. Locations and travel

| Topic | Decision |
|---|---|
| Location cards | A location belongs to one channel or thread: name, description, image (stored like avatars), region, climate, indoor or outdoor, danger (0 to 5), hazards, an encounter table (section 9) and tags. `/location set` (staff) runs in the channel and opens a modal; `/location view` shows the card with the weather and who's here. The new-channel prompt in `MODLOG` gets a "Set up location" button. |
| Regions | A region groups locations (a city, a forest). Locations without a climate take their region's. Weather is rolled per region. |
| Who's here | A character is at the location of its last proxied post (from `proxy_messages`), if that was in the last `PRESENCE_DAYS` (default 7). `/location who` lists them. |
| Travel | Optional (`TRAVEL`, default off). Staff draw routes: from, to, travel time in in-world hours and danger. `/travel <character> <destination>` posts a departure line in the current channel and an arrival line in the destination. On a dangerous route, the bot rolls the route's or destination's encounter table: `d20 + Luck modifier` against `8 + 2 × danger`, failing means an encounter. The result goes to the destination channel and pings the GM role; a bestiary result gets a "Start fight" button that opens `/combat start` with those NPCs added. |
| Travel time | With `TIME_FLOW` set, arrival waits for the in-world travel time; with manual time it is instant (the encounter is the point). Travel never stops a character from posting elsewhere. |

Data: `locations` (`guild_id`, `channel_id` unique, `name`, `description`, `image_id`, `region_id`, `climate`,
`indoor`, `danger`, `hazards`, `table_id`, `tags` JSON), `regions` (`guild_id`, `name`, `climate`, `description`),
`routes` (`guild_id`, `from_id`, `to_id`, `hours`, `danger`, `table_id`, `two_way`).

## 6. Rumor mill

| Topic | Decision |
|---|---|
| Posting | `/rumor post <text> [location]` from any player. The rumor is anonymous to players. Its author is stored and every rumor is logged with its author in `MODLOG`, since anonymous text needs moderation. Staff can block a member from posting rumors. |
| Planted rumors | `/rumor plant` (GM) adds a rumor and marks it true, false or partly true. The mark is hidden. Player rumors are unmarked unless a GM marks them. |
| Modes | `RUMOR_MODE`: `board` (default) posts every rumor anonymously to `RUMOR_CHANNEL` straight away. `whisper` keeps rumors in a pool that characters overhear; a rumor overheard 3 times "spreads" and is posted publicly. In either mode a GM can plant a rumor as `secret`: it is never posted and can only be overheard. |
| Listening | `/rumor listen <character>`, once per real day per character: `d20 + the better of the Perception or Charisma modifier` against Average (12). It draws from rumors the character hasn't heard yet, secret ones and those from its location and region first. Success: one rumor. Strong success: two, and a hint when one is GM-marked ("This one rings true."). Failure: nothing. Bad failure: a false rumor when there is one. |
| Expiry | Rumors fade after `RUMOR_DAYS` (default 14); GMs can pin one so it stays. |

Data: `rumors` (`guild_id`, `author_uid`, `character_id` nullable, `text`, `location_id`, `region_id`, `truth`:
`unknown`, `true`, `false`, `partial`, `secret`, `heard`, `spread_message_id`, `pinned`, `expires_at`, `created_at`),
`rumor_heard` (`rumor_id`, `character_id`, `heard_at`).

## 7. GM checks

The GM calls for a check; players press a button to roll it with their character.

| Topic | Decision |
|---|---|
| Making one | `/check call <stat> <dc> [title] [kind] [visibility] [modifier] [who] [expires]`, open to every member (Rico's call). Whoever calls it gets its GM buttons (Close, Results). Staff can close any check. Kind: `individual` (default), `group` or `opposed`. `who` limits it to a role, a few members or the scene's participants; empty means anyone. Expires after 24 hours by default. |
| The card | "**Perception check** · DC 15 · Spot the pickpocket" with Roll, Help and (for GMs) Close buttons. Each character rolls once. Every roll adds a line: character, natural die, total, outcome. |
| The roll | The check roll from section 0, plus the check's modifier, weather effects for outdoor locations, and an active omen (section 15). |
| Help | Another character can press Help before the target rolls to give one character +2 (as in combat), once per character per check. |
| Group | When the GM closes it, the group succeeds if at least half the rollers succeeded. |
| Opposed | `/check oppose <member> <their character> <your stat> <their stat>` (anyone, between characters), or a GM check with `kind: opposed` against an NPC with a fixed bonus. Each side gets a button; the higher total wins and a tie goes to the defender. |
| Quick check | `/dice` gets a `dc` option: a roll as a character against a DC shows success or failure. |
| Closing | Close posts the summary (who passed, the group result). Expired checks close by themselves. |

Data (as built): `checks` (`guild_id`, `channel_id`, `message_id`, `caller_uid`, `title`, `stat`, `dc`, `kind`
(`individual`, `group`, `opposed`, `passive`), `visibility`, `modifier`, `allowed` JSON (`role`, `member`), `opposed`
JSON (the two sides of a duel, or the NPC's roll), `helps` JSON, `state`, `expires_at`, `closed_at`), `check_rolls`
(`check_id`, `character_id`, `uid`, `name`, `side`, `stat`, `natural`, `total`, `outcome`, `helped_by`, `details`
JSON; one roll per character and check). `scene_id` comes with scenes (phase C).

## 8. Secret rolls

| Topic | Decision |
|---|---|
| Visibility | Every check has one: `public` (default) shows everything; `hidden_dc` shows the rolls and outcomes but not the DC; `secret` shows only "🎲 Aria rolled." while the check's caller (and staff) see the totals and outcomes behind a Results button. |
| Passive checks | `/check passive <stat> <dc> [who]` rolls for every character in the scene (or present at the location) without anyone pressing anything. Only the caller sees the result. A Reveal button sends a private message (DM, written in a modal) to the characters who passed: "You notice the guard's hand drifting to his knife." |
| Secret dice | `/dice` gets a `secret` option for everyone: it answers privately with a Show button to post the roll later. `/table roll` has the same `secret` option. |
| Accountability | When `GM_ROLL_LOG` is set to a channel, every secret roll is logged there, so the server can audit them. Off by default. |

## 9. Roll tables

| Topic | Decision |
|---|---|
| Tables | Per server, made by staff (`/table create | edit | remove | list | view | import | export`). A table rolls `1dN` over ranges ("01-05") or by weight ("3x"). Entries are pasted one per line in a modal. |
| Inline rolls | `{2d6}` in an entry is rolled when it comes up ("{2d6} goblins"); `[[Treasure]]` rolls another table in its place (at most 3 levels deep). |
| Actions | An entry can carry an action: give a catalog item, currency (dice), XP, or add bestiary NPCs (count in dice). Actions only happen when a GM presses Grant (for items, currency and XP; it picks the character) or Start fight (for NPCs, opening `/combat start` with them). |
| Luck | A table can be Luck-touched: rolling as a character shifts the roll by `2 × Luck modifier` toward the good end (loot tables). |
| Rolling | `/table roll <table> [character] [secret]`. Public by default. |
| Packs | The fantasy pack brings loot by tier, encounters by terrain, NPC quirks, tavern and shop names, plot hooks, and the omen decks. |
| Who uses them | Location and route encounters (section 5), job rewards (10), crafting mishaps (13), a great work result (12) and omen decks (15). |

Data (as built): `roll_tables` (`guild_id`, `name`, `description`, `dice` (`1dN` or `weights`), `luck`, `kind`:
`table`, `deck`, `visibility`: `everyone`, `staff`, `pack`, `creator_uid`), `roll_table_entries` (`table_id`, `low`,
`high`, `weight`, `text`, `actions` JSON list, `position`), `table_rolls` (`guild_id`, `table_id`, `table_name`, `uid`,
`character_id`, `channel_id`, `natural`, `rolled`, `text`, `actions` JSON with the dice rolled, `granted_to`,
`fight_id`, `secret`), kept so the card's buttons work later.

Entry syntax: `01-05: text` (ranges) or `3x text` / `text` (weights), one per line; `#` lines are skipped. Actions
follow the text: `| item: Arming Sword`, `| currency: 2d6`, `| xp: 50`, `| npc: 1d4 Grey Wolf` (NPC counts are capped at
10). Long tables go through `/table export` and `/table edit file:` (the form holds 4000 characters).

## 10. Job board

| Topic | Decision |
|---|---|
| Board | `JOB_BOARD`, a forum channel. `/job post` (GM) opens a modal: title, description, then options for the reward (currency, XP, catalog items), slots, minimum level, faction and reputation (section 11), location, and a deadline (real date, or in-world with a calendar). One forum thread per job, tagged Open / Taken / Done / Failed. |
| Claiming | A Claim button (pick a character). Full jobs keep a waiting list. Withdraw button. A character's level, faction standing and the job's tags are checked as for the shop. |
| Finishing | The GM presses Complete, picks which claimed characters took part, and picks an outcome: success (full reward), partial (half, rounded down) or failure (none, and the faction loses standing when the job says so). Rewards are paid at once: currency with reason `job`, XP to the character, items as `granted`, reputation. The thread is locked. |
| Deadlines | A job past its deadline fails by itself unless the GM extends it; claimed characters are told. |
| Player jobs | `JOB_PLAYER_POSTS` (default off): players post jobs as their character and pay the reward up front (held in escrow, reason `escrow`). The poster completes it; cancelling refunds it (reason `refund`). |
| Scenes | A "Start scene" button in a claimed job's thread starts a scene there with the claimers. |

Data: `jobs` (`guild_id`, `thread_id`, `poster_uid`, `poster_character_id`, `title`, `description`, `reward` JSON,
`slots`, `min_level`, `faction_id`, `rep_success`, `rep_failure`, `location_id`, `deadline`, `world_deadline` JSON,
`state`, `escrow`), `job_claims` (`job_id`, `character_id`, `uid`, `state`: `claimed`, `waiting`, `withdrawn`,
`done`, `outcome`).

## 11. Faction reputation

| Topic | Decision |
|---|---|
| Factions | Per server, made by staff (`/faction add | edit | remove | list | view`): name, description, colour, emoji, hidden or not, and rivals. A hidden faction only shows to a character once its standing isn't 0 (secret societies). |
| Standing | −100 to 100 per character and faction, starting at 0. Tiers: Vilified (−100 to −50), Disliked (−49 to −15), Neutral (−14 to 14), Liked (15 to 49), Idolized (50 to 100). |
| Changes | `/gm rep give | take`, jobs, and crafting or selling to a faction (section 13). Gaining standing with a faction costs half as much with each of its rivals (after the Charisma scaling; losses don't spread). Each change is logged. |
| Charisma | Gains are multiplied by `1 + 0.1 × Charisma modifier` (at least ×0.5), rounded. Losses aren't changed. |
| Shop | A catalog item can belong to a faction and need a tier to buy (it shows as locked, like level-locked items). Faction items cost 20% less at Idolized, 10% less at Liked and 25% more at Disliked, and Vilified characters can't buy them. |
| Restrictions | A new tag requirement kind `reputation` (faction and tier) for species, gear and abilities; occupations get an optional faction and tier. |
| Showing it | `/reputation <character>` and a line on the character card with its three strongest standings. |

Data: `factions` (`guild_id`, `name`, `description`, `colour`, `emoji`, `hidden`, `rivals` JSON),
`character_reputation` (`character_id`, `faction_id`, `value`), `reputation_log` (`character_id`, `faction_id`,
`amount`, `reason`, `actor_uid`, `created_at`), `gear_items.faction_id`, `gear_items.faction_tier`,
`occupations.faction_id`, `occupations.faction_tier`.

## 12. Downtime

Once per real day each character can spend downtime on an activity.

| Topic | Decision |
|---|---|
| Command | `/downtime <character> <activity>`. One activity per character per day; the day resets at `DOWNTIME_RESET` (default 00:00 UTC). |
| Activity rule | Only for characters that made a proxied roleplay post in the last `DOWNTIME_ACTIVE_DAYS` (default 7), so idle characters don't earn money in the background. |
| Work | Economy mode only. Pays the occupation's `pay` (staff set it; default `WORK_PAY`, 50, so roleplaying stays the main income) and rolls its `work_stat` against Average (12). Bad failure: a mishap and no pay. Failure: half pay. Success: full pay. Strong success: +50%. Crit: double pay and a roll on the occupation's table (section 9) when it has one. Without an occupation, "odd jobs" pay half and the player picks the stat. Each occupation can have flavor lines per outcome. Ledger reason `work`. |
| Study | Pick a language: Intelligence against Average. Success +1, strong success +2. At `STUDY_DAYS` (default 10) the character speaks it partly; another `STUDY_DAYS` makes it fluent. |
| Craft | Works on a crafting project that takes days (section 13). |
| Carouse | Spends `CAROUSE_COST` (default 50) currency for a free `/rumor listen` with +2, and +1 standing with a faction tied to the channel's location when it has one. |
| Showing it | The result is posted publicly as a short card (activity, roll, outcome, earnings); `DOWNTIME_PRIVATE` makes it private. |

Data: `downtime` (`character_id`, `day`, `activity`, `outcome`, `details` JSON), `occupations.pay`,
`occupations.work_stat`, `occupations.table_id`, `occupations.flavor` JSON, `study_progress` (`character_id`,
`language_id`, `points`).

## 13. Crafting

| Topic | Decision |
|---|---|
| Materials | A fourth catalog kind, `material` (bought, found on tables, given by jobs or GMs, or salvaged). `character_gear` gets `quantity` so materials (and consumables) stack. |
| Recipes | Per server, made by staff: a result item and amount, ingredients (items and amounts), an optional tool (needed, not used up), a stat (Intelligence by default), a DC, an optional occupation (+2 when the crafter has it, or required), a minimum level, a faction, and days (0 = right away). |
| Making | `/craft make <character> <recipe>`. The ingredients are checked first. Success: the item (`source = crafted`) and the ingredients are used up. Failure by less than 5: half of each ingredient is lost (rounded down) and nothing is made. Bad failure: the ingredients are used up; a weapon or armor comes out **cursed**, anything else is lost, and the recipe's mishap table is rolled if it has one. Crit: a weapon or armor comes out **masterwork**; materials and consumables give one extra (Rico's call). |
| Masterwork | `character_gear.quality = masterwork`: a weapon gets +1 to hit, armor +1 DT. Shown as "Masterwork <name>" in the inventory, on the board and in the shop's sell price (+50%). Combat reads it in `Loadout` as an item hit modifier, next to the catalog's `hit_mod`; it doesn't count as proficiency, so the +1 proficiency cap is untouched. |
| Cursed | `character_gear.quality = cursed`: a weapon gets −1 to hit, armor −1 DT. It sells for nothing, and cursed armor can't be unequipped. A GM lifts the curse with `/gm gear uncurse`, which makes it a normal item; it can also be salvaged. |
| Projects | Recipes with days become a project: the ingredients are set aside up front and the character works on it with downtime (section 12), one roll per day. A day counts as work on a success; a bad failure loses the day. |
| Salvage | `/craft salvage <character> <item>` breaks a catalog item into the materials the item lists (`gear_items.salvage` JSON), half of them on average. Broken items can be salvaged. |
| Faction | A recipe or item can belong to a faction; selling or crafting it gives standing (section 11). |
| Browsing | `/craft recipes [character]` shows which recipes the character can make now, which are missing ingredients and which are locked. |

Data: `recipes` (`guild_id`, `name`, `result_item_id`, `result_amount`, `ingredients` JSON, `tool_item_id`, `stat`,
`dc`, `occupation_id`, `occupation_required`, `min_level`, `faction_id`, `days`, `mishap_table_id`, `pack`),
`craft_projects` (`character_id`, `recipe_id`, `days_done`, `state`, `reserved` JSON), `character_gear.quantity`,
`character_gear.quality` (`masterwork`, `cursed` or empty),
`character_gear.source` can be `crafted`, `gear_items.kind` can be `material`, `gear_items.salvage` JSON.

## 14. Letters

| Topic | Decision |
|---|---|
| Writing | `/letter write <from character> <to character>` opens a modal (subject and up to 4000 characters), with an optional language and an optional image. Recipients autocomplete from every approved character on the server. |
| Delivery | After `LETTER_DELAY` real hours (default 6), or a route's travel time when both characters have a location and travel is on. An express courier delivers in an hour for `COURIER_COST` (default 25, economy mode, reason `courier`). |
| Arriving | The recipient's player gets a DM styled as a letter: the sender's name and avatar, the in-world date and the text, with Reply and Keep buttons. With DMs closed, `LETTER_CHANNEL` (when set) gets a "📬 a letter for Aria" ping instead. Every letter stays in `/letter inbox <character>`. |
| Language | A letter in a language the recipient's character doesn't know arrives scrambled, with the same Understand rules as proxied posts. |
| Seals | A sealed letter shows whether anyone opened it on the way. |
| Privacy | Letters are private. Staff can't read them, except one that is reported or intercepted (Rico's call). |
| Reporting | Every delivered letter has a Report button. A reported letter is posted to `MODLOG` with its sender, recipient and text, and only then can staff read it. |
| Interception | `LETTER_INTERCEPT` (default off): an in-game feature a server opts into. GMs see letters in transit (`/gm letters`) and can deliver, delay or destroy one. The write modal warns players that letters on this server can be intercepted. Opening a sealed one marks the seal as broken for the recipient. With it off, `/gm letters` only lists who wrote to whom and when, never the text. |
| Undeliverable | Letters to retired, dead or deleted characters come back to the sender. |

Data: `letters` (`guild_id`, `from_character_id`, `to_character_id`, `subject`, `body`, `language_id`, `image_id`,
`sealed`, `seal_broken`, `express`, `world_date` JSON, `send_at`, `deliver_at`, `state`: `in_transit`, `held`,
`delivered`, `returned`, `destroyed`, `read_at`, `reply_to_id`, `reported_at`, `intercepted_by`).

## 15. Omens and fortune cards

| Topic | Decision |
|---|---|
| Drawing | `/omen draw <character> [deck]`, once every `OMEN_DAYS` (default 7) per character. The card is posted publicly with its meaning. |
| Decks | Built in: a tarot deck (the 22 major arcana, upright or reversed, with our own text) and bone casting (runes). Servers can add decks as roll tables of kind `deck`. A character draws without replacement until its deck is used up and reshuffled. |
| Effects | `OMEN_EFFECTS` (default off, so cards are pure story; Rico's call). With it on, a card can be a boon, a bane or neither. A boon arms bad-roll protection for the character's next failed check or roll (the same as reaching the streak). A bane gives −1 to its next check. Either lasts until used or until the next draw. Most cards are neither. |
| Seers | An occupation can be marked as a seer. Seers can read for another character (`/omen read <seer> <member> <character>`): the reading is public and the other character gets the effect, and it doesn't use up the seer's own draw. |

Data: `characters.omen` JSON (`card`, `effect`, `drawn_at`, `deck`), `omen_draws` (`character_id`, `deck_id`,
`card`, `drawn_at`), `occupations.seer`.

## 16. Answered questions

Rico's answers, 15 November 2026. The sections above already follow them.

| # | Question | Answer |
|---|---|---|
| 1 | Language parts in the chronicle | The original text with a `‹Elvish›` marker. |
| 2 | Starting languages | Common + 1, plus 1 per 2 Intelligence above 5. |
| 3 | Out-of-turn posts in `order` mode | Allowed; the poster moves into the current spot. |
| 4 | A fight started from a scene's channel | Pauses the scene until the fight ends. |
| 5 | Posting while travelling | Never blocked. |
| 6 | Reputation | Charisma scales gains, and rivals lose half. |
| 7 | Work pay | 50 a day by default. |
| 8 | Crafting crits | Masterwork on a crit, cursed on a bad failure (weapons and armor); needs `character_gear.quality`. |
| 9 | Staff reading letters | Only reported letters (and intercepted ones, where a server turns interception on). |
| 10 | Who calls checks | Anyone; the caller runs the check. |
| 11 | Omen effects | Off by default (flavor only); servers can turn them on. |
| 12 | Default rumor mode | `board`. |

## 17. Settings

| Key | Default | Values |
|---|---|---|
| `COMMON_LANGUAGE` | Common | a language name |
| `LANGUAGE_SLOTS` | 1 | 0 to 10 |
| `LANGUAGE_SCRAMBLE` | `speech` | `speech`, `all` |
| `SCENE_NUDGE_HOURS` | 24 | 1 to 336 |
| `SCENE_SKIP_HOURS` | 72 | 0 (never) to 720 |
| `SCENE_IDLE_DAYS` | 14 | 0 (never) to 90 |
| `CHRONICLE` | none | a forum channel |
| `CHRONICLE_CHARACTER_POSTS` | off | toggle |
| `TIME_FLOW` | `manual` | `manual`, `1:1`, `1:2`, `1:4`, `2:1`… |
| `WEATHER_HOURS` | 12 | 1 to 168 |
| `WEATHER_EFFECTS` | on | toggle |
| `TRAVEL` | off | toggle |
| `PRESENCE_DAYS` | 7 | 1 to 60 |
| `RUMOR_MODE` | `board` | `board`, `whisper` |
| `RUMOR_CHANNEL` | none | a channel |
| `RUMOR_DAYS` | 14 | 1 to 90 |
| `GM_ROLL_LOG` | none | a channel |
| `JOB_BOARD` | none | a forum channel |
| `JOB_PLAYER_POSTS` | off | toggle |
| `DOWNTIME_RESET` | 0 | hour, UTC |
| `DOWNTIME_ACTIVE_DAYS` | 7 | 0 (off) to 60 |
| `DOWNTIME_PRIVATE` | off | toggle |
| `WORK_PAY` | 50 | 0 to 100000 |
| `STUDY_DAYS` | 10 | 1 to 100 |
| `CAROUSE_COST` | 50 | 0 to 100000 |
| `LETTER_DELAY` | 6 | hours, 0 to 168 |
| `COURIER_COST` | 25 | 0 to 100000 |
| `LETTER_CHANNEL` | none | a channel |
| `LETTER_INTERCEPT` | off | toggle |
| `OMEN_DAYS` | 7 | 1 to 60 |
| `OMEN_EFFECTS` | off | toggle |

## 18. Commands

- `/language add | edit | remove | list | speak | known`, `/gm language grant | take`, context menu "Understand".
- `/scene start | end | join | leave | pass | away | back | add | remove | move | host | pause | resume | card`,
  `/endscene` (kept).
- `/chronicle make`, `/character scenes`, `/character birthday`.
- `/calendar setup | event add | event remove | events`, `/time`, `/time advance | set`, `/weather`, `/weather set`.
- `/location set | view | who | remove`, `/region add | edit | remove`, `/route add | remove`, `/travel`.
- `/rumor post | listen | plant | mark | pin | block`.
- `/check call | oppose | passive`, `/dice … dc`, `/dice … secret`.
- `/table create | edit | remove | list | view | roll | import | export`.
- `/job post | edit | cancel | list`.
- `/faction add | edit | remove | list | view`, `/reputation`, `/gm rep give | take`.
- `/downtime`.
- `/craft recipes | make | salvage | projects`, `/recipe add | edit | remove`, `/gm gear uncurse`.
- `/letter write | inbox | read`, `/gm letters`.
- `/omen draw | read | decks`.

## 19. Build order

Each phase stands on its own and can be play-tested before the next. Migrations follow the combat ones;
`drop_legacy_combat` is renumbered each time so it stays last while it is unmerged (now `0022`).

| Phase | Tools | Why this order | Migration |
|---|---|---|---|
| A ✅ | GM checks, secret rolls, roll tables | Only touch dice; everything later uses them. | `0016_checks_tables` |
| B ✅ | Calendar and weather, locations and travel | Scenes, letters and rumors read the date and location. Travel uses tables. | `0017_world` |
| C ✅ | Scenes and post order, chronicle | Need locations and the calendar for the card. | `0018_scenes` |
| D ✅ | Languages, letters | Hook into the proxy pipeline; letters need languages and routes. | `0019_languages_letters` |
| E ✅ | Factions, job board, downtime, crafting | The economy round: jobs pay standing, downtime runs crafting and study. | `0020_economy` |
| F ✅ | Rumor mill, omens | Flavor on top of locations, checks and occupations. | `0021_rumors_omens` |

New code areas: `classes/checks/`, `classes/tables/`, `classes/world/` (calendar, weather, locations, travel),
`classes/scenes/` (scenes, chronicle), `classes/language/`, `classes/letters/`, `classes/economy/` (factions, jobs,
downtime, crafting), `classes/flavor/` (rumors, omens), with cogs in `modules/` and timers in `tasks/WorldTask.py`
(calendar, weather, letters, deadlines) and `tasks/SceneTask.py`.

## 20. Phase A as built

Choices made while building checks, secret rolls and roll tables, beyond sections 7 to 9:

| Topic | Decision |
|---|---|
| Who may roll | `/check call` limits a check with `role` and `member` options (either one is enough). Scene participants come with scenes. |
| NPC opposed checks | The NPC rolls `d20 + npc_bonus` once when the check is called; players must beat that total (a tie goes to the NPC), so the check's DC is the NPC's total + 1. With a hidden DC or secret visibility the card shows `?` and the caller gets the NPC's roll privately. |
| Duels | `/check oppose` is between two members' characters (not your own two). Neither side sees the other's total until both rolled; the check then closes itself with the winner. Duel rolls skip bad-roll protection, since a roll can't fail on its own before the other side rolls. Help isn't offered on duels. |
| Crits | Luck 0 or below must confirm a natural crit with a second roll that also reaches the DC, as in combat; an unconfirmed one counts its total. |
| Bad-roll protection | Rolls on checks with a DC count (success = reaching the DC). Passive rolls don't, since the player never sees them. |
| Passive checks | "Present" means an approved character with a proxied post in that channel or thread in the last 7 days (a constant until `PRESENCE_DAYS` arrives with locations). The results and the Reveal button are private and last 15 minutes (Discord's limit for private messages). |
| Closing | The caller or staff close a check; open checks close themselves after `hours` (default 24, at most 168), checked every minute by `tasks/CheckTask.py`. Secret checks keep a Results button after closing. |
| Secret dice | `/dice … secret:true` replaces the planned `/gm roll`, so anyone can roll secretly. `/dice … dc:` treats a critical success as reaching the DC and a critical failure as missing it. |
| GM roll log | `/config singlechannels` sets `GM_ROLL_LOG` (a text channel). Secret check rolls, passive checks, secret `/dice` rolls and secret table rolls are copied there. |
| Grant | Staff only, once per roll. When the roll was made as a character the rewards go to it; otherwise staff pick a member and character. Items missing from the catalog are skipped with a note. The card updates and a public line says what was given. |
| Start fight | The roller or staff. Opens a fight (as `/combat start`) titled after the table, with the NPCs on the last side. NPCs missing from the bestiary are skipped with a note; a second press links the fight already started. |
| Nested tables | `[[name]]` can roll any table on the server, staff-only ones included (only the result shows). |
| Fantasy pack | 11 tables: Loot (Minor) and Loot (Major) (Luck-touched), Trinkets, Road and Wilderness Encounters, NPC Quirks, Tavern Names (with Tavern Adjective and Tavern Noun), Shop Names and Plot Hooks. Its items and NPCs are the fantasy gear pack's; `/table import` warns about any the server doesn't have. Omen decks wait for phase F. |
| Not yet | Weather modifiers on checks (phase B) and omen boons and banes (phase F, off by default). |

Code: `classes/checks/` (`Checks.py` rules, `CheckCard.py` the card, `CheckFlow.py` the Discord side, `RollLog.py`),
`classes/tables/` (`Tables.py` parsing and rolling, `TablePacks.py`, `TableFlow.py`), `views/checks/CheckButtons.py`,
`views/tables/TableButtons.py`, `views/buttons/Show.py`, `modules/Check.py`, `modules/Table.py`, `tasks/CheckTask.py`,
`resources/data/tables/fantasy.json`. `CombatFlow.start` now returns the fight it opened. Tests:
`tests/test_modules/test_checks.py` and `test_tables.py`.

## 21. Phases B to F as built

Choices made while building, beyond (or instead of) sections 1 to 15. Settings are set with `/config roleplay`
(autocomplete lists them all with their values), channels with `/config singlechannels`.

### Phase B: calendar, weather, locations, travel

| Topic | Decision |
|---|---|
| Commands | `/calendar setup | view | birthday`, `/calendar event add | remove | list`, `/time now | advance | set`, `/weather now | set`, `/location set | view | who | list | remove`, `/location region add | edit | remove | list`, `/location route add | remove | list`, `/travel`. Birthdays are `/calendar birthday` (not `/character birthday`). |
| Presets | Gregorian, and a fantasy year of twelve 30-day months with a 28-day moon (original names). Custom calendars are typed as `Name: days: season` lines. |
| Flowing time | `TIME_FLOW` ratios (`1:1`, `2:1`, `4:1`, `7:1`, `1:2`, `1:4`, `1:7`), moved every minute by `tasks/WorldTask.py` in whole parts of the day; a week of events at most is announced after a long jump. |
| Weather | Per region (or the server's own outside any region). A location whose climate differs from its region's reads the region's weather at the same place on its own ladder. Forced weather keeps until the weather would change next. |
| Presence | From `proxy_messages`: a character is at the location of its last post within `PRESENCE_DAYS`. A thread counts as its channel's location. Passive checks use the same setting now. |
| Travel | Origin is the channel's location, else where the character last posted. Without a route travel is instant with the destination's danger. Encounters post the route's (or destination's) table card at the destination, with its Grant and Start fight buttons; without a table the GM settles it. No GM-role ping (there is no GM role). |
| New channels | The new-channel prompt in `MODLOG` has a **Set up location** button (staff or GM role) that makes the channel a location named after it; it stays after answering Yes or No. |

### Phase C: scenes and the chronicle

| Topic | Decision |
|---|---|
| Commands | `/scene start | end | join | leave | pass | away | back | add | remove | move | host | pause | resume | card`, `/chronicle make | character` (instead of `/character scenes`). `/endscene` ends an open scene (host or staff); `rpenddate` is optional and defaults to the calendar. |
| Counting | `Proxy.handle` calls `SceneFlow.on_post` after the rewards; only the participant's scene character counts. Out-of-turn posts reorder as Rico decided. |
| Timers | Nudges, skips, free-mode reminders, idle warnings and resuming after a fight run every 5 minutes from `WorldTask`. A fight started from the scene's channel (or its thread's parent) pauses the scene; it resumes when that fight ends. |
| Chronicle | Read from the channel's history between the card and the end; check, dice and table cards become notes. Posted to `CHRONICLE` (a forum gets a thread; a text channel a message with a thread) with an HTML and a Markdown file and an **Add summary** button (players in it, or staff). |

### Phase D: languages and letters

| Topic | Decision |
|---|---|
| Commands | `/language add | edit | remove | list | known | pick | speak | grant | take | species`, message menu **Understand**, `/letter write | inbox | read | transit | intercept`. Staff grant languages with `/language grant`, not `/gm language`. |
| Starting languages | `/language pick` (not an interview step), up to `LANGUAGE_SLOTS` + 1 per 2 Intelligence above the stat base. |
| Markers | `{Elvish}` switches, `{}` goes back to the post's default, `{common}` (or the common language's name) to common. |
| Webhook buttons | The Understand button is sent on the post's last message; if the library refuses buttons on a webhook, the post goes out without it and the message menu still works. |
| Editing | A language post is edited as written (with markers) and scrambled again; long language posts (several messages) can't be edited. |
| Letters | Replies work from the DM. Interception is `/letter intercept` (read, hold, deliver, destroy) and only when `LETTER_INTERCEPT` is on; `/letter transit` shows only who wrote to whom unless it is on. Reported letters go to `MODLOG` with their text. |

### Phase E: factions, jobs, downtime, crafting

| Topic | Decision |
|---|---|
| Commands | `/faction add | edit | remove | list | standing | give | item` (standing changes are `/faction give`, not `/gm rep`), `/job post | cancel | list`, `/downtime spend | occupation`, `/craft recipes | make | projects | salvage | uncurse`, `/craft recipe add | remove | mishap | salvage | import`. |
| Shop | `Gear.buy` checks a faction item's tier and Vilified standing and prices it by standing. |
| Requirements | Forum tags can need faction standing (`/tagrule add kind:reputation faction tier`): checked against the character when it buys the item or learns the ability, and against a new character's Neutral standing when a species is picked. Occupations can need standing too (`/faction occupation`). |
| Carousing | +1 standing with the faction that holds the location (`/location set faction:`), on top of the rumor. |
| Flavor lines | `/downtime flavor` adds lines per occupation and outcome; one is picked at random, the default line otherwise. |
| Jobs | Forum thread per job; its name carries the state (🟢 open, 🟡 taken, ✅ done, ❌ failed, ⚪ cancelled) instead of forum tags, and finished jobs are locked. Partial success pays half and half the standing; items only on success. Player jobs hold `currency × slots` in escrow and refund what isn't paid out. |
| Downtime | Rolls count toward bad-roll protection. Occupation pay, stat, crit table and seer are set with `/downtime occupation`. |
| Crafting | Materials are catalog items of kind `material` and stack (`character_gear.quantity`). Projects set their ingredients aside up front; a bad failure takes a day of progress back, a crit on any day makes the result masterwork; projects don't make cursed items. Salvage keeps each listed material on a coin flip. The fantasy recipe pack (`resources/data/recipes/fantasy.json`) adds 11 materials (two of them tools), 11 recipes and salvage lists for the fantasy gear pack. |
| Quality in fights | `Loadout.character_stats` runs each owned weapon and the worn armor through `Crafting.adjust_combat`: masterwork +1 / cursed −1 to the item's `hit_mod` (weapons) and DT (armor, never below 0), applied after the catalog values are normalised. Lifting a curse takes it away at the next fight. |

### Phase F: rumors and omens

| Topic | Decision |
|---|---|
| Commands | `/rumor post | listen | plant | mark | pin | block | list`, `/omen draw | read | decks`. Server decks are made with `/table create deck:true` (one card per entry). |
| Listening | Once per real (UTC) day per character; carousing in downtime overhears at +2 without using the day's listen. Whispered rumors spread from `WorldTask` once heard 3 times. |
| Omens | Draws are per character and deck without replacement; a seer's reading counts as the other character's draw. A boon sets the bad-roll streak to armed; a bane adds −1 to the next check (`CheckFlow.make_roll`). |

New code: `classes/world/`, `classes/scenes/`, `classes/language/`, `classes/economy/`, `classes/flavor/`,
`classes/kernel/RoleplaySettings.py`, their `database/transactions/*Transactions.py`, `views/scenes/`, `views/letters/`,
`views/economy/`, the cogs in `modules/` and `tasks/WorldTask.py`; data in `resources/data/decks/` and
`resources/data/recipes/`. Tests: `test_world.py`, `test_scenes.py`, `test_languages.py`, `test_economy.py`,
`test_flavor.py`.

## 22. The pieces built afterwards

Rico asked for the pieces section 21 listed as not built, and for a GM role (16 November 2026). Migration
`0022_roleplay_extras` adds `occupations.faction_id` and `faction_tier`, `locations.faction_id` and
`craft_projects.flawed`.

| Topic | Decision |
|---|---|
| GM role | `/config gmrole` sets `GM_ROLE`. Its members run the roleplay tools as staff do: every roleplay command that needed Manage Messages, and the tools' own staff checks (checks, scenes, jobs, table rewards, chronicle summaries, reading every language). It doesn't give `/gm`, fight GM powers or `/config`. It is pinged on travel encounters. |
| Location button | See phase B: **Set up location** on the new-channel prompt. |
| Reputation tags | A tag rule of kind `reputation` stores `faction id × 10 + tier index`. Members' access counts standing as 0 (a new character's) unless a character is known, so the shop lists such items as locked for members, and buying with a character that qualifies works. |
| Occupation standing | `/faction occupation <occupation> <faction> <tier>`; checked when the occupation is picked (a new character is Neutral) and when an existing character changes occupation. |
| Carousing and flavor | See phase E. |
| Cursed projects | A bad failure on a project still takes a day back and now leaves a flaw. A flawed weapon or armor comes out cursed, a masterwork one plain (crit and flaw cancel), and other results aren't affected. |
| Job tags | Posting a job adds Open, Taken, Done, Failed and Cancelled tags to the job board when the bot may (Manage Channels, and room under Discord's 20 tags), and each job thread carries its state's tag; the emoji stays in the thread name. |
| Interview languages | New characters (and imports) pick their starting languages in the interview, after the stats, from the server's languages minus the common one and the species' own; **skip** leaves them for `/language pick`. The summary shows them and they are taught on submit (trimmed if the stats changed). |
| Kept as they are | Command placement differs from the spec's names in places (`/faction give` for `/gm rep`, `/calendar birthday`, `/chronicle character`, `/language grant`, `/letter intercept`, `/dice … secret` for `/gm roll`, `/craft uncurse`); the spec's names would duplicate these commands. |
