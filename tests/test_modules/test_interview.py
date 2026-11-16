import asyncio
import os
from unittest.mock import patch

from classes.characters.Edits import APPLIED, Edits, RESUBMITTED, REVIEW, UNCHANGED
from classes.characters.ImageStorage import ImageError
from classes.characters.Interview import CANCELLED, CREATE, CREATED, EDIT, Interview, RESPEC
from classes.characters.Review import CHANGES, NEW_CHARACTER, Review
from classes.characters.Sheet import CHOICE, INFO, LONG, NUMBER, SHORT
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions, DENIED, PENDING
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.SheetFieldTransactions import SheetFieldTransactions
from database.transactions.StoredImageTransactions import StoredImageTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

GUILD_NAME = "Test server"


def add_image() -> int :
	"""A stored picture; characters can only point at pictures that exist."""
	return StoredImageTransactions().add(1, 2, "https://example.com/image.png", None).id


class InterviewTestCase(DatabaseTestCase) :
	"""A server with a small sheet: a required number, an optional choice under a note, a long text."""

	def setUp(self) :
		super().setUp()
		self.add_server()
		fields = SheetFieldTransactions()
		self.age = fields.add(GUILD_ID, "Age", type=NUMBER, required=True, min_value=18, section="Basics")
		fields.add(GUILD_ID, "Combat notes", type=INFO, help="Roll a d20.", section="Combat")
		self.archetype = fields.add(GUILD_ID, "Archetype", type=CHOICE, choices=["Spellcaster", "Melee"],
		                            section="Combat")
		self.history = fields.add(GUILD_ID, "History", type=LONG, section="Combat")
		self.stored = []

	def start(self, kind=CREATE, character=None, user_id=USER_ID) :
		draft, text = Interview.start(user_id, GUILD_ID, GUILD_NAME, kind, character)
		return draft, text

	def say(self, text="", attachments=None, user_id=USER_ID) :
		"""Sends one message to the user's interview, the way a DM would, and returns the reply."""

		async def store_image(attachment) :
			if attachment == "broken" :
				raise ImageError("That file is not an image I can use.")
			self.stored.append(attachment)
			return 100 + len(self.stored)

		draft = DraftTransactions().get(user_id)
		return asyncio.run(Interview.answer(draft, text, attachments, store_image))

	def answer_all(self, *messages) :
		reply = None
		for message in messages :
			reply = self.say(message)
		return reply

	def step(self, user_id=USER_ID) :
		return DraftTransactions().get(user_id).step


