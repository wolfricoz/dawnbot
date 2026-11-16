import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from classes.kernel.ConfigData import ConfigData
from classes.progression.Progression import Progression
from classes.proxy.Compose import Compose, MESSAGE_LIMIT, REPLY_MARK
from classes.proxy.Matcher import Matcher
from classes.proxy.Proxy import IGNORE, PROXY, Proxy, TOO_SHORT
from database.transactions.AutoproxyTransactions import AutoproxyTransactions
from database.transactions.CharacterTransactions import CharacterTransactions, PENDING
from database.transactions.ExperienceTransactions import ExperienceTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

CHANNEL_ID = 555
THREAD_ID = 556


def character(id, prefix=None, suffix=None) :
	return SimpleNamespace(id=id, prefix=prefix, suffix=suffix)


class TestMatch(unittest.TestCase) :

	def test_strip(self) :
		self.assertEqual(Matcher.strip("Aria: hello there", "Aria:", None), "hello there")
		self.assertEqual(Matcher.strip("aria:hello", "Aria:", None), "hello")
		self.assertEqual(Matcher.strip("[hello]", "[", "]"), "hello")
		self.assertEqual(Matcher.strip("hello -a", None, "-a"), "hello")
		self.assertIsNone(Matcher.strip("hello", "Aria:", None))
		self.assertIsNone(Matcher.strip("[hello", "[", "]"))
		self.assertIsNone(Matcher.strip("[]", "[]", "]"))
		self.assertIsNone(Matcher.strip("hello", None, None))

	def test_the_longest_trigger_wins(self) :
		a, ab = character(1, "A:"), character(2, "Ab:")
		self.assertEqual(Matcher.match("Ab: hi", False, [a, ab]).character.id, 2)
		self.assertEqual(Matcher.match("A: hi", False, [a, ab]).character.id, 1)
		bracket = character(3, "[", "]")
		self.assertEqual(Matcher.match("[A: hi]", False, [a, bracket]).character.id, 3)

	def test_a_post_needs_text_or_an_attachment(self) :
		aria = character(1, "Aria:")
		self.assertIsNone(Matcher.match("Aria:", False, [aria]))
		match = Matcher.match("Aria:", True, [aria])
		self.assertEqual((match.character.id, match.text), (1, ""))

	def test_autoproxy_and_escape(self) :
		aria, bryn = character(1, "Aria:"), character(2, "Bryn:")
		match = Matcher.match("  hello  ", False, [aria, bryn], autoproxy=bryn)
		self.assertEqual((match.character.id, match.text, match.autoproxy), (2, "hello", True))
		# A trigger still picks another character.
		self.assertEqual(Matcher.match("Aria: hi", False, [aria, bryn], autoproxy=bryn).character.id, 1)
		self.assertIsNone(Matcher.match("\\hello", False, [aria, bryn], autoproxy=bryn))
		self.assertIsNone(Matcher.match("\\Aria: hi", False, [aria, bryn]))
		self.assertIsNone(Matcher.match("hello", False, [aria, bryn]))

	def test_decide(self) :
		self.assertEqual(Proxy.decide(True, False, True), PROXY)
		self.assertEqual(Proxy.decide(True, True, False), TOO_SHORT)
		self.assertEqual(Proxy.decide(False, False, True), IGNORE)
		# Outside roleplay channels there is no minimum length.
		self.assertEqual(Proxy.decide(False, True, False), PROXY)


