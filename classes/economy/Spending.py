"""Healers, starter kits and weapon training (design/economy.md, phase 6).

Healers: a merchant with the `healing` service removes an injury from a character's sheet (the Injuries field the GM
fills after a fight). An injury line can start with its severity, `[minor]`, `[serious]` or `[grave]` (minor when it
doesn't say); healing costs 350, 1,000 or 3,500, times the merchant's markup and changed by Charisma.

Starter kits: with STARTER_KITS on (the default), a new character gets its occupation's kit when it is created, on top
of its starting money. Kit items sell for nothing, so a kit can't be turned into money.

Training raises a weapon's proficiency one step: Awful → Poor 500 and 1 day, Poor → Average 1,500 and 2 days,
Average → Good 5,000 and 5 days, Good → Excellent 14,000 and 10 days. It is paid up front, to a merchant with the
`training` service (times its markup, through Charisma) or to another player's character whose occupation trains,
and the days are spent as downtime (/downtime train). The two-weapons-at-Good-or-Excellent limit still applies; GMs
keep /gm gear proficiency.
"""
import re

from sqlalchemy import Select

from classes.combat import Rules
from classes.gear import Pricing
from classes.kernel import RoleplaySettings
from database.database import CharacterGear, Characters, Merchants, Occupations, Trainings
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.DatabaseTransactions import DatabaseTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping

INJURIES = "Injuries"
MINOR = "minor"
SERIOUS = "serious"
GRAVE = "grave"
SEVERITIES = [MINOR, SERIOUS, GRAVE]
HEAL_PRICE = {MINOR : 350, SERIOUS : 1000, GRAVE : 3500}
SEVERITY_TAG = re.compile(r"^\[(minor|serious|grave)]\s*", re.IGNORECASE)
KIT = "kit"
# step: (from, to, price, days)
TRAINING_STEPS = [(Rules.AWFUL, Rules.POOR, 500, 1), (Rules.POOR, Rules.AVERAGE, 1500, 2),
                  (Rules.AVERAGE, Rules.GOOD, 5000, 5), (Rules.GOOD, Rules.EXCELLENT, 14000, 10)]
GOOD_TIERS = {Rules.GOOD, Rules.EXCELLENT}
TRAINING_REASON = "training"
OPEN = "open"
DONE = "done"


# == injuries and healers ==

# ============================================================
def severity_of(line: str) -> str :
	match = SEVERITY_TAG.match(line.strip())
	return match.group(1).lower() if match else MINOR


# ============================================================
def tagged(text: str, severity: str | None) -> str :
	"""An injury as the sheet keeps it, with its severity when it isn't minor."""
	text = SEVERITY_TAG.sub("", text.strip())
	return f"[{severity}] {text}" if severity in (SERIOUS, GRAVE) else text


# ============================================================
def injuries(character: Characters) -> list[str] :
	current = next((info.value for info in CharacterInfoTransactions().get_all(character.id) if info.key == INJURIES),
	               None)
	return [line for line in (current or "").splitlines() if line.strip()]


# ============================================================
def heal_price(merchant: Merchants, severity: str, character: Characters) -> int :
	if not Pricing.economy(character.guild_id) :
		return 0
	return round(HEAL_PRICE.get(severity, HEAL_PRICE[MINOR]) * (merchant.markup or 1.0) *
	             Pricing.buy_multiplier(character))


# ============================================================
def remove_injury(character: Characters, index: int) -> str | None :
	"""Takes one injury off the sheet; returns the line, or None when there is no such injury."""
	lines = injuries(character)
	if not 0 <= index < len(lines) :
		return None
	removed = lines.pop(index)
	infos = CharacterInfoTransactions()
	if lines :
		infos.edit(character.id, INJURIES, "\n".join(lines))
	else :
		infos.remove(character.id, INJURIES)
	return removed


# == starter kits ==

# ============================================================
def kits_on(guild_id: int) -> bool :
	return RoleplaySettings.toggle(guild_id, ConfigMapping.STARTER_KITS)


# ============================================================
def kit_items(occupation: Occupations | None) -> list :
	if occupation is None :
		return []
	return [item for item in (GearItemTransactions().get(item_id) for item_id in occupation.kit or []) if item]


# ============================================================
def grant_kit(character: Characters, actor_uid: int | None = None) -> list[CharacterGear] :
	"""Gives a new character its occupation's starter kit (source `kit`, worth nothing when sold)."""
	from database.transactions.OccupationTransactions import OccupationTransactions

	if not kits_on(character.guild_id) or not character.occupation_id :
		return []
	given = []
	for item in kit_items(OccupationTransactions().get(character.occupation_id)) :
		entry = CharacterGearTransactions().add(character.id, item.id, item.name, item.kind, KIT, 0, actor_uid)
		if entry is not None :
			given.append(entry)
	return given


# == training ==

