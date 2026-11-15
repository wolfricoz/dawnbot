from classes.characters.Special import Special
from classes.combat import Abilities, Rules
from classes.combat.AbilityFlow import AbilityFlow
from classes.combat.Legendary import Legendary
from classes.combat.Proficiency import Proficiency
from classes.gear.Gear import ARMOR, Gear, WEAPON
from classes.kernel.ConfigData import ConfigData
from database.transactions.AbilityTransactions import AbilityTransactions, APPROVED, PENDING
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID


class TestLegendary(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_grant_doubles_the_limits_and_gives_points(self) :
		character = self.add_character(strength=10)
		self.assertIsNotNone(Special.spend(CharacterTransactions().update(character.id, unspent_points=1), "strength")[1])
		character, _ = Legendary.grant(CharacterTransactions().get_by_id(character.id), USER_ID)
		self.assertTrue(character.legendary)
		self.assertEqual((character.unspent_points, character.legendary_points), (6, 5))
		updated, problem = Special.spend(character, "strength", 6)
		self.assertIsNone(problem)
		self.assertEqual((updated.strength, updated.unspent_points), (16, 0))
		self.assertIsNone(Legendary.grant(updated, USER_ID)[0])

	def test_points_follow_the_setting(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.LEGENDARY_POINTS, 2, overwrite=True)
		self.assertEqual(Legendary.points(GUILD_ID), 2)

	def test_removal_lowers_stats_and_takes_the_points_back(self) :
		character = self.add_character(strength=10)
		character, _ = Legendary.grant(character, USER_ID)
		character, _ = Special.spend(character, "strength", 3)
		# Strength 13 with 2 unspent: 3 points come back from strength (13 → 10), then the 5 legendary points are taken
		# from the 5 unspent.
		updated, text = Legendary.remove(character)
		self.assertFalse(updated.legendary)
		self.assertEqual((updated.strength, updated.unspent_points, updated.legendary_points), (10, 0, 0))
		self.assertIn("Strength 13 → 10", text)
		self.assertIsNone(Legendary.remove(updated)[0])

	def test_preview_shows_what_removal_changes_without_changing_it(self) :
		character = self.add_character(strength=10)
		character, _ = Legendary.grant(character, USER_ID)
		character, _ = Special.spend(character, "strength", 3)
		self.assertEqual(Legendary.preview(character), "This lowers Strength 13 → 10 and leaves 0 unspent points.")
		unchanged = CharacterTransactions().get_by_id(character.id)
		self.assertTrue(unchanged.legendary)
		self.assertEqual(unchanged.strength, 13)

	def test_preview_when_no_stats_drop(self) :
		character = self.add_character(strength=10)
		character, _ = Legendary.grant(character, USER_ID)
		character = CharacterTransactions().update(character.id, unspent_points=6)
		self.assertEqual(Legendary.preview(character), "This doesn't lower any stats and leaves 1 unspent point.")

	def test_removal_takes_owed_points_from_the_highest_stats(self) :
		character = self.add_character(strength=9, agility=8)
		character, _ = Legendary.grant(character, USER_ID)
		character, _ = Special.spend(character, "strength", 1)
		character, _ = Special.spend(character, "agility", 4)
		stats, unspent = Legendary.removal(character)
		# Agility 12 → 10 returns 2, so 2 of the 5 points are covered; the other 3 come off the highest stats.
		self.assertEqual(unspent, 0)
		self.assertEqual(sum(stats.values()), 10 + 10 + 5 * 5 - 3)
		self.assertLessEqual(max(stats.values()), 10)


class TestProficiency(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		self.character = self.add_character()
		items = GearItemTransactions()
		self.weapons = [items.add(GUILD_ID, WEAPON, name, combat={"dice" : "1d6"}) for name in ("Axe", "Bow", "Club")]
		self.armor = items.add(GUILD_ID, ARMOR, "Mail", combat={"armor_class" : "medium", "ac" : 3})

	def own(self, item) :
		return Gear.grant(self.character, item, USER_ID)

	def test_players_set_a_tier_once_and_staff_change_it(self) :
		entry = self.own(self.weapons[0])
		self.assertEqual(Proficiency.label(entry), "No proficiency set")
		self.assertIsNone(Proficiency.set_weapon(entry, "legendary")[0])
		entry, text = Proficiency.set_weapon(entry, "good")
		self.assertEqual(entry.proficiency, "good")
		self.assertIn(f"{Rules.proficiency_bonus('good'):+d} to hit", text)
		self.assertEqual(Proficiency.label(entry), "Good")
		self.assertIsNone(Proficiency.set_weapon(entry, "poor")[0])
		self.assertEqual(Proficiency.set_weapon(entry, "poor", staff=True)[0].proficiency, "poor")

	def test_at_most_two_good_weapons(self) :
		entries = [self.own(weapon) for weapon in self.weapons]
		self.assertIsNotNone(Proficiency.set_weapon(entries[0], "excellent")[0])
		self.assertIsNotNone(Proficiency.set_weapon(entries[1], "good")[0])
		refused, text = Proficiency.set_weapon(entries[2], "good")
		self.assertIsNone(refused)
		self.assertIn("Axe", text)
		self.assertIsNotNone(Proficiency.set_weapon(entries[2], "average")[0])

	def test_armor_entries_and_armor_proficiency(self) :
		entry = self.own(self.armor)
		self.assertIsNone(Proficiency.set_weapon(entry, "good")[0])
		self.assertEqual(Proficiency.label(entry), "")
		self.assertIsNone(Proficiency.set_armor(self.character, "plate")[0])
		character, _ = Proficiency.set_armor(self.character, "medium")
		self.assertEqual(character.armor_proficiency, "medium")
		self.assertIsNone(Proficiency.set_armor(character, "heavy")[0])
		self.assertEqual(Proficiency.set_armor(character, "heavy", staff=True)[0].armor_proficiency, "heavy")

	def test_lost_weapons_cannot_be_set(self) :
		entry = self.own(self.weapons[0])
		CharacterGearTransactions().update(entry.id, status="lost")
		self.assertIsNone(Proficiency.set_weapon(CharacterGearTransactions().get(entry.id), "good")[0])


class TestLearningAbilities(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		AbilityFlow.ensure_schools(GUILD_ID)
		self.school = AbilityFlow.schools(GUILD_ID)[0]

	def ability(self, name: str, kind: str = Abilities.ABILITY, tier: str = Abilities.WEAK, state: str = APPROVED) :
		school_id = self.school.id if kind == Abilities.SPELL else None
		stat = self.school.casting_stat if kind == Abilities.SPELL else "strength"
		effects = [{"key" : "bolt" if kind == Abilities.SPELL else "strike"}]
		return AbilityTransactions().add(GUILD_ID, name, kind=kind, tier=tier, effects=effects, stat=stat,
		                                 damage_type="Blunt", school_id=school_id, state=state)

	def test_check_corrects_names_and_needs_a_school_for_spells(self) :
		values, problem = AbilityFlow.check(GUILD_ID, Abilities.ABILITY, Abilities.WEAK, ["Strike", None], "strength",
		                                    "blunt", None)
		self.assertIsNone(problem)
		self.assertEqual((values["damage_type"], values["effects"]), ("Blunt", [{"key" : "strike"}]))
		self.assertIn("damage_type", AbilityFlow.check(GUILD_ID, Abilities.ABILITY, Abilities.WEAK, ["strike"],
		                                               "strength", None, None)[1])
		self.assertIsNone(AbilityFlow.check(GUILD_ID, Abilities.ABILITY, Abilities.WEAK, ["rend"], "strength", None,
		                                    None)[1])
		self.assertIn("no effect called", AbilityFlow.check(GUILD_ID, Abilities.ABILITY, Abilities.WEAK, ["laser"],
		                                                    "strength", None, None)[1])
		self.assertIsNotNone(AbilityFlow.check(GUILD_ID, Abilities.SPELL, Abilities.WEAK, ["bolt"], None, "Fire",
		                                       None)[1])
		values, problem = AbilityFlow.check(GUILD_ID, Abilities.SPELL, Abilities.WEAK, ["mend"], "strength", None,
		                                    self.school)
		self.assertIsNone(problem)
		self.assertEqual(values["stat"], self.school.casting_stat)

	def test_learn_problems(self) :
		character = self.add_character()
		pending = self.ability("Draft", state=PENDING)
		self.assertIn("not been approved", AbilityFlow.learn_problem(character, pending, None))
		first = self.ability("Smash")
		self.assertIsNone(AbilityFlow.learn_problem(character, first, None))
		AbilityTransactions().learn(character.id, first.id)
		self.assertIn("already knows", AbilityFlow.learn_problem(character, first, None))
		spell = self.ability("Spark", kind=Abilities.SPELL)
		self.assertIn("can't learn spells", AbilityFlow.learn_problem(character, spell, None))

	def test_legendary_characters_get_one_more_slot(self) :
		character = self.add_character()
		for number in range(Abilities.ABILITY_SLOTS) :
			AbilityTransactions().learn(character.id, self.ability(f"Move {number}").id)
		extra = self.ability("One more")
		self.assertIn("at most", AbilityFlow.learn_problem(character, extra, None))
		character, _ = Legendary.grant(character, USER_ID)
		self.assertIsNone(AbilityFlow.learn_problem(character, extra, None))

	def test_event_abilities_skip_the_limits(self) :
		character = self.add_character()
		spell = self.ability("Spark", kind=Abilities.SPELL)
		AbilityTransactions().learn(character.id, spell.id, event=True, granted_by=USER_ID)
		self.assertIsNone(AbilityFlow.learn_problem(character, self.ability("Smash"), None))
