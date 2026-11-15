import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from classes.combat import Abilities, Conditions as C, EffectCatalog, Effects, Rules
from classes.combat.DamageTypes import DEFAULTS
from classes.combat.Engine import CombatError, Engine
from classes.combat.Loadout import Loadout
from classes.combat.State import ACTIVE, AUTO, Combatant, DOWNED, DYING, ENDED, Fight, GM, LIVE, PAUSED, Side, \
	STABLE
from classes.gear.Gear import ARMOR, Gear, WEAPON
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CombatTransactions import CombatTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

TYPES = {name.lower() : {"name" : name, "trigger" : trigger, "effect" : effect} for name, trigger, effect in DEFAULTS}
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
SWORD = {"key" : "sword", "name" : "Sword", "type" : "Slashing", "dice" : "1d8", "attack_stat" : "strength",
         "damage_stat" : "strength", "hit_mod" : 0, "range" : "melee", "properties" : [], "proficiency" : "average"}


class Dice :
	"""A random.Random stand-in that hands out the given rolls in order, then 10s."""

	def __init__(self, *rolls) :
		self.rolls = list(rolls)

	def randint(self, low, high) :
		value = self.rolls.pop(0) if self.rolls else 10
		return max(low, min(high, value))

	def choice(self, options) :
		return options[0]


def fighter(combatant_id: int, side_id: int, name: str, stats: dict | None = None, hp: int = 30, ap: int = 7,
            ac: int = 10, dt: int = 0, sequence: int = 10, controller: str = "player", weapons=None,
            abilities=None, uid: int | None = None) -> Combatant :
	special = {stat : 5 for stat in Rules.STATS} | (stats or {})
	snapshot = {"base" : 5, "special" : special, "level" : 1, "weapons" : weapons or [dict(SWORD)],
	            "armor" : {"armor_class" : "clothing", "ac" : 0, "dt" : dt}, "abilities" : abilities or [],
	            "crit_min" : Rules.crit_min(special["luck"]), "fumble_max" : Rules.fumble_max(special["luck"]),
	            "confirm_crits" : special["luck"] <= 0}
	return Combatant(id=combatant_id, side_id=side_id, kind="character", name=name, stats=snapshot,
	                 uid=uid if uid is not None else combatant_id, controller=controller, hp=hp, hp_max=hp, ap=ap,
	                 ap_max=ap, ac=ac, dt=dt, sequence=sequence, weapon_key="sword", position=combatant_id)


def duel(pacing: str = "async", **fields) -> Fight :
	fight = Fight(id=1, guild_id=GUILD_ID, gm_uid=99, pacing=pacing, sides=[Side(1, "Party", 1), Side(2, "Enemies", 2)])
	fight.combatants = [fighter(1, 1, "Ayla", sequence=12), fighter(2, 2, "Bandit", sequence=8)]
	for key, value in fields.items() :
		setattr(fight, key, value)
	return fight


def engine(fight: Fight, *rolls) -> Engine :
	return Engine(fight, TYPES, rng=Dice(*rolls), now=NOW)


def ability(number: int, name: str, kind: str, tier: str, keys: list[str], stat: str = "intelligence",
            damage_type: str | None = None) -> dict :
	"""An ability as a fight uses it, built from catalog effect keys."""
	record = SimpleNamespace(id=number, name=name, kind=kind, tier=tier, stat=stat, damage_type=damage_type,
	                         activation="active", effects=[{"key" : key} for key in keys])
	return Loadout.ability_data(record)


