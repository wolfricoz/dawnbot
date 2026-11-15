# Characters, proxying, species and gear: design

Status: designed in the interview on 2026-11-14; phases 1 to 5 are implemented (migrations 0004 to 0009).
Combat is out of scope for this round. Characters come first, and combat gets its own round afterwards.

Decisions made while building, beyond what is written below:
- A member's server level is the number of level roles their XP has reached.
- Species changes to the starting stats are each at most 5 up or down.
- Starting gear allows one of each item; the most expensive armor bought is worn.
- An imported character waits for review on its new server like a new one; the original is left as it is.

## 1. Scope

**In scope**

- Server-defined character sheets, filled in through a DM interview
- Staff approval, with approved characters posted to a character forum
- Proxying in the style of Tupperbox: webhooks, prefix/suffix triggers, autoproxy per channel
- Per-character XP, levels and currency. User XP stays and still drives the level roles
- SPECIAL stats (Fallout 1/2 style) using point-buy or rolling, with points earned through levels
- Player-made species with SPECIAL caps, posted to a species forum
- Server-defined roles/occupations, each with an optional limit on how many characters can hold it
- A gear catalog per server (weapons and armor) with genre packs, a shop, an inventory and GM tools
- Retiring, un-retiring, deleting, and importing characters from another server
- Restrictions driven by forum tags (species and gear)

**Out of scope (later)**

- Combat changes: gear stats, effects and balance, plus Fallout derived stats (HP, AP, AC)
- Skills, traits and perks
- Custom stat systems (renaming or replacing SPECIAL)
- Content for genre packs beyond fantasy (the format supports all four)

## 2. Decisions

| Topic | Decision |
|---|---|
| Character scope | Characters belong to one server. Growth (XP, level, currency) is tracked per server. |
| Import | A snapshot copy into another server: name, avatar, prefix/suffix and info fields only. XP, stats, gear and currency start fresh. The copy goes through review. |
| XP | A proxied message gives XP to **both** the character and the user. An unproxied message gives user XP only. Level roles stay on user XP. |
| Recalculate | Rebuilds character XP from dawnbot's own proxy log. It does not scan history. A character's level never goes down. |
| Approval | Every character needs staff approval. Staff means anyone with `manage_messages`. Reviews go to their own review channel with Approve / Deny buttons. A denial asks for a reason, which gets DM'd to the player. |
| After approval | The character is posted to the character forum (`CHARACTER`), one thread per character, kept in sync. Re-approval after an edit is a server setting. |
| Character cap | A server setting, default 3. Retired characters don't count. |
| Retire | Retiring stops proxying, frees a cap slot and handles the thread as configured. A retired character can come back (it counts toward the cap again and needs re-approval) or be deleted. |
| Roleplay channels | `XP_CHANNELS` is the roleplay channel list. Proxying outside it is a setting, default **off**. |
| Short messages | A proxied message under 300 characters in a roleplay channel is **deleted and not proxied**, the same as a normal message there. |
| New channels | A new channel triggers a "add to roleplay channels?" Yes / No prompt in `MODLOG`. Bulk creation (`/template apply`, `/archive restore`) does **not** skip it. |
| Triggers | Prefix and suffix, unique per user per server. Autoproxy is set per channel. |
| Proxied message controls | ❌ to delete, a context-menu action to edit, ❓ to look up the author. Moderators can delete too. |
| Replies | A "replied to @user" line that pings, honouring the reply's ping toggle. Replying to a proxied message pings the player behind it. |
| Avatars | Stored in a central storage guild (in `.env`). Links are refreshed when they expire. |
| Sheet | Defined per server. Field types are short text, long text, number and multiple choice, each required or optional, with a max length. New servers get a default sheet. |
| Sheet changes | Existing characters are left alone. Any new required questions are asked the next time the character is edited. |
| Extra fields | Players can always add their own info fields on top of the sheet (`add_info` and the related commands stay). |
| Interview | Runs in DMs, saved in the database, with no timeout. One interview at a time per user. `back` / `skip` / `cancel` and a final summary. |
| SPECIAL | Fallout 1/2 defaults: each stat starts at 5, plus 5 bonus points, minimum 1, maximum 10. Stats can be lowered to free points. All numbers are server settings. |
| Rolling | Allowed alongside point-buy by default, and a server can restrict it to one method. 7 rolls of `2d6−2` (each kept between 1 and 10), assigned to stats by the player. The total can never exceed the point-buy total, and a roll over it is redone automatically. Rerolls are unlimited. |
| Levels | Reaching level L takes `LEVEL_BASE × L(L−1)/2` XP (default base 1000, the Fallout 1/2 curve). Each level gives `POINTS_PER_LEVEL` SPECIAL points (default 1), which the player spends without review. A respec needs re-approval. |
| Existing characters | **Deleted** in the migration. The old system was never really used. |
| Species | Made by players (description, benefits, drawbacks, SPECIAL caps and starting modifiers), reviewed by staff, and posted to a species forum. Once approved, anyone can use them unless a tag restricts them. Anyone can create one by default, and staff can limit that. |
| Species caps | Changes balance out by points: raising caps by +N means lowering others by −N in total. A species' stat limits stay between −2 and 13. |
| Occupations | Staff define a list of roles/occupations per server, and each character picks one. Each occupation has an optional limit on how many characters can hold it, unlimited by default. Pending characters hold a place. An occupation can be locked behind a server level, a role or staff. |
| Defaults | Economy mode is on. Re-approval triggers on lore edits only. A retired character's thread gets locked, not deleted. |
| Interim combat | Until the combat round, combat reads a character's equipped armor from the new inventory. |
| Restrictions | Tags on forum threads, each linked to a requirement: a role, a minimum **server level**, staff-only, or event-only. |
| Gear | A catalog per server of weapons and armor, with importable genre packs (fantasy, post-apocalyptic, sci-fi, modern; fantasy first). Gear belongs to characters, with no limit on how much a character carries. One armor is equipped at a time; weapons are all carried. |
| Gear requirements | SPECIAL minimums, plus three effects: a penalty when a requirement isn't met, a bonus when it is, and a free-text effect per item. The numbers get worked out in the combat round. |
| Getting gear | Bought at creation or later through `/shop`. Event-only or staff-given items are hidden from the shop and granted by a GM. Level-locked items show in the shop as **locked**. |
| Losing gear | The player or a GM (`manage_messages`) can mark gear lost or broken, or sell it. Selling returns 30% of its value. |
| Economy | A server setting: **free mode** (no currency) or **economy mode**. |
| Currency | Belongs to the character and is earned mainly by roleplaying (proxied messages). Starting amount is 3000. GMs can give or take it. Players can't move it between their own characters. The old per-user currency is removed. |