class TestCreate(InterviewTestCase) :

	def test_whole_interview(self) :
		draft, text = self.start()
		self.assertIn("Creating a character on Test server", text)
		self.assertIn("name", text)
		self.assertEqual(draft.answers["queue"],
		                 ["name", "trigger", f"field:{self.age.id}", f"field:{self.archetype.id}",
		                  f"field:{self.history.id}", "stat_method", "stats", "summary"])

		self.assertIn("speak as Aria", self.say("Aria").text)
		reply = self.say("Aria: text")
		self.assertIn("__**Basics**__", reply.text)
		self.assertIn("at least 18", reply.text)
		reply = self.say("30")
		# The note above a question and its section heading are shown with it.
		self.assertIn("__**Combat**__", reply.text)
		self.assertIn("Roll a d20.", reply.text)
		self.assertIn("1. Spellcaster", reply.text)
		self.assertIn("(optional)", reply.text)
		self.say("2")
		self.assertIn("buy", self.say("Born in the hills.").text)
		self.assertIn("**40**", self.say("buy").text)
		reply = self.say("5 5 5 5 6 6 6")
		self.assertIn("**Summary**", reply.text)
		self.assertIn("Aria", reply.text)
		self.assertIn("`Aria:text`", reply.text)
		self.assertIn("Melee", reply.text)
		self.assertNotIn("Still needed", reply.text)

		reply = self.say("submit")
		self.assertEqual((reply.finished, reply.outcome), (True, CREATED))
		self.assertIsNone(DraftTransactions().get(USER_ID))
		character = CharacterTransactions().get(USER_ID, GUILD_ID, "aria")
		self.assertEqual(reply.character.id, character.id)
		self.assertEqual((character.state, character.prefix, character.suffix), (PENDING, "Aria:", None))
		self.assertEqual((character.strength, character.agility, character.luck), (5, 6, 6))
		# 38 of the 40 points were spent; the starting currency is the server's default.
		self.assertEqual((character.stat_method, character.unspent_points, character.currency),
		                 ("point_buy", 2, 1500))
		self.assertEqual([(info.key, info.value) for info in CharacterInfoTransactions().get_all(character.id)],
		                 [("Age", "30"), ("Archetype", "Melee"), ("History", "Born in the hills.")])

	def test_answers_survive_a_restart(self) :
		"""Every answer is in the database, so a draft read again continues where it was."""
		self.start()
		self.answer_all("Aria", "Aria: text")
		draft = DraftTransactions().get(USER_ID)
		self.assertEqual((draft.step, draft.answers["name"], draft.answers["prefix"]),
		                 (f"field:{self.age.id}", "Aria", "Aria:"))
		self.assertIn("Age", Interview.prompt(draft))

	def test_one_interview_at_a_time(self) :
		self.start()
		draft, text = self.start()
		self.assertIsNone(draft)
		self.assertIn("still creating a character on Test server", text)
		self.assertIsNotNone(self.start(user_id=USER_ID + 1)[0])

	def test_wrong_answers_are_asked_again(self) :
		self.start()
		self.assertIn("limit", self.say("x" * 81).text)
		self.assertIn("discord", self.say("Discord Bot").text.lower())
		self.assertEqual(self.step(), "name")
		self.say("Aria")
		self.assertIn("exactly once", self.say("Aria:").text)
		self.assertIn("before or after", self.say("text").text)
		self.assertEqual(self.step(), "trigger")
		self.say("[text]")
		self.assertIn("at least 18", self.say("17").text)
		self.assertIn("required", self.say("skip").text)
		self.assertEqual(self.step(), f"field:{self.age.id}")

	def test_names_and_triggers_of_other_characters_are_refused(self) :
		self.add_character("Aria", prefix="A:")
		self.start()
		self.assertIn("already have a character called Aria", self.say("aria").text)
		self.say("Bryn")
		self.assertIn("already uses that", self.say("a: text").text)
		reply = self.say("text -b")
		self.assertIn("Age", reply.text)
		self.assertEqual(DraftTransactions().get(USER_ID).answers["suffix"], "-b")

	def test_back_skip_and_cancel(self) :
		self.start()
		self.assertIn("first question", self.say("back").text)
		self.assertIn("cannot be skipped", self.say("skip").text)
		self.answer_all("Aria", "Aria: text", "30")
		self.assertEqual(self.step(), f"field:{self.archetype.id}")
		reply = self.say("back")
		self.assertIn("Current answer: 30", reply.text)
		self.answer_all("31", "skip")
		draft = DraftTransactions().get(USER_ID)
		self.assertEqual((draft.step, draft.answers["fields"]), (f"field:{self.history.id}", {str(self.age.id) : "31"}))
		reply = self.say("cancel")
		self.assertEqual((reply.finished, reply.outcome, reply.character), (True, CANCELLED, None))
		self.assertIsNone(DraftTransactions().get(USER_ID))
		self.assertEqual(CharacterTransactions().get_all(USER_ID, GUILD_ID), [])

	def test_summary_changes_one_answer_and_returns(self) :
		self.start()
		self.answer_all("Aria", "Aria: text", "30", "skip", "skip", "buy", "5 5 5 5 5 5 5")
		# 1 name, 2 speaks with, 3 age, 4 archetype, 5 history, 6 SPECIAL
		reply = self.say("4")
		self.assertIn("Archetype", reply.text)
		self.assertIn("**Summary**", self.say("spellcaster").text)
		self.assertIn("type a number", self.say("back").text.lower())
		self.assertIn("**Summary**", self.answer_all("1", "back").text)
		self.assertEqual(DraftTransactions().get(USER_ID).answers["name"], "Aria")
		# Changing the stats goes through the method again, then back to the summary.
		self.assertIn("buy", self.say("6").text)
		self.assertIn("Your SPECIAL roll", self.say("roll").text)
		self.assertEqual(self.step(), "stats")

	def test_submit_needs_everything(self) :
		self.start()
		self.answer_all("Aria", "Aria: text", "30", "skip", "skip", "buy", "5 5 5 5 5 5 5")
		SheetFieldTransactions().add(GUILD_ID, "Looks", type=SHORT, required=True)
		reply = self.say("submit")
		self.assertFalse(reply.finished)
		self.assertIn("Still needed: Looks", reply.text)
		self.assertIn("**Summary**", self.answer_all("6", "tall").text)
		self.assertEqual(self.say("submit").outcome, CREATED)

	def test_a_question_removed_during_the_interview_is_skipped(self) :
		self.start()
		self.answer_all("Aria", "Aria: text", "30")
		SheetFieldTransactions().remove(GUILD_ID, "Archetype")
		self.assertIn("History", self.say("1").text)

	def test_the_cap_is_checked_again_on_submit(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.CHARACTER_CAP, 1, overwrite=True)
		self.start()
		self.answer_all("Aria", "Aria: text", "30", "skip", "skip", "buy", "5 5 5 5 5 5 5")
		self.add_character("Bryn")
		reply = self.say("submit")
		self.assertFalse(reply.finished)
		self.assertIn("limit", reply.text)
		self.assertIsNone(CharacterTransactions().get(USER_ID, GUILD_ID, "Aria"))