class TestRules(unittest.TestCase) :

	def test_derived_stats(self) :
		average = {stat : 5 for stat in Rules.STATS}
		self.assertEqual(Rules.modifier(8), 3)
		self.assertEqual(Rules.modifier(-2), -7)
		self.assertEqual(Rules.hp_max(average), 30)
		self.assertEqual(Rules.hp_max(average, level=3), 34)
		self.assertEqual(Rules.hp_max(average | {"endurance" : 0}, level=5), 20)
		self.assertEqual(Rules.hp_max({"strength" : -2, "endurance" : -2}), 9)
		self.assertEqual(Rules.ap_max(average), 7)
		self.assertEqual(Rules.ap_max(average | {"agility" : -2}), 4)
		self.assertEqual(Rules.sequence(average), 10)

	def test_armor_class_caps(self) :
		plate = {"ac" : 4}
		self.assertEqual(Rules.armor_class({"agility" : 5}), 10)
		self.assertEqual(Rules.armor_class({"agility" : 10}, plate, shield=True), 18)
		self.assertEqual(Rules.armor_class({"agility" : 20}, plate, shield=True), 18)
		self.assertEqual(Rules.armor_class({"agility" : 20}), 12)
		self.assertEqual(Rules.armor_class({"agility" : 1}, plate), 10)

	def test_crit_and_fumble_ranges(self) :
		self.assertEqual([Rules.crit_min(luck) for luck in (-2, 1, 5, 6, 7, 8, 9, 13, 20, 26)],
		                 [20, 20, 20, 20, 19, 19, 18, 16, 13, 10])
		self.assertEqual(Rules.crit_min(5, widen=2), 18)
		self.assertEqual(Rules.crit_min(26, widen=20), 2)
		self.assertEqual([Rules.fumble_max(luck) for luck in (5, 3, 2, 1, 0, -2)], [1, 1, 2, 2, 3, 3])

	def test_old_weapon_and_armor_values_are_converted(self) :
		weapon = Rules.normalise_weapon({"dice" : "1d8", "modifier" : "damage:agility", "hitmodifier" : 2})
		self.assertEqual((weapon["attack_stat"], weapon["damage_stat"], weapon["hit_mod"], weapon["range"]),
		                 ("agility", "agility", 2, "melee"))
		bow = Rules.normalise_weapon({"dice" : "1d10", "modifier" : "", "hitmodifier" : 1})
		self.assertEqual((bow["attack_stat"], bow["damage_stat"], bow["range"]), ("perception", None, "ranged"))
		self.assertEqual(Rules.normalise_armor({"hp" : 85, "ac" : 14, "hitchance" : 1}),
		                 {"armor_class" : "light", "ac" : 1, "dt" : 1, "hit_mod" : 1, "ability_hit_mod" : 0})
		self.assertEqual(Rules.normalise_armor({"ac" : 19, "hitchance" : -2})["armor_class"], "heavy")
		self.assertEqual(Rules.normalise_armor({"ac" : 19, "hitchance" : -2})["hit_mod"], 0)

	def test_weapon_ap_and_penalties(self) :
		self.assertEqual(Rules.weapon_ap({"properties" : ["light"]}), 2)
		self.assertEqual(Rules.weapon_ap({"properties" : []}), 3)
		self.assertEqual(Rules.weapon_ap({"properties" : ["two_handed"]}), 4)
		self.assertEqual(Rules.weapon_ap({"properties" : ["loading", "light"]}), 5)
		self.assertEqual(Rules.weapon_ap({"properties" : [], "ap" : 6}), 6)
		self.assertEqual(Rules.unmet_penalty({"strength" : 2}, {"strength" : 4}), -2)
		self.assertEqual(Rules.unmet_penalty({"strength" : 1}, {"strength" : 13}), -5)
		self.assertEqual(Rules.armor_penalty("heavy", "light"), -4)
		self.assertEqual(Rules.armor_penalty("light", "heavy"), 0)
		self.assertEqual(Rules.armor_penalty("heavy", None), 0)

	def test_dice_helpers(self) :
		self.assertEqual(Rules.halve_dice("3d6"), "2d6")
		self.assertEqual(Rules.halve_dice("4d8"), "2d8")
		self.assertEqual(Rules.halve_dice("1d6"), "1d3")
		self.assertEqual(Rules.step_down("3d6"), "2d6")
		self.assertEqual(Rules.step_down("1d6"), "1d4")
		with self.assertRaises(ValueError) :
			Rules.parse_dice("d6")

	def test_attack_rolls(self) :
		bonuses = [Rules.Bonus("STR", 3)]
		self.assertTrue(Rules.roll_attack(bonuses, 13, rng=Dice(10)).hit)
		self.assertFalse(Rules.roll_attack(bonuses, 14, rng=Dice(10)).hit)
		strong = Rules.roll_attack(bonuses, 8, rng=Dice(10))
		self.assertTrue(strong.strong and not strong.crit)
		fumble = Rules.roll_attack(bonuses, 2, fumble_to=2, rng=Dice(2))
		self.assertTrue(fumble.fumble and not fumble.hit)
		crit = Rules.roll_attack(bonuses, 30, crit_from=19, rng=Dice(19))
		self.assertTrue(crit.hit and crit.crit and crit.strong)
		# With Luck 0 or below, only a natural 20 can crit, and a second roll has to hit too.
		unconfirmed = Rules.roll_attack(bonuses, 20, crit_from=18, confirm_crits=True, rng=Dice(20, 5))
		self.assertTrue(unconfirmed.hit and not unconfirmed.crit)
		self.assertFalse(Rules.roll_attack(bonuses, 30, crit_from=18, confirm_crits=True, rng=Dice(19)).hit)
		worse = Rules.roll_attack(bonuses, 13, disadvantage=True, rng=Dice(15, 4))
		self.assertEqual((worse.natural, worse.hit), (4, False))

	def test_damage_rolls(self) :
		self.assertEqual(Rules.roll_damage("2d6", 2, 1, rng=Dice(3, 4)).total, 8)
		crit = Rules.roll_damage("2d6", 2, 5, crit=True, rng=Dice(1, 1))
		self.assertEqual((crit.total, crit.rolls), (16, [6, 6, 1, 1]))
		self.assertEqual(Rules.roll_damage("1d4", 0, 9, rng=Dice(1)).total, 1)
		self.assertEqual(Rules.roll_damage("1d6", 0, 3, extra_dice=1, ignore_dt=True, rng=Dice(2, 3)).total, 5)

	def test_weapon_bonuses(self) :
		stats = {"special" : {"strength" : 8}, "armor" : {"hit_mod" : 1}, "level_bonus" : 1, "shield" : True,
		         "armor_penalty" : -2}
		weapon = dict(SWORD) | {"proficiency" : "excellent", "requirement_penalty" : -1}
		total = sum(bonus.value for bonus in Rules.weapon_bonuses(stats, weapon))
		# STR +3, Excellent +1, armor +1, level +1, shield -2, requirements -1, armor proficiency -2
		self.assertEqual(total, 1)
		self.assertEqual(Rules.weapon_crit_widen(weapon | {"properties" : ["keen"]}), 2)
		self.assertEqual(Rules.weapon_bonuses({}, {"to_hit" : 4})[0].value, 4)


