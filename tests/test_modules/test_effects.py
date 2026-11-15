"""The effect catalog: its data, every effect resolving in a fight, the new conditions, passives costing AP, and old
free-text sheet answers becoming blank abilities."""
import random
import unittest

from classes.characters.Card import Card
from classes.combat import Conditions as C, EffectCatalog, Effects, PassiveCatalog, Passives as P, SheetAbilities
from classes.combat.Abilities import SPELL_SLOTS, check_learn
from classes.combat.AbilityFlow import AbilityFlow
from classes.combat.Engine import CombatError, Engine
from classes.combat.State import DOWNED, FLED
from database.transactions.AbilityTransactions import APPROVED, AbilityTransactions, DRAFT
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID
from test_modules.test_combat import TYPES, NOW, ability, duel, engine, fighter


class TestCatalog(unittest.TestCase) :

	def test_there_is_a_lot_to_pick_from(self) :
		self.assertGreaterEqual(len(EffectCatalog.ACTIVE_EFFECTS), 250)
		self.assertGreaterEqual(len(PassiveCatalog.PASSIVE_EFFECTS), 80)
		for catalog in (EffectCatalog.ACTIVE_EFFECTS, PassiveCatalog.PASSIVE_EFFECTS) :
			names = [effect.name.lower() for effect in catalog]
			self.assertEqual(len(names), len(set(names)))
			self.assertEqual({effect.realm for effect in catalog}, {Effects.MAGIC, Effects.PHYSICAL})

	def test_every_entry_fits_discord_and_describes_itself(self) :
		for effect in EffectCatalog.ACTIVE_EFFECTS :
			self.assertIn(effect.category, EffectCatalog.CATEGORIES)
			self.assertIn(effect.mechanic, Effects.MECHANICS)
			self.assertLessEqual(len(effect.key), 100)
			text = Effects.describe(effect, Effects.STRONG, "intelligence", [effect], "Fire")
			self.assertTrue(text.startswith(effect.name))
		for effect in PassiveCatalog.PASSIVE_EFFECTS :
			self.assertIn(effect.category, PassiveCatalog.CATEGORIES)
			self.assertIn(effect.mechanic, P.TYPES)
			entry = P.entry(effect, P.STRONG, "Fire", None)
			self.assertNotIn("nothing the bot knows", P.describe_effect(P.STRONG, entry))

	def test_both_realms_have_modifiers_and_drawbacks(self) :
		for realm in Effects.REALMS :
			for mechanic, kinds in ((Effects.MODIFIER, Effects.MODIFIERS), (Effects.DRAWBACK, Effects.DRAWBACKS)) :
				found = {effect.params["kind"] for effect in EffectCatalog.ACTIVE_EFFECTS
				         if effect.realm == realm and effect.mechanic == mechanic}
				self.assertEqual(found, set(kinds), (realm, mechanic))

	def test_search(self) :
		self.assertEqual(EffectCatalog.find("pyrokinesis").name, "Pyrokinesis")
		self.assertEqual(EffectCatalog.find("Fire Bolt").key, "fire_bolt")
		self.assertTrue(all(effect.realm == Effects.PHYSICAL for effect in EffectCatalog.search("fire",
		                                                                                         Effects.PHYSICAL)))
		self.assertEqual(EffectCatalog.search("fire")[0].name.lower().count("fire"), 1)