class TestCreateStats(InterviewTestCase) :

	def to_stats(self) :
		self.start()
		return self.answer_all("Aria", "Aria: text", "30", "skip", "skip")

	def test_point_buy_is_checked(self) :
		self.to_stats()
		self.say("buy")
		self.assertIn("exactly seven", self.say("5 5 5").text)
		self.assertIn("Take 2 off", self.say("6 6 6 6 6 6 6").text)
		self.assertIn("between 1 and 10", self.say("11 1 5 5 5 5 5").text)
		self.assertEqual(self.step(), "stats")
		self.assertIn("**Summary**", self.say("10 1 5 6 6 6 6").text)

	def test_rolled_values_are_assigned_and_rerolls_counted(self) :
		self.to_stats()
		with patch("classes.characters.Special.Special.roll", side_effect=[[9, 8, 7, 6, 4, 3, 2], [6, 6, 5, 5, 4, 4, 3]]) :
			self.assertIn("9, 8, 7, 6, 4, 3, 2", self.say("roll").text)
			self.assertIn("exactly once", self.say("9 9 7 6 4 3 2").text)
			reply = self.say("reroll")
			self.assertIn("6, 6, 5, 5, 4, 4, 3", reply.text)
			self.assertIn("rerolls so far: 1", reply.text)
			self.assertIn("exactly once", self.say("9 8 7 6 4 3 2").text)
			self.assertIn("rolled, 1 rerolls", self.say("3 4 4 5 5 6 6").text)
		reply = self.say("submit")
		character = reply.character
		self.assertEqual((character.stat_method, character.rerolls, character.unspent_points), ("rolled", 1, 0))
		self.assertEqual((character.strength, character.luck), (3, 6))

	def test_a_roll_is_kept_when_the_player_leaves_and_returns(self) :
		"""Going back or restarting must not hand out a new roll for free."""
		self.to_stats()
		self.say("roll")
		rolled = DraftTransactions().get(USER_ID).rolled_values
		self.answer_all("back", "roll")
		draft = DraftTransactions().get(USER_ID)
		self.assertEqual((draft.rolled_values, draft.rerolls), (rolled, 0))

	def test_a_server_with_one_method_does_not_ask(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_METHOD, "point_buy", overwrite=True)
		draft, _ = self.start()
		self.assertNotIn("stat_method", draft.answers["queue"])
		reply = self.answer_all("Aria", "Aria: text", "30", "skip", "skip")
		self.assertIn("Set your SPECIAL stats", reply.text)
		self.assertIn("**Summary**", self.say("5 5 5 5 5 5 5").text)
		self.assertEqual(self.say("submit").character.stat_method, "point_buy")

	def test_server_rules_apply(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_BONUS, 0, overwrite=True)
		ConfigData().add_key(GUILD_ID, ConfigMapping.STARTING_CURRENCY, 0, overwrite=True)
		self.to_stats()
		self.assertIn("**35**", self.say("buy").text)
		self.assertIn("Take 1 off", self.say("5 5 5 5 5 5 6").text)
		self.say("5 5 5 5 5 5 5")
		self.assertEqual(self.say("submit").character.currency, 0)