class TestConditions(unittest.TestCase) :

	def test_add_refresh_and_count_down(self) :
		conditions = []
		C.add(conditions, C.BLEEDING, 1)
		C.add(conditions, C.BLEEDING, 3)
		self.assertEqual(C.get(conditions, C.BLEEDING)["turns"], 3)
		C.add(conditions, C.EXPOSED, 1)
		C.add(conditions, C.GUARD, None, 4)
		self.assertEqual(C.count_down(conditions), [])
		self.assertTrue(C.has(conditions, C.EXPOSED) and C.has(conditions, C.GUARD))
		C.add(conditions, C.SLOWED, 1)
		self.assertEqual(C.count_down(conditions), [C.SLOWED])
		self.assertEqual(C.text(conditions), "Bleeding 1")

	def test_stun_immunity(self) :
		conditions = [{"name" : C.STUN_IMMUNE, "turns" : 1}]
		self.assertFalse(C.add(conditions, C.STUNNED, 1))
		C.count_down(conditions)
		self.assertTrue(C.add(conditions, C.STUNNED, 1))


class TestAbilityRules(unittest.TestCase) :

	def check(self, kind: str, tier: str, *keys: str, school_stat: str | None = None, stat: str = "intelligence") :
		effects = [EffectCatalog.get(key) for key in keys]
		return Abilities.check_active(kind, tier, effects, school_stat, stat)

	def test_definitions(self) :
		self.assertIsNone(self.check("ability", "weak", "strike"))
		self.assertIn("school", self.check("spell", "weak", "bolt"))
		self.assertIn("Charisma", self.check("spell", "weak", "bolt", school_stat="charisma"))
		self.assertIsNone(self.check("spell", "weak", "bolt", school_stat="intelligence"))
		self.assertIn("physical abilities", self.check("spell", "weak", "strike", school_stat="intelligence"))
		self.assertIn("for spells", self.check("ability", "weak", "fireball"))
		self.assertIn("higher tier", self.check("ability", "cantrip", "stunning_strike"))
		self.assertIsNone(self.check("ability", "weak", "stunning_strike"))
		self.assertIn("at most 2", self.check("ability", "cantrip", "strike", "rend", "trip"))
		self.assertIn("not both", self.check("ability", "weak", "strike", "rally"))
		self.assertIsNone(self.check("ability", "weak", "strike", "rage"))
		self.assertIn("need an effect", self.check("ability", "weak", "sweeping", "reckless"))
		self.assertIn("one of the area", self.check("ability", "strong", "strike", "sweeping", "onslaught"))
		self.assertIn("at most 2 drawbacks", self.check("ability", "strong", "strike", "reckless", "strain",
		                                                  "exhausting"))
		self.assertIn("once per fight already", self.check("ability", "strong", "strike", "one_shot"))
		self.assertIn("picked once", self.check("ability", "weak", "strike", "strike"))

	def test_costs_and_dice(self) :
		effects = [EffectCatalog.get(key) for key in ("pyrokinesis", "widened")]
		self.assertEqual(Effects.ap_cost("normal", effects), 2 + 3 + 2)
		self.assertEqual(Effects.ap_cost("normal", effects + [EffectCatalog.get("blood_price")]), 6)
		self.assertEqual(Effects.target_limit(effects), 3)
		self.assertEqual(Effects.dice("normal", effects[0], effects), "2d6")
		self.assertEqual(Effects.dice("strong", EffectCatalog.get("magic_missile"), []), "3d8")
		self.assertEqual(Effects.dice("cantrip", EffectCatalog.get("bolt"), [EffectCatalog.get("empowered_spell")]),
		                 "1d8")
		self.assertEqual(Effects.ability_uses("weak", [EffectCatalog.get("strike"), EffectCatalog.get("one_shot")]), 1)

	def test_slots(self) :
		spells = [("spell", "cantrip", False), ("spell", "weak", False), ("spell", "weak", False)]
		self.assertIn("Spellcasters", Abilities.check_learn(spells, "spell", "weak", legendary=False))
		self.assertIsNone(Abilities.check_learn(spells, "spell", "weak", legendary=True))
		self.assertIsNone(Abilities.check_learn(spells, "spell", "strong", legendary=False))
		self.assertIn("spellcaster", Abilities.check_learn(spells, "ability", "weak", legendary=False))
		self.assertIsNone(Abilities.check_learn(spells + [("ability", "weak", True)], "spell", "normal", False))
		abilities = [("ability", "strong", False), ("ability", "weak", False)]
		self.assertIn("Strong", Abilities.check_learn(abilities, "ability", "strong", legendary=False))
		self.assertIsNone(Abilities.check_learn(abilities, "ability", "normal", legendary=False))
		self.assertIn("3 ability slots", Abilities.check_learn(abilities + [("ability", "weak", False)], "ability", "weak",
		                                                   legendary=False))


