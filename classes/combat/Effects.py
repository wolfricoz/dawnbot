"""The effects abilities and spells are built from. Players can't write their own rules: an ability is a tier, a stat
and a list of effects from the catalog (classes/combat/EffectCatalog.py for active effects, PassiveCatalog.py for
passive ones), and the bot resolves every effect itself.

Every effect is magic or physical. Spells (kind `spell`) only take magic effects and abilities (kind `ability`) only
physical ones. Each effect has an AP cost: an active ability costs its tier's base AP plus the cost of its effects, and
a passive lowers the character's AP every turn by the cost of its effects.

An active effect has a mechanic, which is what the engine does with it, and parameters, which tune it:

- attack: an attack roll against AC; a hit deals the tier's dice (moved up or down by `steps`) + the stat modifier.
  Parameters: `type` (damage type; None uses the ability's), `hits` (separate attacks, one dice step lower each),
  `ignore_dt`, `drain` (heals the user for half the damage), `on_hit` (a condition the target gets on a hit, no save),
  `execute` (one more die against targets at half HP or less), `accuracy` (to hit bonus), `crit` (crit range wider).
- blast: the target saves (`save`, a stat) against the DC; a failed save takes the dice, a passed one half.
  `on_fail` adds a condition to a failed save.
- afflict: the target saves against the DC or gets `condition` for the tier's turns (+`turns`). `amount` overrides the
  tier's number for conditions that carry one (vulnerable, drained).
- doom: the target saves or is doomed; when the doom runs out it takes the dice.
- dispel: removes `count` helpful conditions from the target (no save).
- heal: heals the dice + modifier; also reaches downed allies. `cleanse` removes a harmful condition, `self_cost`
  makes the user pay half of it in HP.
- shield: the target is shielded for the dice + modifier.
- boost: the target gets a helpful `condition` for the tier's turns (+`turns`).
- cleanse: removes `count` harmful conditions (None is all).
- revive: brings a downed ally back with the dice + modifier in HP.
- companion: a summoned ally attacks a random enemy at the start of each of the user's turns, for the tier's turns + 1.
- escape: the user leaves the fight.
- modifier: changes the whole ability (`area`: up to 3 targets, one dice step lower; `mass`: up to 5, two lower;
  `overcharge`: one dice step higher; `precise`: +2 to hit and DC; `lingering`: conditions last a turn longer).
- drawback: lowers the cost and hurts the user (`blood`: takes half the dice; `exhaust`: drained of 2 AP;
  `reckless`: exposed, -2 AC; `backlash`: takes half the dice when every roll misses or is resisted; `weaken`:
  weakened for a turn; `once`: one use per fight).

aim says who an effect is for: enemy, ally or self. An ability's effects aim at one side (self effects can join
either), and modifiers and drawbacks aim at nothing.
"""
from dataclasses import dataclass, field

from classes.combat import Conditions as C, Rules

MAGIC = "magic"
PHYSICAL = "physical"
REALMS = [MAGIC, PHYSICAL]
REALM_LABELS = {MAGIC : "Magic", PHYSICAL : "Physical"}

ENEMY = "enemy"
ALLY = "ally"
SELF = "self"
NOBODY = "none"

ATTACK = "attack"
BLAST = "blast"
AFFLICT = "afflict"
DOOM = "doom"
DISPEL = "dispel"
HEAL = "heal"
SHIELD = "shield"
BOOST = "boost"
CLEANSE = "cleanse"
REVIVE = "revive"
COMPANION = "companion"
ESCAPE = "escape"
MODIFIER = "modifier"
DRAWBACK = "drawback"
MECHANICS = [ATTACK, BLAST, AFFLICT, DOOM, DISPEL, HEAL, SHIELD, BOOST, CLEANSE, REVIVE, COMPANION, ESCAPE, MODIFIER,
             DRAWBACK]
# Who each mechanic is aimed at when the catalog doesn't say.
DEFAULT_AIM = {ATTACK : ENEMY, BLAST : ENEMY, AFFLICT : ENEMY, DOOM : ENEMY, DISPEL : ENEMY, HEAL : ALLY,
               SHIELD : ALLY, BOOST : ALLY, CLEANSE : ALLY, REVIVE : ALLY, COMPANION : SELF, ESCAPE : SELF,
               MODIFIER : NOBODY, DRAWBACK : NOBODY}