class TestAvatar(InterviewTestCase) :

	def setUp(self) :
		super().setUp()
		patcher = patch.dict(os.environ, {"STORAGE_CHANNEL" : "123"})
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_a_picture_is_asked_when_storage_is_set_up(self) :
		draft, _ = self.start()
		self.assertEqual(draft.answers["queue"][:3], ["name", "trigger", "avatar"])
		self.assertIn("Send a picture for Aria", self.answer_all("Aria", "Aria: text").text)
		self.assertIn("upload an image", self.say("here you go").text.lower())
		self.assertIn("not an image", self.say("", ["broken"]).text)
		self.assertEqual(self.step(), "avatar")
		reply = self.say("", ["first.png"])
		self.assertIn("Age", reply.text)
		self.assertEqual((DraftTransactions().get(USER_ID).answers["avatar_id"], reply.discard_images), (101, []))

	def test_a_replaced_or_cancelled_picture_is_removed_from_storage(self) :
		self.start()
		self.answer_all("Aria", "Aria: text")
		self.say("", ["first.png"])
		self.say("back")
		self.assertEqual(self.say("", ["second.png"]).discard_images, [101])
		self.assertEqual(self.say("cancel").discard_images, [102])

	def test_a_picture_is_required(self) :
		self.start()
		self.answer_all("Aria", "Aria: text")
		self.assertIn("cannot be skipped", self.say("skip").text)


