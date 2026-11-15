"""The balance simulator: plays many simulated fights per effect to find the ones that are far too strong or too weak
for their AP cost. It uses the real engine but no Discord or database, so it can run anywhere:

    .venv/Scripts/python.exe -m classes.combat.Balance [fights per effect] [report path]

Each effect is tried on its own at the lowest tier that allows it (modifiers and drawbacks ride on a plain Bolt or
Strike), in two scenarios:

- duel: a hero with the ability against a copy of itself without one;
- team: the hero and an ally against two foes, so healing, buffs, area and support effects have something to work on.

Everyone has average SPECIAL, 30 HP, AC 12, armor with DT 2 and a 1d8 sword (weapon techniques get a matching weapon).
Every fighter is played by the autopilot (classes/combat/Autopilot.py), so the hero uses its ability the way an NPC
would: when it does something useful, otherwise it attacks. A side that only attacks wins about half the time, so an
effect's win rate shows what it is worth once its AP cost is paid. Fights that nobody wins in time count as half a win.

Outliers are judged per scenario against the other effects of the same tier: above the third quartile + 1.5 × the
spread is "too strong", below the first quartile − 1.5 × the spread "too weak". An effect is too strong if it stands out
in either scenario, and too weak (or "worse than attacking", winning less often than just attacking) only when it does
so in both, since a support effect can't show its worth in a duel. The report is a Markdown file with a table per tier;
the numbers move with the random seed, so a borderline effect is worth a second run before its cost is changed.
"""
import random
import statistics
import sys
from dataclasses import dataclass

from classes.combat import Abilities, EffectCatalog, Effects, Rules
from classes.combat.DamageTypes import DEFAULTS
from classes.combat.Engine import Engine
from classes.combat.State import AUTO, Combatant, Fight, Side

TYPES = {name.lower() : {"name" : name, "trigger" : trigger, "effect" : effect} for name, trigger, effect in DEFAULTS}
WEAPON = {"key" : "sword", "name" : "Sword", "type" : "Slashing", "dice" : "1d8", "attack_stat" : "strength",
          "damage_stat" : "strength", "hit_mod" : 0, "range" : "melee", "properties" : [], "proficiency" : "average"}
HP = 30
AC = 12
DT = 2
AP = 7
DEFAULT_FIGHTS = 200
BASE = {Effects.MAGIC : "bolt", Effects.PHYSICAL : "strike"}
DUEL = "duel"
TEAM = "team"
SCENARIOS = [DUEL, TEAM]
TOO_STRONG = "too strong"
TOO_WEAK = "too weak"
WORSE = "worse than attacking"


@dataclass
class Result :
	"""How one effect did."""
	key: str
	name: str
	realm: str
	tier: str
	ap: int
	duel: float
	team: float
	verdict: str = ""

	# ============================================================
	def wins(self, scenario: str) -> float :
		return self.duel if scenario == DUEL else self.team


# ============================================================
def fighter(number: int, side: int, name: str) -> Combatant :
	special = {stat : 5 for stat in Rules.STATS}
	stats = {"base" : 5, "special" : special, "level" : 1, "weapons" : [dict(WEAPON), dict(Rules.UNARMED)],
	         "armor" : {"armor_class" : "light", "ac" : 0, "dt" : DT}, "abilities" : [], "passives" : [],
	         "crit_min" : 20, "fumble_max" : 1}
	return Combatant(id=number, side_id=side, kind="character", name=name, stats=stats, character_id=number,
	                 uid=number, controller=AUTO, behavior="aggressive", hp=HP, hp_max=HP, ap=AP, ap_max=AP, ac=AC,
	                 dt=DT, sequence=10, weapon_key="sword", position=number)


# ============================================================
def weapon_for(needs: str) -> dict :
	ranged = needs in (Rules.NEEDS_RANGED, "bow", "crossbow", "sling", "javelin", "hatchet", "shuriken", "pistol",
	                   "rifle", "scattergun")
	properties = ["shield"] if needs == Rules.NEEDS_SHIELD else ["thrown"] if needs == Rules.NEEDS_THROWN else []
	return dict(WEAPON) | {"key" : f"gear:{needs}", "name" : f"Practice {needs}",
	                       "kind" : needs if needs in Rules.WEAPON_KINDS else None,
	                       "range" : Rules.RANGED if ranged else Rules.MELEE, "properties" : properties}


# ============================================================
def build(effect: Effects.Effect) -> tuple[dict | None, str] :
	"""The ability the hero gets for an effect, and the tier it is tested at."""
	kind = "spell" if effect.realm == Effects.MAGIC else "ability"
	keys = [effect.key] if effect.main else [BASE[effect.realm], effect.key]
	effects = [EffectCatalog.get(key) for key in keys]
	tier = next((tier for tier in Effects.TIERS if Effects.check(kind, tier, effects) is None), None)
	if tier is None :
		return None, ""
	stat = "intelligence" if kind == "spell" else "strength"
	return Abilities.fight_data(1, effect.name, kind, tier, stat, "Fire", [{"key" : key} for key in keys]), tier


