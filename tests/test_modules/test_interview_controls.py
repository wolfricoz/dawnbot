import asyncio

from classes.characters import Controls
from classes.characters.Access import Access
from classes.characters.Interview import CREATE, CREATED, Interview
from classes.characters.Review import Review
from classes.kernel.ConfigData import ConfigData
from classes.species.SpeciesInterview import CREATE as SPECIES_CREATE, SpeciesInterview
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.SpeciesTransactions import PENDING as SPECIES_PENDING, SpeciesTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import GUILD_ID, USER_ID
from test_modules.test_interview import InterviewTestCase
from test_modules.test_species import SpeciesTestCase, say, say_species
from test_modules.test_starting_gear import StartingGearTestCase, say as gear_say

REVIEW_CHANNEL = 555


def draft() :
	return DraftTransactions().get(USER_ID)


def actions(controls) :
	return [button.action for button in controls.buttons]


def press(action=None, menu=None, value=None) :
	"""What pressing a control on the current question types, or None when it is out of date."""
	current = draft()
	resolved = Controls.resolve(current, current.kind, current.step, action, menu, value)
	return resolved[0] if resolved else None


class TestCharacterControls(InterviewTestCase) :
	"""Name, trigger, Age (required), Archetype (optional choice), History (optional), stats, summary."""

	def test_each_step_offers_what_can_be_typed(self) :
		self.start()
		controls = Controls.build(draft())
		self.assertEqual(actions(controls), ["template", "cancel"])
		self.assertIn("Copy this", self.say(press("template")).text)
		self.say("Aria")
		self.assertEqual(actions(Controls.build(draft())), ["back", "cancel"])
		self.answer_all("Aria: text", "30")

		# An optional choice question: a menu with its numbered options, and Skip.
		controls = Controls.build(draft())
		self.assertEqual(actions(controls), ["back", "skip", "cancel"])
		self.assertEqual([(option.label, option.value) for option in controls.menus[0].options],
		                 [("Spellcaster", "1"), ("Melee", "2")])
		self.say(press(menu="pick", value="2"))
		self.assertEqual(draft().answers["fields"][str(self.archetype.id)], "Melee")
		self.say(press("skip"))

		self.assertEqual(actions(Controls.build(draft())), ["buy", "roll", "back", "cancel"])
		self.say(press("buy"))
		self.say("5 5 5 5 5 5 5")

		controls = Controls.build(draft())
		self.assertEqual(actions(controls), ["submit", "cancel"])
		options = controls.menus[0].options
		self.assertEqual((options[0].label, options[0].value, options[0].description), ("1. Name", "1", "Aria"))
		self.say(press(menu="change", value="1"))
		self.assertEqual(draft().step, "name")

	def test_a_required_question_cannot_be_skipped(self) :
		self.start()
		self.answer_all("Aria", "Aria: text")
		self.assertNotIn("skip", actions(Controls.build(draft())))

	def test_old_controls_are_refused(self) :
		self.start()
		old = draft()
		self.say("Aria")
		self.assertIsNone(Controls.resolve(draft(), old.kind, old.step, "cancel"))
		self.assertIsNone(press(menu="pick", value="1"))
		self.assertIsNone(press("submit"))

	def test_a_long_summary_is_spread_over_menus(self) :
		labels = [f"Question {number}" for number in range(1, 61)]
		menus = Controls._summary_menus(labels, ["x"] * 60)
		self.assertEqual([len(menu.options) for menu in menus], [25, 25, 10])
		self.assertEqual(menus[2].options[0].value, "51")
		self.assertTrue(all(len(menu.placeholder) <= 150 for menu in menus))


