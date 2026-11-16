import asyncio
import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from classes.kernel.ConfigData import ConfigData
from classes.kernel.Queue import Queue
from classes.scenes import AutoSummary, Scenes
from classes.scenes.SceneFlow import SceneFlow
from database.transactions.SceneTransactions import SceneTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
CHANNEL_ID = 700
OLLAMA = {"OLLAMA_URL" : "http://127.0.0.1:11434"}


def post(name, text) :
	return {"kind" : "post", "name" : name, "text" : text, "time" : NOW, "character_id" : 1, "avatar" : None}


def empty_queue() :
	"""Closes the coroutines a test left in the Queue, so they don't warn about never being awaited."""
	while (task := Queue().process()) is not None :
		task.close()


class TestTranscript(unittest.TestCase) :

	def test_posts_become_lines_without_ooc(self) :
		entries = [post("Ayla", "She pushed the door open.\n((brb dinner))\n\n// lag\nOOC: sorry"),
		           {"kind" : "note", "text" : "🎯 Perception check · passed", "time" : NOW},
		           post("Bren", "\"Wait,\" he said.")]
		self.assertEqual(AutoSummary.transcript(entries),
		                 "Ayla: She pushed the door open.\n[🎯 Perception check · passed]\nBren: \"Wait,\" he said.")

	def test_parts_keep_lines_whole(self) :
		text = "\n".join(f"line {number:03}" for number in range(100))
		pieces = AutoSummary.parts(text, size=100)
		self.assertTrue(all(len(piece) <= 100 for piece in pieces))
		self.assertEqual("\n".join(pieces), text)
		self.assertEqual(AutoSummary.parts("x" * 250, size=100), ["x" * 100, "x" * 100, "x" * 50])

	def test_context_window(self) :
		self.assertEqual(AutoSummary.context_for(1000), 4096)
		self.assertEqual(AutoSummary.context_for(AutoSummary.PART_CHARS), 16384)
		self.assertEqual(AutoSummary.context_for(10_000_000), 32768)

	def test_short_scenes_take_one_request(self) :
		with mock.patch.object(AutoSummary, "ask", new=mock.AsyncMock(return_value="They met.")) as ask :
			self.assertEqual(asyncio.run(AutoSummary.summarise([post("Ayla", "Hi")], "Heist")), "They met.")
		ask.assert_awaited_once()
		self.assertIn("Heist", ask.await_args.args[1])

	def test_long_scenes_are_summarised_in_parts(self) :
		entries = [post("Ayla", "word " * 1000) for _ in range(100)]
		with mock.patch.object(AutoSummary, "ask", new=mock.AsyncMock(return_value="x" * 3000)) as ask :
			summary = asyncio.run(AutoSummary.summarise(entries, "Heist", so_far=True))
		pieces = len(AutoSummary.parts(AutoSummary.transcript(entries)))
		self.assertGreater(pieces, 1)
		self.assertEqual(ask.await_count, pieces + 1)
		self.assertIn("so far", ask.await_args.args[1])
		self.assertEqual(len(summary), AutoSummary.MAX_SUMMARY)

	def test_nothing_to_summarise(self) :
		with mock.patch.object(AutoSummary, "ask", new=mock.AsyncMock()) as ask :
			self.assertIsNone(asyncio.run(AutoSummary.summarise([post("Ayla", "((ooc only))")], "Heist")))
		ask.assert_not_awaited()

	def test_unreachable_model(self) :
		# Nothing listens on port 9, so the request fails at once.
		with mock.patch.dict(os.environ, {"OLLAMA_URL" : "http://127.0.0.1:9"}) :
			self.assertIsNone(asyncio.run(AutoSummary.ask("text", "Summarise.")))