class TestTurns(unittest.TestCase) :

	def test_a_fight_needs_two_sides(self) :
		fight = duel()
		fight.combatants[1].side_id = 1
		with self.assertRaises(CombatError) :
			engine(fight).start()

	def test_async_phases_follow_sequence(self) :
		fight = duel()
		fight.combatants[1].sequence = 20
		run = engine(fight)
		run.start()
		self.assertEqual((fight.state, fight.round, fight.order), (ACTIVE, 1, [2, 1]))
		self.assertEqual([combatant.name for combatant in run.actors()], ["Bandit"])
		self.assertEqual(fight.deadline, NOW + timedelta(hours=12))
		self.assertIn(2, run.outcome.pings)
		with self.assertRaises(CombatError) :
			run.attack(fight.combatant(1), 2)

	def test_attacks_spend_ap_and_leftover_ap_is_ac(self) :
		fight = duel()
		run = engine(fight, 15, 4)
		run.start()
		ayla, bandit = fight.combatant(1), fight.combatant(2)
		run.attack(ayla, 2)
		self.assertEqual((ayla.ap, bandit.hp), (4, 26))
		run = engine(fight, 1)
		run.end_turn_action(ayla)
		self.assertEqual(C.amount(ayla.conditions, C.GUARD), 4)
		self.assertEqual(run.effective_ac(ayla), 14)
		self.assertEqual([combatant.name for combatant in run.actors()], ["Bandit"])
		self.assertEqual(bandit.ap, 7)

	def test_switching_weapons_costs_ap(self) :
		fight = duel()
		ayla = fight.combatant(1)
		ayla.stats["weapons"].append(dict(Rules.UNARMED))
		run = engine(fight, 15, 2)
		run.start()
		run.attack(ayla, 2, "unarmed")
		self.assertEqual(ayla.ap, 4)
		self.assertEqual(ayla.weapon_key, "unarmed")

	def test_turn_ends_when_ap_runs_out_and_the_next_side_goes(self) :
		fight = duel()
		run = engine(fight, 15, 4, 15, 4)
		run.start()
		ayla = fight.combatant(1)
		run.attack(ayla, 2)
		run = engine(fight, 15, 4)
		run.attack(ayla, 2)
		# 1 AP is left, which pays for nothing, so the turn ends by itself.
		self.assertTrue(ayla.acted)
		self.assertEqual(C.amount(ayla.conditions, C.GUARD), 1)
		self.assertEqual([combatant.name for combatant in run.actors()], ["Bandit"])

	def test_downing_the_last_enemy_ends_the_fight(self) :
		fight = duel()
		fight.combatant(2).hp = 3
		run = engine(fight, 15, 8)
		run.start()
		outcome = run.attack(fight.combatant(1), 2)
		self.assertEqual((fight.state, fight.winner_side_id, fight.combatant(2).state), (ENDED, 1, DOWNED))
		self.assertTrue(outcome.ended)
		self.assertIsNone(fight.deadline)

	def test_live_turns_follow_sequence(self) :
		fight = duel(pacing=LIVE)
		fight.combatants.append(fighter(3, 1, "Rook", sequence=10))
		fight.combatant(3).conditions.append({"name" : C.SLOWED, "turns" : 2})
		run = engine(fight)
		run.start()
		self.assertEqual(fight.order, [1, 2, 3])
		self.assertEqual([combatant.name for combatant in run.actors()], ["Ayla"])
		self.assertEqual(fight.deadline, NOW + timedelta(minutes=3))
		run.end_turn_action(fight.combatant(1))
		self.assertEqual([combatant.name for combatant in run.actors()], ["Bandit"])

	def test_automatic_npcs_act_at_once(self) :
		fight = duel()
		bandit = fight.combatant(2)
		bandit.controller = AUTO
		bandit.sequence = 20
		run = engine(fight, 15, 4, 15, 4)
		run.start()
		self.assertLess(fight.combatant(1).hp, 30)
		self.assertTrue(bandit.acted)
		self.assertEqual([combatant.name for combatant in run.actors()], ["Ayla"])

	def test_gm_controlled_npcs_wait(self) :
		fight = duel()
		bandit = fight.combatant(2)
		bandit.controller = GM
		bandit.sequence = 20
		run = engine(fight)
		run.start()
		self.assertEqual([combatant.name for combatant in run.actors()], ["Bandit"])

	def test_timeout_gives_automatic_moves_and_pings_after_three(self) :
		fight = duel()
		run = engine(fight)
		run.start()
		ayla = fight.combatant(1)
		ayla.idle_turns = 2
		late = Engine(fight, TYPES, rng=Dice(15, 4), now=NOW + timedelta(hours=13))
		outcome = late.timeout()
		self.assertEqual(ayla.idle_turns, 3)
		self.assertTrue(ayla.acted)
		self.assertLess(fight.combatant(2).hp, 30)
		self.assertTrue(any("missed 3 turns" in ping for ping in outcome.gm_pings))
		self.assertEqual([combatant.name for combatant in late.actors()], ["Bandit"])

	def test_timeout_waits_for_the_deadline(self) :
		fight = duel()
		run = engine(fight)
		run.start()
		Engine(fight, TYPES, now=NOW + timedelta(hours=1)).timeout()
		self.assertFalse(fight.combatant(1).acted)

	def test_pause_keeps_the_time_left(self) :
		fight = duel()
		engine(fight).start()
		Engine(fight, TYPES, now=NOW + timedelta(hours=2)).pause()
		self.assertEqual((fight.state, fight.paused_seconds, fight.deadline), (PAUSED, 10 * 3600, None))
		with self.assertRaises(CombatError) :
			engine(fight).attack(fight.combatant(1), 2)
		Engine(fight, TYPES, now=NOW + timedelta(days=1)).resume()
		self.assertEqual(fight.deadline, NOW + timedelta(days=1, hours=10))


