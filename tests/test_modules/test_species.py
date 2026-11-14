import asyncio
import unittest
from unittest.mock import patch

from classes.characters.Access import Access, EVENT, LEVEL, ROLE, Requirement, STAFF_ONLY
from classes.characters.Card import Card
from classes.characters.Choices import Choices, DEFAULT_SPECIES
from classes.characters.Edits import Edits, REVIEW
from classes.characters.Interview import CREATE, EDIT, Interview
from classes.characters.Review import Review
from classes.characters.SpeciesRules import SpeciesRules
from classes.characters.Special import STATS, Special, StatRules
from classes.kernel.ConfigData import ConfigData
from classes.species.SpeciesInterview import SpeciesInterview
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions, DENIED, PENDING, RETIRED
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.LevelTransactions import LevelTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from database.transactions.SpeciesTransactions import APPROVED as SPECIES_APPROVED, DENIED as SPECIES_DENIED, \
	PENDING as SPECIES_PENDING, SpeciesTransactions
from database.transactions.TagRuleTransactions import TagRuleTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

RULES = StatRules(base=5, bonus=5, minimum=1, maximum=10, method="both")
FORUM = 777
TAG_VETERAN, TAG_KNIGHT, TAG_EVENT = 901, 902, 903
ROLE_KNIGHT = 4242


def say(text, user_id=USER_ID) :
	draft = DraftTransactions().get(user_id)
	return asyncio.run(Interview.answer(draft, text))


def say_species(text, user_id=USER_ID) :
	return SpeciesInterview.answer(DraftTransactions().get(user_id), text)


class TestAccess(DatabaseTestCase) :

	def test_requirements(self) :
		member = Access(role_ids={ROLE_KNIGHT}, level=2)
		self.assertIsNone(member.check([Requirement(ROLE, ROLE_KNIGHT), Requirement(LEVEL, 2)]))
		self.assertIn("level 3", member.check([Requirement(LEVEL, 3)]))
		self.assertIn("role", member.check([Requirement(ROLE, 1)]))
		self.assertIn("staff", member.check([Requirement(STAFF_ONLY)]))
		self.assertIsNone(Access(staff=True).check([Requirement(EVENT), Requirement(LEVEL, 99)]))
		self.assertTrue(Access.hidden([Requirement(EVENT)]))
		self.assertEqual(Access.from_dict(member.to_dict()), member)

	def test_server_level_counts_level_roles_reached(self) :
		for role_id, xp in [(1, 100), (2, 500), (3, 2000)] :
			LevelTransactions().add(GUILD_ID, role_id, xp)
		self.assertEqual([Access.server_level(GUILD_ID, xp) for xp in (0, 100, 600, 5000)], [0, 1, 2, 3])


class TestSpeciesRules(unittest.TestCase) :

	def test_balance(self) :
		check = SpeciesRules.check_definition
		ones, tens, zeros = [1] * 7, [10] * 7, [0] * 7
		self.assertIsNone(check(ones, tens, zeros, RULES))
		self.assertIsNone(check(ones, [12, 10, 10, 10, 8, 10, 10], zeros, RULES))
		self.assertIn("up by 1", check(ones, [12, 10, 10, 10, 9, 10, 10], zeros, RULES))
		self.assertIn("between -2 and 13", check(ones, [14, 10, 10, 10, 6, 10, 10], zeros, RULES))
		self.assertIsNone(check([-2, 4, 1, 1, 1, 1, 1], tens, zeros, RULES))
		self.assertIn("minimums", check([2, 1, 1, 1, 1, 1, 1], tens, zeros, RULES))
		self.assertIn("higher than its maximum", check([4, -2, 1, 1, 1, 1, 1], [3, 12, 10, 10, 10, 10, 10], zeros, RULES))
		self.assertIsNone(check(ones, tens, [2, 0, 0, 0, -2, 0, 0], RULES))
		self.assertIn("add up to 1", check(ones, tens, [1, 0, 0, 0, 0, 0, 0], RULES))
		self.assertIn("at most 5", check(ones, tens, [6, -6, 0, 0, 0, 0, 0], RULES))

	def test_stored_data_and_starting_values(self) :
		limits, modifiers = SpeciesRules.to_data([1] * 7, [12, 10, 10, 10, 8, 10, 10], [1, 0, 0, 0, -1, 0, 0], RULES)
		self.assertEqual((limits, modifiers), ({"strength" : [1, 12], "intelligence" : [1, 8]},
		                                       {"strength" : 1, "intelligence" : -1}))
		bounds = SpeciesRules.limits(None, RULES, limits)
		self.assertEqual((bounds["strength"], bounds["luck"]), ((1, 12), (1, 10)))
		start = SpeciesRules.start_values(RULES, bounds, SpeciesRules.modifiers(None, modifiers))
		self.assertEqual((start["strength"], start["intelligence"], start["luck"]), (6, 4, 5))
		rolled = SpeciesRules.apply_modifiers(dict.fromkeys(start, 8) | {"strength" : 12},
		                                      bounds, SpeciesRules.modifiers(None, modifiers))
		self.assertEqual((rolled["strength"], rolled["intelligence"]), (12, 7))
		text = SpeciesRules.describe(None, RULES, limits, modifiers)
		self.assertIn("**Strength:** 1 to 12, starts +1", text)
		self.assertEqual(SpeciesRules.describe(None, RULES, {}, {}), "No changes to the SPECIAL stats.")

	def test_values_follow_species_limits(self) :
		limits = SpeciesRules.limits(None, RULES, {"strength" : [1, 12], "intelligence" : [1, 8]})
		self.assertIsNone(Special.check_values([12, 5, 5, 5, 3, 5, 5], RULES, 40, limits))
		self.assertIn("for your species", Special.check_values([5, 5, 5, 5, 9, 5, 5], RULES, 40, limits))