# Mechanics that roll the tier's dice.
DICE_MECHANICS = [ATTACK, BLAST, DOOM, HEAL, SHIELD, REVIVE, COMPANION]

AREA = "area"
MASS = "mass"
OVERCHARGE = "overcharge"
PRECISE = "precise"
LINGERING = "lingering"
MODIFIERS = [AREA, MASS, OVERCHARGE, PRECISE, LINGERING]
AREA_TARGETS = 3
MASS_TARGETS = 5
PRECISE_BONUS = 2

BLOOD = "blood"
EXHAUST = "exhaust"
RECKLESS = "reckless"
BACKLASH = "backlash"
WEAKEN = "weaken"
ONCE = "once"
DRAWBACKS = [BLOOD, EXHAUST, RECKLESS, BACKLASH, WEAKEN, ONCE]
EXHAUST_AP = 2
MAX_DRAWBACKS = 2

CANTRIP = "cantrip"
WEAK = "weak"
NORMAL = "normal"
STRONG = "strong"
TIERS = [CANTRIP, WEAK, NORMAL, STRONG]
TIER_INDEX = {CANTRIP : 0, WEAK : 1, NORMAL : 2, STRONG : 3}
# tier: (uses per fight (None is unlimited), dice, condition turns, save DC bonus, base AP, most effects)
TIER_DATA = {
	CANTRIP : (None, "1d6", 1, 0, 1, 2),
	WEAK    : (3, "2d6", 1, 1, 1, 3),
	NORMAL  : (2, "3d6", 2, 2, 2, 4),
	STRONG  : (1, "4d8", 3, 3, 3, 5),
}
# The most an active ability may cost, whatever its effects.
MAX_AP = 12
MIN_AP = 1
# Numbers for conditions that carry one, by tier (Cantrip, Weak, Normal, Strong).
TIER_AMOUNTS = {C.VULNERABLE : (1, 2, 3, 4), C.DRAINED : (1, 1, 2, 3), C.HASTED : (1, 1, 2, 2), C.THORNS : (1, 2, 3, 4)}
# The dice used for a companion's attack and for riposte, one step below the tier's.
RIPOSTE_DICE = ("1d4", "1d6", "1d8", "2d6")


@dataclass(frozen=True)
class Effect :
	"""One entry of the effect catalog."""
	key: str
	name: str
	realm: str
	category: str
	mechanic: str
	cost: int
	text: str
	# The lowest tier that may use it.
	tier: str = CANTRIP
	aim: str = ""
	params: dict = field(default_factory=dict)

	# ============================================================
	@property
	def target(self) -> str :
		return self.aim or DEFAULT_AIM.get(self.mechanic, NOBODY)

	# ============================================================
	@property
	def main(self) -> bool :
		"""Whether it does something by itself (modifiers and drawbacks only change other effects)."""
		return self.mechanic not in (MODIFIER, DRAWBACK)

	# ============================================================
	def label(self) -> str :
		"""`Pyrokinesis (magic, +2 AP): a jet of fire that sets the target alight`"""
		sign = "+" if self.cost >= 0 else ""
		return f"{self.name} ({self.realm}, {sign}{self.cost} AP): {self.text}"


# == building the catalog ==

# ============================================================
def make(key: str, name: str, realm: str, category: str, mechanic: str, cost: int, text: str, tier: str = CANTRIP,
         aim: str = "", **params) -> Effect :
	return Effect(key, name, realm, category, mechanic, cost, text, tier, aim, params)


# ============================================================
def index(effects: list[Effect]) -> dict[str, Effect] :
	"""The catalog by key; refuses duplicate keys and broken entries so mistakes show up at import time."""
	catalog = {}
	for effect in effects :
		if effect.key in catalog :
			raise ValueError(f"Duplicate effect key {effect.key}")
		if effect.realm not in REALMS or effect.tier not in TIERS :
			raise ValueError(f"Effect {effect.key} has a bad realm or tier")
		for name in (effect.params.get("condition"), effect.params.get("on_hit"), effect.params.get("on_fail")) :
			if name is not None and name not in C.DEFINITIONS :
				raise ValueError(f"Effect {effect.key} uses unknown condition {name}")
		catalog[effect.key] = effect
	return catalog


