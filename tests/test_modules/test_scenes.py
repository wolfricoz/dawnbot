import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

from classes.scenes import ChronicleFlow as Chronicle, Scenes
from classes.scenes.SceneFlow import SceneFlow
from database.transactions.SceneTransactions import SceneTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
CHANNEL_ID = 700


def people(*names) :
	return [SimpleNamespace(id=name, uid=index, character_id=index, last_post_at=None, last_nudged_at=None,
	                        joined_at=NOW - timedelta(days=5)) for index, name in enumerate(names)]


def ids(order) :
	return [participant.id for participant in order]


class TestTurns(unittest.TestCase) :

	def test_posting_in_turn_passes_it_on(self) :
		order, turn, passed = Scenes.after_post(people("A", "B", "C"), 1, "B")
		self.assertEqual((ids(order), turn, passed), (["A", "B", "C"], 2, True))
		self.assertEqual(Scenes.after_post(people("A", "B", "C"), 2, "C")[1], 0)

	def test_out_of_turn_posts_move_up(self) :
		# Rico's example: with A B C D and B to post, a post by D makes it A D B C and still B's turn.
		order, turn, passed = Scenes.after_post(people("A", "B", "C", "D"), 1, "D")
		self.assertEqual((ids(order), turn, passed), (["A", "D", "B", "C"], 2, False))
		self.assertEqual(ids(order)[turn], "B")
		# Someone already before the current spot stays where they are.
		order, turn, _ = Scenes.after_post(people("A", "B", "C", "D"), 2, "A")
		self.assertEqual((ids(order), ids(order)[turn]), (["B", "A", "C", "D"], "C"))

	def test_away_members_are_passed_over(self) :
		cast = people("A", "B", "C")
		self.assertEqual(Scenes.next_index(cast, 0, {1}), 2)
		self.assertEqual(Scenes.next_index(cast, 0, {0, 1, 2}), 1)
		self.assertEqual(Scenes.first_present(cast, 1, {1}), 2)
		self.assertEqual(Scenes.after_post(cast, 0, "A", {1})[1], 2)

	def test_nudges_and_skips(self) :
		start = NOW - timedelta(hours=25)
		self.assertTrue(Scenes.nudge_due(start, None, 24, NOW))
		self.assertFalse(Scenes.nudge_due(start, NOW - timedelta(hours=1), 24, NOW))
		self.assertFalse(Scenes.nudge_due(NOW - timedelta(hours=2), None, 24, NOW))
		self.assertTrue(Scenes.skip_due(NOW - timedelta(hours=73), 72, NOW))
		self.assertFalse(Scenes.skip_due(NOW - timedelta(hours=73), 0, NOW))

	def test_free_nudges(self) :
		cast = people("A", "B", "C")
		cast[0].last_post_at = NOW - timedelta(hours=30)
		cast[1].last_post_at = NOW - timedelta(hours=10)
		cast[2].last_post_at = NOW - timedelta(hours=5)
		self.assertEqual(ids(Scenes.free_nudges(cast, 24, NOW)), ["A"])
		cast[0].last_nudged_at = NOW - timedelta(hours=1)
		self.assertEqual(Scenes.free_nudges(cast, 24, NOW), [])

	def test_idle(self) :
		self.assertIsNone(Scenes.idle_state(NOW - timedelta(days=13), None, 14, NOW))
		self.assertEqual(Scenes.idle_state(NOW - timedelta(days=15), None, 14, NOW), "warn")
		warned = NOW - timedelta(days=8)
		self.assertEqual(Scenes.idle_state(NOW - timedelta(days=22), warned, 14, NOW), "end")
		self.assertIsNone(Scenes.idle_state(NOW - timedelta(days=22), NOW - timedelta(days=1), 14, NOW))
		self.assertIsNone(Scenes.idle_state(NOW - timedelta(days=99), None, 0, NOW))


