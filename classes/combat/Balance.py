"""The balance simulator: plays many simulated fights per effect to find the ones that are far too strong or too weak
for their AP cost. It uses the real engine but no Discord or database, so it can run anywhere:

    .venv/Scripts/python.exe -m classes.combat.Balance [fights per effect] [report path]

Each effect is tried on its own at the lowest tier that allows it (modifiers and drawbacks ride on a plain Bolt or
Strike). A hero with the ability fights a copy of itself without one: both have average SPECIAL, 30 HP, AC 12 and a
1d8 weapon. The hero uses the ability whenever it can afford it and has uses left, and attacks with the rest of its AP;
the foe just attacks. A hero that only attacks wins about half the time, so an effect's win rate shows what it is worth
once its AP cost is paid. Weapon techniques get a matching weapon.

Outliers are judged against the other effects of the same tier: above the third quartile + 1.5 × the spread is "too
strong", below the first quartile − 1.5 × the spread "too weak", and anything that wins less often than just attacking
is "worse than attacking". The report is a Markdown file with a table per tier; the numbers move with the random seed,
so a borderline effect is worth a second run before its cost is changed.
"""
import random
import statistics
import sys
from dataclasses import dataclass

from classes.combat import Abilities, EffectCatalog, Effects, Rules
from classes.combat.DamageTypes import DEFAULTS
from classes.combat.Engine import CombatError, Engine
from classes.combat.State import AUTO, Combatant, Fight, PLAYER, Side

TYPES = {name.lower() : {"name" : name, "trigger" : trigger, "effect" : effect} for name, trigger, effect in DEFAULTS}
WEAPON = {"key" : "sword", "name" : "Sword", "type" : "Slashing", "dice" : "1d8", "attack_stat" : "strength",
          "damage_stat" : "strength", "hit_mod" : 0, "range" : "melee", "properties" : [], "proficiency" : "average"}
HP = 30
AC = 12
AP = 7
MAX_ROUNDS = 30
DEFAULT_FIGHTS = 200
BASE = {Effects.MAGIC : "bolt", Effects.PHYSICAL : "strike"}


@dataclass
class Result :
	"""How one effect did."""
	key: str
	name: str
	realm: str
	tier: str
	ap: int
	wins: float
	rounds: float
	verdict: str = ""


# ============================================================
def fighter(number: int, side: int, name: str, controller: str) -> Combatant :
	special = {stat : 5 for stat in Rules.STATS}
	stats = {"base" : 5, "special" : special, "level" : 1, "weapons" : [dict(WEAPON), dict(Rules.UNARMED)],
	         "armor" : {"armor_class" : "clothing", "ac" : 0, "dt" : 0}, "abilities" : [], "passives" : [],
	         "crit_min" : 20, "fumble_max" : 1}
	return Combatant(id=number, side_id=side, kind="character", name=name, stats=stats, character_id=number,
	                 uid=number, controller=controller, hp=HP, hp_max=HP, ap=AP, ap_max=AP, ac=AC, dt=0, sequence=10,
	                 weapon_key="sword", position=number)


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
def worth_using(ability: dict, hero: Combatant, foe: Combatant, used_this_turn: int) -> bool :
	"""Whether a sensible player would use the ability now: damage as often as AP allows; anything else at most once a
	turn, and only when it would change something (a condition not there yet, healing when hurt)."""
	mechanics = {effect.get("mechanic") for effect in ability.get("effects") or []}
	if mechanics & {Effects.ATTACK, Effects.BLAST} :
		return True
	if used_this_turn :
		return False
	if mechanics & {Effects.HEAL, Effects.REVIVE} and not mechanics - {Effects.HEAL, Effects.REVIVE, Effects.MODIFIER,
	                                                                   Effects.DRAWBACK} :
		return hero.hp < hero.hp_max * 0.6
	for effect in ability.get("effects") or [] :
		params = effect.get("params") or {}
		name = params.get("condition")
		if effect.get("mechanic") == Effects.COMPANION :
			name = "companion"
		if effect.get("mechanic") == Effects.DOOM :
			name = "doomed"
		if effect.get("mechanic") == Effects.SHIELD :
			name = "shielded"
		target = foe if effect.get("aim") == Effects.ENEMY else hero
		if name is None or not any(condition.get("name") == name for condition in target.conditions) :
			return True
	return False


# ============================================================
def hero_turn(engine: Engine, hero: Combatant, foe: Combatant) -> None :
	"""Uses the ability when it is worth it, then attacks with what is left."""
	used_this_turn = 0
	for _ in range(10) :
		if hero not in engine.actors() :
			return
		ability = hero.abilities[0] if hero.abilities else None
		used = False
		if ability is not None and worth_using(ability, hero, foe, used_this_turn) :
			left = engine.ability_uses_left(hero, ability)
			if (left is None or left > 0) and engine.ability_ap(ability) <= hero.ap :
				aim = engine.ability_aim(ability)
				targets = [foe.id] if aim == Effects.ENEMY else [hero.id]
				try :
					engine.use_ability(hero, 1, targets)
					used = True
					used_this_turn += 1
				except CombatError :
					used = False
		if not used :
			try :
				engine.attack(hero, foe.id)
			except CombatError :
				engine.end_turn_action(hero)
				return
		if engine.fight.state != "active" :
			return


