"""The numbers of combat: stat modifiers, derived stats, weapon and armor values, and attack and damage rolls.

Everything here is plain arithmetic on dictionaries, with no database or Discord, so the rules can be tested and reused
by the quick roll (/combat attack) and by fights. See design/combat.md for the rules in words.
"""
import random
import re
from dataclasses import dataclass, field

STATS = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]
STAT_SHORT = {"strength" : "STR", "perception" : "PER", "endurance" : "END", "charisma" : "CHA",
              "intelligence" : "INT", "agility" : "AGI", "luck" : "LCK"}

# == proficiency ==
EXCELLENT = "excellent"
GOOD = "good"
AVERAGE = "average"
POOR = "poor"
AWFUL = "awful"
PROFICIENCY = {EXCELLENT : 1, GOOD : 1, AVERAGE : 0, POOR : -1, AWFUL : -2}
PROFICIENCY_ORDER = [EXCELLENT, GOOD, AVERAGE, POOR, AWFUL]
# A character can be Good or Excellent with at most this many weapons.
MAX_GOOD_WEAPONS = 2

# == armor ==
CLOTHING = "clothing"
LIGHT = "light"
MEDIUM = "medium"
HEAVY = "heavy"
ARMOR_CLASSES = [CLOTHING, LIGHT, MEDIUM, HEAVY]
BASE_AC = 10
AC_CAP = 18
AGILITY_AC_CAP = 2
SHIELD_AC = 2
SHIELD_ATTACK = -2
ARMOR_STEP_PENALTY = -2

# == weapons ==
MELEE = "melee"
RANGED = "ranged"
RANGES = [MELEE, RANGED]
PROPERTIES = ["light", "heavy", "two_handed", "reach", "thrown", "loading", "keen", "focus", "shield"]
DICE = re.compile(r"([1-9]\d?)d([1-9]\d{0,2})")
UNARMED_KEY = "unarmed"
UNARMED = {"key" : UNARMED_KEY, "name" : "Unarmed", "type" : "blunt", "dice" : "1d4", "attack_stat" : "strength",
           "damage_stat" : "strength", "hit_mod" : 0, "range" : MELEE, "properties" : ["light"], "ap" : None,
           "proficiency" : AVERAGE, "requirement_penalty" : 0}
WEAPON_DEFAULTS = {"type" : None, "dice" : "1d6", "attack_stat" : "strength", "damage_stat" : "strength",
                   "hit_mod" : 0, "range" : MELEE, "properties" : [], "ap" : None}
ARMOR_DEFAULTS = {"armor_class" : CLOTHING, "ac" : 0, "dt" : 0, "hit_mod" : 0, "ability_hit_mod" : 0}
NEW_WEAPON_KEYS = {"type", "attack_stat", "damage_stat", "hit_mod", "range", "properties", "ap"}
NEW_ARMOR_KEYS = {"armor_class", "dt", "ability_hit_mod", "hit_mod"}
UNMET_PENALTY_CAP = -5

# == hp, ap ==
HP_BASE = 15
HP_MINIMUM = 5
AP_BASE = 5
AP_MINIMUM = 2
AIMED_PENALTY = -4
STRONG_MARGIN = 5


# ============================================================
def modifier(value: int, base: int = 5) -> int :
	"""Each point above the base is +1, each point below it -1."""
	return int(value) - int(base)


# ============================================================
def stat(stats: dict, name: str | None) -> int :
	return int((stats or {}).get(name, 0)) if name else 0


# == derived stats ==

# ============================================================
def hp_max(stats: dict, level: int = 1, base: int = 5) -> int :
	"""15 + STR + (2 x END), plus 2 + END modifier (at least 1) per level after the first. Endurance at 0 or below
	gives nothing from levels."""
	endurance = stat(stats, "endurance")
	per_level = 0 if endurance <= 0 else max(1, 2 + modifier(endurance, base))
	value = HP_BASE + stat(stats, "strength") + 2 * endurance + max(0, int(level) - 1) * per_level
	return max(HP_MINIMUM, value)