class TestCompose(unittest.TestCase) :

	def test_reply_line(self) :
		line = Compose.reply_line("Where are   you going?", "https://link", 42)
		self.assertEqual(line, f"{REPLY_MARK}Replying to <@42>: [Where are you going?](https://link)")
		self.assertIn("Aria (<@42>)", Compose.reply_line("hi", "https://link", 42, "Aria"))
		self.assertIn("**Bot**", Compose.reply_line("hi", "https://link", None, "Bot"))
		self.assertIn("[a message]", Compose.reply_line("", "https://link", 42))

	def test_snippet(self) :
		self.assertEqual(Compose.snippet("x" * 100), "x" * 79 + "…")
		self.assertEqual(Compose.snippet("see [this]"), "see (this)")
		# Quoting a proxied reply leaves out its own reply line.
		self.assertEqual(Compose.snippet(f"{REPLY_MARK}Replying to <@1>: [x](y)\nThe answer"), "The answer")

	def test_strip_reply_line(self) :
		self.assertEqual(Compose.strip_reply_line(f"{REPLY_MARK}Replying\nbody\nmore"),
		                 (f"{REPLY_MARK}Replying", "body\nmore"))
		self.assertEqual(Compose.strip_reply_line("body"), (None, "body"))

	def test_split(self) :
		self.assertEqual(Compose.split("hello"), ["hello"])
		self.assertEqual(Compose.split("hello", "line"), ["line\nhello"])
		self.assertEqual(Compose.split("", "line"), ["line"])
		self.assertEqual(Compose.split(""), [""])
		chunks = Compose.split("word " * 900, "line")
		self.assertEqual(len(chunks), 3)
		self.assertTrue(chunks[0].startswith("line\n"))
		self.assertTrue(all(len(chunk) <= MESSAGE_LIMIT for chunk in chunks))

	def test_allowed_mentions_follow_the_member(self) :
		mentioned = SimpleNamespace(id=7)
		message = SimpleNamespace(
			mentions=[mentioned, mentioned], author=object(),
			role_mentions=[SimpleNamespace(id=1, mentionable=True), SimpleNamespace(id=2, mentionable=False)],
			channel=SimpleNamespace(permissions_for=lambda member : SimpleNamespace(mention_everyone=False)))
		allowed = Compose.allowed_mentions(message, extra_user=9)
		self.assertEqual(sorted(user.id for user in allowed.users), [7, 9])
		self.assertEqual([role.id for role in allowed.roles], [1])
		self.assertFalse(allowed.everyone)
		message.channel = SimpleNamespace(permissions_for=lambda member : SimpleNamespace(mention_everyone=True))
		allowed = Compose.allowed_mentions(message)
		self.assertTrue(allowed.everyone)
		self.assertTrue(allowed.roles)


