import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from classes.checks import CheckCard, Checks
from classes.checks.CheckFlow import CheckFlow
from classes.checks.Checks import BAD, CRIT, FAILURE, FUMBLE, ROLLED, STRONG, SUCCESS
from classes.combat.Rules import Bonus
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.CheckTransactions import CheckTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

CHANNEL_ID = 555
OTHER_USER = 99


class FixedRng :
	"""randint returns the given numbers in order."""

	def __init__(self, *values) :
		self.values = list(values)

	def randint(self, low, high) :
		return self.values.pop(0)


def stats(**values) :
	return {stat : 5 for stat in ("strength", "perception", "endurance", "charisma", "intelligence", "agility",
	                              "luck")} | values


class TestCheckRules(unittest.TestCase) :

	def test_dc_names_and_numbers(self) :
		self.assertEqual([Checks.parse_dc(text) for text in ("easy", "Average", "HARD", "very hard", "very_hard",
		                                                     "veryhard", "heroic")], [8, 12, 15, 18, 18, 18, 22])
		self.assertEqual((Checks.parse_dc("15"), Checks.parse_dc(13), Checks.parse_dc(" 7 ")), (15, 13, 7))
		self.assertEqual([Checks.parse_dc(text) for text in ("0", "41", "tricky", None, "")], [None] * 5)
		self.assertEqual(Checks.dc_text(15), "DC 15 (Hard)")
		self.assertEqual(Checks.dc_text(14), "DC 14")
		self.assertEqual(Checks.dc_text(15, hidden=True), "DC ?")

	def test_outcomes_follow_the_margin(self) :
		# Perception 8: +3.
		character = stats(perception=8)
		self.assertEqual(Checks.roll(character, "perception", 12, rng=FixedRng(14)).outcome, STRONG)  # 17
		self.assertEqual(Checks.roll(character, "perception", 12, rng=FixedRng(9)).outcome, SUCCESS)  # 12
		self.assertEqual(Checks.roll(character, "perception", 12, rng=FixedRng(8)).outcome, FAILURE)  # 11
		self.assertEqual(Checks.roll(character, "perception", 12, rng=FixedRng(4)).outcome, BAD)  # 7

	def test_crits_and_fumbles_ignore_the_total(self) :
		self.assertEqual(Checks.roll(stats(), "strength", 40, rng=FixedRng(20)).outcome, CRIT)
		self.assertEqual(Checks.roll(stats(strength=13), "strength", 2, modifier=20, rng=FixedRng(1)).outcome, FUMBLE)

	def test_luck_widens_crits_and_fumbles(self) :
		self.assertEqual(Checks.roll(stats(luck=9), "agility", 30, rng=FixedRng(18)).outcome, CRIT)
		self.assertNotEqual(Checks.roll(stats(luck=6), "agility", 30, rng=FixedRng(19)).outcome, CRIT)
		self.assertEqual(Checks.roll(stats(luck=2), "agility", 2, modifier=10, rng=FixedRng(2)).outcome, FUMBLE)
		self.assertEqual(Checks.roll(stats(luck=0), "agility", 2, modifier=10, rng=FixedRng(3)).outcome, FUMBLE)

	def test_crippled_luck_must_confirm_a_crit(self) :
		# Luck 0 rolls at -5. A natural 20 crits only when a second roll (here 2 - 5) also reaches the DC; otherwise
		# the total (20 - 5 = 15) decides.
		result = Checks.roll(stats(luck=0), "luck", 18, rng=FixedRng(20, 2))
		self.assertEqual(result.outcome, FAILURE)
		self.assertTrue(result.notes)
		confirmed = Checks.roll(stats(luck=0), "luck", 10, rng=FixedRng(20, 19))
		self.assertEqual(confirmed.outcome, CRIT)

	def test_modifiers_add_up(self) :
		result = Checks.roll(stats(intelligence=7), "intelligence", 10, modifier=-1,
		                     extras=[Bonus("Help (Bram)", 2)], rng=FixedRng(10))
		self.assertEqual([bonus.value for bonus in result.bonuses], [2, -1, 2])
		self.assertEqual(result.total, 13)
		self.assertEqual(result.bonuses[0].label, "INT 7")

	def test_server_stat_base(self) :
		self.assertEqual(Checks.roll(stats(charisma=6), "charisma", 10, base=6, rng=FixedRng(10)).total, 10)

	def test_duel_rolls_have_no_outcome_until_compared(self) :
		self.assertEqual(Checks.roll(stats(), "strength", None, rng=FixedRng(10)).outcome, ROLLED)
		self.assertEqual(Checks.roll(stats(), "strength", None, rng=FixedRng(20)).outcome, CRIT)

	def test_opposed_winner(self) :
		def result(total, outcome=ROLLED) :
			return Checks.CheckResult(natural=10, rolls=[10], bonuses=[], total=total, dc=None, outcome=outcome)

		self.assertEqual(Checks.opposed_winner(result(15), result(12)), 1)
		self.assertEqual(Checks.opposed_winner(result(12), result(15)), 2)
		self.assertEqual(Checks.opposed_winner(result(14), result(14)), 2)
		self.assertEqual(Checks.opposed_winner(result(5, CRIT), result(25)), 1)
		self.assertEqual(Checks.opposed_winner(result(25, FUMBLE), result(3)), 2)
		self.assertEqual(Checks.opposed_winner(result(9, CRIT), result(8, CRIT)), 1)

	def test_group_needs_half(self) :
		self.assertTrue(Checks.group_passed([SUCCESS, FAILURE]))
		self.assertTrue(Checks.group_passed([CRIT, STRONG, BAD]))
		self.assertFalse(Checks.group_passed([SUCCESS, FAILURE, FUMBLE]))
		self.assertIsNone(Checks.group_passed([]))

	def test_who_may_roll(self) :
		self.assertTrue(Checks.may_roll({}, 1, []))
		self.assertTrue(Checks.may_roll({"member" : 1}, 1, []))
		self.assertFalse(Checks.may_roll({"member" : 1}, 2, []))
		self.assertTrue(Checks.may_roll({"role" : 7}, 2, [7]))
		self.assertTrue(Checks.may_roll({"role" : 7, "member" : 2}, 2, []))
		self.assertFalse(Checks.may_roll({"role" : 7, "member" : 3}, 2, [8]))

	def test_help_is_used_once(self) :
		helps = [{"helper_uid" : 5, "helper_character_id" : 50, "helper_name" : "Bram", "target_uid" : 1,
		          "used" : False}]
		updated, help_ = Checks.take_help(helps, 1)
		self.assertEqual(help_["helper_name"], "Bram")
		self.assertTrue(updated[0]["used"])
		self.assertFalse(helps[0]["used"])
		self.assertIsNone(Checks.take_help(updated, 1)[1])
		self.assertIsNone(Checks.take_help(helps, 2)[1])

	def test_help_problems(self) :
		helps = [{"helper_character_id" : 50, "target_uid" : 1}]
		self.assertIsNotNone(Checks.help_problem(helps, 5, 51, 5))
		self.assertIsNotNone(Checks.help_problem(helps, 5, 50, 1))
		self.assertIsNone(Checks.help_problem(helps, 5, 51, 1))