class TestChronicleText(unittest.TestCase) :

	def test_rendering(self) :
		entries = [{"kind" : "post", "name" : "Aria <3", "time" : NOW, "text" : "**Hi** *there*", "character_id" : 1,
		            "avatar" : None},
		           {"kind" : "note", "text" : "🎯 Perception check · 2 of 3 succeeded", "time" : NOW},
		           {"kind" : "post", "name" : "Bram", "time" : NOW, "text" : "one two three", "character_id" : 2,
		            "avatar" : "https://x/y.png"},
		           {"kind" : "post", "name" : "Aria", "time" : NOW, "text" : "four", "character_id" : 1, "avatar" : None}]
		page = Chronicle.render_html("Test & more", "meta", entries)
		self.assertIn("Aria &lt;3", page)
		self.assertIn("<b>Hi</b>", page)
		self.assertIn("<i>there</i>", page)
		self.assertIn("Test &amp; more", page)
		self.assertIn("> 🎯 Perception check", Chronicle.render_markdown("T", "m", entries))
		self.assertEqual(Chronicle.counts(entries), {1 : (2, 3), 2 : (1, 3)})

	def test_card_notes(self) :
		import discord

		card = discord.Embed(title="🎯 Perception check · DC 15")
		card.add_field(name="Result", value="2 of 3 succeeded.")
		self.assertIn("2 of 3", Chronicle.card_note(SimpleNamespace(embeds=[card])))
		scene_card = discord.Embed(title="🎭 The heist")
		self.assertIsNone(Chronicle.card_note(SimpleNamespace(embeds=[scene_card])))
		dice = discord.Embed(title="Pick the lock", description="*Nice*\n# 🎲 17\n")
		dice.set_author(name="Aria · Agility check")
		self.assertIn("rolled 17", Chronicle.card_note(SimpleNamespace(embeds=[dice])))

	def test_scene_range_ignores_a_reposted_card(self) :
		# /scene card moves card_message_id to the new card; the chronicle still starts where the scene did.
		later_card = Chronicle.snowflake(NOW + timedelta(days=2))
		scene = SimpleNamespace(started_at=NOW, ended_at=NOW + timedelta(days=3), card_message_id=later_card)
		first, last = Chronicle.scene_range(scene)
		self.assertEqual(first, Chronicle.snowflake(NOW))
		self.assertLess(first, later_card)
		self.assertEqual(last, Chronicle.snowflake(NOW + timedelta(days=3), high=True))

	def test_links(self) :
		self.assertEqual(Chronicle.ChronicleFlow.parse_link("https://discord.com/channels/1/2/3"), (1, 2, 3))
		self.assertIsNone(Chronicle.ChronicleFlow.parse_link("nope"))