class TestDraftedSummaries(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		AutoSummary._ending.clear()
		AutoSummary._waiting.clear()
		self.scene = SceneTransactions().create(GUILD_ID, CHANNEL_ID, "Heist", USER_ID, mode=Scenes.ORDER,
		                                        state=Scenes.ENDED, turn_started_at=NOW)
		self.chronicle = SceneTransactions().add_chronicle(GUILD_ID, "Heist", CHANNEL_ID, scene_id=self.scene.id)

	def tearDown(self) :
		empty_queue()
		super().tearDown()

	def test_switched_on_by_env_and_setting(self) :
		with mock.patch.dict(os.environ, {"OLLAMA_URL" : ""}) :
			self.assertFalse(AutoSummary.available(GUILD_ID))
		with mock.patch.dict(os.environ, OLLAMA) :
			self.assertTrue(AutoSummary.available(GUILD_ID))
			ConfigData().add_key(GUILD_ID, ConfigMapping.SCENE_AI_SUMMARY, "DISABLED", overwrite=True)
			self.assertFalse(AutoSummary.available(GUILD_ID))

	def test_saved_on_scene_and_chronicle(self) :
		self.assertTrue(AutoSummary.save(self.scene.id, self.chronicle.id, "They stole the crown."))
		self.assertEqual(SceneTransactions().get(self.scene.id).summary, "They stole the crown.")
		self.assertEqual(SceneTransactions().chronicle(self.chronicle.id).summary, "They stole the crown.")

	def test_written_summaries_win(self) :
		SceneTransactions().update_chronicle(self.chronicle.id, summary="Written by Ayla.")
		self.assertFalse(AutoSummary.save(self.scene.id, self.chronicle.id, "Draft"))
		self.assertIsNone(SceneTransactions().get(self.scene.id).summary)
		SceneTransactions().update(self.scene.id, summary="From /scene end.")
		self.assertFalse(AutoSummary.save(self.scene.id, None, "Draft"))

	def test_one_job_per_ending_scene(self) :
		self.assertTrue(AutoSummary.queue_scene_end(None, self.scene.id, self.chronicle.id))
		self.assertFalse(AutoSummary.queue_scene_end(None, self.scene.id, self.chronicle.id))
		self.assertEqual(len(Queue().normal_priority_queue), 1)

	def run_ending(self, drafted) :
		timeline = SimpleNamespace(id=1, content=f"# Heist\n{AutoSummary.TIMELINE_LINE}{AutoSummary.DRAFTING}",
		                           edit=mock.AsyncMock())
		AutoSummary._ending.add(self.scene.id)
		with mock.patch.object(AutoSummary, "scene_entries", new=mock.AsyncMock(return_value=[])), \
				mock.patch.object(AutoSummary, "summarise", new=mock.AsyncMock(return_value=drafted)), \
				mock.patch.object(AutoSummary, "_post_draft", new=mock.AsyncMock()) as posted, \
				mock.patch.object(AutoSummary, "_add_to_card", new=mock.AsyncMock()) as carded :
			asyncio.run(AutoSummary.scene_ended(None, self.scene.id, self.chronicle.id, timeline))
		self.assertNotIn(self.scene.id, AutoSummary._ending)
		return timeline.edit.await_args.kwargs["content"], posted, carded

	def test_ending_fills_everything_in(self) :
		content, posted, carded = self.run_ending("They stole the crown.")
		self.assertIn(f"{AutoSummary.TIMELINE_LINE}They stole the crown.", content)
		posted.assert_awaited_once()
		carded.assert_awaited_once()
		self.assertEqual(SceneTransactions().get(self.scene.id).summary, "They stole the crown.")

	def test_no_answer_falls_back_to_post_below(self) :
		content, posted, carded = self.run_ending(None)
		self.assertIn(f"{AutoSummary.TIMELINE_LINE}{AutoSummary.NO_SUMMARY}", content)
		posted.assert_not_awaited()
		self.assertIsNone(SceneTransactions().get(self.scene.id).summary)

	def test_timeline_says_it_is_drafting(self) :
		channel = SimpleNamespace(send=mock.AsyncMock(return_value="sent"))
		guild = SimpleNamespace(id=GUILD_ID)
		with mock.patch.object(ConfigData, "get_channel", new=mock.AsyncMock(return_value=channel)) :
			sent = asyncio.run(SceneFlow._timeline(None, guild, self.scene, USER_ID, None, drafting=True))
			asyncio.run(SceneFlow._timeline(None, guild, self.scene, USER_ID, None))
		self.assertEqual(sent, "sent")
		first, second = (call.args[0] for call in channel.send.await_args_list)
		self.assertIn(AutoSummary.DRAFTING, first)
		self.assertIn(AutoSummary.NO_SUMMARY, second)

	def test_requests_share_one_job(self) :
		SceneTransactions().update(self.scene.id, state=Scenes.OPEN)
		first, second = (SimpleNamespace(guild_id=GUILD_ID, client=None, user=SimpleNamespace(id=uid))
		                 for uid in (USER_ID, USER_ID + 1))
		with mock.patch.dict(os.environ, OLLAMA), \
				mock.patch("views.combat.Pickers.reply", new=mock.AsyncMock()) as replied :
			asyncio.run(AutoSummary.request(first, self.scene))
			asyncio.run(AutoSummary.request(second, self.scene))
		self.assertEqual(replied.await_count, 2)
		self.assertEqual(len(Queue().high_priority_queue), 1)
		empty_queue()
		with mock.patch.object(AutoSummary, "scene_entries", new=mock.AsyncMock(return_value=[])), \
				mock.patch.object(AutoSummary, "summarise", new=mock.AsyncMock(return_value="So far, so good.")) as made, \
				mock.patch.object(AutoSummary, "_answer", new=mock.AsyncMock()) as answered :
			asyncio.run(AutoSummary.story_so_far(None, self.scene.id))
		self.assertTrue(made.await_args.kwargs["so_far"])
		self.assertEqual(answered.await_count, 2)
		self.assertIn("So far, so good.", answered.await_args.args[1])
		self.assertEqual(AutoSummary._waiting, {})

	def test_requests_need_the_model(self) :
		interaction = SimpleNamespace(guild_id=GUILD_ID, client=None)
		with mock.patch.dict(os.environ, {"OLLAMA_URL" : ""}), \
				mock.patch("views.combat.Pickers.reply", new=mock.AsyncMock()) as replied :
			asyncio.run(AutoSummary.request(interaction, self.scene))
		self.assertIn("aren't set up", replied.await_args.args[1])
		self.assertTrue(Queue().empty())