class TestConditionsInFights(unittest.TestCase) :

	def test_bleeding_ticks_at_the_start_of_the_turn(self) :
		fight = duel()
		fight.combatant(1).conditions.append({"name" : C.BLEEDING, "turns" : 2})
		engine(fight, 3).start()
		self.assertEqual(fight.combatant(1).hp, 27)

	def test_stunned_loses_the_turn_and_cannot_be_stunned_again_at_once(self) :
		fight = duel()
		ayla = fight.combatant(1)
		ayla.conditions.append({"name" : C.STUNNED, "turns" : 1})
		run = engine(fight)
		run.start()
		self.assertTrue(ayla.acted)
		self.assertEqual([combatant.name for combatant in run.actors()], ["Bandit"])
		self.assertFalse(C.add(ayla.conditions, C.STUNNED, 1))

	def test_strong_slashing_hit_makes_the_target_bleed(self) :
		fight = duel()
		run = engine(fight, 18, 4)
		run.start()
		run.attack(fight.combatant(1), 2)
		self.assertTrue(C.has(fight.combatant(2).conditions, C.BLEEDING))

	def test_piercing_strong_hit_ignores_dt_and_lightning_arcs(self) :
		fight = duel()
		fight.combatants.append(fighter(3, 2, "Thug", sequence=1))
		bandit = fight.combatant(2)
		bandit.dt = 3
		ayla = fight.combatant(1)
		ayla.stats["weapons"] = [dict(SWORD) | {"type" : "Piercing", "key" : "sword"},
		                         dict(SWORD) | {"type" : "Lightning", "key" : "orb"}]
		run = engine(fight, 18, 4)
		run.start()
		run.attack(ayla, 2, "sword")
		self.assertEqual(bandit.hp, 30 - 4)
		bandit.dt = 0
		run = engine(fight, 18, 4)
		run.attack(ayla, 2, "orb")
		self.assertEqual(fight.combatant(3).hp, 30 - 2)

	def test_shield_absorbs_damage(self) :
		fight = duel()
		fight.combatant(2).conditions.append({"name" : C.SHIELDED, "turns" : 2, "amount" : 3})
		run = engine(fight, 15, 5)
		run.start()
		run.attack(fight.combatant(1), 2)
		self.assertEqual(fight.combatant(2).hp, 28)
		self.assertFalse(C.has(fight.combatant(2).conditions, C.SHIELDED))

	def test_fumble_leaves_the_attacker_open_until_its_next_turn(self) :
		fight = duel()
		run = engine(fight, 1)
		run.start()
		ayla = fight.combatant(1)
		run.attack(ayla, 2)
		self.assertTrue(C.has(ayla.conditions, C.EXPOSED))
		run.end_turn_action(ayla)
		self.assertTrue(C.has(ayla.conditions, C.EXPOSED))