# ============================================================
def ap_max(stats: dict) -> int :
	"""5 + AGI / 2, rounded down, and never below 2."""
	return max(AP_MINIMUM, AP_BASE + stat(stats, "agility") // 2)


# ============================================================
def armor_class(stats: dict, armor: dict | None = None, shield: bool = False, base: int = 5) -> int :
	"""10 + armor bonus + shield + AGI modifier. Agility adds at most +2 (a negative modifier counts in full) and the
	total is at most 18."""
	armor = armor or ARMOR_DEFAULTS
	agility = min(modifier(stat(stats, "agility"), base), AGILITY_AC_CAP)
	value = BASE_AC + int(armor.get("ac", 0)) + (SHIELD_AC if shield else 0) + agility
	return min(value, AC_CAP)


# ============================================================
def sequence(stats: dict) -> int :
	return 2 * stat(stats, "perception")


# ============================================================
def crit_min(luck: int, widen: int = 0) -> int :
	"""The lowest natural roll that crits: 20 at Luck 8 or less, one lower for every 4 points of Luck above 8 (19 at 9,
	18 at 13, 15 at 25). widen lowers it further (Excellent proficiency, keen weapons)."""
	value = 20 if luck <= 8 else 20 - ((luck - 9) // 4 + 1)
	return max(2, value - widen)


# ============================================================
def fumble_max(luck: int) -> int :
	"""The highest natural roll that fumbles: 1, or 2 at Luck 1 to 2, or 3 at Luck 0 and below."""
	if luck >= 3 :
		return 1
	return 2 if luck >= 1 else 3


# ============================================================
def level_bonus(level: int) -> int :
	"""+1 at levels 4, 8, 12 and 16."""
	return min(4, max(0, int(level) // 4))


# ============================================================
def crippled(stats: dict) -> list[str] :
	"""The stats at 0 or below."""
	return [name for name in STATS if stat(stats, name) <= 0]


# == weapons and armor ==

# ============================================================
def parse_dice(dice: str) -> tuple[int, int] :
	match = DICE.fullmatch(str(dice or "").strip().lower())
	if not match :
		raise ValueError(f"dice must look like 1d8 or 2d6, not {dice!r}.")
	return int(match.group(1)), int(match.group(2))


# ============================================================
def dice_text(amount: int, sides: int) -> str :
	return f"{amount}d{sides}"


# ============================================================
def halve_dice(dice: str) -> str :
	"""Half the dice, rounded up (3d6 becomes 2d6); a single die becomes one half its size (1d6 becomes 1d3)."""
	amount, sides = parse_dice(dice)
	if amount > 1 :
		return dice_text((amount + 1) // 2, sides)
	return dice_text(1, max(2, sides // 2))


# ============================================================
def step_down(dice: str) -> str :
	"""One dice step lower: one die fewer (3d6 becomes 2d6); a single die gets 2 sides smaller (1d6 becomes 1d4)."""
	amount, sides = parse_dice(dice)
	if amount > 1 :
		return dice_text(amount - 1, sides)
	return dice_text(1, max(2, sides - 2))


# ============================================================
def normalise_weapon(combat: dict | None) -> dict :
	"""A weapon's combat values in the current shape. Values in the old shape (dice, modifier `damage:<stat>` or
	`dice:<stat>`, hitmodifier) are converted: the stat in the modifier becomes the attack and damage stat, and a weapon
	without one becomes a ranged Perception weapon."""
	combat = dict(combat or {})
	if NEW_WEAPON_KEYS & combat.keys() :
		weapon = dict(WEAPON_DEFAULTS) | {key : value for key, value in combat.items() if key in WEAPON_DEFAULTS}
		weapon["properties"] = [prop for prop in weapon.get("properties") or [] if prop in PROPERTIES]
		return weapon
	modifier_text = str(combat.get("modifier") or "").lower()
	damage_stat = modifier_text.split(":", 1)[1] if ":" in modifier_text else None
	damage_stat = damage_stat if damage_stat in STATS else None
	attack_stat = damage_stat if damage_stat in ("strength", "agility", "intelligence", "charisma") else "perception"
	return dict(WEAPON_DEFAULTS) | {"dice" : combat.get("dice") or WEAPON_DEFAULTS["dice"],
	                                "attack_stat" : attack_stat,
	                                "damage_stat" : damage_stat if attack_stat != "perception" else None,
	                                "hit_mod" : int(combat.get("hitmodifier") or 0),
	                                "range" : RANGED if attack_stat == "perception" else MELEE}


# Old armor sets: (highest old AC, armor class, AC bonus, DT).
LEGACY_ARMOR = [(12, CLOTHING, 0, 0), (13, LIGHT, 1, 0), (14, LIGHT, 1, 1), (15, MEDIUM, 2, 1), (16, MEDIUM, 2, 2),
                (17, MEDIUM, 3, 2), (18, HEAVY, 3, 3)]


# ============================================================
def normalise_armor(combat: dict | None) -> dict :
	"""An armor set's combat values in the current shape. Old values (hp, ap, ac from 12 up, hitchance) are converted
	by their AC; old hit penalties are dropped."""
	combat = dict(combat or {})
	if NEW_ARMOR_KEYS & combat.keys() and "hp" not in combat :
		armor = dict(ARMOR_DEFAULTS) | {key : value for key, value in combat.items() if key in ARMOR_DEFAULTS}
		armor["armor_class"] = armor["armor_class"] if armor["armor_class"] in ARMOR_CLASSES else CLOTHING
		return armor
	old_ac = int(combat.get("ac") or 12)
	armor_class, bonus, dt = HEAVY, 4, 3
	for highest, kind, ac_bonus, threshold in LEGACY_ARMOR :
		if old_ac <= highest :
			armor_class, bonus, dt = kind, ac_bonus, threshold
			break
	return dict(ARMOR_DEFAULTS) | {"armor_class" : armor_class, "ac" : bonus, "dt" : dt,
	                               "hit_mod" : max(0, int(combat.get("hitchance") or 0))}


# ============================================================
def weapon_ap(weapon: dict) -> int :
	"""What an attack costs: 5 with loading, 4 heavy or two-handed, 2 light, otherwise 3. An ap value overrides it."""
	if weapon.get("ap") :
		return int(weapon["ap"])
	properties = set(weapon.get("properties") or [])
	if "loading" in properties :
		return 5
	if properties & {"heavy", "two_handed"} :
		return 4
	if "light" in properties :
		return 2
	return 3


# ============================================================
def proficiency_bonus(tier: str | None) -> int :
	return PROFICIENCY.get((tier or AWFUL).lower(), PROFICIENCY[AWFUL])


# ============================================================
def unmet_penalty(stats: dict, requirements: dict | None) -> int :
	"""-1 per missing point of the SPECIAL requirements, at most -5."""
	missing = sum(max(0, int(minimum) - stat(stats, name)) for name, minimum in (requirements or {}).items()
	              if name in STATS)
	return max(UNMET_PENALTY_CAP, -missing)


# ============================================================
def armor_penalty(armor_class: str | None, proficiency: str | None) -> int :
	"""-2 to hit for every step the armor is heavier than the wearer's armor proficiency; none when unknown."""
	if proficiency not in ARMOR_CLASSES or armor_class not in ARMOR_CLASSES :
		return 0
	steps = ARMOR_CLASSES.index(armor_class) - ARMOR_CLASSES.index(proficiency)
	return ARMOR_STEP_PENALTY * max(0, steps)


# == rolls ==

@dataclass
class Bonus :
	"""One part of a roll's modifier, such as `STR +3`."""
	label: str
	value: int


# ============================================================
def bonus_text(bonuses: list[Bonus]) -> str :
	parts = [f"{bonus.label} {bonus.value:+d}" for bonus in bonuses if bonus.value]
	return ", ".join(parts) if parts else "no modifiers"


@dataclass
class AttackRoll :
	natural: int
	rolls: list[int]
	bonuses: list[Bonus]
	total: int
	target: int
	hit: bool
	crit: bool = False
	fumble: bool = False
	strong: bool = False
	confirm: int | None = None

	# ============================================================
	@property
	def modifier(self) -> int :
		return sum(bonus.value for bonus in self.bonuses)

	# ============================================================
	def text(self, against: str = "AC") -> str :
		"""`14 (11 + 3) vs AC 13`"""
		dice = self.natural if len(self.rolls) == 1 else f"{self.natural} of {'/'.join(map(str, self.rolls))}"
		return f"{self.total} ({dice} {self.modifier:+d}) vs {against} {self.target}"


# ============================================================
def roll_attack(bonuses: list[Bonus], target: int, crit_from: int = 20, fumble_to: int = 1,
                disadvantage: bool = False, confirm_crits: bool = False,
                rng: random.Random | None = None) -> AttackRoll :
	"""Rolls d20 + bonuses against a target number. A natural roll at or below fumble_to misses and fumbles; one at or
	above crit_from (or a natural 20) hits and crits. With confirm_crits only a natural 20 can crit, and only when a
	second roll also hits. A strong hit beats the target by 5 or more, or crits."""
	rng = rng or random
	rolls = [rng.randint(1, 20)]
	if disadvantage :
		rolls.append(rng.randint(1, 20))
	natural = min(rolls)
	modifier_total = sum(bonus.value for bonus in bonuses)
	total = natural + modifier_total
	result = AttackRoll(natural=natural, rolls=rolls, bonuses=bonuses, total=total, target=target, hit=False)
	if natural <= fumble_to and natural < 20 :
		result.fumble = True
		return result
	crit_from = 20 if confirm_crits else min(20, crit_from)
	if natural >= crit_from :
		result.hit = True
		result.crit = True
		if confirm_crits :
			result.confirm = rng.randint(1, 20)
			result.crit = result.confirm + modifier_total >= target
	else :
		result.hit = total >= target
	result.strong = result.crit or (result.hit and total >= target + STRONG_MARGIN)
	return result


@dataclass
class DamageRoll :
	dice: str
	rolls: list[int]
	bonus: int
	dt: int
	total: int
	crit: bool = False
	ignored_dt: bool = False
	notes: list[str] = field(default_factory=list)

	# ============================================================
	def text(self) -> str :
		"""`2d6 [3, 5] +2 - DT 1 = 9`"""
		parts = f"{self.dice} {self.rolls}"
		if self.bonus :
			parts += f" {self.bonus:+d}"
		if self.dt and not self.ignored_dt :
			parts += f" - DT {self.dt}"
		return f"{parts} = {self.total}"


# ============================================================
def roll_damage(dice: str, bonus: int = 0, dt: int = 0, crit: bool = False, extra_dice: int = 0,
                ignore_dt: bool = False, minimum: int = 1, rng: random.Random | None = None) -> DamageRoll :
	"""Damage: the dice + bonus - DT, at least minimum. A crit counts the dice at their maximum, adds one more roll of
	them and ignores DT."""
	rng = rng or random
	amount, sides = parse_dice(dice)
	amount += max(0, extra_dice)
	if crit :
		rolls = [sides] * amount + [rng.randint(1, sides) for _ in range(amount)]
		ignore_dt = True
	else :
		rolls = [rng.randint(1, sides) for _ in range(amount)]
	total = sum(rolls) + bonus - (0 if ignore_dt else dt)
	return DamageRoll(dice=dice_text(amount, sides), rolls=rolls, bonus=bonus, dt=dt, total=max(minimum, total),
	                  crit=crit, ignored_dt=ignore_dt and bool(dt))


# ============================================================
def roll_dice(dice: str, bonus: int = 0, rng: random.Random | None = None) -> tuple[int, list[int]] :
	"""Rolls dice for healing and shields: the total (at least 0) and the rolls."""
	rng = rng or random
	amount, sides = parse_dice(dice)
	rolls = [rng.randint(1, sides) for _ in range(amount)]
	return max(0, sum(rolls) + bonus), rolls


# ============================================================
def weapon_bonuses(stats: dict, weapon: dict, base: int = 5) -> list[Bonus] :
	"""The lasting parts of an attack bonus with a weapon, from a combatant's snapshot (see Loadout): the attack stat,
	proficiency, the weapon's and armor's hit modifiers, level bonus, shield, unmet requirements and armor that is too
	heavy. NPCs use their flat to_hit instead of stats."""
	if "to_hit" in weapon :
		return [Bonus("to hit", int(weapon["to_hit"]))]
	special = stats.get("special") or {}
	attack_stat = weapon.get("attack_stat")
	bonuses = []
	if attack_stat :
		bonuses.append(Bonus(STAT_SHORT.get(attack_stat, attack_stat), modifier(stat(special, attack_stat), base)))
	bonuses.append(Bonus(f"{(weapon.get('proficiency') or AWFUL).capitalize()}",
	                     proficiency_bonus(weapon.get("proficiency"))))
	bonuses.append(Bonus("weapon", int(weapon.get("hit_mod") or 0)))
	armor = stats.get("armor") or {}
	bonuses.append(Bonus("armor", int(armor.get("hit_mod") or 0)))
	bonuses.append(Bonus("level", int(stats.get("level_bonus") or 0)))
	if stats.get("shield") and "shield" not in (weapon.get("properties") or []) :
		bonuses.append(Bonus("shield", SHIELD_ATTACK))
	bonuses.append(Bonus("requirements", int(weapon.get("requirement_penalty") or 0)))
	bonuses.append(Bonus("armor proficiency", int(stats.get("armor_penalty") or 0)))
	return bonuses


# ============================================================
def damage_bonus(stats: dict, weapon: dict, base: int = 5) -> int :
	"""What a weapon adds to its damage: the damage stat's modifier (none for weapons without one, or NPCs)."""
	if "to_hit" in weapon :
		return 0
	damage_stat = weapon.get("damage_stat")
	if not damage_stat :
		return 0
	return modifier(stat(stats.get("special") or {}, damage_stat), base)


# ============================================================
def weapon_crit_widen(weapon: dict) -> int :
	"""How much a weapon widens its wielder's crit range: 1 for Excellent proficiency, 1 for keen."""
	widen = 1 if (weapon.get("proficiency") or "").lower() == EXCELLENT else 0
	return widen + (1 if "keen" in (weapon.get("properties") or []) else 0)


# ============================================================
def expected_damage(stats: dict, weapon: dict, target_ac: int, target_dt: int, base: int = 5) -> float :
	"""Roughly what an attack is worth on average, used to pick weapons for automatic moves."""
	try :
		amount, sides = parse_dice(weapon.get("dice", "1d4"))
	except ValueError :
		return 0.0
	bonus = sum(b.value for b in weapon_bonuses(stats, weapon, base))
	chance = max(0.05, min(0.95, (21 - (target_ac - bonus)) / 20))
	per_hit = max(1.0, amount * (sides + 1) / 2 + damage_bonus(stats, weapon, base) - target_dt)
	return chance * per_hit