## 3. Data model

New and changed tables (Alembic migration `0004`).

### characters (changed)

| Column | Notes |
|---|---|
| `id`, `uid`, `guild_id`, `name` | as now |
| `status` | `pending`, `approved`, `denied`, `retired` |
| `prefix`, `suffix` | triggers, unique per (`uid`, `guild_id`) |
| `avatar_id` | FK to `stored_images` |
| `species_id` | FK to `species`, nullable |
| `occupation_id` | FK to `occupations`, nullable |
| `strength` … `luck` | the seven SPECIAL stats |
| `stat_method` | `point_buy` or `rolled` (shown on the review card, along with `rerolls`) |
| `rerolls` | the number of rerolls used |
| `xp`, `level` | per character |
| `unspent_points` | replaces `prestige` (renamed) |
| `currency` | per character |
| `forum_thread_id`, `review_message_id` | Discord ids |
| `imported_from` | the source character id, when the character is an import (kept as a plain number, since the source can be deleted) |
| `approved_by`, `approved_at` | |

`armor` (FK) is removed. Gear moves to `character_gear`. See "Interim combat" in section 11.

### character_info (changed)

- `value` becomes `Text` so a long backstory fits.
- `sheet_field_id` is added as a nullable FK. Null means an extra field the player added.

### sheet_fields (new)

