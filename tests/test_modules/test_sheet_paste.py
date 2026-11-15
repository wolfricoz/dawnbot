import unittest
from types import SimpleNamespace

from classes.characters import SheetPaste
from classes.characters.Interview import CREATE, EDIT, Interview
from classes.characters.Sheet import DEFAULT_SHEET
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.DraftTransactions import DraftTransactions
from test_modules.base import GUILD_ID, USER_ID
from test_modules.test_interview import InterviewTestCase

BUILTINS = {SheetPaste.NAME, SheetPaste.PROXY, SheetPaste.PREFIX, SheetPaste.SUFFIX, SheetPaste.SPECIES}


def default_fields() :
	"""The default sheet as field objects, without a database."""
	blank = {"max_length" : None, "min_value" : None, "max_value" : None, "choices" : None, "help" : None,
	         "required" : False}
	return [SimpleNamespace(id=index, **(blank | definition)) for index, definition in enumerate(DEFAULT_SHEET, start=1)]


def by_label(entries) :
	return {entry.label : entry for entry in entries}


class TestParse(unittest.TestCase) :
	"""Reading labels and answers out of sheets written in different styles."""

	def setUp(self) :
		self.fields = default_fields()
		self.ids = {field.label : field.id for field in self.fields}

	def parse(self, text) :
		return by_label(SheetPaste.parse(text, self.fields, BUILTINS))

	def test_labels_match_questions_by_name_synonym_and_part(self) :
		entries = self.parse("**Name:** Aria Vel\nRace: Elf\nNickname: Ari\nGender: Female\nSexuality: Bi\n"
		                     "Goals: Find her brother\nInterests: Bread\nClothing: A coat")
		self.assertEqual(entries["Name"].target, (SheetPaste.NAME,))
		self.assertEqual(entries["Name"].value, "Aria Vel")
		self.assertEqual(entries["Race"].target, (SheetPaste.SPECIES,))
		self.assertEqual(entries["Nickname"].target, (SheetPaste.FIELD, self.ids["Known alias"]))
		self.assertEqual(entries["Gender"].target, (SheetPaste.FIELD, self.ids["Gender representation"]))
		self.assertEqual(entries["Sexuality"].target, (SheetPaste.FIELD, self.ids["Sexual orientation"]))
		self.assertEqual(entries["Goals"].target, (SheetPaste.FIELD, self.ids["Goals / ambitions"]))
		self.assertEqual(entries["Interests"].target, (SheetPaste.FIELD, self.ids["Interests / quirks"]))
		self.assertEqual(entries["Clothing"].target, (SheetPaste.FIELD, self.ids["Apparel"]))

	def test_template_marks_and_hints_are_ignored(self) :
		entries = self.parse("Age* (a number, at least 18): 24\nCombat archetype (Spellcaster / Melee / Ranged): Melee")
		self.assertEqual(entries["Age"].value, "24")
		self.assertEqual(entries["Combat archetype"].target, (SheetPaste.FIELD, self.ids["Combat archetype"]))

	def test_dashes_separate_known_labels_only(self) :
		entries = self.parse("Height: 5'7\nWeight - 130lbs\nPersonality: Calm - mostly")
		self.assertEqual(entries["Height"].value, "5'7")
		self.assertEqual(entries["Weight"].value, "130lbs")
		self.assertEqual(entries["Personality"].value, "Calm - mostly")

	def test_headings_collect_the_paragraphs_under_them(self) :
		entries = self.parse("Age: 30\n\n# Backstory\nShe grew up in the woods.\nHe said: hello there.\n\nLater she left."
		                     "\n\n__Appearance__\nTall.\nSilver hair.")
		history = entries["Backstory"]
		self.assertEqual(history.target, (SheetPaste.FIELD, self.ids["History"]))
		self.assertEqual(history.value, "She grew up in the woods.\nHe said: hello there.\n\nLater she left.")
		self.assertEqual(entries["Appearance"].value, "Tall.\nSilver hair.")

	def test_unknown_labels_become_extras_but_sentences_do_not(self) :
		entries = self.parse("Age: 30\nTheme song: Some song\nShe was born in a small town, far away: Then she left."
		                     "\nVoice: Soft")
		self.assertIsNone(entries["Theme song"].target)
		self.assertEqual(entries["Theme song"].value,
		                 "Some song\nShe was born in a small town, far away: Then she left.")
		self.assertEqual(set(entries), {"Age", "Theme song", "Voice"})

	def test_section_headings_and_dividers_are_skipped(self) :
		entries = self.parse("== Basic information ==\nAge: 30\n━━━━━━━━\nAbout:\nStrengths: Brave")
		self.assertEqual(set(entries), {"Age", "Strengths"})
		self.assertEqual(entries["Age"].value, "30")

	def test_placeholders_count_as_empty(self) :
		entries = self.parse("Age: 30\nVoice: N/A\nReligion: None")
		self.assertEqual(entries["Voice"].value, "")
		self.assertEqual(entries["Religion"].value, "None")

	def test_links_and_times_are_not_labels(self) :
		entries = self.parse("History: Started at 10:30 one day.\nhttps://example.com/aria")
		self.assertEqual(entries["History"].value, "Started at 10:30 one day.\nhttps://example.com/aria")

	def test_a_sheet_needs_two_questions(self) :
		self.assertFalse(SheetPaste.is_sheet(SheetPaste.parse("Name: Aria", self.fields, BUILTINS)))
		self.assertFalse(SheetPaste.is_sheet(SheetPaste.parse("Just an answer.\nTheme: x", self.fields, BUILTINS)))
		self.assertTrue(SheetPaste.is_sheet(SheetPaste.parse("Name: Aria\nAge: 30", self.fields, BUILTINS)))

	def test_answers_are_eased_into_shape(self) :
		fields = {field.label : field for field in self.fields}
		self.assertEqual(SheetPaste.coerce(fields["Age"], "24 years old"), ("24", None))
		self.assertIsNotNone(SheetPaste.coerce(fields["Age"], "early 20s")[1])
		self.assertEqual(SheetPaste.coerce(fields["Combat archetype"], "Melee fighter"), ("Melee", None))
		self.assertEqual(SheetPaste.coerce(fields["Height"], "5'7\n(tall)"), ("5'7 (tall)", None))

	def test_template_reads_back_as_the_same_questions(self) :
		blocks = SheetPaste.template(self.fields, {SheetPaste.NAME, SheetPaste.PROXY, SheetPaste.SPECIES})
		self.assertTrue(all(block.startswith("```") and len(block) <= 2000 for block in blocks))
		text = "\n".join(block.strip("`") for block in blocks)
		self.assertIn("Age* (a number, at least 18):", text)
		self.assertIn("Combat archetype (Spellcaster / Melee / Ranged):", text)
		entries = SheetPaste.parse(text, self.fields, BUILTINS)
		questions = {field.id for field in self.fields if field.type != "info"}
		self.assertEqual({entry.target[1] for entry in entries if entry.target and entry.target[0] == "field"},
		                 questions)
		self.assertTrue(all(entry.value == "" for entry in entries))


