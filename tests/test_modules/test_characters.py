import random
import unittest
from datetime import datetime, timedelta, timezone

from classes.characters.Card import Card, DESCRIPTION_LIMIT, chunk_text
from classes.characters.ImageStorage import ImageStorage, MAX_BYTES
from classes.characters.Sheet import CHOICE, DEFAULT_SHEET, INFO, LONG, NUMBER, SHORT, Sheet
from classes.characters.Special import POINT_BUY, ROLLED, STATS, Special, StatRules
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import CharacterTransactions, DENIED, PENDING, RETIRED
from database.transactions.SheetFieldTransactions import SheetFieldTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

OTHER_GUILD = 396757854637260811
DEFAULT_RULES = StatRules(base=5, bonus=5, minimum=1, maximum=10, method="both")


class TestSpecialRules(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_defaults_follow_fallout(self) :
		rules = Special.rules(GUILD_ID)
		self.assertEqual(rules, DEFAULT_RULES)
		self.assertEqual((rules.budget, rules.methods), (40, [POINT_BUY, ROLLED]))

	def test_settings_change_the_rules(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_MIN, -2, overwrite=True)
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_MAX, 13, overwrite=True)
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_BONUS, 0, overwrite=True)
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_METHOD, "rolled", overwrite=True)
		rules = Special.rules(GUILD_ID)
		self.assertEqual((rules.minimum, rules.maximum, rules.bonus, rules.budget, rules.methods),
		                 (-2, 13, 0, 35, [ROLLED]))

	def test_contradicting_settings_fall_back(self) :
		"""A minimum above the maximum would make every character impossible."""
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_MIN, 9, overwrite=True)
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_MAX, 3, overwrite=True)
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_METHOD, "dice", overwrite=True)
		rules = Special.rules(GUILD_ID)
		self.assertEqual((rules.minimum, rules.maximum, rules.method), (1, 10, "both"))


class TestSpecialValues(unittest.TestCase) :

	def test_parse_needs_exactly_seven_numbers(self) :
		self.assertEqual(Special.parse("5 5, 5,5 6 7 7"), [5, 5, 5, 5, 6, 7, 7])
		self.assertEqual(Special.parse("-2 5 5 5 6 7 7"), [-2, 5, 5, 5, 6, 7, 7])
		self.assertIsNone(Special.parse("5 5 5 5 6 7"))
		self.assertIsNone(Special.parse("5 5 5 5 6 7 7 7"))
		self.assertIsNone(Special.parse("strength 5 5 5 5 6 7 7"))

	def test_point_buy_limits(self) :
		self.assertIsNone(Special.check_values([5, 5, 5, 5, 6, 7, 7], DEFAULT_RULES, 40))
		# Lowering one stat frees points for another, and points may be left over.
		self.assertIsNone(Special.check_values([1, 10, 5, 5, 5, 5, 9], DEFAULT_RULES, 40))
		self.assertIsNone(Special.check_values([5, 5, 5, 5, 5, 5, 5], DEFAULT_RULES, 40))
		self.assertIn("41", Special.check_values([5, 5, 5, 5, 7, 7, 7], DEFAULT_RULES, 40))
		self.assertIn("Luck", Special.check_values([5, 5, 5, 5, 5, 5, 11], DEFAULT_RULES, 40))
		self.assertIn("Strength", Special.check_values([0, 5, 5, 5, 5, 5, 5], DEFAULT_RULES, 40))

	def test_rolls_stay_inside_the_rules(self) :
		rng = random.Random(7)
		for _ in range(300) :
			values = Special.roll(DEFAULT_RULES, rng)
			self.assertEqual(len(values), 7)
			self.assertTrue(all(1 <= value <= 10 for value in values), values)
			self.assertLessEqual(sum(values), DEFAULT_RULES.budget)
			self.assertEqual(values, sorted(values, reverse=True))

	def test_roll_ends_with_a_tiny_budget(self) :
		"""With 7 points for 7 stats nearly every roll is too high; it is lowered instead of rolled forever."""
		rules = StatRules(base=1, bonus=0, minimum=1, maximum=10, method="rolled")
		self.assertEqual(Special.roll(rules, random.Random(1)), [1] * 7)

	def test_rolled_values_are_assigned_once_each(self) :
		rolled = [9, 7, 6, 5, 4, 3, 2]
		self.assertIsNone(Special.check_assignment([2, 3, 4, 5, 6, 7, 9], rolled))
		self.assertIsNotNone(Special.check_assignment([9, 9, 6, 5, 4, 3, 2], rolled))
		self.assertIsNotNone(Special.check_assignment([10, 7, 6, 5, 4, 3, 2], rolled))

	def test_level_curve(self) :
		"""Fallout 1 and 2: level 2 at 1000, level 3 at 3000, level 10 at 45000."""
		self.assertEqual([Special.xp_for_level(level, 1000) for level in (1, 2, 3, 5, 10)],
		                 [0, 1000, 3000, 10000, 45000])
		self.assertEqual([Special.level_for_xp(xp, 1000) for xp in (0, 999, 1000, 2999, 3000, 45000)],
		                 [1, 1, 2, 2, 3, 10])