class TestEveryEffectInAFight(unittest.TestCase) :
	"""Each main effect, used at Strong, resolves without errors and the fight stays consistent."""

	def run_effect(self, effect: Effects.Effect, seed: int) -> None :
		kind = "spell" if effect.realm == Effects.MAGIC else "ability"
		built = ability(1, effect.name, kind, Effects.STRONG, [effect.key], damage_type="Fire")
		fight = duel()
		fight.combatants.append(fighter(3, 1, "Rook", sequence=5))
		fight.combatants.append(fighter(4, 2, "Thug", sequence=4))
		ayla = fight.combatant(1)
		ayla.stats["abilities"] = [built]
		ayla.ap_max = 30
		run = Engine(fight, TYPES, rng=random.Random(seed), now=NOW)
		run.start()
		aim = built["aim"]
		if effect.mechanic == Effects.REVIVE :
			rook = fight.combatant(3)
			rook.hp, rook.state = 0, DOWNED
			targets = [3]
		else :
			targets = [2] if aim == Effects.ENEMY else [3] if aim == Effects.ALLY else [1]
		run.use_ability(ayla, 1, targets)
		for combatant in fight.combatants :
			self.assertGreaterEqual(combatant.hp, 0)
			self.assertLessEqual(combatant.hp, combatant.hp_max)
		# Play on a few turns so conditions tick, companions attack and dooms come due.
		for _ in range(6) :
			for actor in list(run.actors()) :
				run.end_turn_action(actor) if actor in run.actors() else None
				if fight.state != "active" :
					return

	def test_all_effects(self) :
		for number, effect in enumerate(EffectCatalog.ACTIVE_EFFECTS) :
			if not effect.main :
				continue
			with self.subTest(effect=effect.key) :
				self.run_effect(effect, number)


