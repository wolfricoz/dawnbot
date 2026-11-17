"""Lifestyle (design/economy.md, phase 6), off by default (LIFESTYLE).

Each character pays every week for how it lives: Destitute 0, Poor 70, Modest 250, Comfortable 700, Wealthy 1,750,
Aristocratic 5,000. A character without a choice lives Modestly. Destitute characters get −2 to haggling and Poor ones
−1; Comfortable and better have their Worn gear looked after for free each week; Wealthy and Aristocratic get +2 to
haggling and to listening for rumors. A character that can't pay drops to the best lifestyle it can afford (Destitute
is free). Choosing a lifestyle pays its first week straight away.
"""
from datetime import datetime, timedelta, timezone

from classes.kernel import RoleplaySettings
from database.database import Characters
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from resources.configs.ConfigMapping import ConfigMapping

DESTITUTE = "destitute"
POOR = "poor"
MODEST = "modest"
COMFORTABLE = "comfortable"
WEALTHY = "wealthy"
ARISTOCRATIC = "aristocratic"
TIERS = [DESTITUTE, POOR, MODEST, COMFORTABLE, WEALTHY, ARISTOCRATIC]
WEEKLY = {DESTITUTE : 0, POOR : 70, MODEST : 250, COMFORTABLE : 700, WEALTHY : 1750, ARISTOCRATIC : 5000}
HAGGLE = {DESTITUTE : -2, POOR : -1, WEALTHY : 2, ARISTOCRATIC : 2}
RUMOR = {WEALTHY : 2, ARISTOCRATIC : 2}
UPKEEP = {COMFORTABLE, WEALTHY, ARISTOCRATIC}
WEEK = timedelta(days=7)
REASON = "lifestyle"


# ============================================================
def on(guild_id: int) -> bool :
	return RoleplaySettings.toggle(guild_id, ConfigMapping.LIFESTYLE)


# ============================================================
def of(character: Characters) -> str | None :
	"""The character's lifestyle, or None when the server doesn't use lifestyles."""
	if not on(character.guild_id) :
		return None
	tier = getattr(character, "lifestyle", None)
	return tier if tier in TIERS else MODEST


# ============================================================
def haggle_bonus(character: Characters) -> int :
	return HAGGLE.get(of(character), 0)


# ============================================================
def rumor_bonus(character: Characters) -> int :
	return RUMOR.get(of(character), 0)


# ============================================================
def choose(character: Characters, tier: str, actor_uid: int | None = None,
           now: datetime | None = None) -> tuple[Characters | None, str | None] :
	"""Changes the character's lifestyle and pays its first week."""
	from classes.gear.Gear import Gear

	if not on(character.guild_id) :
		return None, "This server doesn't use lifestyles."
	if tier not in TIERS :
		return None, f"A lifestyle is one of {', '.join(TIERS)}."
	cost = WEEKLY[tier] if Gear.economy(character.guild_id) else 0
	if cost :
		_, problem = Gear.change_currency(character, -cost, REASON, actor_uid, note=f"{tier.capitalize()} week")
		if problem :
			return None, problem
	now = now or datetime.now(timezone.utc)
	return CharacterTransactions().update(character.id, lifestyle=tier, lifestyle_paid_until=now + WEEK), None


# ============================================================
def affordable(tier: str, currency: int) -> str :
	"""The best lifestyle up to this one the character can pay for."""
	for candidate in reversed(TIERS[:TIERS.index(tier) + 1]) :
		if WEEKLY[candidate] <= currency :
			return candidate
	return DESTITUTE


# ============================================================
def upkeep(character: Characters) -> int :
	"""Comfortable and better: Worn gear is looked after. Returns how many items were."""
	from classes.gear import Condition
	from database.transactions.CharacterGearTransactions import CharacterGearTransactions

	count = 0
	for entry in CharacterGearTransactions().get_all(character.id) :
		if Condition.of(entry) == Condition.WORN :
			Condition.restore(entry)
			count += 1
	return count


# ============================================================
def weekly(character: Characters, now: datetime | None = None) -> tuple[str, int] | None :
	"""Charges a character's week when it is due: (the lifestyle it now lives, what it paid), or None when nothing
	was due."""
	from classes.gear.Gear import Gear

	now = now or datetime.now(timezone.utc)
	if character.state != APPROVED or not on(character.guild_id) :
		return None
	paid_until = getattr(character, "lifestyle_paid_until", None)
	if paid_until is not None and paid_until > now :
		return None
	tier = affordable(of(character), character.currency) if Gear.economy(character.guild_id) else of(character)
	cost = WEEKLY[tier] if Gear.economy(character.guild_id) else 0
	if cost :
		_, problem = Gear.change_currency(character, -cost, REASON, None, note=f"{tier.capitalize()} week")
		if problem :
			tier, cost = DESTITUTE, 0
	start = paid_until if paid_until is not None and paid_until > now - WEEK else now
	CharacterTransactions().update(character.id, lifestyle=tier, lifestyle_paid_until=start + WEEK)
	if tier in UPKEEP :
		upkeep(character)
	return tier, cost


# ============================================================
def weekly_all(now: datetime | None = None) -> int :
	"""Charges every character whose week is due; returns how many were charged."""
	count = 0
	for character in CharacterTransactions().get_every_character() :
		if character.state == APPROVED and on(character.guild_id) and weekly(character, now) is not None :
			count += 1
	return count
