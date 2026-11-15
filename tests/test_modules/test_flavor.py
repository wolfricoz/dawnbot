import random
from datetime import datetime, timedelta, timezone

from classes.checks.CheckFlow import CheckFlow
from classes.combat import Fortune
from classes.flavor import OmenFlow
from classes.flavor.RumorFlow import FALSE, RumorFlow, TRUE
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.CheckTransactions import CheckTransactions
from database.transactions.FlavorTransactions import FlavorTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID


class FixedRng :
	def __init__(self, *values) :
		self.values = list(values)

	def randint(self, low, high) :
		return self.values.pop(0)


class TestRumors(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		self.listener = self.add_character("Ears", user_id=USER_ID + 1, perception=8)

	def rumor(self, text, **fields) :
		values = dict(expires_at=datetime.now(timezone.utc) + timedelta(days=1), truth="unknown", heard=0) | fields
		return FlavorTransactions().add_rumor(GUILD_ID, USER_ID, text, **values)

	def test_outcomes(self) :
		self.rumor("The mayor is a vampire", truth=TRUE)
		self.rumor("The well is cursed", truth=FALSE)
		self.rumor("Bread prices go up")
		# Perception 8: +3 against 12. 16 is strong: two rumors and a hint.
		outcome, heard = RumorFlow.overhear(self.listener, rng=FixedRng(16))
		self.assertEqual(len(heard), 2)
		self.assertTrue(any("(" in line for line in heard))
		outcome, heard = RumorFlow.overhear(self.listener, rng=FixedRng(9))
		self.assertEqual(len(heard), 1)
		outcome, heard = RumorFlow.overhear(self.listener, rng=FixedRng(5))
		self.assertEqual(heard, [])

	def test_bad_failure_hears_a_false_rumor(self) :
		self.rumor("The truth", truth=TRUE)
		self.rumor("A lie", truth=FALSE)
		outcome, heard = RumorFlow.overhear(self.listener, rng=FixedRng(2))
		self.assertEqual(heard, ["A lie"])

	def test_secret_first_and_no_repeats(self) :
		self.rumor("Plain")
		self.rumor("Hidden", secret=True, planted=True)
		self.assertEqual(RumorFlow.overhear(self.listener, rng=FixedRng(10))[1], ["Hidden"])
		self.assertEqual(RumorFlow.overhear(self.listener, rng=FixedRng(10))[1], ["Plain"])
		self.assertEqual(RumorFlow.overhear(self.listener, rng=FixedRng(10))[1], [])

	def test_faded_and_own_rumors_are_left_out(self) :
		self.rumor("Old news", expires_at=datetime.now(timezone.utc) - timedelta(days=1))
		self.rumor("Old but pinned", expires_at=datetime.now(timezone.utc) - timedelta(days=1), pinned=True)
		FlavorTransactions().add_rumor(GUILD_ID, USER_ID + 1, "My own", expires_at=None, heard=0)
		self.assertEqual([rumor.text for rumor in RumorFlow.candidates(self.listener)], ["Old but pinned"])

	def test_whispers_spread(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.RUMOR_MODE, "whisper", overwrite=True)
		rumor = self.rumor("Spreading")
		RumorFlow._to_spread.clear()
		for index in range(3) :
			character = self.add_character(f"Listener{index}", user_id=USER_ID + 10 + index, perception=8)
			RumorFlow.overhear(character, rng=FixedRng(12))
		self.assertEqual(FlavorTransactions().rumor(rumor.id).heard, 3)
		self.assertIn(rumor.id, RumorFlow._to_spread)
		RumorFlow._to_spread.clear()

	def test_listens_and_blocks(self) :
		self.assertFalse(FlavorTransactions().listened(self.listener.id, "2026-11-15"))
		FlavorTransactions().mark_listen(GUILD_ID, self.listener.id, "2026-11-15")
		self.assertTrue(FlavorTransactions().listened(self.listener.id, "2026-11-15"))
		FlavorTransactions().set_blocked(GUILD_ID, USER_ID, True)
		self.assertTrue(FlavorTransactions().blocked(GUILD_ID, USER_ID))
		FlavorTransactions().set_blocked(GUILD_ID, USER_ID, False)
		self.assertFalse(FlavorTransactions().blocked(GUILD_ID, USER_ID))


class TestOmens(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_decks(self) :
		decks = OmenFlow.built_in()
		self.assertEqual(len(decks["tarot"]["cards"]), 22)
		self.assertIn("bones", decks)
		for deck in decks.values() :
			for card in deck["cards"] :
				self.assertIn(card.get("effect", "none"), ("boon", "bane", "none"))
				self.assertTrue(card["upright"])

	def test_draw_without_repeats_and_cooldown(self) :
		character = self.add_character()
		seen = set()
		for _ in range(12) :
			drawn, problem = OmenFlow.draw(CharacterTransactions().get_by_id(character.id), "bones",
			                               rng=random.Random(len(seen)))
			self.assertIsNone(problem)
			seen.add(drawn["card"])
			# Pretend the cooldown passed.
			record = CharacterTransactions().get_by_id(character.id)
			past = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
			CharacterTransactions().update(character.id, omen=dict(record.omen, drawn_at=past))
		self.assertEqual(len(seen), 12)
		drawn, problem = OmenFlow.draw(CharacterTransactions().get_by_id(character.id), "bones")
		self.assertIsNone(problem)
		self.assertIsNotNone(OmenFlow.draw(CharacterTransactions().get_by_id(character.id), "bones")[1])
		self.assertIsNotNone(OmenFlow.draw(CharacterTransactions().get_by_id(character.id), "nope")[1])

	def test_effects_are_off_by_default(self) :
		character = self.add_character()
		for seed in range(30) :
			CharacterTransactions().update(character.id, omen=None)
			drawn, _ = OmenFlow.draw(CharacterTransactions().get_by_id(character.id), "tarot",
			                         rng=random.Random(seed))
			self.assertEqual(drawn["effect"], "none")

	def test_boons_and_banes(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.OMEN_EFFECTS, "ENABLED", overwrite=True)
		character = self.add_character()
		effects = set()
		for seed in range(60) :
			CharacterTransactions().update(character.id, omen=None, bad_streak=0)
			drawn, _ = OmenFlow.draw(CharacterTransactions().get_by_id(character.id), "tarot",
			                         rng=random.Random(seed))
			record = CharacterTransactions().get_by_id(character.id)
			effects.add(drawn["effect"])
			if drawn["effect"] == "boon" :
				self.assertTrue(Fortune.armed(record.bad_streak))
			if drawn["effect"] == "bane" :
				self.assertTrue(OmenFlow.bane(record))
		self.assertTrue({"boon", "bane"} <= effects)

	def test_banes_cost_one_on_the_next_check(self) :
		character = self.add_character(omen={"effect" : "bane", "used" : False})
		check = CheckTransactions().create(GUILD_ID, 1, USER_ID, "perception", dc=12,
		                                   expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
		result, _ = CheckFlow.make_roll(check, character, "perception", [])
		self.assertIn(("Omen", -1), [(bonus.label, bonus.value) for bonus in result.bonuses])
		self.assertFalse(OmenFlow.bane(CharacterTransactions().get_by_id(character.id)))
		result, _ = CheckFlow.make_roll(check, CharacterTransactions().get_by_id(character.id), "perception", [])
		self.assertNotIn("Omen", [bonus.label for bonus in result.bonuses])
