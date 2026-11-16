"""The economy report staff read with /economy report (design/economy.md).

It reads the currency ledger and the characters' balances: how much the server's active characters hold, the median,
last week's money coming in and going out by reason, the richest characters and the biggest earners. It tells staff
when prices or income need adjusting, and helps spot one-sided trades once trading exists.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import median

from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.CurrencyTransactions import CurrencyTransactions

DAYS = 7
TOP = 5
# How ledger reasons read in the report.
REASON_LABELS = {
	"start"    : "starting money",
	"roleplay" : "roleplay posts",
	"buy"      : "shop purchases",
	"sell"     : "selling gear",
	"gm_give"  : "given by GMs",
	"gm_take"  : "taken by GMs",
	"job"      : "jobs",
	"work"     : "downtime work",
	"escrow"   : "job rewards held",
	"refund"   : "refunds",
	"repair"   : "repairs",
	"refill"   : "ammunition refills",
	"trade_in" : "trades (received)",
	"trade_out" : "trades (given)",
	"pay"      : "payments between characters",
	"market"   : "market sales",
	"market_fee" : "market fees",
	"lodging"  : "rooms",
}


@dataclass
class EconomyReport :
	characters: int = 0
	total: int = 0
	median: int = 0
	# (reason, amount, changes), money in and money out
	income: list[tuple[str, int, int]] = field(default_factory=list)
	spending: list[tuple[str, int, int]] = field(default_factory=list)
	# (name, amount)
	richest: list[tuple[str, int]] = field(default_factory=list)
	earners: list[tuple[str, int]] = field(default_factory=list)


# ============================================================
def label(reason: str) -> str :
	return REASON_LABELS.get(reason, reason.replace("_", " "))


# ============================================================
def build(guild_id: int, now: datetime | None = None, days: int = DAYS) -> EconomyReport :
	now = now or datetime.now(timezone.utc)
	since = now - timedelta(days=days)
	active = [character for character in CharacterTransactions().get_in_guild(guild_id)
	          if character.state == APPROVED]
	balances = [character.currency or 0 for character in active]
	report = EconomyReport(characters=len(active), total=sum(balances),
	                       median=int(median(balances)) if balances else 0)
	for reason, amount, changes in CurrencyTransactions().totals(guild_id, since) :
		(report.income if amount > 0 else report.spending).append((reason, amount, changes))
	report.richest = [(character.name, character.currency or 0)
	                  for character in sorted(active, key=lambda record : -(record.currency or 0))[:TOP]]
	names = {character.id : character.name for character in CharacterTransactions().get_in_guild(guild_id)}
	report.earners = [(names.get(character_id, f"#{character_id}"), amount)
	                  for character_id, amount in CurrencyTransactions().earners(guild_id, since, TOP)]
	return report


# ============================================================
def lines(report: EconomyReport, currency: str, days: int = DAYS) -> dict[str, str] :
	"""The report as embed fields: {field name: text}."""
	fields = {"Held" : f"{report.characters} active characters hold {report.total} {currency} "
	                   f"(median {report.median})."}
	income = sum(amount for _, amount, _ in report.income)
	spending = -sum(amount for _, amount, _ in report.spending)
	fields[f"Last {days} days"] = f"{income} {currency} came in and {spending} went out."
	if report.income :
		fields["Came in"] = "\n".join(f"{label(reason)}: {amount} ({changes}×)"
		                              for reason, amount, changes in report.income)
	if report.spending :
		fields["Went out"] = "\n".join(f"{label(reason)}: {-amount} ({changes}×)"
		                               for reason, amount, changes in report.spending)
	if report.richest :
		fields["Richest"] = "\n".join(f"{name}: {amount}" for name, amount in report.richest)
	if report.earners :
		fields["Biggest earners"] = "\n".join(f"{name}: +{amount}" for name, amount in report.earners)
	return fields