class TestEffectsInFights(unittest.TestCase) :

	def setup(self, keys: list[str], kind: str = "spell", tier: str = "normal", *rolls, **fields) :
		fight = duel()
		fight.combatants.append(fighter(3, 1, "Rook", sequence=5))
		ayla = fight.combatant(1)
		ayla.stats["abilities"] = [ability(1, "Test", kind, tier, keys, **fields)]
		ayla.ap_max = 20
		run = engine(fight, *rolls)
		run.start()
		return fight, run, ayla, fight.combatant(2)

	def test_on_hit_drain_and_area(self) :
		fight, run, ayla, bandit = self.setup(["pyrokinesis"], "spell", "normal", 15, 3, 3, 3)
		run.use_ability(ayla, 1, [2])
		self.assertTrue(C.has(bandit.conditions, C.BURNING))
		self.assertEqual(ayla.ap, 20 - 5)
		fight, run, ayla, bandit = self.setup(["life_drain"], "spell", "normal", 15, 4, 4, 4)
		ayla.hp = 10
		run.use_ability(ayla, 1, [2])
		self.assertEqual((bandit.hp, ayla.hp), (30 - 12, 16))
		fight, run, ayla, bandit = self.setup(["bolt", "widened"], "spell", "normal", damage_type="Arcane")
		fight.combatants.append(fighter(4, 2, "Thug"))
		self.assertEqual(fight.combatant(1).stats["abilities"][0]["targets"], 3)
		run.use_ability(ayla, 1, [2, 4])
		self.assertLess(fight.combatant(4).hp, 30)

	def test_saves_sleep_and_waking(self) :
		fight, run, ayla, bandit = self.setup(["sleep"], "spell", "normal", 2)
		run.use_ability(ayla, 1, [2])
		self.assertTrue(C.has(bandit.conditions, C.ASLEEP))
		run.damage(bandit, 1, ayla)
		self.assertFalse(C.has(bandit.conditions, C.ASLEEP))
		C.add(bandit.conditions, C.ASLEEP, turns=2)
		run.begin_turn(bandit)
		self.assertEqual((bandit.ap, bandit.acted), (0, True))

	def test_charm_taunt_and_disarm(self) :
		fight, run, ayla, bandit = self.setup(["strike"], "ability", "weak", damage_type="Blunt")
		fight.combatants.append(fighter(4, 2, "Thug"))
		C.add(ayla.conditions, C.CHARMED, turns=2, source=2)
		with self.assertRaises(CombatError) :
			run.attack(ayla, 2)
		self.assertEqual([enemy.id for enemy in run.ability_targets(ayla, ayla.abilities[0])], [4])
		C.remove(ayla.conditions, C.CHARMED)
		C.add(ayla.conditions, C.TAUNTED, turns=2, source=4)
		with self.assertRaises(CombatError) :
			run.attack(ayla, 2)
		C.remove(ayla.conditions, C.TAUNTED)
		C.add(ayla.conditions, C.DISARMED, turns=1)
		with self.assertRaises(CombatError) :
			run.attack(ayla, 2, "sword")
		ayla.stats["weapons"].append({"key" : "unarmed", "name" : "Unarmed", "type" : "Blunt", "dice" : "1d4",
		                              "attack_stat" : "strength", "range" : "melee", "properties" : []})
		run.attack(ayla, 2, "unarmed")

	def test_doom_companion_haste_and_drain(self) :
		fight, run, ayla, bandit = self.setup(["doom"], "spell", "normal", 2, 6, 6, 6, 6, 6, 6)
		run.use_ability(ayla, 1, [2])
		self.assertEqual(C.get(bandit.conditions, C.DOOMED)["amount"], 36)
		bandit.conditions[-1]["turns"] = 1
		bandit.acted = False
		run.end_turn(bandit)
		self.assertEqual(bandit.hp, 0)
		fight, run, ayla, bandit = self.setup(["raise_dead"], "spell", "normal", damage_type="Slashing")
		run.use_ability(ayla, 1, [1])
		self.assertTrue(C.has(ayla.conditions, C.COMPANION))
		engine(fight, 20, 5, 5, 5).begin_turn(ayla)
		self.assertLess(bandit.hp, 30)
		C.add(ayla.conditions, C.HASTED, turns=2, value=2)
		C.add(ayla.conditions, C.DRAINED, turns=1, value=3)
		engine(fight).begin_turn(ayla)
		self.assertEqual(ayla.ap, 20 + 2 - 3)
		self.assertFalse(C.has(ayla.conditions, C.DRAINED))

	def test_defensive_conditions(self) :
		fight, run, ayla, bandit = self.setup(["strike"], "ability", "weak", damage_type="Blunt")
		C.add(bandit.conditions, C.INTANGIBLE, turns=1)
		self.assertEqual(run.damage(bandit, 8, ayla), 0)
		self.assertEqual(run.damage(bandit, 8, ayla, magic=True), 8)
		C.remove(bandit.conditions, C.INTANGIBLE)
		C.add(bandit.conditions, C.WARDED, turns=1)
		self.assertEqual(run.damage(bandit, 8, ayla, magic=True), 4)
		C.remove(bandit.conditions, C.WARDED)
		C.add(bandit.conditions, C.VULNERABLE, turns=1, value=3)
		self.assertEqual(run.damage(bandit, 2, ayla), 5)
		C.add(bandit.conditions, C.WITHERED, turns=1)
		self.assertEqual(run.heal(bandit, 10), 0)
		C.add(bandit.conditions, C.UNDYING, turns=1)
		run.damage(bandit, 100, ayla)
		self.assertEqual((bandit.hp, bandit.state), (1, "active"))
		C.add(bandit.conditions, C.EVASIVE, turns=1)
		run.resolve_attack(ayla, bandit, ayla.weapons[0])
		self.assertEqual(bandit.hp, 1)
		self.assertFalse(C.has(bandit.conditions, C.EVASIVE))

	def test_reflect_and_drawbacks(self) :
		fight, run, ayla, bandit = self.setup(["bolt", "blood_price"], "spell", "weak", 15, 3, 3, 2, damage_type="Fire")
		C.add(bandit.conditions, C.REFLECTING, turns=2)
		run.use_ability(ayla, 1, [2])
		# 3 + 3 + INT 0 = 6: half bounces back, then the blood price (1d6 rolled 2).
		self.assertEqual((bandit.hp, ayla.hp), (27, 30 - 3 - 2))
		fight, run, ayla, bandit = self.setup(["strike", "reckless", "one_shot"], "ability", "weak",
		                                      damage_type="Blunt")
		self.assertEqual(ayla.abilities[0]["ap"], 1)
		run.use_ability(ayla, 1, [2])
		self.assertTrue(C.has(ayla.conditions, C.EXPOSED))
		with self.assertRaises(CombatError) :
			run.use_ability(ayla, 1, [2])

	def test_escape_and_self_boosts(self) :
		fight, run, ayla, bandit = self.setup(["rage"], "ability", "weak")
		self.assertEqual(run.ability_targets(ayla, ayla.abilities[0]), [ayla])
		run.use_ability(ayla, 1, [])
		self.assertTrue(C.has(ayla.conditions, C.EMPOWERED))
		fight, run, ayla, bandit = self.setup(["teleport"], "spell", "normal")
		run.use_ability(ayla, 1, [])
		self.assertEqual(ayla.state, FLED)


