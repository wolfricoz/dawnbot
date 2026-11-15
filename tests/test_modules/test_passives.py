"""Passive abilities: their rules, slots, and what they do in fights."""
import unittest

from classes.combat import Abilities, Conditions as C, Passives as P
from classes.combat.AbilityFlow import AbilityFlow
from classes.combat.Loadout import Loadout
from classes.combat.State import DOWNED
from database.transactions.AbilityTransactions import APPROVED, AbilityTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID
from test_modules.test_combat import duel, engine, fighter

TYPE_NAMES = ["Slashing", "Piercing", "Fire"]


def passive(number: int, tier: str, **parts) -> dict :
	return {"id" : number, "name" : f"Passive {number}", "tier" : tier} | P.normalise(parts)


class TestPassiveRules(unittest.TestCase) :

	def test_checks(self) :
		values, problem = P.check("strong", {"type" : "bonus", "field" : "to_hit", "scope" : "piercing"}, TYPE_NAMES)
		self.assertEqual((values["scope"], problem), ("Piercing", None))
		self.assertIsNotNone(P.check("weak", {"type" : "bonus", "field" : "hp", "scope" : "melee"}, TYPE_NAMES)[1])
		self.assertIsNotNone(P.check("cantrip", {"type" : "bonus", "field" : "hp"}, TYPE_NAMES)[1])
		self.assertIsNotNone(P.check("strong", {"type" : "immune", "condition" : "stunned"}, TYPE_NAMES)[1])
		self.assertIsNone(P.check("normal", {"type" : "immune", "condition" : "stunned"}, TYPE_NAMES)[1])
		self.assertIsNotNone(P.check("weak", {"type" : "trigger", "trigger" : "last_stand"}, TYPE_NAMES)[1])
		self.assertIsNotNone(P.check("weak", {"type" : "trigger", "trigger" : "on_strong_hit"}, TYPE_NAMES)[1])
		self.assertIsNotNone(P.check("weak", {"type" : "resist", "scope" : "cold"}, TYPE_NAMES)[1])
		values, _ = P.check("normal", {"type" : "stacks", "field" : "damage"}, TYPE_NAMES)
		self.assertEqual(values["scope"], "any")
		self.assertIsNotNone(P.check("weak", {"type" : "aura", "field" : "hp"}, TYPE_NAMES)[1])

	def test_describe(self) :
		self.assertEqual(P.describe("strong", {"type" : "bonus", "field" : "to_hit", "scope" : "Piercing"}),
		                 "Strong passive · +3 to hit with Piercing · 2 slots")
		self.assertIn("up to 3", P.describe("normal", {"type" : "stacks", "field" : "damage", "scope" : "magic"}))

	def test_slots(self) :
		one_active = [("ability", "weak", False, False)]
		self.assertIsNone(Abilities.check_learn(one_active, "ability", "normal", False, passive=True))
		self.assertIn("3 ability slots", Abilities.check_learn(one_active + [("ability", "weak", False, False)],
		                                                         "ability", "normal", False, passive=True))
		one_passive = [("ability", "normal", False, True)]
		self.assertIn("passive 2", Abilities.check_learn(one_passive, "ability", "weak", False, passive=True))
		self.assertIsNone(Abilities.check_learn(one_passive, "ability", "weak", True, passive=True))
		self.assertIn("Strong", Abilities.check_learn([("ability", "strong", False, True)], "ability", "strong",
		                                              False))
		self.assertIn("spellcaster", Abilities.check_learn([("spell", "weak", False)], "ability", "weak", False,
		                                                   passive=True))