class TestActions(unittest.TestCase) :

	def test_help_and_revive(self) :
		fight = duel()
		fight.combatants.append(fighter(3, 1, "Rook"))
		rook = fight.combatant(3)
		rook.state, rook.hp = DOWNED, 0
		run = engine(fight, 12)
		run.start()
		ayla = fight.combatant(1)
		run.revive(ayla, 3)
		self.assertEqual((rook.state, rook.hp), ("active", 1))
		run = engine(fight)
		with self.assertRaises(CombatError) :
			run.help(ayla, 1)
		run.help(ayla, 3)
		self.assertEqual(C.amount(rook.conditions, C.HELPED), 2)

	def test_crippled_stats_block_actions(self) :
		fight = duel()
		ayla = fight.combatant(1)
		ayla.stats["special"] |= {"charisma" : 0, "intelligence" : 0, "agility" : 0}
		run = engine(fight)
		run.start()
		with self.assertRaises(CombatError) :
			run.help(ayla, 1)
		run.flee(ayla)
		self.assertEqual(ayla.state, "active")
		self.assertTrue(ayla.acted)

	def test_flee(self) :
		fight = duel()
		fight.combatants.append(fighter(3, 1, "Rook", sequence=12))
		run = engine(fight, 15)
		run.start()
		run.flee(fight.combatant(1))
		self.assertEqual(fight.combatant(1).state, "fled")
		self.assertEqual(fight.state, ACTIVE)

	def test_other_waits_for_the_gm(self) :
		fight = duel()
		run = engine(fight)
		run.start()
		ayla = fight.combatant(1)
		run.other(ayla, "Kicks sand in his eyes")
		self.assertEqual(fight.pending[0]["number"], 1)
		self.assertEqual(C.amount(ayla.conditions, C.GUARD), 7)
		Engine(fight, TYPES, now=NOW).settle_other(1, "He is blinded", fight.combatant(2), -4)
		self.assertEqual((fight.pending, fight.combatant(2).hp), ([], 26))

	def test_abilities(self) :
		bolt = ability(7, "Firebolt", "spell", "weak", ["fire_bolt"])
		mend = ability(8, "Mend", "spell", "cantrip", ["mend"], damage_type="Restoration")
		fight = duel()
		ayla = fight.combatant(1)
		ayla.stats["abilities"] = [bolt, mend]
		ayla.stats["special"]["intelligence"] = 8
		ayla.ap_max = 20
		run = engine(fight, 12, 3, 3)
		run.start()
		run.use_ability(ayla, 7, [2])
		self.assertEqual(fight.combatant(2).hp, 30 - 9)
		self.assertEqual(ayla.ability_uses["7"], 1)
		ayla.hp = 10
		ayla.conditions.append({"name" : C.BURNING, "turns" : 2})
		run = engine(fight, 2)
		run.use_ability(ayla, 8, [1])
		self.assertEqual(ayla.hp, 15)
		self.assertFalse(C.has(ayla.conditions, C.BURNING))
		ayla.ability_uses["7"] = 3
		with self.assertRaises(CombatError) :
			engine(fight).use_ability(ayla, 7, [2])
		ayla.conditions.append({"name" : C.SILENCED, "turns" : 1})
		with self.assertRaises(CombatError) :
			engine(fight).use_ability(ayla, 8, [1])

	def test_condition_abilities_use_a_save(self) :
		hold = ability(9, "Hold", "ability", "normal", ["caltrops"], stat="charisma", damage_type="Mental")
		fight = duel()
		ayla = fight.combatant(1)
		ayla.stats["abilities"] = [hold]
		run = engine(fight, 5)
		run.start()
		run.use_ability(ayla, 9, [2])
		bandit = fight.combatant(2)
		# DC 12 against a save of 5: a strong failure, so Mental's effect (Silenced) applies as well.
		self.assertEqual(C.get(bandit.conditions, C.SLOWED)["turns"], 2)
		self.assertTrue(C.has(bandit.conditions, C.SILENCED))