class TestPasteInInterview(InterviewTestCase) :
	"""The small sheet from InterviewTestCase: Age (required number), Archetype (choice), History (long)."""

	SHEET = ("Name: Aria\n"
	         "Proxy: Aria: text\n"
	         "Age: 24 years old\n"
	         "Archetype: Melee fighter\n"
	         "Theme song: Some song\n"
	         "History:\nShe grew up in the woods.\n\nThen she left.")

	def test_a_pasted_sheet_fills_the_draft_and_skips_to_what_is_missing(self) :
		self.start()
		reply = self.say(self.SHEET)
		self.assertIn("I read your sheet", reply.text)
		self.assertIn("Filled in 5 answers", reply.text)
		self.assertIn("kept as extra fields: Theme song", reply.text)
		draft = DraftTransactions().get(USER_ID)
		self.assertEqual(draft.answers["name"], "Aria")
		self.assertEqual((draft.answers["prefix"], draft.answers["suffix"]), ("Aria:", None))
		self.assertEqual(draft.answers["fields"], {str(self.age.id) : "24", str(self.archetype.id) : "Melee",
		                                           str(self.history.id) : "She grew up in the woods.\n\nThen she left."})
		self.assertEqual(draft.answers["queue"], ["stat_method", "stats", "summary"])
		self.assertEqual(draft.step, "stat_method")

		self.answer_all("buy", "5 5 5 5 5 5 5")
		character = self.say("submit").character
		self.assertEqual(character.name, "Aria")
		info = {row.key : row.value for row in CharacterInfoTransactions().get_all(character.id)}
		self.assertEqual(info["Age"], "24")
		self.assertEqual(info["Theme song"], "Some song")

	def test_a_refused_answer_is_asked_again(self) :
		self.start()
		reply = self.say("Name: Aria\nProxy: Aria: text\nAge: 12")
		self.assertIn("**Age**: That has to be at least 18.", reply.text)
		draft = DraftTransactions().get(USER_ID)
		self.assertEqual(draft.step, f"field:{self.age.id}")
		self.assertNotIn(f"field:{self.archetype.id}", draft.answers["queue"])
		self.assertIn("**Summary**", self.answer_all("30", "buy", "5 5 5 5 5 5 5").text)

	def test_a_taken_trigger_is_asked_again(self) :
		self.add_character("Ayla", prefix="Aria:")
		self.start()
		reply = self.say("Name: Aria\nProxy: Aria: text\nAge: 30")
		self.assertIn("**Proxy**: Another of your characters", reply.text)
		self.assertEqual(self.step(), "trigger")

	def test_prefix_and_suffix_can_be_given_separately(self) :
		self.start()
		self.say("Name: Aria\nPrefix: [\nSuffix: ]\nAge: 30")
		draft = DraftTransactions().get(USER_ID)
		self.assertEqual((draft.answers["prefix"], draft.answers["suffix"]), ("[", "]"))

	def test_one_label_is_just_an_answer(self) :
		self.start()
		self.say("Aria")
		reply = self.say("Proxy: Aria: text")
		self.assertNotIn("I read your sheet", reply.text)

	def test_a_long_answer_needs_three_labels_to_count_as_a_sheet(self) :
		self.start()
		self.answer_all("Aria", "Aria: text", "30", "skip")
		self.assertEqual(self.step(), f"field:{self.history.id}")
		reply = self.say("She met him. Age: 20 at the time.\nArchetype: Melee, back then.")
		self.assertNotIn("I read your sheet", reply.text)
		self.assertIn("She met him.", DraftTransactions().get(USER_ID).answers["fields"][str(self.history.id)])

	def test_pasting_at_the_summary_changes_answers(self) :
		self.start()
		self.answer_all("Aria", "Aria: text", "30", "skip", "skip", "buy", "5 5 5 5 5 5 5")
		self.assertEqual(self.step(), "summary")
		reply = self.say("Age: 40\nArchetype: Spellcaster")
		self.assertIn("**Summary**", reply.text)
		self.assertEqual(DraftTransactions().get(USER_ID).answers["fields"][str(self.archetype.id)], "Spellcaster")

	def test_edit_reports_labels_it_cannot_keep(self) :
		character = self.add_character("Aria", prefix="Aria:")
		self.start(EDIT, character)
		reply = self.say("Age: 41\nArchetype: Melee\nTheme song: x")
		self.assertIn("**Theme song**: not on this server's sheet", reply.text)
		self.assertEqual(self.step(), "summary")
		fields = DraftTransactions().get(USER_ID).answers["fields"]
		self.assertEqual((fields[str(self.age.id)], fields[str(self.archetype.id)]), ("41", "Melee"))
		self.assertTrue(self.say("submit").finished)

	def test_template_command_sends_the_blank_sheet(self) :
		self.start()
		reply = self.say("template")
		self.assertIn("```", reply.text)
		self.assertIn("Age* (a number, at least 18):", reply.text)
		self.assertIn("Archetype (Spellcaster / Melee):", reply.text)
		self.assertNotIn("Combat notes", reply.text)
		self.assertEqual(self.step(), "name")

	def test_the_intro_mentions_pasting(self) :
		_, text = self.start(CREATE)
		self.assertIn("Paste the whole sheet", text)