class TestCheckRecords(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def make_check(self, **fields) :
		values = dict(dc=12, expires_at=datetime.now(timezone.utc) + timedelta(hours=1)) | fields
		return CheckTransactions().create(GUILD_ID, CHANNEL_ID, USER_ID, "perception", **values)

	def test_each_character_rolls_once(self) :
		character = self.add_character()
		check = self.make_check()
		first = CheckTransactions().add_roll(check.id, character.id, USER_ID, character.name, "perception",
		                                     natural=10, total=10, outcome=FAILURE)
		self.assertIsNotNone(first)
		self.assertIsNone(CheckTransactions().add_roll(check.id, character.id, USER_ID, character.name, "perception",
		                                               natural=15, total=15, outcome=SUCCESS))
		self.assertEqual(len(CheckTransactions().rolls(check.id)), 1)

	def test_expired_checks(self) :
		old = self.make_check(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
		self.make_check()
		closed = self.make_check(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1), state=Checks.CLOSED)
		expired = [check.id for check in CheckTransactions().expired(datetime.now(timezone.utc))]
		self.assertEqual(expired, [old.id])
		self.assertNotIn(closed.id, expired)

	def test_secret_cards_hide_totals(self) :
		character = self.add_character()
		check = self.make_check(visibility=Checks.SECRET)
		CheckTransactions().add_roll(check.id, character.id, USER_ID, character.name, "perception", natural=17,
		                             total=17, outcome=STRONG)
		rolls = CheckTransactions().rolls(check.id)
		card = CheckCard.embed(check, rolls)
		text = " ".join(field.value for field in card.fields) + card.title
		self.assertNotIn("17", text)
		self.assertIn("DC ?", card.title)
		self.assertIn("rolled", text)
		self.assertIn("17", CheckCard.results_text(check, rolls))

	def test_public_card_and_group_result(self) :
		check = self.make_check(kind=Checks.GROUP, state=Checks.CLOSED)
		for number, outcome in enumerate([SUCCESS, FAILURE, STRONG]) :
			character = self.add_character(f"Hero{number}", user_id=USER_ID + number)
			CheckTransactions().add_roll(check.id, character.id, character.uid, character.name, "perception",
			                             natural=10, total=10 + number, outcome=outcome)
		card = CheckCard.embed(check, CheckTransactions().rolls(check.id))
		self.assertIn("DC 12", card.title)
		result = [field.value for field in card.fields if field.name == "Result"][0]
		self.assertIn("group succeeds", result)
		self.assertIn("2 of 3", result)

	def test_duel_hides_totals_until_both_rolled_and_picks_a_winner(self) :
		mine = self.add_character("Aria")
		theirs = self.add_character("Bram", user_id=OTHER_USER)
		opposed = {"1" : {"uid" : USER_ID, "character_id" : mine.id, "name" : "Aria", "stat" : "agility"},
		           "2" : {"uid" : OTHER_USER, "character_id" : theirs.id, "name" : "Bram", "stat" : "perception"}}
		check = self.make_check(kind=Checks.OPPOSED, dc=None, opposed=opposed)
		CheckTransactions().add_roll(check.id, mine.id, USER_ID, "Aria", "agility", side=1, natural=12, total=14,
		                             outcome=ROLLED)
		card = CheckCard.embed(check, CheckTransactions().rolls(check.id))
		self.assertNotIn("14", " ".join(field.value for field in card.fields))
		self.assertEqual(CheckFlow.settle_duel(check), {})
		CheckTransactions().add_roll(check.id, theirs.id, OTHER_USER, "Bram", "perception", side=2, natural=13,
		                             total=14, outcome=ROLLED)
		changes = CheckFlow.settle_duel(check)
		self.assertEqual(changes["opposed"]["winner"], 2)
		self.assertEqual(changes["state"], Checks.CLOSED)
		updated = CheckTransactions().update(check.id, **changes)
		card = CheckCard.embed(updated, CheckTransactions().rolls(check.id))
		result = [field.value for field in card.fields if field.name == "Result"][0]
		self.assertIn("Bram", result)

	def test_npc_opposed_card(self) :
		check = self.make_check(kind=Checks.OPPOSED, dc=15,
		                        opposed={"npc" : "Guard", "bonus" : 2, "natural" : 12, "total" : 14})
		self.assertIn("Guard", CheckCard.title(check))
		self.assertIn("**14**", CheckCard.description(check))
		hidden = self.make_check(kind=Checks.OPPOSED, dc=15, visibility=Checks.HIDDEN_DC,
		                         opposed={"npc" : "Guard", "bonus" : 2, "natural" : 12, "total" : 14})
		self.assertNotIn("14", CheckCard.description(hidden))

	def test_make_roll_uses_bad_roll_protection(self) :
		import random

		character = self.add_character(perception=1, bad_streak=3)
		check = self.make_check(dc=40)
		random.seed(4)
		result, first = CheckFlow.make_roll(check, character, "perception", [])
		# DC 40 can't be reached without a crit, so the roll was made again.
		self.assertIsNotNone(first)
		duel = self.make_check(dc=None, kind=Checks.OPPOSED)
		self.assertIsNone(CheckFlow.make_roll(duel, character, "perception", [])[1])

	def test_present_characters(self) :
		here = self.add_character("Here")
		gone = self.add_character("Gone")
		elsewhere = self.add_character("Elsewhere")
		ProxyTransactions().log([1001], here.id, USER_ID, GUILD_ID, CHANNEL_ID, 400, True, 1, 1)
		ProxyTransactions().log([1002], gone.id, USER_ID, GUILD_ID, CHANNEL_ID, 400, True, 1, 1)
		ProxyTransactions().mark_deleted([1002])
		ProxyTransactions().log([1003], elsewhere.id, USER_ID, GUILD_ID, CHANNEL_ID + 1, 400, True, 1, 1)
		guild = SimpleNamespace(id=GUILD_ID, get_member=lambda uid : None)
		self.assertEqual([character.name for character in CheckFlow.present(guild, CHANNEL_ID, None, None)],
		                 ["Here"])
		member = SimpleNamespace(id=OTHER_USER)
		self.assertEqual(CheckFlow.present(guild, CHANNEL_ID, None, member), [])
		CharacterTransactions().update(here.id, state="retired")
		self.assertEqual(CheckFlow.present(guild, CHANNEL_ID, None, None), [])