class TestGearControls(StartingGearTestCase) :

	def test_add_and_take_out_by_menu(self) :
		self.to_gear()
		controls = Controls.build(draft())
		self.assertEqual(actions(controls), ["done", "back", "cancel"])
		add = controls.menus[0]
		# Locked items are not offered; the Lance is level 2 and the Crown staff only.
		self.assertEqual([option.label for option in add.options], ["Sword", "Bow", "Leather", "Plate"])
		self.assertEqual(add.options[0].description, "weapon · 100 currency")
		gear_say(press(menu="add", value=f"#{self.bow.id}"))
		controls = Controls.build(draft())
		# 900 of the 1500 is left after the Bow.
		descriptions = {option.label : option.description for option in controls.menus[0].options}
		self.assertIn("more than you have left", descriptions["Plate"])
		self.assertNotIn("more than you have left", descriptions["Leather"])
		self.assertEqual([option.label for option in controls.menus[1].options], ["Bow"])
		self.assertEqual(press(menu="remove", value=f"#{self.bow.id}"), "remove 3")
		gear_say(press(menu="remove", value=f"#{self.bow.id}"))
		self.assertEqual(draft().answers["gear"], [])


class TestSpeciesStep(SpeciesTestCase) :

	def start(self, access=None) :
		Interview.start(USER_ID, GUILD_ID, "Test server", CREATE, access=access or Access())
		say("Aria")
		return say("Aria: text")

	def allow_species(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.CHARACTER_REVIEW, REVIEW_CHANNEL, overwrite=True)

	def test_one_species_is_still_asked(self) :
		for species in (self.orc, self.elf, self.fae) :
			SpeciesTransactions().delete(species.id)
		reply = self.start()
		self.assertEqual(draft().step, "species")
		self.assertIn("1. **Human**", reply.text)
		# Human changes nothing, so there is no second line saying so.
		self.assertEqual(reply.text.lower().count("no changes to the special stats"), 1)
		self.assertIsNone(draft().answers.get("species_id"))
		self.assertIn("Still needed: a species", Interview._summary(draft()))

	def test_menu_lists_species_and_their_changes(self) :
		self.start()
		menu = Controls.build(draft()).menus[0]
		self.assertEqual([option.label for option in menu.options], ["Human", "Orc"])
		self.assertEqual(menu.options[1].description, "Strength: 1 to 12, starts +1, Intelligence: 1 to 8, starts -1")
		self.assertEqual(press(menu="pick", value=f"#{self.orc.id}"), "Orc")
		# Without a review channel, no species can be made.
		self.assertNotIn(Controls.NEW_SPECIES_VALUE, [option.value for option in menu.options])
		self.assertIn("not set up reviews", say("new").text)

	def test_make_a_species_in_the_middle_of_a_character(self) :
		self.allow_species()
		reply = self.start()
		self.assertIn("Make a new species", reply.text)
		menu = Controls.build(draft()).menus[0]
		self.assertEqual(menu.options[-1].value, Controls.NEW_SPECIES_VALUE)
		reply = say(press(menu="pick", value=Controls.NEW_SPECIES_VALUE))
		self.assertIn("Your character is saved", reply.text)
		species_draft = draft()
		self.assertEqual((species_draft.kind, species_draft.step), (SPECIES_CREATE, "name"))
		self.assertEqual(actions(Controls.build(species_draft)), ["cancel"])
		self.assertEqual(Controls.build(species_draft).buttons[0].label, "Cancel species")

		for answer in ["Dwarf", "Short.", "Tough.", "Slow."] :
			say_species(answer)
		self.assertEqual(actions(Controls.build(draft())), ["keep", "back", "cancel"])
		for _ in range(3) :
			say_species(press("keep"))
		controls = Controls.build(draft())
		self.assertEqual(actions(controls), ["submit", "cancel"])
		self.assertEqual(controls.menus[0].options[0].label, "1. Name")
		reply = say_species(press("submit"))

		dwarf = reply.species
		self.assertEqual((dwarf.name, dwarf.state, reply.outcome), ("Dwarf", SPECIES_PENDING, "created"))
		self.assertIn("Back to your character", reply.text)
		character_draft = draft()
		self.assertEqual((character_draft.kind, character_draft.answers["name"], character_draft.answers["species_id"]),
		                 (CREATE, "Aria", dwarf.id))
		self.assertEqual(character_draft.step, "stat_method")
		self.assertIn("Dwarf (waiting for review)", Interview._summary(character_draft))

		say("buy")
		reply = say("5 5 5 5 5 5 5")
		self.assertNotIn("Still needed", reply.text)
		reply = say("submit")
		self.assertEqual(reply.outcome, CREATED)
		character = reply.character
		self.assertEqual(character.species_id, dwarf.id)
		self.assertIn("has not been approved yet", Review.waiting_on(character))
		SpeciesInterview.approve(dwarf)
		self.assertIsNone(Review.waiting_on(character))

	def test_cancelling_the_species_goes_back_to_the_character(self) :
		self.allow_species()
		self.start()
		say("orc")
		say("back")
		say("new")
		say_species("Dwarf")
		reply = say_species("cancel")
		self.assertIn("Cancelled the species", reply.text)
		self.assertIn("What species is your character?", reply.text)
		character_draft = draft()
		self.assertEqual((character_draft.kind, character_draft.step), (CREATE, "species"))
		self.assertEqual(character_draft.answers["species_id"], self.orc.id)
		self.assertIsNone(SpeciesTransactions().find(GUILD_ID, "Dwarf"))

	def test_a_species_made_earlier_stays_pickable(self) :
		self.allow_species()
		mine = SpeciesTransactions().add(GUILD_ID, "Dwarf", creator_uid=USER_ID, state=SPECIES_PENDING)
		self.start()
		self.assertIn("**Dwarf** (waiting for review)", Interview.prompt(draft()))
		say("dwarf")
		self.assertEqual(draft().answers["species_id"], mine.id)

	def test_species_creation_switched_off(self) :
		self.allow_species()
		ConfigData().add_key(GUILD_ID, ConfigMapping.SPECIES_CREATION, "off", overwrite=True)
		self.start()
		self.assertNotIn(Controls.NEW_SPECIES_VALUE,
		                 [option.value for option in Controls.build(draft()).menus[0].options])
		self.assertIn("does not take new species", say("new").text)
		self.assertEqual(draft().step, "species")


