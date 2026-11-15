import asyncio
from unittest.mock import patch

from classes.characters import StatPanel
from classes.characters.Interview import Interview, RESPEC
from classes.characters.Special import STATS
from classes.kernel.ConfigData import ConfigData
from database.transactions.DraftTransactions import DraftTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import GUILD_ID, USER_ID
from test_modules.test_interview import InterviewTestCase


class StatPickerTestCase(InterviewTestCase) :

	def to_stats(self, method="buy") :
		self.start()
		self.answer_all("Aria", "Aria: text", "30", "skip", "skip", method)
		self.assertEqual(self.step(), "stats")
		return self.draft()

	def draft(self) :
		return DraftTransactions().get(USER_ID)


class TestPointBuy(StatPickerTestCase) :

	def test_starts_at_the_base_with_the_bonus_left(self) :
		state = StatPanel.state(self.to_stats())
		self.assertEqual(state.values, {stat : 5 for stat in STATS})
		self.assertEqual((state.left, state.budget), (5, 40))
		# Every menu stops at what the points left can pay for.
		self.assertEqual([option.value for option in state.options["strength"]], [str(n) for n in range(1, 11)])
		self.assertIn("costs 3 points, leaves 2", state.options["strength"][7].description)
		self.assertIn("Points left: **5** of 40", StatPanel.header(self.draft()))

	def test_picks_keep_count_and_limit_the_other_menus(self) :
		draft = self.to_stats()
		self.assertIsNone(StatPanel.choose(draft, "strength", "9"))
		self.assertIsNone(StatPanel.choose(self.draft(), "agility", "6"))
		state = StatPanel.state(self.draft())
		self.assertEqual(state.left, 0)
		self.assertEqual(state.options["luck"][-1].value, "5")
		self.assertIsNone(StatPanel.choose(self.draft(), "luck", "1"))
		self.assertEqual(StatPanel.state(self.draft()).left, 4)

	def test_overspending_and_bad_values_are_refused(self) :
		draft = self.to_stats()
		StatPanel.choose(draft, "strength", "10")
		self.assertIn("enough points", StatPanel.choose(self.draft(), "agility", "7"))
		self.assertIn("between 1 and 10", StatPanel.choose(self.draft(), "luck", "11"))
		self.assertIsNotNone(StatPanel.choose(self.draft(), "charm", "5"))

	def test_confirming_feeds_the_interview(self) :
		draft = self.to_stats()
		StatPanel.choose(draft, "strength", "8")
		draft = self.draft()
		self.assertEqual(StatPanel.answer_text(draft), "8 5 5 5 5 5 5")
		reply = asyncio.run(Interview.answer(draft, StatPanel.answer_text(draft)))
		self.assertIn("**Summary**", reply.text)
		self.assertEqual(self.draft().answers["stats"]["strength"], 8)

	def test_reset_goes_back_to_the_start(self) :
		draft = self.to_stats()
		StatPanel.choose(draft, "strength", "8")
		StatPanel.reset(self.draft())
		self.assertEqual(StatPanel.state(self.draft()).left, 5)

	def test_returning_to_the_step_starts_from_the_saved_stats(self) :
		self.to_stats()
		self.answer_all("10 1 5 6 6 6 6", "6")
		self.assertEqual(self.step(), "stat_method")
		self.say("buy")
		self.assertEqual(StatPanel.state(self.draft()).values["strength"], 10)

	def test_respec_starts_from_the_character(self) :
		character = self.add_character("Aria", strength=8, luck=2, unspent_points=1)
		self.start(RESPEC, character)
		state = StatPanel.state(self.draft())
		self.assertEqual((state.values["strength"], state.values["luck"], state.left), (8, 2, 1))