# == tiers ==

# ============================================================
def tier_index(tier: str) -> int :
	return TIER_INDEX.get(tier, 0)


# ============================================================
def uses(tier: str) -> int | None :
	return TIER_DATA[tier][0]


# ============================================================
def base_dice(tier: str) -> str :
	return TIER_DATA[tier][1]


# ============================================================
def turns(tier: str) -> int :
	return TIER_DATA[tier][2]


# ============================================================
def dc_bonus(tier: str) -> int :
	return TIER_DATA[tier][3]


# ============================================================
def base_ap(tier: str) -> int :
	return TIER_DATA[tier][4]


# ============================================================
def max_effects(tier: str) -> int :
	return TIER_DATA[tier][5]


# ============================================================
def step_up(dice: str) -> str :
	"""One dice step higher: one die more (2d6 becomes 3d6); a single small die gets 2 sides bigger (1d4 becomes 1d6)."""
	amount, sides = Rules.parse_dice(dice)
	if amount == 1 and sides < 8 :
		return Rules.dice_text(1, sides + 2)
	return Rules.dice_text(amount + 1, sides)


# ============================================================
def shift(dice: str, steps: int) -> str :
	for _ in range(abs(steps)) :
		dice = step_up(dice) if steps > 0 else Rules.step_down(dice)
	return dice


# == checking an ability ==

# ============================================================
def resolve(keys: list[str], catalog: dict[str, Effect]) -> tuple[list[Effect], str | None] :
	"""The catalog entries for a list of keys, or the first key that isn't one."""
	found = []
	for key in keys :
		effect = catalog.get(key)
		if effect is None :
			return [], f"There is no effect called {key}. See /ability effects."
		found.append(effect)
	return found, None


# ============================================================
def realm_of(kind: str) -> str :
	"""Spells take magic effects, abilities physical ones."""
	return MAGIC if kind == "spell" else PHYSICAL


# ============================================================
def check(kind: str, tier: str, effects: list[Effect]) -> str | None :
	"""Why a list of active effects doesn't make a valid ability of this kind and tier, or None when it does."""
	if tier not in TIERS :
		return f"The tier must be one of {', '.join(TIERS)}."
	if not effects :
		return "Pick at least one effect."
	realm = realm_of(kind)
	wrong = [effect.name for effect in effects if effect.realm != realm]
	if wrong :
		other = "spells" if realm == PHYSICAL else "physical abilities"
		article = "an" if kind[0] in "aeiou" else "a"
		return f"{', '.join(wrong)} {'is' if len(wrong) == 1 else 'are'} for {other}; {article} {kind} only takes " \
		       f"{realm} effects."
	if len({effect.key for effect in effects}) != len(effects) :
		return "Each effect can only be picked once."
	if len(effects) > max_effects(tier) :
		return f"A {tier.capitalize()} {kind} has at most {max_effects(tier)} effects."
	too_low = [effect.name for effect in effects if tier_index(tier) < tier_index(effect.tier)]
	if too_low :
		return f"{', '.join(too_low)} needs a higher tier (see /ability effects)."
	if not any(effect.main for effect in effects) :
		return "Modifiers and drawbacks need an effect to change; add one that does something."
	aims = {effect.target for effect in effects if effect.target in (ENEMY, ALLY)}
	if len(aims) > 1 :
		return "An ability is aimed at enemies or at allies, not both (effects on yourself go with either)."
	modifiers = [effect.params.get("kind") for effect in effects if effect.mechanic == MODIFIER]
	if AREA in modifiers and MASS in modifiers :
		return "Pick one of the area modifiers."
	if (AREA in modifiers or MASS in modifiers) and not aims :
		return "An area needs effects aimed at enemies or allies, not only at yourself."
	if len([effect for effect in effects if effect.mechanic == DRAWBACK]) > MAX_DRAWBACKS :
		return f"An ability has at most {MAX_DRAWBACKS} drawbacks."
	drawbacks = [effect.params.get("kind") for effect in effects if effect.mechanic == DRAWBACK]
	if ONCE in drawbacks and uses(tier) == 1 :
		return "A Strong ability can only be used once per fight already; pick another drawback."
	if ap_cost(tier, effects) > MAX_AP :
		return f"That would cost {ap_cost(tier, effects)} AP; an ability costs at most {MAX_AP}."
	return None