class TestSceneRecords(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		self.refresh = mock.patch.object(SceneFlow, "refresh", new=mock.AsyncMock())
		self.refresh.start()

	def tearDown(self) :
		self.refresh.stop()
		super().tearDown()

	def make_scene(self, mode=Scenes.ORDER, names=("A", "B", "C", "D")) :
		scene = SceneTransactions().create(GUILD_ID, CHANNEL_ID, "Heist", USER_ID, mode=mode, state=Scenes.OPEN,
		                                   turn_started_at=NOW)
		characters = []
		for index, name in enumerate(names) :
			character = self.add_character(name, user_id=USER_ID + index)
			SceneTransactions().add_participant(scene.id, character.id, character.uid, index + 1)
			characters.append(character)
		return scene, characters

	def post(self, character, text="word " * 10) :
		asyncio.run(SceneFlow.on_post(None, SimpleNamespace(id=CHANNEL_ID), character, text))

	def names(self, scene) :
		from database.transactions.CharacterTransactions import CharacterTransactions

		return [CharacterTransactions().get_by_id(participant.character_id).name
		        for participant in SceneTransactions().participants(scene.id)]

	def test_posts_move_the_turn(self) :
		scene, (a, b, c, d) = self.make_scene()
		self.post(a)
		self.assertEqual(SceneTransactions().get(scene.id).turn_index, 1)
		self.post(d)
		self.assertEqual(self.names(scene), ["A", "D", "B", "C"])
		scene = SceneTransactions().get(scene.id)
		self.assertEqual(self.names(scene)[scene.turn_index], "B")
		participant = SceneTransactions().participant(scene.id, d.id)
		self.assertEqual((participant.posts, participant.words), (1, 10))

	def test_outsiders_and_ended_scenes_dont_count(self) :
		scene, (a, *_) = self.make_scene(names=("A", "B"))
		stranger = self.add_character("Stranger", user_id=USER_ID + 50)
		self.post(stranger)
		self.assertEqual(SceneTransactions().get(scene.id).turn_index, 0)
		SceneTransactions().update(scene.id, state=Scenes.ENDED)
		self.post(a)
		self.assertEqual(SceneTransactions().participant(scene.id, a.id).posts, 0)

	def test_free_scenes_have_no_turns(self) :
		scene, (a, b) = self.make_scene(Scenes.FREE, ("A", "B"))
		self.post(b)
		self.assertEqual(SceneTransactions().get(scene.id).turn_index, 0)
		self.assertEqual(SceneTransactions().participant(scene.id, b.id).posts, 1)

	def test_fights_pause_scenes(self) :
		scene, _ = self.make_scene(names=("A",))
		self.assertIsNone(SceneFlow.pause_for_fight([1, None], 5))
		paused = SceneFlow.pause_for_fight([None, CHANNEL_ID], 5)
		self.assertEqual((paused.state, paused.paused_by_fight), (Scenes.PAUSED, 5))
		self.assertEqual(SceneTransactions().open_in(CHANNEL_ID).id, scene.id)

	def test_away(self) :
		self.assertTrue(SceneTransactions().set_away(USER_ID, NOW + timedelta(days=2)))
		cast = [SimpleNamespace(uid=USER_ID), SimpleNamespace(uid=USER_ID + 1)]
		self.assertEqual(SceneFlow.away_uids(cast, NOW), {USER_ID})
		SceneTransactions().set_away(USER_ID, None)
		self.assertEqual(SceneFlow.away_uids(cast, NOW), set())

	def test_skips_pass_the_turn(self) :
		scene, (a, b) = self.make_scene(names=("A", "B"))
		SceneTransactions().update(scene.id, turn_started_at=NOW - timedelta(hours=80))
		with mock.patch.object(SceneFlow, "_say", new=mock.AsyncMock()) as said :
			asyncio.run(SceneFlow._turn_timers(None, SceneTransactions().get(scene.id), NOW))
		self.assertEqual(SceneTransactions().get(scene.id).turn_index, 1)
		self.assertEqual(SceneTransactions().participant(scene.id, a.id).skips, 1)
		said.assert_awaited()

	def test_nudge_once(self) :
		scene, (a, b) = self.make_scene(names=("A", "B"))
		SceneTransactions().update(scene.id, turn_started_at=NOW - timedelta(hours=30))
		with mock.patch.object(SceneFlow, "_nudge", new=mock.AsyncMock()) as nudged :
			asyncio.run(SceneFlow._turn_timers(None, SceneTransactions().get(scene.id), NOW))
			asyncio.run(SceneFlow._turn_timers(None, SceneTransactions().get(scene.id), NOW))
		self.assertEqual(nudged.await_count, 1)

	def test_chronicles_of_a_character(self) :
		character = self.add_character()
		chronicle = SceneTransactions().add_chronicle(GUILD_ID, "Old tale", CHANNEL_ID)
		SceneTransactions().set_chronicle_characters(chronicle.id, {character.id : (3, 120)})
		self.assertEqual([record.title for record in SceneTransactions().chronicles_of(character.id)], ["Old tale"])