class TrainingTransactions(DatabaseTransactions) :

	# ============================================================
	def add(self, **fields) -> Trainings :
		with self.createsession() as session :
			training = Trainings(state=OPEN, days_done=0, **fields)
			session.add(training)
			self.commit(session)
			return training

	# ============================================================
	def open_for(self, entry_id: int) -> Trainings | None :
		with self.createsession() as session :
			return session.scalar(Select(Trainings).where(Trainings.entry_id == entry_id, Trainings.state == OPEN))

	# ============================================================
	def of_character(self, character_id: int) -> list[Trainings] :
		with self.createsession() as session :
			return list(session.scalars(Select(Trainings).where(Trainings.character_id == character_id,
			                                                    Trainings.state == OPEN)).all())

	# ============================================================
	def update(self, training_id: int, **fields) -> Trainings | None :
		with self.createsession() as session :
			training = session.scalar(Select(Trainings).where(Trainings.id == training_id))
			if training is None :
				return None
			for key, value in fields.items() :
				setattr(training, key, value)
			self.commit(session)
			return training


# ============================================================
def next_step(entry: CharacterGear) -> tuple[str, str, int, int] | None :
	current = entry.proficiency or Rules.AWFUL
	return next((step for step in TRAINING_STEPS if step[0] == current), None)


# ============================================================
def training_problem(entry: CharacterGear) -> str | None :
	if entry.kind != "weapon" or entry.status != "owned" :
		return "Pick one of your character's weapons."
	step = next_step(entry)
	if step is None :
		return f"{entry.name} can't be trained any further."
	if TrainingTransactions().open_for(entry.id) is not None :
		return f"{entry.name} is already being trained; spend the days with /downtime train."
	if step[1] in GOOD_TIERS and (entry.proficiency or "") not in GOOD_TIERS :
		others = [other for other in CharacterGearTransactions().get_all(entry.character_id)
		          if other.id != entry.id and other.kind == "weapon" and (other.proficiency or "") in GOOD_TIERS]
		if len(others) >= Rules.MAX_GOOD_WEAPONS :
			return f"A character can be Good or Excellent with at most {Rules.MAX_GOOD_WEAPONS} weapons."
	return None


# ============================================================
def training_price(entry: CharacterGear, character: Characters, merchant: Merchants | None = None) -> int :
	step = next_step(entry)
	if step is None or not Pricing.economy(character.guild_id) :
		return 0
	if merchant is None :
		return step[2]
	return round(step[2] * (merchant.markup or 1.0) * Pricing.buy_multiplier(character))


# ============================================================
def start_with_merchant(character: Characters, entry: CharacterGear, merchant: Merchants,
                        actor_uid: int) -> tuple[Trainings | None, str | None] :
	from classes.economy import Merchants as MerchantRules
	from classes.gear.Gear import Gear

	if MerchantRules.TRAINING not in (merchant.services or []) :
		return None, f"{merchant.name} doesn't train fighters."
	problem = training_problem(entry)
	if problem :
		return None, problem
	cost = training_price(entry, character, merchant)
	if cost :
		_, problem = Gear.change_currency(character, -cost, TRAINING_REASON, actor_uid, note=f"{entry.name} at "
		                                                                                    f"{merchant.name}")
		if problem :
			return None, problem
	step = next_step(entry)
	return TrainingTransactions().add(character_id=character.id, entry_id=entry.id, target=step[1],
	                                  days_needed=step[3], paid=cost, trainer=merchant.name), None


# ============================================================
def start_with_trainer(character: Characters, entry: CharacterGear, trainer: Characters,
                       actor_uid: int) -> tuple[Trainings | None, str | None] :
	"""Training paid to another player's character whose occupation trains."""
	from classes.economy import Trading
	from database.transactions.OccupationTransactions import OccupationTransactions
	from database.transactions.TradeTransactions import Payment, TradeTransactions, Transfer

	occupation = OccupationTransactions().get(trainer.occupation_id) if trainer.occupation_id else None
	if occupation is None or not occupation.trains :
		return None, f"{trainer.name}'s occupation doesn't train others; staff set that with /downtime occupation."
	problem = Trading.pair_problem(character, trainer) or training_problem(entry)
	if problem :
		return None, problem
	cost = training_price(entry, character)
	if cost :
		problem = TradeTransactions().transfer(Transfer(payments=[
			Payment(character.id, -cost, TRAINING_REASON, f"{entry.name} with {trainer.name}", actor_uid),
			Payment(trainer.id, cost, TRAINING_REASON, f"Trained {character.name}", actor_uid)]), character.guild_id)
		if problem :
			return None, problem
	step = next_step(entry)
	return TrainingTransactions().add(character_id=character.id, entry_id=entry.id, target=step[1],
	                                  days_needed=step[3], paid=cost, trainer=trainer.name), None


# ============================================================
def train_day(training: Trainings) -> tuple[Trainings, list[str]] :
	"""A day of training; the last one raises the proficiency."""
	from classes.combat.Proficiency import Proficiency

	entry = CharacterGearTransactions().get(training.entry_id)
	days = training.days_done + 1
	if days < training.days_needed :
		training = TrainingTransactions().update(training.id, days_done=days)
		return training, [f"🗡️ A day of training with {training.trainer or 'a trainer'} ({days}/{training.days_needed})."]
	updated, message = Proficiency.set_weapon(entry, training.target, staff=True) if entry else (None, "")
	if updated is None :
		return TrainingTransactions().update(training.id, days_done=days), \
		       [f"The last day of training is done, but it couldn't take hold: {message}"]
	training = TrainingTransactions().update(training.id, days_done=days, state=DONE)
	return training, [f"🗡️ Training done! {message}"]