class TestEdit(InterviewTestCase) :

	def setUp(self) :
		super().setUp()
		self.character = self.add_character("Aria", prefix="Aria:", avatar_id=add_image())
		CharacterInfoTransactions().set_answer(self.character.id, self.age.id, "Age", "30")

	def test_edit_starts_at_the_summary(self) :
		draft, text = self.start(EDIT, self.character)
		self.assertEqual(draft.step, "summary")
		self.assertIn("Editing Aria on Test server", text)
		self.assertIn("**Age:** 30", text)
		self.assertNotIn("SPECIAL", text)

	def test_nothing_changed(self) :
		self.start(EDIT, self.character)
		reply = self.say("submit")
		self.assertEqual((reply.outcome, reply.finished), (UNCHANGED, True))

	def test_lore_changes_wait_for_review_and_the_rest_applies(self) :
		self.start(EDIT, self.character)
		# 1 name, 2 speaks with, 3 age, 4 archetype, 5 history
		self.answer_all("1", "Aria Stormborn", "2", "text ~a", "3", "31")
		reply = self.say("submit")
		self.assertEqual(reply.outcome, REVIEW)
		character = CharacterTransactions().get_by_id(self.character.id)
		# The prefix and suffix are not lore, so they changed at once; the name and age wait.
		self.assertEqual((character.name, character.prefix, character.suffix), ("Aria", None, "~a"))
		self.assertEqual(character.pending_changes, {"name" : "Aria Stormborn", "fields" : {str(self.age.id) : "31"}})
		self.assertEqual(CharacterInfoTransactions().get_answers(character.id), {self.age.id : "30"})

	def test_new_required_questions_are_asked_first(self) :
		looks = SheetFieldTransactions().add(GUILD_ID, "Looks", type=SHORT, required=True)
		draft, text = self.start(EDIT, self.character)
		self.assertEqual(draft.answers["queue"], [f"field:{looks.id}", "summary"])
		self.assertIn("Looks", text)
		self.assertIn("**Summary**", self.say("tall").text)

	def test_own_name_and_trigger_can_be_kept(self) :
		self.start(EDIT, self.character)
		self.assertIn("**Summary**", self.answer_all("1", "ARIA").text)
		self.assertIn("**Summary**", self.answer_all("2", "aria: text").text)

	def test_a_denied_character_is_resubmitted(self) :
		CharacterTransactions().update(self.character.id, state=DENIED)
		self.start(EDIT, CharacterTransactions().get_by_id(self.character.id))
		self.answer_all("3", "32")
		reply = self.say("submit")
		self.assertEqual(reply.outcome, RESUBMITTED)
		character = CharacterTransactions().get_by_id(self.character.id)
		self.assertEqual((character.state, character.pending_changes), (PENDING, None))
		self.assertEqual(CharacterInfoTransactions().get_answers(character.id), {self.age.id : "32"})

	def test_respec_keeps_the_total_and_is_always_reviewed(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.REAPPROVAL_ON_EDIT, "none", overwrite=True)
		character = CharacterTransactions().update(self.character.id, unspent_points=2)
		draft, text = self.start(RESPEC, character)
		self.assertEqual(draft.step, "stats")
		self.assertIn("**37** points", text)
		self.assertIn("Take 1 off", self.say("10 10 5 5 5 2 1").text)
		self.say("10 10 5 5 4 2 1")
		reply = self.say("submit")
		self.assertEqual(reply.outcome, REVIEW)
		character = CharacterTransactions().get_by_id(self.character.id)
		self.assertEqual((character.strength, character.pending_changes["stats"]["strength"]), (5, 10))
		character, _, kind = Review.approve(character, 99)
		self.assertEqual(kind, CHANGES)
		self.assertEqual((character.strength, character.luck, character.unspent_points, character.pending_changes),
		                 (10, 1, 0, None))