class TestPassivesInFights(unittest.TestCase) :

	def test_join_bonuses(self) :
		combatant = fighter(1, 1, "Ayla", ac=16)
		combatant.stats["passives"] = [passive(1, "normal", type="bonus", field="hp"),
		                               passive(2, "strong", type="bonus", field="ac"),
		                               passive(3, "weak", type="bonus", field="ap")]
		Loadout.apply_passives(combatant)
		self.assertEqual((combatant.hp, combatant.hp_max, combatant.ac, combatant.ap_max), (40, 40, 18, 8))

	def test_scoped_bonuses_and_auras(self) :
		fight = duel()
		fight.combatants.append(fighter(3, 1, "Rook"))
		ayla, rook = fight.combatant(1), fight.combatant(3)
		ayla.stats["passives"] = [passive(1, "normal", type="bonus", field="to_hit", scope="Slashing"),
		                          passive(2, "strong", type="aura", field="damage")]
		run = engine(fight)
		self.assertEqual(run.passive_roll(ayla, "Slashing", False, False), (2, 0))
		self.assertEqual(run.passive_roll(ayla, "Fire", True, False), (0, 0))
		self.assertEqual(run.passive_roll(rook, None, False, False), (0, 2))
		ayla.state = DOWNED
		self.assertEqual(run.passive_roll(rook, None, False, False), (0, 0))

	def test_resist_immune_and_last_stand(self) :
		fight = duel()
		ayla, bandit = fight.combatant(1), fight.combatant(2)
		ayla.stats["passives"] = [passive(1, "normal", type="resist", scope="magic"),
		                          passive(2, "normal", type="immune", condition="stunned"),
		                          passive(3, "normal", type="trigger", trigger="last_stand")]
		run = engine(fight)
		self.assertEqual(run.damage(ayla, 6, bandit, magic=True), 2)
		self.assertEqual(run.damage(ayla, 3, bandit, magic=True), 1)
		self.assertEqual(run.damage(ayla, 3, bandit), 3)
		self.assertFalse(run.inflict(ayla, C.STUNNED, 1))
		self.assertTrue(run.inflict(ayla, C.BLINDED, 1))
		run.damage(ayla, 100, bandit)
		self.assertEqual((ayla.hp, ayla.state), (1, "active"))
		run.damage(ayla, 100, bandit)
		self.assertEqual(ayla.state, DOWNED)

	def test_stacks_from_magic(self) :
		fight = duel()
		ayla, bandit = fight.combatant(1), fight.combatant(2)
		ayla.stats["passives"] = [passive(1, "normal", type="stacks", field="damage", scope="magic"),
		                          passive(2, "weak", type="stacks", field="ac", scope="any")]
		run = engine(fight)
		run.damage(ayla, 2, bandit)
		self.assertEqual(run.passive_roll(ayla, None, False, False), (0, 0))
		for _ in range(5) :
			run.damage(ayla, 1, bandit, magic=True)
		self.assertEqual(run.passive_roll(ayla, None, False, False), (0, 3))
		self.assertEqual(run.effective_ac(ayla), 12)

	def test_own_stack_limits(self) :
		values, problem = P.check("weak", {"type" : "stacks", "field" : "damage", "scope" : "magic", "limit" : 24},
		                          TYPE_NAMES)
		self.assertEqual((values["limit"], problem), (24, None))
		self.assertIsNotNone(P.check("weak", {"type" : "stacks", "field" : "damage", "limit" : 31}, TYPE_NAMES)[1])
		self.assertIsNone(P.check("weak", {"type" : "bonus", "field" : "hp", "limit" : 9}, TYPE_NAMES)[0]["limit"])
		self.assertIn("up to 24", P.describe("weak", values))
		fight = duel()
		ayla, bandit = fight.combatant(1), fight.combatant(2)
		ayla.stats["passives"] = [passive(1, "weak", type="stacks", field="damage", scope="magic", limit=24)]
		run = engine(fight)
		for _ in range(30) :
			run.damage(ayla, 0 if ayla.hp < 2 else 1, bandit, magic=True)
			ayla.hp = 30
		self.assertEqual(run.passive_roll(ayla, None, True, False), (0, 24))
		self.assertEqual(P.max_stacks({"tier" : "strong"}), 5)

	def test_regenerate_counter_and_strong_hits(self) :
		fight = duel()
		ayla, bandit = fight.combatant(1), fight.combatant(2)
		bandit.stats["passives"] = [passive(1, "weak", type="trigger", trigger="counter")]
		ayla.stats["passives"] = [passive(2, "normal", type="trigger", trigger="on_strong_hit", condition="weakened")]
		run = engine(fight, 2, 3)
		run.start()
		run.attack(ayla, 2)
		self.assertEqual(ayla.hp, 27)
		run = engine(fight, 2)
		run.attack(ayla, 2)
		# Once per round: the second miss isn't countered.
		self.assertEqual(ayla.hp, 27)
		run = engine(fight, 20, 4, 4)
		run.resolve_attack(ayla, bandit, ayla.weapons[0])
		self.assertTrue(C.has(bandit.conditions, C.WEAKENED))
		ayla.stats["passives"].append(passive(3, "strong", type="trigger", trigger="regenerate"))
		ayla.hp = 20
		engine(fight, 5).begin_turn(ayla)
		self.assertEqual(ayla.hp, 25)


class TestPassiveAbilities(DatabaseTestCase) :

	def test_learning_and_loadout(self) :
		self.add_server()
		values, problem = AbilityFlow.check_passive(GUILD_ID, "normal", {"type" : "bonus", "field" : "hp"})
		self.assertIsNone(problem)
		iron = AbilityTransactions().add(GUILD_ID, "Iron Skin", state=APPROVED, creator_uid=USER_ID, **values)
		values, _ = AbilityFlow.check_passive(GUILD_ID, "weak", {"type" : "resist", "scope" : "fire"})
		self.assertEqual(values["damage_type"], "Fire")
		salamander = AbilityTransactions().add(GUILD_ID, "Salamander", state=APPROVED, **values)
		character = self.add_character()
		self.assertIsNone(AbilityFlow.learn_problem(character, iron, None))
		AbilityTransactions().learn(character.id, iron.id)
		self.assertIn("passive 2", AbilityFlow.learn_problem(character, salamander, None))
		combatant = Loadout.for_character(character, 1)
		self.assertEqual([entry["name"] for entry in combatant.passives], ["Iron Skin"])
		self.assertEqual((combatant.abilities, combatant.hp), ([], 40))
		self.assertIn("Normal passive", AbilityFlow.summary(iron))