class TestPassiveCosts(unittest.TestCase) :

	def test_spell_passives_take_a_spell_slot(self) :
		full = [("spell", tier, False) for tier, count in SPELL_SLOTS.items() for _ in range(count) if tier != "strong"]
		self.assertIsNone(check_learn(full, "spell", "strong", False, passive=True))
		self.assertIn("Spellcasters", check_learn(full, "spell", "weak", False, passive=True))
		self.assertIn("spellcaster", check_learn(full, "ability", "weak", False, passive=True))

	def test_lifesteal_thorns_and_berserk(self) :
		fight = duel()
		ayla, bandit = fight.combatant(1), fight.combatant(2)
		ayla.stats["passives"] = [{"id" : 1, "name" : "Thirst", "tier" : "strong", "type" : P.LIFESTEAL},
		                          {"id" : 2, "name" : "Fury", "tier" : "weak", "type" : P.BERSERK}]
		bandit.stats["passives"] = [{"id" : 3, "name" : "Spikes", "tier" : "normal", "type" : P.THORNS}]
		run = engine(fight, 15, 8)
		ayla.hp = 10
		run.resolve_attack(ayla, bandit, ayla.weapons[0])
		# 8 + STR 0 + berserk 2 = 10; half of it heals Ayla, then the thorns take 3.
		self.assertEqual((bandit.hp, ayla.hp), (20, 10 + 5 - 3))


class TestAbilityLearning(DatabaseTestCase) :

	def test_ap_limits(self) :
		self.add_server()
		AbilityFlow.ensure_schools(GUILD_ID)
		character = self.add_character()
		values, _ = AbilityFlow.check(GUILD_ID, "ability", "strong", ["whirlwind", "onslaught"], "strength",
		                              None, None)
		big = AbilityTransactions().add(GUILD_ID, "Storm of Steel", state=APPROVED, **values)
		self.assertIn("only has 7 AP", AbilityFlow.learn_problem(character, big, None))
		values, _ = AbilityFlow.check_passive(GUILD_ID, "ability", "strong", ["bloodthirst", "commander",
		                                                                      "regeneration_passive"], None, None)
		greedy = AbilityTransactions().add(GUILD_ID, "Everything", state=APPROVED, **values)
		self.assertIn("at least 3 must remain", AbilityFlow.learn_problem(character, greedy, None))


class TestSheetAbilities(DatabaseTestCase) :

	def test_old_answers_become_blank_abilities(self) :
		self.add_server()
		character = self.add_character()
		infos = CharacterInfoTransactions()
		infos.add(character.id, "Magics", "- Fireball (Strong)\n- Heal")
		infos.add(character.id, "Weapon proficiencies", "Sword - Excellent")
		infos.add(character.id, "Height", "Tall")
		notes, weapons, created, linked = SheetAbilities.SheetAbilities.convert_character(character)
		self.assertEqual((created, linked, weapons), (2, 0, ["Sword - Excellent"]))
		fireball = AbilityTransactions().find(GUILD_ID, "Fireball")
		self.assertEqual((fireball.state, fireball.kind, fireball.tier, fireball.creator_uid),
		                 (DRAFT, "spell", "strong", USER_ID))
		self.assertEqual([item.name for _, item in AbilityTransactions().known(character.id)], ["Fireball", "Heal"])
		keys = [info.key for info in infos.get_all(character.id)]
		self.assertIn("Magics (old)", keys)
		# A second run has nothing left to do.
		self.assertEqual(SheetAbilities.SheetAbilities.convert_character(character), ([], [], 0, 0))
		text = Card.sheet_text(infos.get_all(character.id), [])
		self.assertIn("Height", text)
		self.assertNotIn("Fireball", text)
		self.assertIsNotNone(SheetAbilities.reserved_problem("Spells"))
		self.assertIsNone(SheetAbilities.reserved_problem("Armor proficiency"))
		combatant_abilities = __import__("classes.combat.Loadout", fromlist=["Loadout"]).Loadout.abilities(character.id)
		self.assertEqual(combatant_abilities, [])