class TestEdits(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		self.age = SheetFieldTransactions().add(GUILD_ID, "Age", type=NUMBER)
		self.old, self.new, self.newer = add_image(), add_image(), add_image()
		self.character = self.add_character("Aria", prefix="Aria:", avatar_id=self.old)

	def set_mode(self, mode) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.REAPPROVAL_ON_EDIT, mode, overwrite=True)

	def test_what_each_mode_sends_to_review(self) :
		changes = {"name" : "B", "prefix" : "b:", "extras" : [], "stats" : {}, "fields" : {}, "avatar_id" : 9}
		self.assertEqual(sorted(Edits.split(GUILD_ID, changes)[1]), ["avatar_id", "fields", "name", "stats"])
		self.set_mode("none")
		self.assertEqual(sorted(Edits.split(GUILD_ID, changes)[1]), ["stats"])
		self.set_mode("all")
		self.assertEqual(Edits.split(GUILD_ID, changes)[0], {})

	def test_changes_apply_at_once_without_review(self) :
		self.set_mode("none")
		outcome, character, unused = Edits.submit(self.character, {"name" : "Bryn", "avatar_id" : self.new,
		                                                           "fields" : {str(self.age.id) : "40"}})
		self.assertEqual((outcome, character.name, character.avatar_id, character.pending_changes),
		                 (APPLIED, "Bryn", self.new, None))
		# The old picture is no longer used.
		self.assertEqual(unused, [self.old])
		self.assertEqual(CharacterInfoTransactions().get_answers(character.id), {self.age.id : "40"})

	def test_later_changes_join_the_ones_already_waiting(self) :
		_, character, unused = Edits.submit(self.character, {"avatar_id" : self.new, "fields" : {str(self.age.id) : "40"}})
		self.assertEqual(unused, [])
		outcome, character, unused = Edits.submit(character, {"avatar_id" : self.newer, "fields" : {"999" : "x"}})
		self.assertEqual(outcome, REVIEW)
		self.assertEqual(character.pending_changes, {"avatar_id" : self.newer, "fields" : {str(self.age.id) : "40", "999" : "x"}})
		# The first new picture was replaced before anyone approved it.
		self.assertEqual(unused, [self.new])

	def test_approve_applies_and_deny_discards(self) :
		_, character, _ = Edits.submit(self.character, {"name" : "Bryn", "avatar_id" : self.new})
		self.assertTrue(Review.is_open(character))
		denied, unused, kind = Review.deny(character)
		self.assertEqual((kind, denied.name, denied.avatar_id, denied.pending_changes, unused),
		                 (CHANGES, "Aria", self.old, None, [self.new]))
		self.assertFalse(Review.is_open(denied))

		_, character, _ = Edits.submit(denied, {"name" : "Bryn", "avatar_id" : self.newer})
		approved, unused, kind = Review.approve(character, 99)
		self.assertEqual((kind, approved.name, approved.avatar_id, approved.pending_changes, approved.state, unused),
		                 (CHANGES, "Bryn", self.newer, None, APPROVED, [self.old]))

	def test_a_name_taken_in_the_meantime_is_not_applied(self) :
		_, character, _ = Edits.submit(self.character, {"name" : "Bryn"})
		self.add_character("Bryn")
		approved, _, _ = Review.approve(character, 99)
		self.assertEqual(approved.name, "Aria")

	def test_extra_fields_are_reviewed_in_all_mode(self) :
		self.set_mode("all")
		extras = [{"key" : "Motto", "value" : "onward"}]
		outcome, character, _ = Edits.submit(self.character, {"extras" : extras})
		self.assertEqual(outcome, REVIEW)
		self.assertEqual(CharacterInfoTransactions().get_extras(character.id), [])
		self.assertIn("**Motto:** onward", Edits.describe(character, character.pending_changes))
		Review.approve(character, 99)
		self.assertEqual([info.key for info in CharacterInfoTransactions().get_extras(character.id)], ["Motto"])

	def test_describe_shows_old_and_new(self) :
		text = Edits.describe(self.character, {"name" : "Bryn", "prefix" : None, "fields" : {str(self.age.id) : "40"},
		                                       "stats" : dict.fromkeys(["strength", "perception", "endurance",
		                                                                "charisma", "intelligence", "agility",
		                                                                "luck"], 5) | {"strength" : 6}})
		self.assertIn("**Name:** Aria → Bryn", text)
		self.assertIn("`Aria:` → `none`", text)
		self.assertIn("**Age:** 40", text)
		self.assertIn("S 5 · P 5 · E 5 · C 5 · I 5 · A 5 · L 5 → S 6", text)


class TestReview(DatabaseTestCase) :

	def test_a_new_character_is_approved_or_denied(self) :
		character = self.add_character(state=PENDING, review_message_id=555)
		self.assertEqual((Review.kind(character), Review.is_open(character)), (NEW_CHARACTER, True))
		self.assertEqual(CharacterTransactions().get_by_review_message(555).id, character.id)

		denied, unused, kind = Review.deny(character)
		self.assertEqual((denied.state, denied.review_message_id, unused, kind), (DENIED, None, [], NEW_CHARACTER))
		self.assertFalse(Review.is_open(denied))

		pending = CharacterTransactions().update(denied.id, state=PENDING)
		approved, unused, kind = Review.approve(pending, 99)
		self.assertEqual((approved.state, approved.approved_by, kind), (APPROVED, 99, NEW_CHARACTER))
		self.assertIsNotNone(approved.approved_at)
		self.assertFalse(Review.is_open(approved))