class TestControlsView(SpeciesTestCase) :

	def test_view_fits_discord_limits(self) :
		from views.buttons import InterviewControls

		ConfigData().add_key(GUILD_ID, ConfigMapping.CHARACTER_REVIEW, REVIEW_CHANNEL, overwrite=True)
		Interview.start(USER_ID, GUILD_ID, "Test server", CREATE, access=Access())
		say("Aria")
		say("Aria: text")

		async def build() :
			return InterviewControls.view(draft())

		view = asyncio.run(build())
		payload = view.to_components()
		self.assertLessEqual(len(payload), 5)
		select = payload[0]["components"][0]
		self.assertEqual(select["custom_id"], "ivm:create:species:pick")
		buttons = [button["custom_id"] for button in payload[1]["components"]]
		self.assertEqual(buttons, ["iv:create:species:back", "iv:create:species:cancel"])
		self.assertTrue(all(len(option["label"]) <= 100 for option in select["options"]))
		self.assertEqual(InterviewControls.token("field:12"), "field.12")


class FakeUser :
	"""A DM user that records what was sent and which messages had their controls taken off."""

	def __init__(self) :
		self.id = USER_ID
		self.sent = []
		self.stripped = []
		self.dm_channel = self

	async def send(self, content=None, view=None) :
		from types import SimpleNamespace

		message = SimpleNamespace(id=len(self.sent) + 1, components=view.to_components() if view else [])
		self.sent.append((content, view))
		return message

	def get_partial_message(self, message_id) :
		user = self

		class Partial :
			async def edit(self, view=None) :
				user.stripped.append(message_id)

		return Partial()


class TestSendingControls(InterviewTestCase) :

	def test_each_question_carries_its_controls_and_the_last_ones_come_off(self) :
		from classes.characters.CharacterFlow import CharacterFlow

		user = FakeUser()
		_, text = self.start()
		self.assertTrue(asyncio.run(CharacterFlow.send_question(user, text)))
		self.assertEqual(draft().answers["controls_message"], 1)
		asyncio.run(CharacterFlow.answer_text(None, user, draft(), "Aria"))
		self.assertEqual(user.stripped, [1])
		self.assertIn("speak as Aria", user.sent[-1][0])
		self.assertEqual(draft().answers["controls_message"], 2)
		# A press takes its own message's controls off, so they are not taken off twice.
		asyncio.run(CharacterFlow.answer_text(None, user, draft(), "back", pressed_message_id=2))
		self.assertEqual(user.stripped, [1])
		self.assertEqual(draft().step, "name")