# ============================================================
def fight(scenario: str, ability: dict | None, needs: list[str], seed: int) -> float :
	"""One fight, played entirely by the autopilot. @return: 1 when the hero's side won, 0 when it lost, 0.5 when
	nobody won in time."""
	names = [("Hero", 1), ("Foe", 2)] if scenario == DUEL else [("Hero", 1), ("Ally", 1), ("Foe", 2), ("Brute", 2)]
	combatants = [fighter(number + 1, side, name) for number, (name, side) in enumerate(names)]
	hero = combatants[0]
	if ability is not None :
		hero.stats["abilities"] = [ability]
	for requirement in needs :
		hero.stats["weapons"].append(weapon_for(requirement))
	# Who goes first alternates, so going first isn't counted as the effect's value.
	for combatant in combatants :
		combatant.sequence = 11 if (combatant.side_id == 1) == bool(seed % 2) else 10
	state = Fight(id=1, guild_id=0, gm_uid=0, pacing="live", sides=[Side(1, "Heroes", 1), Side(2, "Foes", 2)])
	state.combatants = combatants
	Engine(state, TYPES, rng=random.Random(seed)).start()
	if state.state != "ended" or state.winner_side_id is None :
		return 0.5
	return 1.0 if state.winner_side_id == 1 else 0.0


# ============================================================
def measure(scenario: str, ability: dict | None, needs: list[str], fights: int, seed: int = 0) -> float :
	return sum(fight(scenario, ability, needs, seed * 100003 + number) for number in range(fights)) / fights


# ============================================================
def run(fights: int = DEFAULT_FIGHTS, effects: list | None = None) -> tuple[dict[str, float], list[Result]] :
	"""Measures every effect (or the given ones). @return: the baseline win rate per scenario and one result per
	effect."""
	baseline = {scenario : measure(scenario, None, [], fights * 2) for scenario in SCENARIOS}
	results = []
	for number, effect in enumerate(effects or EffectCatalog.ACTIVE_EFFECTS) :
		ability, tier = build(effect)
		if ability is None :
			continue
		needs = Effects.requirements(ability["effects"])
		results.append(Result(effect.key, effect.name, effect.realm, tier, ability["ap"],
		                      measure(DUEL, ability, needs, fights, number + 1),
		                      measure(TEAM, ability, needs, fights, number + 1)))
	judge(baseline, results)
	return baseline, results


# ============================================================
def bounds(group: list[Result], scenario: str) -> tuple[float, float] :
	"""The low and high outlier limits of a tier in a scenario."""
	q1, _, q3 = statistics.quantiles([result.wins(scenario) for result in group], n=4)
	spread = q3 - q1
	return q1 - 1.5 * spread, q3 + 1.5 * spread


# ============================================================
def judge(baseline: dict[str, float], results: list[Result]) -> None :
	"""Marks the outliers of each tier."""
	for tier in Effects.TIERS :
		group = [result for result in results if result.tier == tier]
		if len(group) < 4 :
			continue
		limits = {scenario : bounds(group, scenario) for scenario in SCENARIOS}
		for result in group :
			if any(result.wins(scenario) > limits[scenario][1] for scenario in SCENARIOS) :
				result.verdict = TOO_STRONG
			elif all(result.wins(scenario) < limits[scenario][0] for scenario in SCENARIOS) :
				result.verdict = TOO_WEAK
			elif all(result.wins(scenario) < baseline[scenario] - 0.05 for scenario in SCENARIOS) :
				result.verdict = WORSE


# ============================================================
def report(baseline: dict[str, float], results: list[Result], fights: int) -> str :
	lines = ["# Effect balance report", "",
	         f"{len(results)} effects, {fights} fights each in two scenarios (a duel and a 2-vs-2 team fight, everyone "
	         f"in DT 2 armor). A side that only attacks wins {baseline[DUEL]:.0%} of duels and {baseline[TEAM]:.0%} of "
	         f"team fights. Run `python -m classes.combat.Balance` to make a new one; see classes/combat/Balance.py for "
	         f"the method.", ""]
	counts = {verdict : len([result for result in results if result.verdict == verdict])
	          for verdict in (TOO_STRONG, TOO_WEAK, WORSE)}
	lines.append(", ".join(f"{count} {verdict}" for verdict, count in counts.items()) + ".")
	for tier in Effects.TIERS :
		group = sorted((result for result in results if result.tier == tier),
		               key=lambda result : -max(result.duel, result.team))
		if not group :
			continue
		medians = " / ".join(f"{statistics.median(result.wins(scenario) for result in group):.0%}"
		                     for scenario in SCENARIOS)
		lines += ["", f"## {tier.capitalize()} ({len(group)} effects, median win rate {medians} duel / team)", "",
		          "| Effect | Realm | AP | Duel | Team | Verdict |", "|---|---|---|---|---|---|"]
		for result in group :
			if result.verdict :
				lines.append(f"| {result.name} (`{result.key}`) | {result.realm} | {result.ap} | {result.duel:.0%} | "
				             f"{result.team:.0%} | {result.verdict} |")
		lines.append(f"| *{len([result for result in group if not result.verdict])} others within range* | | | | | |")
	return "\n".join(lines) + "\n"


# ============================================================
def main() -> None :
	fights = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FIGHTS
	path = sys.argv[2] if len(sys.argv) > 2 else "design/balance-report.md"
	baseline, results = run(fights)
	with open(path, "w", encoding="utf-8") as file :
		file.write(report(baseline, results, fights))
	flagged = len([result for result in results if result.verdict])
	print(f"Baseline {baseline[DUEL]:.0%} duel, {baseline[TEAM]:.0%} team; {flagged} of {len(results)} effects "
	      f"flagged; report in {path}")


if __name__ == "__main__" :
	main()
