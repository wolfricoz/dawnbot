"""Omens and fortune cards (design/roleplay-tools.md, section 15): drawing from the built-in decks (tarot, bones) or a
server's own decks (roll tables made as decks), without replacement until the deck runs out, once every OMEN_DAYS days.

With OMEN_EFFECTS on (it is off by default: cards are pure story, Rico's call), a card can be a boon, which arms
bad-roll protection for the next failed roll, or a bane, -1 on the next check. Seers (occupations marked seer) read for
other characters; that draw counts as the other character's.
"""
import json
import os
import random
from datetime import datetime, timedelta, timezone

from classes.combat import Fortune
from classes.kernel import RoleplaySettings
from database.database import Characters
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.FlavorTransactions import FlavorTransactions
from database.transactions.RollTableTransactions import RollTableTransactions
from resources.configs.ConfigMapping import ConfigMapping

DECK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "resources",
                        "data", "decks")
BOON = "boon"
BANE = "bane"
NONE = "none"
TABLE_PREFIX = "table:"
BANE_PENALTY = -1


# ============================================================
def built_in() -> dict[str, dict] :
	"""The built-in decks by key: {"title", "cards": [{"name", "upright", "reversed"?, "effect"?,
	"reversed_effect"?}]}."""
	decks = {}
	if not os.path.isdir(DECK_DIR) :
		return decks
	for filename in sorted(os.listdir(DECK_DIR)) :
		key, extension = os.path.splitext(filename)
		if extension != ".json" :
			continue
		with open(os.path.join(DECK_DIR, filename), encoding="utf-8") as file :
			decks[key] = json.load(file)
	return decks


# ============================================================
def deck_cards(guild_id: int, deck: str) -> tuple[str, list[dict]] | None :
	"""A deck's title and cards, from the built-in decks or the server's deck tables."""
	if deck.startswith(TABLE_PREFIX) :
		table = RollTableTransactions().get(int(deck[len(TABLE_PREFIX) :]))
		if table is None or table.guild_id != guild_id :
			return None
		cards = [{"name" : entry.text.split(":", 1)[0][:100], "upright" : entry.text}
		         for entry in RollTableTransactions().entries(table.id)]
		return table.name, cards
	data = built_in().get(deck)
	if data is None :
		return None
	return data.get("title", deck.capitalize()), data.get("cards", [])


# ============================================================
def decks(guild_id: int) -> list[tuple[str, str]] :
	"""(key, title) of every deck a server can draw from."""
	found = [(key, data.get("title", key.capitalize())) for key, data in built_in().items()]
	found += [(f"{TABLE_PREFIX}{table.id}", table.name) for table in RollTableTransactions().get_all(guild_id, "deck")]
	return found


# ============================================================
def next_draw_at(character: Characters) -> datetime | None :
	"""When the character may draw again, or None when it may now."""
	omen = character.omen or {}
	drawn = omen.get("drawn_at")
	if not drawn :
		return None
	when = datetime.fromisoformat(drawn) + timedelta(days=RoleplaySettings.number(character.guild_id,
	                                                                              ConfigMapping.OMEN_DAYS))
	return when if when > datetime.now(timezone.utc) else None


# ============================================================
def draw(character: Characters, deck: str, reader_uid: int | None = None,
         rng: random.Random | None = None) -> tuple[dict | None, str | None] :
	"""Draws a card for a character. Returns {"card", "deck", "orientation", "text", "effect"} or None and why not."""
	rng = rng or random
	found = deck_cards(character.guild_id, deck)
	if found is None or not found[1] :
		return None, "There is no such deck."
	title, cards = found
	wait = next_draw_at(character)
	if wait is not None :
		return None, f"{character.name} can draw again <t:{int(wait.timestamp())}:R>."
	history = FlavorTransactions().draws(character.id, deck)
	cycle = max([entry.cycle for entry in history] + [1])
	drawn = {entry.card for entry in history if entry.cycle == cycle}
	remaining = [card for card in cards if card["name"] not in drawn]
	if not remaining :
		cycle += 1
		remaining = list(cards)
	card = rng.choice(remaining)
	reversed_ = "reversed" in card and rng.random() < 0.5
	text = card["reversed"] if reversed_ else card["upright"]
	effect = (card.get("reversed_effect") if reversed_ else card.get("effect")) or NONE
	if not RoleplaySettings.toggle(character.guild_id, ConfigMapping.OMEN_EFFECTS) :
		effect = NONE
	FlavorTransactions().add_draw(character.id, deck, card["name"], cycle, reader_uid)
	omen = {"card" : card["name"], "deck" : deck, "effect" : effect, "used" : effect == NONE,
	        "drawn_at" : datetime.now(timezone.utc).isoformat()}
	changes = {"omen" : omen}
	if effect == BOON :
		changes["bad_streak"] = max(int(character.bad_streak or 0), Fortune.STREAK)
	CharacterTransactions().update(character.id, **changes)
	return {"card" : card["name"], "deck" : title, "orientation" : "reversed" if reversed_ else "upright",
	        "text" : text, "effect" : effect}, None


# ============================================================
def bane(character: Characters) -> bool :
	"""Whether the character carries an unused bane."""
	omen = character.omen or {}
	return omen.get("effect") == BANE and not omen.get("used")


# ============================================================
def use_bane(character_id: int) -> None :
	character = CharacterTransactions().get_by_id(character_id)
	if character is not None and bane(character) :
		CharacterTransactions().update(character_id, omen=dict(character.omen, used=True))