class TestRolled(StatPickerTestCase) :

	def to_roll(self, roll) :
		with patch("classes.characters.Special.Special.roll", return_value=roll) :
			self.to_stats("roll")
		return self.draft()

	def test_values_are_placed_once_each(self) :
		draft = self.to_roll([9, 8, 7, 6, 4, 3, 2])
		state = StatPanel.state(draft)
		self.assertFalse(state.complete)
		self.assertEqual([option.label for option in state.options["luck"]][:2], ["Luck 9", "Luck 8"])
		StatPanel.choose(draft, "strength", "0")
		state = StatPanel.state(self.draft())
		self.assertNotIn("0", [option.value for option in state.options["luck"]])
		self.assertTrue(state.options["strength"][0].default)
		self.assertEqual(state.unplaced, [8, 7, 6, 4, 3, 2])
		self.assertIsNone(StatPanel.answer_text(self.draft()))

	def test_equal_values_share_an_option_and_both_can_be_placed(self) :
		draft = self.to_roll([6, 6, 5, 5, 4, 4, 3])
		state = StatPanel.state(draft)
		self.assertEqual([option.label for option in state.options["strength"]],
		                 ["Strength 6", "Strength 5", "Strength 4", "Strength 3"])
		StatPanel.choose(draft, "strength", "0")
		StatPanel.choose(self.draft(), "perception", "0")
		assign = self.draft().answers["stat_assign"]
		self.assertEqual(sorted([assign["strength"], assign["perception"]]), [0, 1])
		self.assertIn("already placed", StatPanel.choose(self.draft(), "endurance", "0"))

	def test_a_full_placement_confirms(self) :
		draft = self.to_roll([9, 8, 7, 6, 4, 3, 2])
		for stat, index in zip(STATS, [6, 5, 4, 3, 2, 1, 0]) :
			StatPanel.choose(self.draft(), stat, str(index))
		self.assertEqual(StatPanel.answer_text(self.draft()), "2 3 4 6 7 8 9")
		self.assertIn("Every value is placed", StatPanel.header(self.draft()))

	def test_reroll_clears_the_placement(self) :
		draft = self.to_roll([9, 8, 7, 6, 4, 3, 2])
		StatPanel.choose(draft, "strength", "0")
		with patch("classes.characters.Special.Special.roll", return_value=[5, 5, 5, 5, 5, 5, 5]) :
			StatPanel.reroll(self.draft())
		draft = self.draft()
		self.assertEqual((draft.rerolls, draft.answers.get("stat_assign")), (1, None))
		self.assertIn("Rerolls so far: 1", StatPanel.header(draft))


class TestPickerView(StatPickerTestCase) :

	def test_view_fits_discord_limits(self) :
		from views.multiselect import StatPicker

		draft = self.to_stats()

		async def build() :
			return StatPicker.build(draft, "A note.")

		view = asyncio.run(build())
		payload = view.to_components()
		self.assertLessEqual(view.total_children_count, 40)
		container = payload[0]
		rows = [component for component in container["components"] if component["type"] == 1]
		self.assertEqual(len(rows), 8)
		selects = [row["components"][0] for row in rows[:7]]
		self.assertEqual([select["custom_id"] for select in selects], [f"stat_pick:{stat}" for stat in STATS])
		self.assertTrue(all(len(select["options"]) <= 25 for select in selects))
		self.assertTrue(all(len(option["label"]) <= 100 and len(option.get("description") or "") <= 100
		                    for select in selects for option in select["options"]))
		buttons = [button["custom_id"] for button in rows[7]["components"]]
		self.assertEqual(buttons, ["stat_btn:confirm", "stat_btn:reset"])

	def test_closed_once_the_step_is_done(self) :
		self.to_stats()
		self.say("5 5 5 5 5 5 5")
		self.assertFalse(StatPanel.is_open(self.draft()))

	def test_one_method_server_shows_the_picker_right_away(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.STAT_METHOD, "point_buy", overwrite=True)
		self.start()
		self.answer_all("Aria", "Aria: text", "30", "skip", "skip")
		self.assertTrue(StatPanel.is_open(self.draft()))