# ============================================================
def duel(ability: dict | None, needs: list[str], seed: int) -> tuple[float, int] :
	"""One fight. @return: 1 when the hero won, 0 when it lost, 0.5 when nobody won in time; and the rounds it took."""
	fight = Fight(id=1, guild_id=0, gm_uid=0, pacing="live", sides=[Side(1, "Hero", 1), Side(2, "Foe", 2)])
	hero = fighter(1, 1, "Hero", PLAYER)
	foe = fighter(2, 2, "Foe", AUTO)
	foe.behavior = "aggressive"
	if ability is not None :
		hero.stats["abilities"] = [ability]
	for requirement in needs :
		hero.stats["weapons"].append(weapon_for(requirement))
	fight.combatants = [hero, foe]
	rng = random.Random(seed)
	# Who goes first alternates, so going first isn't counted as the effect's value.
	hero.sequence, foe.sequence = (11, 10) if seed % 2 else (10, 11)
	engine = Engine(fight, TYPES, rng=rng)
	engine.start()
	while fight.state == "active" and fight.round <= MAX_ROUNDS :
		if hero in engine.actors() :
			hero_turn(engine, hero, foe)
		elif not engine.actors() :
			engine.settle()
			if not engine.actors() and fight.state == "active" :
				break
		else :
			break
	if fight.state == "active" or fight.winner_side_id is None :
		return 0.5, fight.round
	return (1.0 if fight.winner_side_id == 1 else 0.0), fight.round


# ============================================================
def measure(ability: dict | None, needs: list[str], fights: int, seed: int = 0) -> tuple[float, float] :
	wins = rounds = 0
	for number in range(fights) :
		won, length = duel(ability, needs, seed * 100003 + number)
		wins += won
		rounds += length
	return wins / fights, rounds / fights


# ============================================================
def run(fights: int = DEFAULT_FIGHTS, effects: list | None = None) -> tuple[float, list[Result]] :
	"""Measures every effect (or the given ones). @return: the baseline win rate and one result per effect."""
	baseline, _ = measure(None, [], fights * 2)
	results = []
	for number, effect in enumerate(effects or EffectCatalog.ACTIVE_EFFECTS) :
		ability, tier = build(effect)
		if ability is None :
			continue
		wins, rounds = measure(ability, Effects.requirements(ability["effects"]), fights, number + 1)
		results.append(Result(effect.key, effect.name, effect.realm, tier, ability["ap"], wins, rounds))
	judge(baseline, results)
	return baseline, results


# ============================================================
def judge(baseline: float, results: list[Result]) -> None :
	"""Marks the outliers of each tier."""
	for tier in Effects.TIERS :
		group = [result for result in results if result.tier == tier]
		if len(group) < 4 :
			continue
		q1, _, q3 = statistics.quantiles([result.wins for result in group], n=4)
		spread = q3 - q1
		for result in group :
			if result.wins > q3 + 1.5 * spread :
				result.verdict = "too strong"
			elif result.wins < q1 - 1.5 * spread :
				result.verdict = "too weak"
			elif result.wins < baseline - 0.05 :
				result.verdict = "worse than attacking"


# ============================================================
def report(baseline: float, results: list[Result], fights: int) -> str :
	lines = [f"# Effect balance report", "",
	         f"{len(results)} effects, {fights} fights each. A hero that only attacks wins {baseline:.0%} of the time. "
	         f"Run `python -m classes.combat.Balance` to make a new one; see classes/combat/Balance.py for the method.",
	         ""]
	flagged = [result for result in results if result.verdict]
	counts = {verdict : len([result for result in flagged if result.verdict == verdict])
	          for verdict in ("too strong", "too weak", "worse than attacking")}
	lines.append(", ".join(f"{count} {verdict}" for verdict, count in counts.items()) + ".")
	for tier in Effects.TIERS :
		group = sorted((result for result in results if result.tier == tier), key=lambda result : -result.wins)
		if not group :
			continue
		median = statistics.median(result.wins for result in group)
		lines += ["", f"## {tier.capitalize()} ({len(group)} effects, median win rate {median:.0%})", "",
		          "| Effect | Realm | AP | Win rate | Rounds | Verdict |", "|---|---|---|---|---|---|"]
		for result in group :
			if result.verdict :
				lines.append(f"| {result.name} (`{result.key}`) | {result.realm} | {result.ap} | {result.wins:.0%} | "
				             f"{result.rounds:.1f} | {result.verdict} |")
		lines.append(f"| *{len([r for r in group if not r.verdict])} others within range* | | | | | |")
	return "\n".join(lines) + "\n"


# ============================================================
def main() -> None :
	fights = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FIGHTS
	path = sys.argv[2] if len(sys.argv) > 2 else "design/balance-report.md"
	baseline, results = run(fights)
	with open(path, "w", encoding="utf-8") as file :
		file.write(report(baseline, results, fights))
	flagged = len([result for result in results if result.verdict])
	print(f"Baseline {baseline:.0%}; {flagged} of {len(results)} effects flagged; report in {path}")


if __name__ == "__main__" :
	main()