class TestProxyLog(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.character = self.add_character()

	def log(self, ids, length=400, counted=True, xp=80) :
		ProxyTransactions().log(ids, self.character.id, USER_ID, GUILD_ID, CHANNEL_ID, length, counted, xp, 13)

	def test_a_long_post_is_one_entry(self) :
		self.log([10, 11, 12], length=4500)
		post = ProxyTransactions().get_post(11)
		self.assertEqual([entry.message_id for entry in post], [10, 11, 12])
		self.assertEqual([(entry.length, entry.counted, entry.xp_awarded) for entry in post],
		                 [(4500, True, 80), (0, False, 0), (0, False, 0)])
		self.assertEqual(ProxyTransactions().count(self.character.id), 1)
		self.assertEqual(ProxyTransactions().get_post(99), [])

	def test_counted_lengths_skip_deleted_and_uncounted_posts(self) :
		self.log([10], length=400)
		self.log([20], length=500)
		self.log([30], length=600, counted=False, xp=0)
		self.assertEqual(ProxyTransactions().mark_deleted([20, 999]), 1)
		self.assertEqual(ProxyTransactions().counted_lengths(self.character.id), [400])
		self.assertEqual(ProxyTransactions().counted_lengths_by_user(GUILD_ID), {USER_ID : [400]})

	def test_adjust_length(self) :
		self.log([10, 11], length=400)
		ProxyTransactions().adjust_length(10, -50)
		self.assertEqual(ProxyTransactions().get(10).length, 350)
		ProxyTransactions().adjust_length(10, -1000)
		self.assertEqual(ProxyTransactions().get(10).length, 0)

	def test_the_log_outlives_the_character(self) :
		self.log([10])
		CharacterTransactions().delete(self.character.id)
		self.assertIsNone(ProxyTransactions().get(10).character_id)


class TestAutoproxy(DatabaseTestCase) :

	def test_set_get_clear(self) :
		aria, bryn = self.add_character("Aria"), self.add_character("Bryn")
		autoproxy = AutoproxyTransactions()
		autoproxy.set(USER_ID, GUILD_ID, CHANNEL_ID, aria.id)
		self.assertEqual(autoproxy.get(USER_ID, [THREAD_ID, CHANNEL_ID]), aria.id)
		# A thread's own setting comes before its parent's.
		autoproxy.set(USER_ID, GUILD_ID, THREAD_ID, bryn.id)
		self.assertEqual(autoproxy.get(USER_ID, [THREAD_ID, CHANNEL_ID]), bryn.id)
		autoproxy.set(USER_ID, GUILD_ID, CHANNEL_ID, bryn.id)
		self.assertEqual(autoproxy.get(USER_ID, [CHANNEL_ID]), bryn.id)
		self.assertIsNone(autoproxy.get(USER_ID + 1, [CHANNEL_ID]))
		self.assertTrue(autoproxy.clear(USER_ID, THREAD_ID))
		self.assertFalse(autoproxy.clear(USER_ID, THREAD_ID))
		CharacterTransactions().delete(bryn.id)
		self.assertIsNone(autoproxy.get(USER_ID, [THREAD_ID, CHANNEL_ID]))


# ============================================================
# Fakes: just enough of a Discord message for posting as a character
# ============================================================

class FakeChannel :
	def __init__(self, can_manage=True) :
		self.id = CHANNEL_ID
		self.guild = SimpleNamespace(id=GUILD_ID)
		self.type = discord.ChannelType.text
		self.can_manage = can_manage
		self.sent = []

	def permissions_for(self, member) :
		return SimpleNamespace(manage_webhooks=self.can_manage, manage_messages=True, mention_everyone=False)

	async def send(self, *args, **kwargs) :
		self.sent.append(args)


class FakeWebhook :
	def __init__(self) :
		self.sent = []

	async def send(self, **kwargs) :
		self.sent.append(kwargs)
		return SimpleNamespace(id=1000 + len(self.sent))


def fake_message(content, channel, manage_messages=False) :
	author = SimpleNamespace(id=USER_ID, bot=False, send=AsyncMock(), mention=f"<@{USER_ID}>",
	                         guild_permissions=SimpleNamespace(manage_messages=manage_messages))
	guild = SimpleNamespace(id=GUILD_ID, name="Test server", me=object(), filesize_limit=10 * 1024 * 1024)
	return SimpleNamespace(id=1, content=content, author=author, guild=guild, channel=channel, webhook_id=None,
	                       type=discord.MessageType.default, stickers=[], attachments=[], mentions=[],
	                       role_mentions=[], reference=None, delete=AsyncMock())


class TestPosting(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		self.character = self.add_character("Aria", prefix="Aria:")
		self.webhook = FakeWebhook()
		patcher = patch("classes.proxy.Proxy.WebhookManager.get", new=AsyncMock(return_value=self.webhook))
		patcher.start()
		self.addCleanup(patcher.stop)
		self.bot = SimpleNamespace(get_guild=lambda guild_id : None)

	def roleplay_channel(self) :
		ConfigData().add_to_list(GUILD_ID, ConfigMapping.XP_CHANNELS, CHANNEL_ID)

	def post(self, message) :
		return asyncio.run(Proxy.handle(self.bot, message))

	def test_a_post_in_a_roleplay_channel(self) :
		self.roleplay_channel()
		text = "x" * 400
		message = fake_message(f"Aria: {text}", FakeChannel())
		self.assertTrue(self.post(message))
		self.assertEqual(len(self.webhook.sent), 1)
		sent = self.webhook.sent[0]
		self.assertEqual((sent["content"], sent["username"]), (text, "Aria"))
		message.delete.assert_awaited_once()
		entry = ProxyTransactions().get(1001)
		# XP: 400 / 5 = 80; currency: 400 / 8 = 50.
		self.assertEqual((entry.length, entry.counted, entry.xp_awarded, entry.currency_awarded), (400, True, 80, 50))
		character = CharacterTransactions().get_by_id(self.character.id)
		self.assertEqual((character.xp, character.currency), (80, 50))
		self.assertEqual(ExperienceTransactions().get(USER_ID, GUILD_ID).xp, 80)

	def test_a_long_post_is_split(self) :
		self.roleplay_channel()
		self.post(fake_message("Aria: " + "word " * 900, FakeChannel()))
		self.assertEqual(len(self.webhook.sent), 3)
		self.assertEqual([entry.message_id for entry in ProxyTransactions().get_post(1003)], [1001, 1002, 1003])

	def test_a_short_post_is_removed(self) :
		self.roleplay_channel()
		message = fake_message("Aria: *nods*", FakeChannel())
		self.assertTrue(self.post(message))
		self.assertEqual(self.webhook.sent, [])
		message.delete.assert_awaited_once()
		message.author.send.assert_awaited_once()
		self.assertEqual(CharacterTransactions().get_by_id(self.character.id).xp, 0)

	def test_staff_may_post_short(self) :
		self.roleplay_channel()
		self.post(fake_message("Aria: *nods*", FakeChannel(), manage_messages=True))
		self.assertEqual(len(self.webhook.sent), 1)

	def test_outside_roleplay_channels(self) :
		message = fake_message("Aria: hi", FakeChannel())
		self.assertFalse(self.post(message))
		self.assertEqual(self.webhook.sent, [])
		message.delete.assert_not_awaited()

		ConfigData().add_key(GUILD_ID, ConfigMapping.PROXY_OUTSIDE_RP, "TRUE", overwrite=True)
		self.assertTrue(self.post(fake_message("Aria: hi", FakeChannel())))
		entry = ProxyTransactions().get(1001)
		self.assertEqual((entry.counted, entry.xp_awarded), (False, 0))
		self.assertEqual(CharacterTransactions().get_by_id(self.character.id).xp, 0)

	def test_missing_permissions_leave_the_message(self) :
		self.roleplay_channel()
		message = fake_message("Aria: " + "x" * 400, FakeChannel(can_manage=False))
		with patch("classes.proxy.Proxy.PermissionNotice.notify", new=AsyncMock()) as notify :
			self.assertFalse(self.post(message))
		self.assertEqual(notify.await_args.args[1], ["manage_webhooks"])
		self.assertEqual(self.webhook.sent, [])
		message.delete.assert_not_awaited()

	def test_only_approved_characters_post(self) :
		self.roleplay_channel()
		CharacterTransactions().update(self.character.id, state=PENDING)
		self.assertFalse(self.post(fake_message("Aria: " + "x" * 400, FakeChannel())))

	def test_autoproxy(self) :
		self.roleplay_channel()
		AutoproxyTransactions().set(USER_ID, GUILD_ID, CHANNEL_ID, self.character.id)
		self.post(fake_message("y" * 400, FakeChannel()))
		self.assertEqual(self.webhook.sent[0]["content"], "y" * 400)
		self.assertFalse(self.post(fake_message("\\" + "y" * 400, FakeChannel())))

	def test_level_ups_from_posting(self) :
		self.roleplay_channel()
		ConfigData().add_key(GUILD_ID, ConfigMapping.LEVEL_BASE, 100, overwrite=True)
		self.post(fake_message("Aria: " + "x" * 1500, FakeChannel()))
		character = CharacterTransactions().get_by_id(self.character.id)
		# 300 XP reaches level 3 at base 100.
		self.assertEqual((character.xp, character.level, character.unspent_points), (300, 3, 2))


class TestRecount(DatabaseTestCase) :

	def test_recount_includes_posts_made_as_characters(self) :
		self.add_server()
		character = self.add_character()
		ProxyTransactions().log([10], character.id, USER_ID, GUILD_ID, CHANNEL_ID, 400, True, 80, 13)
		ProxyTransactions().log([20], character.id, USER_ID, GUILD_ID, CHANNEL_ID, 500, False, 0, 0)
		ExperienceTransactions().add_xp(USER_ID, GUILD_ID, 999)
		guild = SimpleNamespace(id=GUILD_ID, name="Test server", members=[SimpleNamespace(id=USER_ID, bot=False)],
		                        get_channel_or_thread=lambda channel_id : None)
		self.assertEqual(asyncio.run(Progression.recount(guild)), 1)
		self.assertEqual(ExperienceTransactions().get(USER_ID, GUILD_ID).xp, 80)
