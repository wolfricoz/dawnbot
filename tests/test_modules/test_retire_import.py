import asyncio

from classes.characters.Access import Access
from classes.characters.Choices import Choices
from classes.characters.Edits import Edits
from classes.characters.Interview import CREATED, IMPORT, Interview
from classes.characters.Retirement import Retirement
from classes.characters.Review import Review
from classes.characters.Sheet import LONG, NUMBER
from classes.kernel.ConfigData import ConfigData
from database.transactions.AutoproxyTransactions import AutoproxyTransactions
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions, PENDING, RETIRED
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from database.transactions.ServerTransactions import ServerTransactions
from database.transactions.SheetFieldTransactions import SheetFieldTransactions
from database.transactions.StoredImageTransactions import StoredImageTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

OTHER_GUILD = 396757854637260811


def say(text) :
	return asyncio.run(Interview.answer(DraftTransactions().get(USER_ID), text))


class TestRetirement(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		self.guard = OccupationTransactions().add(GUILD_ID, "Guard", max_holders=1)
		self.character = self.add_character(occupation_id=self.guard.id)

	def test_retire(self) :
		AutoproxyTransactions().set(USER_ID, GUILD_ID, 555, self.character.id)
		image = StoredImageTransactions().add(1, 2, "https://example.com/a.png", None)
		_, character, _ = Edits.submit(self.character, {"avatar_id" : image.id})
		character = CharacterTransactions().update(character.id, review_message_id=99)
		retired, unused, problem = Retirement.retire(character)
		self.assertIsNone(problem)
		self.assertEqual((retired.state, retired.pending_changes, retired.review_message_id), (RETIRED, None, None))
		# The picture waiting for review is no longer needed, and autoproxy is off.
		self.assertEqual(unused, [image.id])
		self.assertIsNone(AutoproxyTransactions().get(USER_ID, [555]))
		# A retired character frees its place under the cap and in its occupation.
		self.assertEqual(CharacterTransactions().count_active(USER_ID, GUILD_ID), 0)
		self.assertTrue(Choices.room_for(self.guard.id))
		self.assertIsNotNone(Retirement.retire(retired)[2])

	def test_only_approved_characters_retire(self) :
		pending = self.add_character("Bryn", state=PENDING)
		self.assertIn("approved", Retirement.retire(pending)[2])

	def test_unretire(self) :
		retired, _, _ = Retirement.retire(self.character)
		back, note, problem = Retirement.unretire(retired)
		self.assertEqual((back.state, back.occupation_id, note, problem), (PENDING, self.guard.id, None, None))
		self.assertIn("not retired", Retirement.unretire(back)[2])
		approved, _, _ = Review.approve(back, 1)
		self.assertEqual(approved.state, APPROVED)

	def test_unretire_checks_the_cap_and_the_occupation(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.CHARACTER_CAP, 1, overwrite=True)
		retired, _, _ = Retirement.retire(self.character)
		self.add_character("Bryn", occupation_id=self.guard.id)
		self.assertIn("limit", Retirement.unretire(retired)[2])
		ConfigData().add_key(GUILD_ID, ConfigMapping.CHARACTER_CAP, 3, overwrite=True)
		back, note, _ = Retirement.unretire(retired)
		self.assertIsNone(back.occupation_id)
		self.assertIn("full", note)


class TestImport(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		ServerTransactions().add(OTHER_GUILD, "owner", "Other server", 10, "", owner_id=USER_ID)
		self.age = SheetFieldTransactions().add(GUILD_ID, "Age", type=NUMBER, required=True)
		self.history = SheetFieldTransactions().add(GUILD_ID, "History", type=LONG)
		self.looks = SheetFieldTransactions().add(GUILD_ID, "Looks", type=LONG, required=True)
		other_age = SheetFieldTransactions().add(OTHER_GUILD, "Age", type=NUMBER)
		self.source = self.add_character("Aria", guild_id=OTHER_GUILD, prefix="Aria:", strength=9, xp=5000,
		                                 level=4, currency=777)
		CharacterInfoTransactions().set_answer(self.source.id, other_age.id, "Age", "30")
		CharacterInfoTransactions().add(self.source.id, "history", "Born in the hills.")
		CharacterInfoTransactions().add(self.source.id, "Motto", "Onward.")

	def start(self) :
		return Interview.start(USER_ID, GUILD_ID, "Test server", IMPORT, self.source, Access(), avatar_id=None,
		                       source_guild_name="Other server")

	def test_copies_answers_and_asks_only_what_is_missing(self) :
		draft, text = self.start()
		self.assertIn("Bringing Aria to Test server", text)
		answers = draft.answers
		self.assertEqual((answers["name"], answers["prefix"], answers["imported_from"]), ("Aria", "Aria:", self.source.id))
		# Answers are matched to this server's questions by name, whatever their case; the rest become extra fields.
		self.assertEqual(answers["fields"], {str(self.age.id) : "30", str(self.history.id) : "Born in the hills."})
		self.assertEqual(answers["extras"], [{"key" : "Motto", "value" : "Onward."}])
		# Only the missing required question and the stats are asked.
		self.assertEqual(answers["queue"], [f"field:{self.looks.id}", "stat_method", "stats", "summary"])
		self.assertIsNone(draft.target_id)

	def test_a_clashing_name_and_trigger_are_asked_again(self) :
		self.add_character("Aria", prefix="Aria:")
		draft, text = self.start()
		self.assertEqual(draft.answers["queue"][:2], ["name", "trigger"])
		self.assertIn("name", text.lower())

	def test_submit_makes_a_fresh_character(self) :
		self.start()
		say("tall")
		say("buy")
		reply = say("5 5 5 5 6 7 7")
		self.assertIn("**Summary**", reply.text)
		reply = say("submit")
		self.assertEqual(reply.outcome, CREATED)
		character = reply.character
		self.assertEqual((character.guild_id, character.state, character.imported_from), (GUILD_ID, PENDING,
		                                                                                   self.source.id))
		# Experience, stats and currency start fresh.
		self.assertEqual((character.xp, character.level, character.strength, character.currency), (0, 1, 5, 3000))
		self.assertEqual([(info.key, info.value) for info in CharacterInfoTransactions().get_all(character.id)],
		                 [("Age", "30"), ("History", "Born in the hills."), ("Looks", "tall"), ("Motto", "Onward.")])
		# The original is left as it was.
		source = CharacterTransactions().get_by_id(self.source.id)
		self.assertEqual((source.guild_id, source.xp, source.currency), (OTHER_GUILD, 5000, 777))

	def test_characters_elsewhere(self) :
		self.add_character("Here")
		self.add_character("Retired", guild_id=OTHER_GUILD, state=RETIRED)
		self.add_character("Pending", guild_id=OTHER_GUILD, state=PENDING)
		names = [character.name for character in CharacterTransactions().get_elsewhere(USER_ID, GUILD_ID)]
		self.assertEqual(names, ["Aria", "Retired"])