`id`, `guild_id`, `position`, `section` (the heading it's grouped under on the sheet, e.g. "Appearance"), `label`, `help` (the hint shown with the question, e.g. "up to 3"), `type` (`short`, `long`, `number`, `choice`), `required`, `max_length`, `min_value`, `max_value`, `choices` (JSON).

### drafts (new)

These hold the state of a DM interview. They're used for creating, editing, importing and creating species.

`id`, `uid` (**unique**, so one interview per user), `guild_id`, `kind` (`create`, `edit`, `import`, `species`), `target_id` (the character or species being edited), `step`, `answers` (JSON), `rolled_values` (JSON), `rerolls`, `created_at`, `updated_at`.

For an edit that needs re-approval, the changes wait in the draft and are applied when approved. The last approved version keeps proxying in the meantime.

### proxy_messages (new)

`message_id` (PK), `character_id`, `uid`, `guild_id`, `channel_id`, `length`, `xp_awarded`, `currency_awarded`, `deleted`, `created_at`.

This table is the source for recalculating XP, the ❓ author lookup, edit and delete permissions, and reply pings.

### autoproxy (new)

`uid`, `channel_id` (unique together), `guild_id`, `character_id`.

### stored_images (new)

`id`, `storage_channel_id`, `storage_message_id`, `url`, `expires_at`.

### species (new)

`id`, `guild_id`, `creator_uid`, `name`, `description`, `benefits`, `drawbacks`, `status` (`pending`, `approved`, `denied`), `stat_caps` (JSON: the max per stat), `stat_modifiers` (JSON), `forum_thread_id`.

### occupations (new)

`id`, `guild_id`, `name`, `description`, `max_holders` (nullable; null means unlimited, which is the default), `min_level` (nullable, server level), `role_id` (nullable), `staff_only`, `position`.

Occupations have no forum, so their restrictions are stored directly on the row instead of coming from tags.

### tag_requirements (new)

`id`, `guild_id`, `forum_channel_id`, `tag_id`, `kind` (`role`, `level`, `staff_only`, `event`), `value` (a role id or a level).

### gear_items (new)

These are the server's catalog. They replace the global `armors` and `weapons` tables once combat moves over.

`id`, `guild_id`, `kind` (`weapon`, `armor`), `name`, `description`, `price`, `requirements` (JSON, e.g. `{"strength": 8}`), `effect_met`, `effect_unmet`, `effect` (text), `combat` (JSON, reserved for the combat round: dice/modifier/hit chance, or HP/AP/AC), `forum_thread_id`, `pack` (the source genre pack, if imported).

### character_gear (new)

`id`, `character_id`, `gear_item_id`, `equipped`, `status` (`owned`, `lost`, `broken`, `sold`), `source` (`creation`, `shop`, `granted`), `price_paid`, `changed_by`, timestamps.

At most one armor with `equipped = true` per character.

### currency_transactions (new)

`id`, `character_id`, `amount`, `reason` (`start`, `roleplay`, `buy`, `sell`, `gm_give`, `gm_take`), `actor_uid`, `created_at`.

This is a ledger for disputes and audits.

### Removed

- `experience.currency`
- `characters.armor`
- every existing row in `characters`, which also removes their `character_info` and `combat_instance_entities` rows through the cascade

## 4. Settings

New `ConfigMapping` keys, plus two entries in `.env`.

| Key | Type | Default | Notes |
|---|---|---|---|
| `XP_CHANNELS` | list | (existing) | the roleplay channels |
| `CHARACTER` | channel | (existing) | the character forum |
| `CHARACTER_REVIEW` | channel | none | the staff review queue |
| `SPECIES_FORUM` | channel | none | |
| `GEAR_FORUM` | channel | none | optional; needed only for tag restrictions on gear |
| `PROXY_OUTSIDE_RP` | toggle | off | |
| `CHARACTER_CAP` | setting | 3 | |
| `REAPPROVAL_ON_EDIT` | setting | `lore` | `none` / `lore` (sheet answers, avatar, name, species) / `all`. Spending points never needs review; a respec always does. |
| `RETIRE_THREAD` | setting | `lock` | `lock` (lock and archive) or `delete` |
| `STAT_METHOD` | setting | `both` | `both` / `point_buy` / `rolled` |
| `STAT_BASE` | setting | 5 | |
| `STAT_BONUS` | setting | 5 | |
| `STAT_MIN` | setting | 1 | |
| `STAT_MAX` | setting | 10 | |
| `LEVEL_BASE` | setting | 1000 | |
| `POINTS_PER_LEVEL` | setting | 1 | |
| `SPECIES_CREATION` | setting | `everyone` | `everyone` / `staff` / `off` |
| `ECONOMY` | setting | `economy` | `economy` / `free` |
| `STARTING_CURRENCY` | setting | 3000 | |

`.env`: `STORAGE_GUILD`, `STORAGE_CHANNEL`.

### Default sheet

New servers get this sheet, based on the one the community already uses. Name, occupation and species are built-in steps of the interview, so they aren't sheet fields: occupation comes from `/occupation`, and species links to its entry in the species forum. "Required" follows the `*` marks in the original sheet. Help texts are shown with each question.

| Section | Field | Type | Required | Help / limits |
|---|---|---|---|---|
| Basic information | Known alias | short | yes | |
| | Age | number | yes | minimum 18 |
| | Relationship status | short | yes | |
| | Sexual orientation | short | yes | |
| | Gender representation | short | yes | |
| Appearance | Height | short | yes | |
| | Weight | short | yes | |
| | Physical description | long | no | optional if the avatar shows it |
| | Apparel | long | yes | |
| | Voice | short | no | |
| | Distinguishing features | long | no | tattoos, scars, etc. |
| Personality | Personality | long | no | traits, or a description of the character's personality |
| About | Strengths | long | no | up to 3 |
| | Weaknesses | long | no | up to 3 |
| | Fears | long | no | up to 3 |
| | Non-combat skills | long | yes | max 5 |
| | Interests / quirks | long | no | |
| | Known associates | long | no | |
| | Religion | short | no | |
| | Goals / ambitions | long | yes | |
| | Past occupations | long | no | |
| Character history | History | long | no | |
| Combat | Combat archetype | choice | no | Spellcaster / Melee / Ranged |
| | Armor proficiency | choice | no | Unarmored / Light / Medium / Heavy |

The Combat section starts with an info note, "Combat", that points to `/ability`, the shop and `/gear proficiency`; the review card leaves it out.

Magic school, Weapon proficiencies, Shield, Magics and Abilities used to be free-text questions here. The combat round removed them: weapons, abilities and magic can only come from the bot's own systems (the gear catalog and the effect catalog). Those labels can't be added back as questions or extra fields, and `/ability import_sheets` turns old answers into blank abilities. See design/combat.md, section 1.

## 5. Commands

### Characters (`/character`)

| Command | Who | Notes |
|---|---|---|
| `create` | player | Checks the cap and that DMs are open, then starts the DM interview |
| `edit <character>` | player | Starts a DM interview, beginning with any new required questions |
| `import <character>` | player | Run on the target server. Autocomplete lists the player's characters on other servers |
| `spend <stat> [amount]` | player | Spends unspent points, up to the cap (including species caps) |
| `respec <character>` | player | Redistributes stats, then goes back for re-approval |
| `retire` / `unretire` | player | `unretire` checks the cap and sends the character back for review |
| `delete` | player | Allowed in any status |
| `profile` / `show` / `list` | anyone | Adds Luck to the embeds (currently missing) |
| `add_info` / `edit_info` / `remove_info` / `move_info` | player | Kept for extra fields |
| `autoproxy <character\|off>` | player | Applies to the current channel |

### Sheet (`/sheet`, server owner or staff)

`field add | edit | remove | move | list`, `preview`, `reset` (back to the default sheet).

`template` (anyone): the server's sheet as blank text to copy, fill in elsewhere and paste into the interview.

### Species (`/species`)

`create` (DM interview), `edit`, `list`, `view`. Approve and deny happen through the review buttons.

### Occupations (`/occupation`)

- `add <name> [limit] [description] [min_level] [role] [staff_only]`, `edit`, `remove`, `move` (staff). Leaving `limit` out means unlimited.
- `list` (anyone): shows each occupation as filled/limit, for example `Guard 3/5` or `Merchant 7/∞`.
- Changing occupation goes through `/character edit`.

### Gear

- `/shop [kind]`: browse the catalog (locked items marked with the reason) and buy
- `/inventory [character]`
- `/gear equip | unequip | sell | lose | break`: player actions on their own gear
- `/armory add | edit | remove | list | import <pack>` (staff): manage the catalog
- `/gm gear grant | take | lose | break`, `/gm currency give | take` (`manage_messages`)

### Staff tools

- `/tagrule add | remove | list`: link a forum tag to a requirement
- `/proxy recalculate [character]`: rebuild XP from the proxy log

### Context menus and reactions

- "Edit proxied message" (the author)
- ❌ delete (the author or a moderator)
- ❓ who wrote this (DMs the person who asked)

## 6. Flows

### 6.1 DM interview (create)

1. `/character create` checks the cap and whether DMs are open, and makes sure there's no interview already in progress. Then it creates a `drafts` row.
2. Each DM question names the server and the character. The order is:
   - built-in fields: name, then prefix/suffix (checked for uniqueness), then avatar (an image upload, png/jpg/webp/gif up to 8 MB, uploaded to storage right away)
   - species (a multiple-choice list filtered by tag requirements)
   - occupation (a multiple-choice list; full occupations show as full and can't be picked), skipped if the server has none
   - the server's sheet fields
   - SPECIAL: point-buy or roll, depending on `STAT_METHOD`, within the species caps
   - starting gear (a shop with `STARTING_CURRENCY`; free picks in free mode)
3. `back`, `skip` (optional fields only) and `cancel` work at every step. Every answer is saved as it comes in, so a restart loses nothing.
4. A summary lets the player fix any answer, then submit.

**Pasting a sheet** (`classes/characters/SheetPaste.py`). At any step of a create, edit or import, the player can paste a whole sheet written elsewhere (a character site, a document, an old post) in one message. Typing `template` in the DM sends the server's blank sheet to fill in, the same as `/sheet template`.
- The paste is read as `Label: value` lines, `Label - value` (only for labels the server asks), and headings on their own line with paragraphs under them. Required marks (`*`), hints in brackets, bullets and markdown are ignored.
- Labels match the sheet's questions by name, by a part of a name (`Goals` for `Goals / ambitions`), by the words of a name (`Gender` for `Gender representation`) or by a synonym (`Backstory` for `History`). `Name`, `Proxy` (or `Prefix` and `Suffix`), `Species`/`Race` and `Occupation` fill the interview's own steps. An image sent with the paste becomes the picture.
- A message counts as a sheet when it answers at least 2 questions (3 while answering a long question, where a label or two can come up in passing).
- Every answer goes through the same checks as a typed one, with some allowances: `24 years old` for a number, `Melee fighter` for the option Melee. Refused answers are listed and asked again.
- Labels the sheet doesn't ask become extra fields on a new character. An edit lists them and points to `/character add_info`.
- After a paste, the interview asks only the required questions that are still missing, then stats, gear and the summary. Optional questions that were left out can be answered from the summary.

**SPECIAL picker** (`classes/characters/StatPanel.py`, `views/multiselect/StatPicker.py`). When the interview reaches the stats step, a components v2 message follows the question, with one menu per stat. Typing seven numbers still works.
- Point-buy: each menu lists only the values the points left can pay for, with the cost of each option, and the heading shows the points left. Unspent points are kept, as with typing.
- Rolling: each menu lists the rolled values not placed on another stat yet (equal values share one option). Confirm unlocks once every value is placed, and Reroll rolls again and counts the reroll.
- Picks are kept in the draft (`stat_work`, `stat_assign`), and the menus are dynamic items found by who pressed them, so the picker survives a restart. Confirm feeds the values to the interview as if they were typed. A picker whose draft has moved past the stats step closes when it's pressed.
5. Submitting creates the character as `pending` and posts the review card.

### 6.2 Review

- The review card shows: avatar, sheet answers, extra fields, species, stats (with the method and the number of rerolls), starting gear, and "imported from" if it's an import.
- **Approve**: status becomes `approved`, the character is posted (or updated) in the `CHARACTER` forum, and the card is marked done.
- **Deny**: a modal asks for the reason, which gets DM'd to the player. The character stays `denied`, and the player can edit and resubmit.
- The forum post uses several messages when the sheet is longer than one embed allows (6000 characters total, 1024 per field).

### 6.3 Proxying

On each guild message:

1. Skip bots, webhooks and DMs.
2. Look for the user's `approved` characters on this server. Match the prefix or suffix, preferring the longest match. Otherwise use autoproxy for this channel. A message that starts with `\` is never proxied (an escape for when autoproxy is on).
3. Check the channel is a roleplay channel (threads count through their parent), unless `PROXY_OUTSIDE_RP` is on.
4. In a roleplay channel, if the text left after removing the trigger is under 300 characters: delete the message, tell the player why, and stop.
5. Get the channel's webhook, creating and caching it if needed. Threads use the parent channel's webhook with `thread=`.
6. If the message is a reply, add the "replied to" line. Ping only if the original reply had its ping on. For a proxied target, ping the real player.
7. Send the message with the character's name and a refreshed avatar link, copying attachments over.
8. Delete the original, write `proxy_messages`, then give XP and currency to the character and XP to the user.

The bot needs Manage Webhooks and Manage Messages. Missing permissions go through `PermissionNotice`.

The existing 300-character rule in `ProgressionListener` must not handle messages the proxy pipeline already took over.

### 6.4 XP, levels and recalculation

- Character XP for a message is `length / XP_GAIN`, and currency is `length / CURRENCY_GAIN`. User XP works as it does now.
- The level is the largest L with `LEVEL_BASE × L(L−1)/2 ≤ xp`. Each new level adds `POINTS_PER_LEVEL` to `unspent_points` and gets announced in `ANNOUNCEMENT`.
- A deleted proxied message is marked `deleted` in the log.
- `/proxy recalculate` recomputes XP from the log entries that aren't deleted. It doesn't touch currency, since that may already be spent.
- **A level never goes down.** If a recalculation lowers XP, the character keeps its level and every point that level earned. It reaches the next level once its XP passes that level's threshold again. If a recalculation raises XP, the character levels up as normal.

### 6.5 Avatars

- An image is uploaded to `STORAGE_CHANNEL` as a message, and the channel and message ids are stored.
- Before use, the bot checks the `ex=` expiry in the link and refreshes it through Discord's attachment refresh endpoint when the link is close to expiring.
- Replacing or deleting an avatar deletes the old storage message. A denied character's image gets deleted too.

### 6.6 New-channel prompt

`on_guild_channel_create` (text or forum channels) posts "Add #channel to the roleplay channels?" with Yes / No buttons in `MODLOG`. Only `manage_messages` users can answer, and the buttons keep working after a restart.

### 6.7 Import

`/character import` on the target server copies the name, avatar (a new storage copy), prefix/suffix and info fields into a draft. Info fields that match the target server's sheet labels are filled in. The interview then asks the remaining questions: species, required fields, stats and gear. The import ends as `pending` and goes through review. The source character is left as it was.

### 6.8 Retire, un-retire and delete

- **Retire**: `approved` becomes `retired`. Proxying and autoproxy stop, and the thread is locked or deleted according to `RETIRE_THREAD`.
- **Un-retire**: checks the cap, then the character goes back to `pending` and through review.
- **Delete**: works in any status. It removes the character, its storage image, its thread (depending on the setting) and its gear rows. Proxy log rows are kept but no longer point to the character.

### 6.9 Species

- `/species create` runs as a DM interview: name, description, benefits, drawbacks, then SPECIAL cap changes and starting modifiers.
- **Balancing:** cap changes must add up to 0 (raising one cap by +N means lowering others by −N), and so must the modifiers. A species' stat limits (min and max) stay between −2 and 13.
- Staff review it with the same card and buttons. Once approved, it's posted to `SPECIES_FORUM`.
- New servers start with a `Human` species with no changes.

### 6.10 Occupations

- Staff define each server's occupations. Each one has an optional `max_holders`, unlimited by default.
- An occupation can require a minimum server level, a role, or staff assignment (`staff_only`). Occupations a player can't pick are shown as locked, with the reason.
- **What counts toward the limit:** `approved` and `pending` characters both count, so a submission reserves its place and two reviews can't overfill an occupation. `retired`, `denied` and deleted characters free the place.
- The Approve button checks the limit again before approving, in case staff lowered it in the meantime.
- Lowering a limit below the current number of holders doesn't remove anyone. It only blocks new picks until enough places are free.
- Removing an occupation that characters still hold is refused until they've switched to another one, or staff confirm clearing it from those characters.
- Switching occupation is an edit, and it follows `REAPPROVAL_ON_EDIT` like the rest of the sheet's lore.

### 6.11 Tag restrictions

- Owners create tags in the species or gear forum. `/tagrule` links a tag to `role:<id>`, `level:<n>` (server level), `staff_only` or `event`.
- Dawnbot reads the thread's current tags (cached, and refreshed when the thread is updated), so retagging takes effect immediately.
- What each requirement means:
  - **Species:** if requirements aren't met, the species is hidden from the choice list. `staff_only` species can only be assigned by staff.
  - **Gear:** `role` and `level` requirements make an item show as locked in `/shop` along with the reason. `event` and `staff_only` items are hidden and can only be granted.

### 6.12 Gear and the economy

- Genre packs are JSON files in `resources/data/gear/<genre>.json`, with **fantasy first**. `/armory import` copies a pack into the server's catalog (and creates forum posts if `GEAR_FORUM` is set).
- **Economy mode:** buying costs `price`, and selling returns 30% of `price_paid`. Every change is logged in `currency_transactions`.
- **Free mode:** no currency is shown, buying is free, and selling returns nothing.
- Lost and broken items stay in the inventory history with their status. They aren't counted as carried.
- SPECIAL requirements don't block owning or equipping. They decide whether `effect_met` or `effect_unmet` applies, and the numbers get worked out in the combat round.

## 7. Migration (`0004`)

1. Create the new tables.
2. **Delete all characters**, which also deletes their info and combat entries through the cascade. Drop `characters.armor`, rename `prestige` to `unspent_points`, and add the new columns.
3. Drop `experience.currency`.
4. Change `character_info.value` to `Text` and add `sheet_field_id`.
5. Add a `Human` species and the default sheet fields for every existing server. New servers get them through `ServerSetup`.

Before running this against a real database, the person running it confirms that existing characters will be deleted.

## 8. Implementation phases

1. **Foundation.** The migration, the settings, image storage, the sheet and default sheet, the character rework (status, SPECIAL rules, levels), the DM interview engine, review, and the forum posts.
2. **Proxying.** The webhook pipeline, triggers, autoproxy, reactions and context menus, replies, the proxy log, XP and currency, recalculation, and the new-channel prompt.
3. **Species, occupations and tag rules.**
4. **Gear.** The catalog, the fantasy pack, the shop, inventory, GM tools and economy mode.
5. **Import and retire/un-retire,** plus polish.

Each phase comes with tests through `tests/run_tests.py` and updated docs from `docsGenerator.py`.

## 9. Later

- The combat round: gear stats and effects, Fallout derived stats, and moving combat to `gear_items` and `character_gear`
- Skills (Fallout's fixed list), traits and perks
- Custom stat systems
- Pack content for post-apocalyptic, sci-fi and modern

## 10. Still open

- **Two combat systems.** The default sheet's combat section uses its own d20 rules: weapon proficiency tiers (Excellent +2 to Awful −2), archetypes, armor proficiency, spells and abilities. This round uses SPECIAL and a gear catalog. The combat round has to decide how they fit together, for example whether proficiency tiers become data dawnbot understands, and how SPECIAL feeds attack rolls and AC. Until then, the sheet's combat fields are plain text. (Settled in the combat round: proficiency lives on the character's weapon records, and spells and abilities are built from the effect catalog; the free-text fields are gone.)
- **A species stat minimum below 1** (down to −2) means a character of that species can have a negative stat. Point-buy and rolling then need to allow values below 1 for that species, and combat's `floor(stat × 0.5)` gives a negative modifier. That seems intended, but confirm it when the combat round starts.

## 11. Risks

- **Interim combat.** Combat currently reads `characters.armor` and the global `armors` table. Phase 1 adds a small adapter so combat reads the equipped armor from `character_gear` instead. Phase 4 maps that armor's catalog entry onto the HP/AP/AC/hit-chance values combat expects. Until a character has armor equipped, combat uses the defaults from the `armors` table. The global `weapons` table isn't tied to characters, so it stays as it is until the combat round.
- **Webhook limits.** Discord allows 15 webhooks per channel, and dawnbot uses one per channel. Webhook sends are rate-limited per webhook, which matters in busy channels.
- **DM reliability.** Players with closed DMs can't create characters. This is checked up front.
- **Forum tag limit.** Each forum allows 20 tags, which caps how many distinct restrictions a forum can have.