# == what the ability works out to ==

# ============================================================
def ap_cost(tier: str, effects: list[Effect]) -> int :
	"""The tier's base AP plus the effects' costs (drawbacks take some off), at least 1."""
	return max(MIN_AP, base_ap(tier) + sum(effect.cost for effect in effects))


# ============================================================
def modifiers(effects: list[Effect]) -> set[str] :
	return {effect.params.get("kind") for effect in effects if effect.mechanic == MODIFIER}


# ============================================================
def drawbacks(effects: list[Effect]) -> set[str] :
	return {effect.params.get("kind") for effect in effects if effect.mechanic == DRAWBACK}


# ============================================================
def ability_uses(tier: str, effects: list[Effect]) -> int | None :
	return 1 if ONCE in drawbacks(effects) else uses(tier)


# ============================================================
def target_limit(effects: list[Effect]) -> int :
	found = modifiers(effects)
	return MASS_TARGETS if MASS in found else AREA_TARGETS if AREA in found else 1


# ============================================================
def aim(effects: list[Effect]) -> str :
	"""Who the ability is pointed at: enemy, ally, or self when every effect is on the user."""
	aims = {effect.target for effect in effects if effect.target in (ENEMY, ALLY)}
	return aims.pop() if aims else SELF


# ============================================================
def dice_steps(effects: list[Effect]) -> int :
	"""How many steps the area, mass and overcharge modifiers move every effect's dice."""
	found = modifiers(effects)
	return (1 if OVERCHARGE in found else 0) - (2 if MASS in found else 1 if AREA in found else 0)


# ============================================================
def dice(tier: str, effect: Effect | dict, effects: list[Effect] | None = None) -> str :
	"""An effect's dice: the tier's, moved by its own steps and the ability's modifiers; extra hits are a step lower."""
	params = effect.params if isinstance(effect, Effect) else effect.get("params") or {}
	steps = int(params.get("steps") or 0) + (dice_steps(effects) if effects else 0)
	if int(params.get("hits") or 1) > 1 :
		steps -= 1
	return shift(base_dice(tier), steps)


# ============================================================
def tier_amount(tier: str, condition: str, override: int | None = None) -> int | None :
	"""The number a condition carries at this tier (vulnerable, drained, hasted, thorns), or None."""
	if override is not None :
		return int(override)
	values = TIER_AMOUNTS.get(condition)
	return values[tier_index(tier)] if values else None


# ============================================================
def snapshot(effect: Effect) -> dict :
	"""An effect as a fight stores it, so changes to the catalog don't change a running fight."""
	return {"key" : effect.key, "name" : effect.name, "realm" : effect.realm, "mechanic" : effect.mechanic,
	        "aim" : effect.target, "params" : dict(effect.params)}


# == describing ==