class TestLethalAndGm(unittest.TestCase) :

	def test_death_rolls_and_confirming_a_death(self) :
		fight = duel(lethal=True)
		fight.combatants.append(fighter(3, 1, "Rook", sequence=20))
		rook = fight.combatant(3)
		rook.state, rook.hp = DOWNED, 0
		rook.character_id = 55
		run = engine(fight, 2)
		run.start()
		self.assertEqual(rook.death_failures, 1)
		rook.death_failures = 2
		engine(fight, 3).begin_turn(rook)
		self.assertEqual(rook.state, DYING)
		outcome = engine(fight).confirm_death(rook)
		self.assertEqual(outcome.deaths, {3 : 55})
		self.assertEqual(rook.state, "dead")

	def test_three_successes_mean_stable(self) :
		fight = duel(lethal=True)
		fight.combatants.append(fighter(3, 1, "Rook"))
		rook = fight.combatant(3)
		rook.state, rook.hp, rook.death_successes = DOWNED, 0, 2
		engine(fight, 15).begin_turn(rook)
		self.assertEqual(rook.state, STABLE)

	def test_gm_tools(self) :
		fight = duel()
		run = engine(fight)
		run.start()
		bandit = fight.combatant(2)
		run.adjust_hp(bandit, -10)
		self.assertEqual(bandit.hp, 20)
		run.set_condition(bandit, C.WEAKENED, 2)
		self.assertTrue(C.has(bandit.conditions, C.WEAKENED))
		run.set_condition(bandit, C.WEAKENED, None)
		self.assertFalse(C.has(bandit.conditions, C.WEAKENED))
		run.end_phase()
		self.assertEqual([combatant.name for combatant in run.actors()], ["Bandit"])
		run.remove(bandit)
		self.assertEqual((fight.state, fight.winner_side_id), (ENDED, 1))

	def test_undo_restores_the_snapshot(self) :
		fight = duel()
		engine(fight).start()
		snapshot = fight.snapshot()
		engine(fight, 15, 4).attack(fight.combatant(1), 2)
		self.assertEqual(fight.combatant(2).hp, 26)
		fight.restore(snapshot)
		self.assertEqual((fight.combatant(2).hp, fight.combatant(1).ap), (30, 7))

	def test_join_rules(self) :
		fight = duel()
		run = engine(fight)
		self.assertIsNone(run.join_problem(1, 5, 77))
		fight.combatant(1).character_id = 77
		self.assertIn("already", run.join_problem(1, 5, 77))
		fight.kind = "pvp"
		self.assertIn("invite", run.join_problem(2, 5, 78))
		fight.invites = {"2" : [5]}
		self.assertIsNone(run.join_problem(2, 5, 78))
		run.start()
		self.assertIn("late", run.join_problem(2, 5, 78))


