"""Weapon techniques needing a weapon, the immunity after control conditions, concentration, minibosses and bosses,
and new default damage types reaching servers."""
import unittest

from classes.combat import Conditions as C, Rules
from classes.combat.DamageTypes import DamageTypes, OFFERED_KEY
from classes.combat.Engine import CombatError
from classes.combat.Loadout import Loadout, rank_of
from classes.gear.Packs import Packs
from classes.kernel.ConfigData import ConfigData
from database.transactions.DamageTypeTransactions import DamageTypeTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID
from test_modules.test_combat import ability, duel, engine, fighter
from test_modules.test_effects import weapon_for


class TestWeaponTechniques(unittest.TestCase) :

	def test_kinds_from_items_and_names(self) :
		self.assertEqual(Rules.weapon_kind({"name" : "Two-Hand Greatblade"}), "greatsword")
		self.assertEqual(Rules.weapon_kind({"name" : "Riverglass Sabre"}), "scimitar")
		self.assertEqual(Rules.weapon_kind({"name" : "Hedge Knife"}), "dagger")
		self.assertEqual(Rules.weapon_kind({"name" : "Windlass Crossbow"}), "crossbow")
		self.assertEqual(Rules.weapon_kind({"name" : "Oddly Named Thing", "kind" : "spear"}), "spear")
		self.assertIsNone(Rules.weapon_kind({"name" : "Ember Wand", "properties" : ["focus"]}))
		self.assertTrue(Rules.meets({"name" : "Greatsword"}, "sword"))
		self.assertFalse(Rules.meets({"name" : "Ember Wand", "range" : "ranged", "properties" : ["focus"]}, "ranged"))
		self.assertTrue(Rules.meets({"name" : "Hedge Knife", "properties" : ["thrown"]}, "thrown"))
		self.assertTrue(Rules.meets({"key" : "natural", "name" : "Attack"}, "claw"))
		self.assertFalse(Rules.meets({"key" : "natural", "name" : "Attack"}, "spear"))
		self.assertEqual(Packs.combat_for("weapon", None, {"kind" : "Spear"})["kind"], "spear")
		self.assertNotIn("kind", Packs.combat_for("weapon", None, {"kind" : "none"}))
		with self.assertRaises(ValueError) :
			Packs.combat_for("weapon", None, {"kind" : "lightsaber"})

	def test_a_technique_needs_its_weapon(self) :
		fight = duel()
		ayla = fight.combatant(1)
		ayla.stats["abilities"] = [ability(1, "Thrust", "ability", "weak", ["spear_crippling"], stat="strength")]
		run = engine(fight)
		run.start()
		self.assertIn("needs a spear", run.weapon_problem(ayla, ayla.abilities[0]))
		with self.assertRaises(CombatError) :
			run.use_ability(ayla, 1, [2])
		ayla.stats["weapons"].append(weapon_for("spear", "excellent"))
		self.assertIsNone(run.weapon_problem(ayla, ayla.abilities[0]))
		C.add(ayla.conditions, C.DISARMED, turns=1)
		self.assertIn("disarmed", run.weapon_problem(ayla, ayla.abilities[0]))
		C.remove(ayla.conditions, C.DISARMED)
		# d20 10 + STR 0 + Excellent +1 = 11 against AC 10: a hit that slows.
		engine(fight, 10, 4).use_ability(ayla, 1, [2])
		self.assertTrue(C.has(fight.combatant(2).conditions, C.SLOWED))

	def test_unarmed_styles_need_nothing(self) :
		fight = duel()
		ayla = fight.combatant(1)
		ayla.stats["abilities"] = [ability(1, "Kick", "ability", "weak", ["martial_toppling"], stat="strength")]
		self.assertIsNone(engine(fight).weapon_problem(ayla, ayla.abilities[0]))


class TestControlImmunity(unittest.TestCase) :

	def test_control_conditions_cant_chain(self) :
		conditions = []
		C.add(conditions, C.ASLEEP, turns=1)
		self.assertEqual(C.count_down(conditions), [C.ASLEEP])
		self.assertFalse(C.add(conditions, C.ASLEEP, turns=2))
		self.assertTrue(C.add(conditions, C.CHARMED, turns=1))
		self.assertEqual(C.visible(conditions), [{"name" : C.CHARMED, "turns" : 1}])
		self.assertTrue(C.add(conditions, C.ASLEEP, turns=2, force=True))
		C.remove(conditions, C.ASLEEP)
		# The immunity lasts until the end of the combatant's next turn.
		conditions = []
		C.add(conditions, C.RESTRAINED, turns=1)
		C.count_down(conditions)
		C.count_down(conditions)
		self.assertTrue(C.add(conditions, C.RESTRAINED, turns=1))

	def test_waking_and_cleansing_give_immunity(self) :
		fight = duel()
		ayla, bandit = fight.combatant(1), fight.combatant(2)
		run = engine(fight)
		C.add(bandit.conditions, C.ASLEEP, turns=3)
		run.damage(bandit, 2, ayla)
		self.assertFalse(run.inflict(bandit, C.ASLEEP, 2))
		C.add(bandit.conditions, C.CURSED, turns=3)
		C.cleanse(bandit.conditions)
		self.assertFalse(run.inflict(bandit, C.CURSED, 2))
		self.assertTrue(run.inflict(bandit, C.SLOWED, 2))
		run.set_condition(bandit, C.CURSED, 2)
		self.assertTrue(C.has(bandit.conditions, C.CURSED))