class SpeciesTestCase(DatabaseTestCase) :
	"""A server with Human, a strong species, a knight-only species and an event species."""

	def setUp(self) :
		super().setUp()
		self.add_server()
		Choices.ensure_default_species(GUILD_ID)
		self.human = SpeciesTransactions().find(GUILD_ID, DEFAULT_SPECIES)
		self.orc = SpeciesTransactions().add(GUILD_ID, "Orc", state=SPECIES_APPROVED, description="Strong.",
		                                     benefits="Strength.", drawbacks="Temper.",
		                                     stat_limits={"strength" : [1, 12], "intelligence" : [1, 8]},
		                                     stat_modifiers={"strength" : 1, "intelligence" : -1})
		self.elf = SpeciesTransactions().add(GUILD_ID, "Elf", state=SPECIES_APPROVED, description="Old.",
		                                     tag_ids=[TAG_KNIGHT])
		self.fae = SpeciesTransactions().add(GUILD_ID, "Fae", state=SPECIES_APPROVED, tag_ids=[TAG_EVENT])
		SpeciesTransactions().add(GUILD_ID, "Draft", state=SPECIES_PENDING)
		TagRuleTransactions().set(GUILD_ID, FORUM, TAG_KNIGHT, ROLE, ROLE_KNIGHT)
		TagRuleTransactions().set(GUILD_ID, FORUM, TAG_EVENT, EVENT, None)

	def names(self, access) :
		return [species.name for species in Choices.species(GUILD_ID, access)]


class TestSpeciesChoices(SpeciesTestCase) :

	def test_the_default_species_is_added_once(self) :
		self.assertEqual(self.human.state, SPECIES_APPROVED)
		SpeciesTransactions().delete(self.human.id)
		ConfigData().data = {}
		self.assertFalse(Choices.ensure_default_species(GUILD_ID))
		self.assertIsNone(SpeciesTransactions().find(GUILD_ID, DEFAULT_SPECIES))

	def test_tags_restrict_who_may_pick(self) :
		self.assertEqual(self.names(Access()), ["Human", "Orc"])
		self.assertEqual(self.names(Access(role_ids={ROLE_KNIGHT})), ["Elf", "Human", "Orc"])
		self.assertEqual(self.names(Access(staff=True)), ["Elf", "Fae", "Human", "Orc"])
		# Retagging a post changes the rule at once.
		SpeciesTransactions().update(self.orc.id, tag_ids=[TAG_VETERAN])
		TagRuleTransactions().set(GUILD_ID, FORUM, TAG_VETERAN, LEVEL, 3)
		self.assertEqual(self.names(Access(level=2)), ["Human"])
		self.assertEqual(self.names(Access(level=3)), ["Human", "Orc"])
		self.assertEqual(TagRuleTransactions().remove(TAG_VETERAN), 1)
		self.assertEqual(self.names(Access()), ["Human", "Orc"])

	def test_spend_stops_at_the_species_maximum(self) :
		character = self.add_character(species_id=self.orc.id, strength=11, intelligence=8, unspent_points=3)
		character, problem = Special.spend(character, "strength")
		self.assertEqual((character.strength, problem), (12, None))
		self.assertIn("above 12", Special.spend(character, "strength")[1])
		self.assertIn("above 8", Special.spend(character, "intelligence")[1])