class TestLevels(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		self.character = self.add_character()

	def test_levels_give_points(self) :
		character, gained = Special.add_xp(self.character, 3500)
		self.assertEqual((character.xp, character.level, character.unspent_points, gained), (3500, 3, 2, 2))
		character, gained = Special.add_xp(character, 100)
		self.assertEqual((character.level, character.unspent_points, gained), (3, 2, 0))

	def test_points_per_level_setting(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.POINTS_PER_LEVEL, 2, overwrite=True)
		ConfigData().add_key(GUILD_ID, ConfigMapping.LEVEL_BASE, 100, overwrite=True)
		character, gained = Special.add_xp(self.character, 300)
		self.assertEqual((character.level, character.unspent_points, gained), (3, 4, 2))

	def test_a_level_never_goes_down(self) :
		character, _ = Special.set_xp(self.character, 3000)
		character, gained = Special.set_xp(character, 200)
		self.assertEqual((character.xp, character.level, character.unspent_points, gained), (200, 3, 2, 0))
		# Earning the XP back does not give the same levels twice.
		character, gained = Special.set_xp(character, 3000)
		self.assertEqual((character.level, character.unspent_points, gained), (3, 2, 0))

	def test_spend(self) :
		character, _ = Special.add_xp(self.character, 3000)
		character, problem = Special.spend(character, "strength", 2)
		self.assertIsNone(problem)
		self.assertEqual((character.strength, character.unspent_points), (7, 0))
		self.assertIn("0 unspent", Special.spend(character, "luck")[1])

	def test_spend_stops_at_the_maximum(self) :
		character = CharacterTransactions().update(self.character.id, strength=10, unspent_points=3)
		updated, problem = Special.spend(character, "strength")
		self.assertIsNone(updated)
		self.assertIn("10", problem)
		self.assertIsNotNone(Special.spend(character, "charm")[1])


class TestCharacterTransactions(DatabaseTestCase) :

	def test_names_are_unique_per_server_without_case(self) :
		self.assertEqual(self.add_character("Ayla").name, "Ayla")
		self.assertIsNone(self.add_character("ayla"))
		self.assertIsNotNone(self.add_character("Ayla", guild_id=OTHER_GUILD))
		self.assertEqual(CharacterTransactions().get(USER_ID, GUILD_ID, "AYLA").name, "Ayla")
		self.assertEqual(len(CharacterTransactions().get_all(USER_ID, GUILD_ID)), 1)

	def test_new_characters_wait_for_review(self) :
		character = CharacterTransactions().add(USER_ID, GUILD_ID, "Ayla")
		self.assertEqual((character.state, character.level, character.xp), (PENDING, 1, 0))

	def test_retired_characters_do_not_count_toward_the_cap(self) :
		self.add_character("One")
		self.add_character("Two", state=PENDING)
		self.add_character("Three", state=DENIED)
		self.add_character("Four", state=RETIRED)
		self.assertEqual(CharacterTransactions().count_active(USER_ID, GUILD_ID), 3)

	def test_prefix_and_suffix_are_unique_per_user_and_server(self) :
		ayla = self.add_character("Ayla", prefix="A:", suffix=None)
		transactions = CharacterTransactions()
		self.assertTrue(transactions.trigger_taken(USER_ID, GUILD_ID, "a:", None))
		self.assertFalse(transactions.trigger_taken(USER_ID, GUILD_ID, "A:", "!"))
		self.assertFalse(transactions.trigger_taken(USER_ID, GUILD_ID, "A:", None, exclude_id=ayla.id))
		self.assertFalse(transactions.trigger_taken(USER_ID, OTHER_GUILD, "A:", None))
		self.assertFalse(transactions.trigger_taken(USER_ID + 1, GUILD_ID, "A:", None))

	def test_update_can_clear_a_field(self) :
		character = self.add_character(pending_changes={"name" : "Bryn"})
		updated = CharacterTransactions().update(character.id, pending_changes=None, suffix="!")
		self.assertEqual((updated.pending_changes, updated.suffix, updated.prefix), (None, "!", "ayla:"))


class TestSheet(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_new_servers_get_the_default_sheet_once(self) :
		self.assertTrue(Sheet.ensure(GUILD_ID))
		fields = SheetFieldTransactions().get_all(GUILD_ID)
		self.assertEqual([field.label for field in fields], [field["label"] for field in DEFAULT_SHEET])
		self.assertEqual([field.position for field in fields], list(range(1, len(DEFAULT_SHEET) + 1)))
		age = SheetFieldTransactions().find(GUILD_ID, "age")
		self.assertEqual((age.type, age.required, age.min_value, age.section), (NUMBER, True, 18, "Basic information"))
		self.assertFalse(Sheet.ensure(GUILD_ID))

	def test_an_emptied_sheet_stays_empty(self) :
		Sheet.ensure(GUILD_ID)
		SheetFieldTransactions().clear(GUILD_ID)
		ConfigData().data = {}
		self.assertFalse(Sheet.ensure(GUILD_ID))
		self.assertEqual(SheetFieldTransactions().get_all(GUILD_ID), [])
		Sheet.reset(GUILD_ID)
		self.assertEqual(len(SheetFieldTransactions().get_all(GUILD_ID)), len(DEFAULT_SHEET))

	def test_add_move_remove(self) :
		fields = SheetFieldTransactions()
		for label in ["Age", "Looks", "Backstory"] :
			self.assertIsNotNone(fields.add(GUILD_ID, label, type=SHORT))
		self.assertIsNone(fields.add(GUILD_ID, "age", type=SHORT))
		self.assertEqual(fields.add(GUILD_ID, "Species", position=1, type=SHORT).position, 1)
		self.assertTrue(fields.move(GUILD_ID, "backstory", 2))
		self.assertEqual([field.label for field in fields.get_all(GUILD_ID)], ["Species", "Backstory", "Age", "Looks"])
		self.assertTrue(fields.remove(GUILD_ID, "AGE"))
		self.assertFalse(fields.remove(GUILD_ID, "Age"))
		self.assertEqual([field.position for field in fields.get_all(GUILD_ID)], [1, 2, 3])

	def test_questions_leave_out_notes(self) :
		SheetFieldTransactions().add(GUILD_ID, "Rules", type=INFO, help="Read these.")
		SheetFieldTransactions().add(GUILD_ID, "Age", type=NUMBER, required=True)
		self.assertEqual([field.label for field in Sheet.questions(GUILD_ID)], ["Age"])

	def test_answers_are_checked_by_type(self) :
		fields = SheetFieldTransactions()
		age = fields.add(GUILD_ID, "Age", type=NUMBER, min_value=18, max_value=900)
		self.assertEqual(Sheet.check(age, " 30 "), ("30", None))
		for wrong in ["17", "901", "thirty", ""] :
			self.assertIsNone(Sheet.check(age, wrong)[0], wrong)

		archetype = fields.add(GUILD_ID, "Archetype", type=CHOICE, choices=["Spellcaster", "Melee", "Ranged"])
		self.assertEqual(Sheet.check(archetype, "2"), ("Melee", None))
		self.assertEqual(Sheet.check(archetype, "ranged"), ("Ranged", None))
		self.assertIsNone(Sheet.check(archetype, "4")[0])
		self.assertIsNone(Sheet.check(archetype, "Healer")[0])

		alias = fields.add(GUILD_ID, "Alias", type=SHORT)
		self.assertEqual(Sheet.check(alias, "x" * 200)[1], None)
		self.assertIsNotNone(Sheet.check(alias, "x" * 201)[1])
		history = fields.add(GUILD_ID, "History", type=LONG, max_length=10)
		self.assertIsNotNone(Sheet.check(history, "x" * 11)[1])

	def test_missing_required(self) :
		age = SheetFieldTransactions().add(GUILD_ID, "Age", type=NUMBER, required=True)
		looks = SheetFieldTransactions().add(GUILD_ID, "Looks", type=LONG, required=True)
		SheetFieldTransactions().add(GUILD_ID, "Voice", type=SHORT)
		self.assertEqual([field.label for field in Sheet.missing_required(GUILD_ID, {})], ["Age", "Looks"])
		self.assertEqual([field.label for field in Sheet.missing_required(GUILD_ID, {str(age.id) : "30"})], ["Looks"])
		self.assertEqual(Sheet.missing_required(GUILD_ID, {age.id : "30", looks.id : "tall"}), [])

	def test_question_definitions_are_checked(self) :
		check = Sheet.validate_definition
		self.assertIsNone(check(CHOICE, None, None, None, ["a", "b"]))
		self.assertIsNotNone(check(CHOICE, None, None, None, ["a"]))
		self.assertIsNotNone(check(CHOICE, None, None, None, ["a", "A"]))
		self.assertIsNotNone(check(SHORT, 5000, None, None, None))
		self.assertIsNotNone(check(SHORT, None, 1, None, None))
		self.assertIsNotNone(check(NUMBER, None, 10, 1, None))
		self.assertIsNotNone(check("essay", None, None, None, None))


class TestSheetAnswers(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		fields = SheetFieldTransactions()
		self.looks = fields.add(GUILD_ID, "Looks", type=LONG, section="Appearance")
		self.age = fields.add(GUILD_ID, "Age", type=NUMBER, section="Basics", position=1)
		self.character = self.add_character()
		self.info = CharacterInfoTransactions()

	def display(self) :
		return [(info.key, info.value) for info in self.info.get_all(self.character.id)]

	def test_answers_show_in_sheet_order_before_extra_fields(self) :
		self.info.add(self.character.id, "Theme song", "none")
		self.info.set_answer(self.character.id, self.looks.id, "Looks", "tall")
		self.info.set_answer(self.character.id, self.age.id, "Age", "30")
		self.assertEqual(self.display(), [("Age", "30"), ("Looks", "tall"), ("Theme song", "none")])
		self.assertEqual(self.info.get_answers(self.character.id), {self.age.id : "30", self.looks.id : "tall"})
		self.assertEqual([info.key for info in self.info.get_extras(self.character.id)], ["Theme song"])

	def test_answers_are_replaced_and_cleared(self) :
		self.info.set_answer(self.character.id, self.age.id, "Age", "30")
		self.info.set_answer(self.character.id, self.age.id, "Age", "31")
		self.assertEqual(self.display(), [("Age", "31")])
		self.info.set_answer(self.character.id, self.age.id, "Age", None)
		self.assertEqual(self.display(), [])

	def test_an_extra_field_with_the_questions_name_becomes_the_answer(self) :
		self.info.add(self.character.id, "age", "old")
		self.info.set_answer(self.character.id, self.age.id, "Age", "30")
		self.assertEqual(self.display(), [("Age", "30")])
		self.assertEqual(self.info.get_extras(self.character.id), [])

	def test_extra_field_commands_leave_answers_alone(self) :
		self.info.set_answer(self.character.id, self.age.id, "Age", "30")
		self.assertIsNone(self.info.add(self.character.id, "AGE", "duplicate"))
		self.assertIsNone(self.info.edit(self.character.id, "Age", "99"))
		self.assertFalse(self.info.remove(self.character.id, "Age"))
		self.info.replace_extras(self.character.id, [{"key" : "Motto", "value" : "onward"},
		                                             {"key" : "Pet", "value" : "a cat"}])
		self.assertEqual(self.display(), [("Age", "30"), ("Motto", "onward"), ("Pet", "a cat")])

	def test_a_removed_questions_answers_stay_as_extra_fields(self) :
		self.info.set_answer(self.character.id, self.age.id, "Age", "30")
		SheetFieldTransactions().remove(GUILD_ID, "Age")
		self.assertEqual(self.display(), [("Age", "30")])
		self.assertEqual([info.key for info in self.info.get_extras(self.character.id)], ["Age"])

	def test_long_answers_fit(self) :
		self.info.set_answer(self.character.id, self.looks.id, "Looks", "x" * 6000)
		self.assertEqual(len(self.info.get_all(self.character.id)[0].value), 6000)


class TestCard(DatabaseTestCase) :

	def test_chunk_text_breaks_between_lines(self) :
		self.assertEqual(chunk_text("one\ntwo\nthree", 8), ["one\ntwo", "three"])
		self.assertEqual(chunk_text("", 10), [""])
		chunks = chunk_text("word " * 100, 60)
		self.assertTrue(all(len(chunk) <= 60 for chunk in chunks))
		self.assertEqual(" ".join(chunks).split(), ["word"] * 100)
		self.assertEqual([len(chunk) for chunk in chunk_text("x" * 25, 10)], [10, 10, 5])

	def test_a_long_sheet_continues_in_more_embeds(self) :
		self.add_server()
		history = SheetFieldTransactions().add(GUILD_ID, "History", type=LONG, section="Background")
		character = self.add_character(prefix="Ayla:", suffix=None, luck=9)
		CharacterInfoTransactions().set_answer(character.id, history.id, "History", "A long tale. " * 700)
		CharacterInfoTransactions().add(character.id, "Motto", "onward")
		embeds = Card.embeds(character, "https://example.com/a.png")
		self.assertGreater(len(embeds), 2)
		self.assertTrue(all(len(embed.description) <= DESCRIPTION_LIMIT for embed in embeds))
		self.assertTrue(all(len(embed) <= 6000 for embed in embeds))
		first = embeds[0]
		self.assertEqual((first.title, first.thumbnail.url), ("Ayla", "https://example.com/a.png"))
		self.assertIn("**__Background__**", first.description)
		fields = {field.name : field.value for field in first.fields}
		self.assertEqual(fields["SPECIAL"], "S 5 · P 5 · E 5 · C 5 · I 5 · A 5 · L 9")
		self.assertEqual(fields["Speaks with"], "`Ayla:text`")
		self.assertIn("**Motto:** onward", embeds[-1].description)

	def test_trigger_text(self) :
		self.assertEqual(Card.trigger_text("[", "]"), "`[text]`")
		self.assertEqual(Card.trigger_text(None, " -a"), "`text -a`")
		self.assertEqual(Card.trigger_text(None, None), "none")
		self.assertEqual(len(STATS), 7)


class TestImageStorage(unittest.TestCase) :

	def test_uploads_are_checked(self) :
		self.assertIsNone(ImageStorage.check("image/png", 1000))
		self.assertIsNone(ImageStorage.check("image/jpeg; charset=binary", MAX_BYTES))
		self.assertIsNotNone(ImageStorage.check("image/png", MAX_BYTES + 1))
		self.assertIsNotNone(ImageStorage.check("application/pdf", 1000))
		self.assertIsNotNone(ImageStorage.check(None, 1000))

	def test_expiry_is_read_from_the_link(self) :
		expires = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
		url = f"https://cdn.discordapp.com/attachments/1/2/image.png?ex={int(expires.timestamp()):x}&is=abc&hm=def"
		self.assertEqual(ImageStorage.expiry(url), expires)
		self.assertIsNone(ImageStorage.expiry("https://cdn.discordapp.com/attachments/1/2/image.png"))
		self.assertIsNone(ImageStorage.expiry("https://cdn.discordapp.com/attachments/1/2/image.png?ex=zzz"))

	def test_links_are_refreshed_before_they_expire(self) :
		now = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
		self.assertTrue(ImageStorage.is_fresh(now + timedelta(hours=2), now))
		self.assertFalse(ImageStorage.is_fresh(now + timedelta(minutes=10), now))
		self.assertFalse(ImageStorage.is_fresh(now - timedelta(hours=1), now))
		self.assertFalse(ImageStorage.is_fresh(None, now))