class TestFightStorage(DatabaseTestCase) :

	def test_create_save_and_load(self) :
		self.add_server()
		fight = CombatTransactions().create(GUILD_ID, USER_ID, ["Party", "Enemies"], title="Ambush", thread_id=5)
		self.assertEqual([side.name for side in fight.sides], ["Party", "Enemies"])
		character = self.add_character()
		combatant = Loadout.for_character(character, fight.sides[0].id)
		CombatTransactions().add_combatant(fight.id, combatant)
		npc = Loadout.for_preset("minion", "Rat", fight.sides[1].id)
		CombatTransactions().add_combatant(fight.id, npc)
		fight = CombatTransactions().load_by_thread(5)
		self.assertEqual([combatant.name for combatant in fight.combatants], ["Ayla", "Rat"])
		self.assertEqual(CombatTransactions().open_fight_of(character.id), fight.id)
		engine(fight).start()
		CombatTransactions().save(fight)
		loaded = CombatTransactions().load(fight.id)
		self.assertEqual((loaded.state, loaded.round, loaded.order), (ACTIVE, 1, fight.order))
		CombatTransactions().log(fight.id, 1, "attack", "x", snapshot=fight.snapshot())
		CombatTransactions().log(fight.id, 1, "note", "y")
		self.assertEqual(CombatTransactions().last_undoable(fight.id).action, "attack")

	def test_loadout_reads_gear_and_proficiency(self) :
		self.add_server()
		character = self.add_character(strength=8, agility=7)
		items = GearItemTransactions()
		sword = items.add(GUILD_ID, WEAPON, "Sabre", combat={"type" : "Slashing", "dice" : "2d6",
		                                                      "attack_stat" : "agility", "damage_stat" : "agility",
		                                                      "hit_mod" : 1, "properties" : []},
		                  requirements={"agility" : 9})
		shield = items.add(GUILD_ID, WEAPON, "Buckler", combat={"type" : "Blunt", "dice" : "1d4",
		                                                        "properties" : ["shield", "light"]})
		mail = items.add(GUILD_ID, ARMOR, "Mail", combat={"armor_class" : "heavy", "ac" : 4, "dt" : 3})
		entry = Gear.grant(character, sword, USER_ID)
		CharacterGearTransactions().update(entry.id, proficiency="good")
		Gear.equip(Gear.grant(character, shield, USER_ID))
		Gear.equip(Gear.grant(character, mail, USER_ID))
		CharacterInfoTransactions().add(character.id, "Armor proficiency", "Light")
		combatant = Loadout.for_character(character, 1)
		stats = combatant.stats
		sabre = next(weapon for weapon in stats["weapons"] if weapon["name"] == "Sabre")
		self.assertEqual((sabre["proficiency"], sabre["requirement_penalty"]), ("good", -2))
		self.assertTrue(stats["shield"])
		self.assertEqual(stats["armor_penalty"], -4)
		# 10 + plate 4 + shield 2 + AGI +2 = 18 (the cap)
		self.assertEqual((combatant.ac, combatant.dt, combatant.hp, combatant.ap), (18, 3, 33, 8))
		self.assertEqual(combatant.weapon_key, f"gear:{entry.id}")
		self.assertEqual(stats["weapons"][-1]["key"], "unarmed")