class TestOccupations(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		self.guard = OccupationTransactions().add(GUILD_ID, "Guard", max_holders=2)
		self.captain = OccupationTransactions().add(GUILD_ID, "Captain", max_holders=1, min_level=2)
		self.king = OccupationTransactions().add(GUILD_ID, "King", staff_only=True)
		self.farmer = OccupationTransactions().add(GUILD_ID, "Farmer")

	def test_names_and_order(self) :
		self.assertIsNone(OccupationTransactions().add(GUILD_ID, "guard"))
		self.assertTrue(OccupationTransactions().move(GUILD_ID, "farmer", 1))
		self.assertEqual([o.name for o in OccupationTransactions().get_all(GUILD_ID)],
		                 ["Farmer", "Guard", "Captain", "King"])
		self.assertTrue(OccupationTransactions().delete(self.captain.id))
		self.assertEqual([o.position for o in OccupationTransactions().get_all(GUILD_ID)], [1, 2, 3])

	def test_who_holds_a_place(self) :
		self.add_character("A", occupation_id=self.guard.id)
		self.add_character("B", state=PENDING, occupation_id=self.guard.id)
		self.add_character("C", state=RETIRED, occupation_id=self.guard.id)
		self.add_character("D", state=DENIED, occupation_id=self.guard.id)
		# An approved character with a change to Guard waiting for review holds a place too.
		self.add_character("E", occupation_id=self.farmer.id, pending_changes={"occupation_id" : self.guard.id})
		self.assertEqual(sorted(c.name for c in OccupationTransactions().holders(self.guard.id)), ["A", "B", "E"])
		self.assertFalse(Choices.room_for(self.guard.id))
		a = CharacterTransactions().get(USER_ID, GUILD_ID, "A")
		self.assertFalse(Choices.room_for(self.guard.id, a.id))

	def test_choices_show_why_one_is_locked(self) :
		self.add_character("A", occupation_id=self.captain.id)
		choices = {choice.occupation.name : choice for choice in Choices.occupations(GUILD_ID, Access(level=2))}
		self.assertEqual(choices["Guard"].label, "Guard (0/2)")
		self.assertEqual(choices["Farmer"].label, "Farmer (0/∞)")
		self.assertIsNone(choices["Guard"].locked)
		self.assertEqual(choices["Captain"].locked, "is full")
		self.assertIn("staff", choices["King"].locked)
		choices = {choice.occupation.name : choice for choice in Choices.occupations(GUILD_ID, Access(level=1))}
		self.assertIn("level 2", choices["Captain"].locked)
		# The character already holding Captain is not shut out of it.
		a = CharacterTransactions().get(USER_ID, GUILD_ID, "A")
		choices = {c.occupation.name : c for c in Choices.occupations(GUILD_ID, Access(level=2), a.id)}
		self.assertIsNone(choices["Captain"].locked)

	def test_a_removed_occupation_is_not_applied_from_a_waiting_change(self) :
		character = self.add_character(occupation_id=self.farmer.id)
		_, character, _ = Edits.submit(character, {"occupation_id" : self.guard.id})
		OccupationTransactions().delete(self.guard.id)
		character, _, _ = Review.approve(character, 1)
		self.assertEqual(character.occupation_id, self.farmer.id)


class TestCharacterInterview(SpeciesTestCase) :

	def setUp(self) :
		super().setUp()
		self.guard = OccupationTransactions().add(GUILD_ID, "Guard", max_holders=1)
		self.king = OccupationTransactions().add(GUILD_ID, "King", staff_only=True)

	def to_species(self, access=None) :
		draft, _ = Interview.start(USER_ID, GUILD_ID, "Test server", CREATE, access=access or Access())
		say("Aria")
		return draft, say("Aria: text")

	def test_species_and_occupation_steps(self) :
		draft, reply = self.to_species()
		self.assertEqual(draft.answers["queue"][:4], ["name", "trigger", "species", "occupation"])
		self.assertIn("1. **Human**", reply.text)
		self.assertIn("2. **Orc**", reply.text)
		self.assertNotIn("Elf", reply.text)
		self.assertNotIn("Fae", reply.text)
		self.assertIn("please pick", say("Elf").text.lower())
		reply = say("orc")
		self.assertIn("1. Guard (0/1)", reply.text)
		self.assertIn("2. King (0/∞) (unavailable: is only given out by staff)", reply.text)
		self.assertIn("is only given out by staff", say("2").text)
		self.assertIn("Please pick an occupation", say("skip").text)
		say("guard")
		# Orc starts at Strength 6 and Intelligence 4; the budget stays 40.
		reply = say("buy")
		self.assertIn("starts you at S 6 · P 5 · E 5 · C 5 · I 4 · A 5 · L 5", reply.text)
		self.assertIn("I 1-8", reply.text)
		self.assertIn("for your species", say("5 5 5 5 9 5 6").text)
		self.assertIn("**Summary**", say("12 5 5 5 3 5 5").text)
		reply = say("submit")
		character = reply.character
		self.assertEqual((character.species_id, character.occupation_id, character.strength, character.unspent_points),
		                 (self.orc.id, self.guard.id, 12, 0))
		fields = {field.name : field.value for field in Card.embeds(character)[0].fields}
		self.assertEqual((fields["Species"], fields["Occupation"]), ("Orc", "Guard"))

	def test_rolled_stats_get_the_species_changes(self) :
		self.to_species()
		say("orc")
		say("guard")
		with patch("classes.characters.Special.Special.roll", return_value=[10, 8, 6, 5, 4, 3, 2]) :
			say("roll")
			reply = say("10 8 6 5 4 3 2")
		self.assertIn("S 11 · P 8 · E 6 · C 5 · I 3 · A 3 · L 2", reply.text)

	def test_a_full_occupation_is_refused_on_submit(self) :
		self.to_species()
		say("human")
		say("guard")
		say("buy")
		say("5 5 5 5 5 5 5")
		self.add_character("Bryn", occupation_id=self.guard.id, user_id=USER_ID + 1)
		reply = say("submit")
		self.assertFalse(reply.finished)
		self.assertIn("filled up", reply.text)

	def test_with_no_open_occupation_it_can_be_skipped(self) :
		OccupationTransactions().update(self.guard.id, staff_only=True)
		self.to_species()
		reply = say("human")
		self.assertIn("Type **skip**", reply.text)
		self.assertIn("buy", say("skip").text)
		draft = DraftTransactions().get(USER_ID)
		self.assertEqual((draft.step, draft.answers["occupation_id"]), ("stat_method", None))

	def test_changing_species_in_an_edit_asks_for_new_stats_when_they_do_not_fit(self) :
		character = self.add_character(species_id=self.human.id, intelligence=10, unspent_points=1)
		draft, text = Interview.start(USER_ID, GUILD_ID, "Test server", EDIT, character, Access())
		self.assertIn("**Species:** Human", text)
		# 1 name, 2 speaks with, 3 species, 4 occupation
		say("3")
		reply = say("orc")
		self.assertIn("do not fit", reply.text)
		# 30 + 10 in stats and 1 unspent point.
		self.assertIn("**41** points", reply.text)
		self.assertIn("for your species", say("5 5 5 5 9 5 5").text)
		self.assertIn("**Summary**", say("12 5 5 5 8 5 1").text)
		reply = say("submit")
		self.assertEqual(reply.outcome, REVIEW)
		character = CharacterTransactions().get_by_id(character.id)
		self.assertEqual(character.pending_changes["species_id"], self.orc.id)
		self.assertEqual(character.pending_changes["stats"]["strength"], 12)
		character, _, _ = Review.approve(character, 1)
		self.assertEqual((character.species_id, character.strength, character.intelligence, character.unspent_points),
		                 (self.orc.id, 12, 8, 0))
		self.assertEqual(Special.summary({stat : getattr(character, stat) for stat in STATS}),
		                 "S 12 · P 5 · E 5 · C 5 · I 8 · A 5 · L 1")

	def test_changing_to_a_species_the_stats_fit(self) :
		character = self.add_character(species_id=self.human.id)
		Interview.start(USER_ID, GUILD_ID, "Test server", EDIT, character, Access())
		say("3")
		self.assertIn("**Summary**", say("orc").text)


class TestSpeciesInterview(SpeciesTestCase) :

	def start(self) :
		return SpeciesInterview.start(USER_ID, GUILD_ID, "Test server")

	def test_whole_interview(self) :
		draft, text = self.start()
		self.assertIn("Creating a species on Test server", text)
		self.assertIn("already has a species called Orc", say_species("orc").text)
		say_species("Dwarf")
		say_species("Short and sturdy.")
		say_species("Tough.")
		reply = say_species("Slow.")
		self.assertIn("highest each stat", reply.text)
		self.assertIn("up by 4", say_species("12 10 12 10 10 10 10").text)
		reply = say_species("10 10 12 10 10 8 10")
		self.assertIn("lowest each stat", reply.text)
		self.assertIn("above its highest", say_species("-2 -2 -1 1 1 9 1").text)
		reply = say_species("skip")
		self.assertIn("starting stats", reply.text)
		self.assertIn("add up to 1", say_species("0 0 1 0 0 0 0").text)
		reply = say_species("0 0 1 0 0 -1 0")
		self.assertIn("**Endurance:** 1 to 12, starts +1", reply.text)
		self.assertIn("**Agility:** 1 to 8, starts -1", reply.text)
		self.assertNotIn("Still needed", reply.text)
		reply = say_species("submit")
		species = reply.species
		self.assertEqual((species.name, species.state, species.creator_uid), ("Dwarf", SPECIES_PENDING, USER_ID))
		self.assertEqual(species.stat_limits, {"endurance" : [1, 12], "agility" : [1, 8]})
		self.assertEqual(species.stat_modifiers, {"endurance" : 1, "agility" : -1})
		self.assertIsNone(DraftTransactions().get(USER_ID))

	def test_back_and_summary(self) :
		self.start()
		self.assertIn("first question", say_species("back").text)
		for answer in ["Dwarf", "Short.", "Tough.", "Slow.", "skip", "skip", "skip"] :
			reply = say_species(answer)
		self.assertIn("**Summary**", reply.text)
		self.assertIn("benefits", say_species("3").text)
		self.assertIn("**Summary**", say_species("Very tough.").text)
		self.assertEqual(DraftTransactions().get(USER_ID).answers["benefits"], "Very tough.")
		self.assertIn("Cancelled", say_species("cancel").text)

	def test_review(self) :
		species = SpeciesTransactions().add(GUILD_ID, "Dwarf", creator_uid=USER_ID, state=SPECIES_PENDING,
		                                    description="Short.")
		self.assertTrue(SpeciesInterview.is_open(species))
		species = SpeciesInterview.deny(species)
		self.assertEqual((species.state, SpeciesInterview.is_open(species)), (SPECIES_DENIED, False))
		species = SpeciesTransactions().update(species.id, state=SPECIES_PENDING)
		species = SpeciesInterview.approve(species)
		self.assertEqual(species.state, SPECIES_APPROVED)

	def test_editing_an_approved_species_waits_for_review(self) :
		draft, text = SpeciesInterview.start(USER_ID, GUILD_ID, "Test server", self.orc)
		self.assertEqual((draft.step, draft.species_id), ("summary", self.orc.id))
		self.assertIn("`12 10 10 10 8 10 10`", text)
		say_species("2")
		say_species("Very strong.")
		reply = say_species("submit")
		self.assertEqual(reply.outcome, REVIEW)
		orc = SpeciesTransactions().get(self.orc.id)
		self.assertEqual((orc.description, orc.pending_changes["description"]), ("Strong.", "Very strong."))
		orc = SpeciesInterview.approve(orc)
		self.assertEqual((orc.description, orc.pending_changes, orc.stat_limits["strength"]),
		                 ("Very strong.", None, [1, 12]))

	def test_tag_rules(self) :
		rules = TagRuleTransactions()
		rules.set(GUILD_ID, FORUM, TAG_VETERAN, LEVEL, 3)
		rules.set(GUILD_ID, FORUM, TAG_VETERAN, LEVEL, 5)
		rules.set(GUILD_ID, FORUM, TAG_VETERAN, ROLE, ROLE_KNIGHT)
		self.assertEqual(sorted((r.kind, r.value) for r in rules.for_tags([TAG_VETERAN])),
		                 [(LEVEL, 5), (ROLE, ROLE_KNIGHT)])
		self.assertEqual(rules.remove(TAG_VETERAN, LEVEL), 1)
		self.assertEqual(len(rules.get_all(GUILD_ID)), 3)