class TestConcentration(unittest.TestCase) :

	def setup(self, *rolls) :
		fight = duel()
		fight.combatants.append(fighter(3, 1, "Rook"))
		ayla = fight.combatant(1)
		ayla.stats["abilities"] = [ability(1, "Haste", "spell", "normal", ["haste"]),
		                           ability(2, "Bless", "spell", "normal", ["bless"]),
		                           ability(3, "Bolt", "spell", "normal", ["fire_bolt"])]
		ayla.ap_max = 20
		run = engine(fight, *rolls)
		run.start()
		return fight, run, ayla, fight.combatant(3)

	def test_one_spell_at_a_time(self) :
		fight, run, ayla, rook = self.setup()
		self.assertTrue(ayla.abilities[0]["concentration"])
		self.assertFalse(ayla.abilities[2]["concentration"])
		run.use_ability(ayla, 1, [3])
		self.assertTrue(C.has(rook.conditions, C.HASTED))
		self.assertEqual(ayla.stats["concentration"]["name"], "Haste")
		run.use_ability(ayla, 2, [3])
		self.assertFalse(C.has(rook.conditions, C.HASTED))
		self.assertTrue(C.has(rook.conditions, C.BLESSED))
		run.use_ability(ayla, 3, [2])
		self.assertEqual(ayla.stats["concentration"]["name"], "Bless")

	def test_damage_can_break_it(self) :
		fight, run, ayla, rook = self.setup()
		run.use_ability(ayla, 1, [3])
		bandit = fight.combatant(2)
		engine(fight, 15).damage(ayla, 4, bandit)
		self.assertIn("concentration", ayla.stats)
		engine(fight, 3).damage(ayla, 4, bandit)
		self.assertNotIn("concentration", ayla.stats)
		self.assertFalse(C.has(rook.conditions, C.HASTED))
		run.use_ability(ayla, 2, [3])
		engine(fight).damage(ayla, 100, bandit)
		self.assertNotIn("concentration", ayla.stats)
		self.assertFalse(C.has(rook.conditions, C.BLESSED))

	def test_physical_and_self_boosts_need_none(self) :
		self.assertFalse(ability(1, "Rally", "ability", "weak", ["rally"])["concentration"])
		self.assertFalse(ability(2, "Form", "spell", "weak", ["vampire_form"])["concentration"])
		self.assertTrue(ability(3, "Hex", "spell", "weak", ["hex"])["concentration"])


class TestBosses(unittest.TestCase) :

	def test_hp_follows_the_players(self) :
		self.assertEqual((Rules.boss_hp("boss", 4), Rules.boss_hp("miniboss", 4)), (225, 150))
		self.assertEqual(Rules.boss_hp("boss", 0), Rules.boss_hp("boss", 1))
		self.assertEqual((rank_of("Mini"), rank_of("boss"), rank_of("")), ("miniboss", "boss", None))
		fight = duel()
		fight.combatants = [fighter(number, 1, f"Hero {number}") for number in range(1, 5)]
		for hero in fight.combatants :
			hero.character_id = hero.id
		boss = Loadout.for_preset("boss", "Dragon", 2, position=9)
		boss.id = 9
		miniboss = Loadout.for_preset("miniboss", "Drake", 2, position=10)
		miniboss.id = 10
		fight.combatants += [boss, miniboss]
		run = engine(fight)
		run.joined(boss)
		self.assertEqual(boss.hp_max, 225)
		run.start()
		self.assertEqual((boss.hp, boss.hp_max, miniboss.hp_max), (225, 225, 150))
		self.assertTrue(any("225 HP against 4 players" in line for line in run.outcome.lines))
		late = Loadout.for_preset("standard", "Bandit", 2)
		self.assertNotIn("rank", late.stats)


class TestDamageTypeDefaults(DatabaseTestCase) :

	def test_new_defaults_reach_servers_once(self) :
		self.add_server()
		transactions = DamageTypeTransactions()
		for name in ("Slashing", "Fire") :
			transactions.add(GUILD_ID, name, trigger="strong_hit", effect={"kind" : "none"}, pack="default")
		DamageTypes.ensure(GUILD_ID)
		names = {record.name for record in transactions.get_all(GUILD_ID)}
		# Only the defaults added since the original set arrive; the original ones staff deleted stay gone.
		self.assertEqual(names, {"Slashing", "Fire", "Acid", "Necrotic", "Sonic"})
		transactions.delete(transactions.find(GUILD_ID, "Acid").id)
		DamageTypes.ensure(GUILD_ID)
		self.assertNotIn("Acid", {record.name for record in transactions.get_all(GUILD_ID)})
		self.assertIn("Sonic", ConfigData().get_guild(GUILD_ID).get(OFFERED_KEY))

	def test_a_new_server_gets_every_default(self) :
		self.add_server()
		DamageTypes.ensure(GUILD_ID)
		self.assertEqual(len(DamageTypeTransactions().get_all(GUILD_ID)), 14)


