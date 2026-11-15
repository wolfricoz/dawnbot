"""Faction reputation (design/roleplay-tools.md, section 11): standing tiers, Charisma-scaled gains, rivals, and what
standing does to faction items in the shop.

Standing runs from -100 to 100: Vilified (-100 to -50), Disliked (-49 to -15), Neutral (-14 to 14), Liked (15 to 49),
Idolized (50 to 100). Gains are multiplied by 1 + 0.1 x Charisma modifier (at least x0.5); losses aren't. Gaining
standing with a faction costs half as much with each of its rivals (Rico's call). Faction items cost 20% less at
Idolized, 10% less at Liked and 25% more at Disliked; Vilified characters can't buy them.
"""
from classes.characters.Special import Special
from classes.combat import Rules
from database.database import Characters, Factions, GearItems
from database.transactions.EconomyTransactions import EconomyTransactions

MINIMUM = -100
MAXIMUM = 100
VILIFIED = "vilified"
DISLIKED = "disliked"
NEUTRAL = "neutral"
LIKED = "liked"
IDOLIZED = "idolized"
TIERS = [VILIFIED, DISLIKED, NEUTRAL, LIKED, IDOLIZED]
TIER_EMOJI = {VILIFIED : "☠️", DISLIKED : "👎", NEUTRAL : "😐", LIKED : "👍", IDOLIZED : "🌟"}
PRICE = {VILIFIED : None, DISLIKED : 1.25, NEUTRAL : 1.0, LIKED : 0.9, IDOLIZED : 0.8}
RIVAL_SHARE = 0.5


# ============================================================
def tier(value: int) -> str :
	if value <= -50 :
		return VILIFIED
	if value <= -15 :
		return DISLIKED
	if value < 15 :
		return NEUTRAL
	if value < 50 :
		return LIKED
	return IDOLIZED


# ============================================================
def meets(value: int, needed: str | None) -> bool :
	"""Whether a standing reaches a tier."""
	return needed is None or needed not in TIERS or TIERS.index(tier(value)) >= TIERS.index(needed)


# ============================================================
def scaled_gain(amount: int, charisma: int, base: int = 5) -> int :
	"""A gain scaled by Charisma; losses stay as they are."""
	if amount <= 0 :
		return amount
	return round(amount * max(0.5, 1 + 0.1 * Rules.modifier(charisma, base)))


# ============================================================
def clamp(value: int) -> int :
	return max(MINIMUM, min(MAXIMUM, value))


# ============================================================
def tier_text(value: int) -> str :
	current = tier(value)
	return f"{TIER_EMOJI[current]} {current.capitalize()} ({value:+d})"


class FactionFlow :

	# ============================================================
	@staticmethod
	def change(character: Characters, faction: Factions, amount: int, reason: str,
	           actor_uid: int | None = None, rivals: bool = True) -> list[str] :
		"""Changes a character's standing. Gains are scaled by Charisma and cost rivals half. Returns lines saying what
		changed."""
		base = Special.rules(character.guild_id).base
		change = scaled_gain(amount, character.charisma, base)
		lines = [FactionFlow._apply(character, faction, change, reason, actor_uid)]
		if rivals and change > 0 :
			loss = -int(change * RIVAL_SHARE)
			for rival_id in faction.rivals or [] :
				rival = EconomyTransactions().faction(int(rival_id))
				if rival is not None and loss :
					lines.append(FactionFlow._apply(character, rival, loss, f"rival of {faction.name}", actor_uid))
		return lines

	# ============================================================
	@staticmethod
	def _apply(character: Characters, faction: Factions, change: int, reason: str, actor_uid: int | None) -> str :
		before = EconomyTransactions().standing(character.id, faction.id)
		after = clamp(before + change)
		EconomyTransactions().set_standing(character.id, faction.id, after, after - before, reason, actor_uid)
		moved = f" · now {tier(after).capitalize()}" if tier(after) != tier(before) else ""
		return f"{faction.emoji or '⚑'} {faction.name}: {after - before:+d} ({after:+d}){moved}"

	# ============================================================
	@staticmethod
	def visible(character: Characters) -> list[tuple[Factions, int]] :
		"""The factions a character sees with its standing: hidden ones only once standing isn't 0."""
		standings = EconomyTransactions().standings(character.id)
		found = []
		for faction in EconomyTransactions().factions(character.guild_id) :
			value = standings.get(faction.id, 0)
			if faction.hidden and value == 0 :
				continue
			found.append((faction, value))
		return found

	# ============================================================
	@staticmethod
	def strongest(character: Characters, count: int = 3) -> list[tuple[Factions, int]] :
		return sorted([entry for entry in FactionFlow.visible(character) if entry[1]],
		              key=lambda entry : -abs(entry[1]))[:count]

	# == the shop ==

	# ============================================================
	@staticmethod
	def buy_problem(character: Characters, item: GearItems) -> str | None :
		"""Why a character can't buy a faction item, or None."""
		faction = EconomyTransactions().faction(getattr(item, "faction_id", None))
		if faction is None :
			return None
		value = EconomyTransactions().standing(character.id, faction.id)
		if PRICE[tier(value)] is None :
			return f"{faction.name} won't sell to {character.name} ({tier(value)})."
		needed = getattr(item, "faction_tier", None)
		if not meets(value, needed) :
			return f"{item.name} needs {needed.capitalize()} standing with {faction.name}; {character.name} is " \
			       f"{tier(value).capitalize()}."
		return None

	# ============================================================
	@staticmethod
	def price_for(character: Characters, item: GearItems, price: int) -> int :
		faction_id = getattr(item, "faction_id", None)
		if not faction_id or not price :
			return price
		multiplier = PRICE[tier(EconomyTransactions().standing(character.id, faction_id))] or 1.0
		return max(0, round(price * multiplier))