# ============================================================
def describe(effect: Effect, tier: str, stat: str, effects: list[Effect], damage_type: str | None = None) -> str :
	"""What one effect does at this tier, like `Pyrokinesis: attack, 3d6 + INT Fire, Burning on a hit`."""
	short = Rules.STAT_SHORT.get(stat, stat)
	params = effect.params
	mechanic = effect.mechanic
	length = turns(tier) + int(params.get("turns") or 0) + (1 if LINGERING in modifiers(effects) else 0)
	plural = "s" if length != 1 else ""
	type_name = params.get("type") or damage_type or "untyped"
	roll = f"{dice(tier, effect, effects)} + {short}"
	if mechanic == ATTACK :
		hits = int(params.get("hits") or 1)
		parts = [f"{'%d attacks' % hits if hits > 1 else 'attack'}, {roll} {type_name}"]
		if params.get("accuracy") :
			parts.append(f"{int(params['accuracy']):+d} to hit")
		if params.get("crit") :
			parts.append(f"crits {params['crit']} wider")
		if params.get("ignore_dt") :
			parts.append("ignores DT")
		if params.get("drain") :
			parts.append("heals you for half")
		if params.get("execute") :
			parts.append("+1 die at half HP or less")
		if params.get("on_hit") :
			parts.append(f"{C.label(params['on_hit'])} on a hit ({length} turn{plural})")
		text = ", ".join(parts)
	elif mechanic == BLAST :
		save = Rules.STAT_SHORT.get(params.get("save") or "agility", "AGI")
		text = f"{save} save, {roll} {type_name} (half on a save)"
		if params.get("on_fail") :
			text += f", {C.label(params['on_fail'])} on a failed save ({length} turn{plural})"
	elif mechanic == AFFLICT :
		name = params.get("condition")
		save = Rules.STAT_SHORT.get(params.get("save") or C.save_stat(name), "END")
		amount = tier_amount(tier, name, params.get("amount"))
		text = f"{save} save or {C.label(name)}{f' {amount}' if amount else ''} for {length} turn{plural}"
	elif mechanic == DOOM :
		text = f"END save or doomed: takes {dice(tier, effect, effects)} when it runs out in {length} turn{plural}"
	elif mechanic == DISPEL :
		count = int(params.get("count") or 1)
		text = f"removes {count} helpful condition{'s' if count != 1 else ''}"
	elif mechanic == HEAL :
		text = f"heals {roll}" + (", removes a harmful condition" if params.get("cleanse") else "") \
		       + (", you pay half in HP" if params.get("self_cost") else "")
	elif mechanic == SHIELD :
		text = f"shield of {roll}"
	elif mechanic == BOOST :
		name = params.get("condition")
		amount = tier_amount(tier, name, params.get("amount"))
		text = f"{C.label(name)}{f' {amount}' if amount else ''} for {length} turn{plural} ({C.describe(name)})"
	elif mechanic == CLEANSE :
		count = params.get("count")
		text = "removes every harmful condition" if count is None else \
			f"removes {count} harmful condition{'s' if int(count) != 1 else ''}"
	elif mechanic == REVIVE :
		text = f"revives a downed ally with {roll} HP"
	elif mechanic == COMPANION :
		text = f"summons an ally that attacks for {dice(tier, effect, effects)} {type_name} each turn for " \
		       f"{length + 1} turns"
	elif mechanic == ESCAPE :
		text = "you leave the fight"
	elif mechanic == MODIFIER :
		kind = params.get("kind")
		text = {AREA : f"up to {AREA_TARGETS} targets, dice one step lower",
		        MASS : f"up to {MASS_TARGETS} targets, dice two steps lower",
		        OVERCHARGE : "dice one step higher", PRECISE : f"+{PRECISE_BONUS} to hit and DC",
		        LINGERING : "conditions last a turn longer"}.get(kind, kind)
	else :
		kind = params.get("kind")
		half = Rules.halve_dice(base_dice(tier))
		text = {BLOOD : f"you take {half}", EXHAUST : f"you start your next turn with {EXHAUST_AP} less AP",
		        RECKLESS : "you are exposed (-2 AC) until your next turn",
		        BACKLASH : f"you take {half} when every roll misses or is resisted",
		        WEAKEN : "you are weakened for a turn", ONCE : "one use per fight"}.get(kind, kind)
	if effect.target == SELF and mechanic not in (COMPANION, ESCAPE, MODIFIER, DRAWBACK) :
		text += " (on you)"
	return f"{effect.name}: {text}"


# ============================================================
def summary(kind: str, tier: str, stat: str, effects: list[Effect], damage_type: str | None = None) -> str :
	"""`Normal spell · 6 AP · 2 uses · up to 3 targets` followed by one line per effect."""
	count = ability_uses(tier, effects)
	head = [f"{tier.capitalize()} {kind}", f"{ap_cost(tier, effects)} AP",
	        "unlimited uses" if count is None else f"{count} use{'s' if count != 1 else ''}"]
	limit = target_limit(effects)
	if limit > 1 :
		head.append(f"up to {limit} {'enemies' if aim(effects) == ENEMY else 'allies'}")
	if not effects :
		return " · ".join(head) + "\nNo effects yet: build it with /ability edit."
	return " · ".join(head) + "\n" + "\n".join(f"- {describe(effect, tier, stat, effects, damage_type)}"
	                                          for effect in effects)