class TestBalanceSimulator(unittest.TestCase) :

	def test_a_small_run(self) :
		from classes.combat import Balance, EffectCatalog

		effects = [EffectCatalog.get(key) for key in ("fireball", "rage", "spear_crippling", "widened")]
		baseline, results = Balance.run(20, effects)
		self.assertTrue(0.2 < baseline < 0.8)
		self.assertEqual([result.key for result in results], ["fireball", "rage", "spear_crippling", "widened"])
		self.assertTrue(all(0 <= result.wins <= 1 for result in results))
		text = Balance.report(baseline, results, 20)
		self.assertIn("# Effect balance report", text)


class TestNpcAbilities(unittest.TestCase) :

	def setup(self, *keys_by_ability, behavior: str = "aggressive") :
		from classes.combat.State import AUTO

		fight = duel()
		fight.combatants.append(fighter(3, 1, "Rook"))
		fight.combatants.append(fighter(4, 2, "Thug"))
		mage = fight.combatant(2)
		mage.controller, mage.behavior, mage.ap_max = AUTO, behavior, 20
		mage.stats["abilities"] = [ability(number + 10, f"Ability {number}", "spell", "normal", list(keys))
		                           for number, keys in enumerate(keys_by_ability)]
		return fight, mage

	def test_control_goes_on_the_toughest_enemy(self) :
		from classes.combat.Autopilot import Autopilot

		fight, mage = self.setup(["hold_person"], ["fire_bolt"])
		fight.combatant(1).hp = 30
		fight.combatant(3).hp = 12
		ability, targets = Autopilot(engine(fight)).ability_move(mage, "aggressive")
		self.assertEqual((ability["name"], [target.name for target in targets]), ("Ability 0", ["Ayla"]))
		C.add(fight.combatant(1).conditions, C.STUNNED, turns=1)
		C.add(fight.combatant(3).conditions, C.STUNNED, turns=1)
		ability, targets = Autopilot(engine(fight)).ability_move(mage, "aggressive")
		self.assertEqual(ability["name"], "Ability 1")
		self.assertEqual(targets[0].name, "Rook")

	def test_healing_reviving_and_buffing(self) :
		from classes.combat.Autopilot import Autopilot
		from classes.combat.State import DOWNED

		fight, mage = self.setup(["cure_wounds"], ["bless"], ["fire_bolt"])
		thug = fight.combatant(4)
		pilot = Autopilot(engine(fight))
		ability, targets = pilot.ability_move(mage, "aggressive")
		self.assertEqual(ability["name"], "Ability 2")
		ability, targets = pilot.ability_move(mage, "support")
		self.assertEqual(ability["name"], "Ability 2")
		thug.hp = 5
		ability, targets = pilot.ability_move(mage, "aggressive")
		self.assertEqual((ability["name"], targets[0].name), ("Ability 0", "Thug"))
		thug.hp, thug.state = 0, DOWNED
		ability, targets = pilot.ability_move(mage, "aggressive")
		self.assertEqual((ability["name"], targets[0].name), ("Ability 0", "Thug"))

	def test_concentration_and_area_targets(self) :
		from classes.combat.Autopilot import Autopilot

		fight, mage = self.setup(["haste"], ["bless"], ["fireball", "widened"])
		run = engine(fight)
		pilot = Autopilot(run)
		ability, targets = pilot.ability_move(mage, "aggressive")
		self.assertEqual(ability["name"], "Ability 2")
		self.assertEqual(sorted(target.name for target in targets), ["Ayla", "Rook"])
		mage.stats["abilities"] = mage.stats["abilities"][:2]
		run.start()
		mage.ap = 20
		run.resolve_and_use(mage, mage.abilities[0], [mage])
		# Concentrating on Haste: Bless would break it, so the mage holds off.
		self.assertIsNone(pilot.ability_move(mage, "aggressive"))

	def test_a_whole_automatic_turn(self) :
		from classes.combat.Autopilot import Autopilot

		fight, mage = self.setup(["hold_person"], ["fire_bolt"])
		run = engine(fight, 1, 1, 15, 4, 15, 4, 15, 4)
		run.start()
		mage.ap, mage.acted = 20, False
		Autopilot(run).take_turn(mage)
		self.assertTrue(any("uses **Ability 0**" in line for line in run.outcome.lines))
		self.assertTrue(any("uses **Ability 1**" in line for line in run.outcome.lines))
