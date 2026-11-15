"""Downtime (design/roleplay-tools.md, section 12): once per real day a character spends downtime on work, study,
crafting or carousing. Only characters that made a proxied post in the last DOWNTIME_ACTIVE_DAYS days can, so idle
characters don't earn in the background.

Work rolls the occupation's stat against Average (12) and pays its pay (WORK_PAY by default, 50): a bad failure pays
nothing, a failure half, a success all, a strong success half as much again and a crit double, plus a roll on the
occupation's table. Without an occupation it is odd jobs: half pay, and the player picks the stat. Study rolls
Intelligence against Average: success +1, strong +2; STUDY_DAYS points teach a language partly, twice that fluently.
"""
import random
from datetime import datetime, timedelta, timezone

from classes.checks import Checks
from classes.combat import Fortune
from classes.characters.Special import Special
from classes.kernel import RoleplaySettings
from database.database import Characters
from database.transactions.ProxyTransactions import ProxyTransactions
from resources.configs.ConfigMapping import ConfigMapping

WORK = "work"
STUDY = "study"
CRAFT = "craft"
CAROUSE = "carouse"
ACTIVITIES = [WORK, STUDY, CRAFT, CAROUSE]
DC = Checks.DCS["average"]
PAY_SHARE = {Checks.CRIT : 2.0, Checks.STRONG : 1.5, Checks.SUCCESS : 1.0, Checks.FAILURE : 0.5, Checks.BAD : 0.0,
             Checks.FUMBLE : 0.0}
ODD_JOBS_SHARE = 0.5
STUDY_POINTS = {Checks.CRIT : 2, Checks.STRONG : 2, Checks.SUCCESS : 1}
FLAVOR = {
	Checks.CRIT : "A day to remember: everything went right.",
	Checks.STRONG : "A good, honest day's work.",
	Checks.SUCCESS : "The work got done.",
	Checks.FAILURE : "A slow day; only half the pay.",
	Checks.BAD : "A mishap: no pay today.",
	Checks.FUMBLE : "A disaster of a day: no pay, and a story to tell.",
}


# ============================================================
def day_key(now: datetime, reset_hour: int) -> str :
	"""The downtime day a moment falls in; a new day starts at reset_hour (UTC)."""
	return (now - timedelta(hours=reset_hour)).date().isoformat()


# ============================================================
def next_reset(now: datetime, reset_hour: int) -> datetime :
	start = (now - timedelta(hours=reset_hour)).replace(hour=0, minute=0, second=0, microsecond=0)
	return start + timedelta(days=1, hours=reset_hour)


# ============================================================
def pay(base: int, outcome: str, odd_jobs: bool = False) -> int :
	share = PAY_SHARE.get(outcome, 0) * (ODD_JOBS_SHARE if odd_jobs else 1)
	return int(base * share)


# ============================================================
def active(character: Characters, now: datetime | None = None) -> bool :
	"""Whether the character posted recently enough for downtime."""
	days = RoleplaySettings.number(character.guild_id, ConfigMapping.DOWNTIME_ACTIVE_DAYS)
	if days <= 0 :
		return True
	last = ProxyTransactions().last_post_at(character.id)
	if last is None :
		return False
	last = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
	return (now or datetime.now(timezone.utc)) - last <= timedelta(days=days)


# ============================================================
def roll(character: Characters, stat: str, bonus: int = 0, rng: random.Random | None = None) :
	"""A downtime roll: the stat against Average, with bad-roll protection. Returns (result, first roll or None)."""
	stats = Checks.stats_of(character)
	base = Special.rules(character.guild_id).base

	def make() :
		return Checks.roll(stats, stat, DC, base, bonus, None, rng)

	return Fortune.for_character(character.id, make, lambda result : result.success, lambda result : result.total)


# ============================================================
def study_stage(points: int, study_days: int) -> str | None :
	"""What points of study have taught: None, partial or fluent."""
	if points >= 2 * study_days :
		return "fluent"
	if points >= study_days :
		return "partial"
	return None
