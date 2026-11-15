import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import discord

from classes.kernel.ConfigData import ConfigData
from classes.kernel.ServerSync import sync_server
from classes.setup.BotSetup import BotSetup, CATEGORY_NAMES, CHANNEL_STEPS, INFO, ROLEPLAY_CHANNEL, STAFF, \
	TOGGLE_OFF, TOGGLE_ON
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID


# ============================================================
# Fakes: just enough of a guild for BotSetup. The channels subclass discord's own, so isinstance checks hold.
# ============================================================

class FakeRole :
	def __init__(self, name, permissions=None, default=False, managed=False) :
		self.name = name
		self.permissions = permissions or discord.Permissions.none()
		self.default, self.managed = default, managed

	def is_default(self) :
		return self.default


class FakeMember :
	def __init__(self, permissions) :
		self.guild_permissions = permissions


def init_channel(channel, guild, name, category=None, topic=None, overwrites=None) :
	channel.guild = guild
	channel.name = name
	channel.id = guild.next_id()
	channel.category_id = category.id if category else None
	channel.fake_category = category
	channel.fake_topic = topic
	channel.fake_overwrites = overwrites or {}
	channel.allowed = discord.Permissions.all()


class FakeText(discord.TextChannel) :
	def __init__(self, guild, name, category=None, topic=None, overwrites=None) :
		init_channel(self, guild, name, category, topic, overwrites)

	def permissions_for(self, member) :
		return self.allowed


class FakeForum(discord.ForumChannel) :
	def __init__(self, guild, name, category=None, topic=None, overwrites=None) :
		init_channel(self, guild, name, category, topic, overwrites)

	def permissions_for(self, member) :
		return self.allowed


class FakeCategory(discord.CategoryChannel) :
	def __init__(self, guild, name, overwrites=None) :
		init_channel(self, guild, name, overwrites=overwrites)


class FakeGuild :
	def __init__(self, forums: bool = True, permissions: discord.Permissions | None = None) :
		self.id = GUILD_ID
		self.name = "Test server"
		self.owner = SimpleNamespace(name="owner")
		self.owner_id = USER_ID
		self.member_count = 5
		self.default_role = FakeRole("@everyone", default=True)
		self.me = FakeMember(permissions or discord.Permissions.all())
		self.roles = [self.default_role]
		self.categories = []
		self.loose = []
		self.forums = forums
		# Whether the new-channel prompt was quiet at each creation.
		self.quiet = []
		self._next = 1000 << 22

	def next_id(self) :
		self._next += 1 << 22
		return self._next

	@property
	def channels(self) :
		return self.categories + self.loose

	@property
	def text_channels(self) :
		return [channel for channel in self.loose if isinstance(channel, discord.TextChannel)]

	def get_channel(self, channel_id) :
		return next((channel for channel in self.channels if channel.id == channel_id), None)

	def add(self, cls, name, category=None, **kwargs) :
		channel = cls(self, name, category, **kwargs)
		self.loose.append(channel)
		return channel

	async def create_category(self, name, overwrites=None, reason=None) :
		category = FakeCategory(self, name, overwrites)
		self.categories.append(category)
		return category

	async def create_forum(self, name, category=None, topic=None, overwrites=None, reason=None) :
		if not self.forums :
			raise discord.HTTPException(SimpleNamespace(status=400, reason="Bad Request"), "no forums here")
		self.quiet.append(BotSetup.is_creating(self.id))
		return self.add(FakeForum, name, category, topic=topic, overwrites=overwrites)

	async def create_text_channel(self, name, category=None, topic=None, overwrites=None, reason=None) :
		self.quiet.append(BotSetup.is_creating(self.id))
		return self.add(FakeText, name, category, topic=topic, overwrites=overwrites)


def run(coroutine) :
	return asyncio.run(coroutine)


class SetupTestCase(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		BotSetup._creating = {}
		self.guild = FakeGuild()

	def tearDown(self) :
		BotSetup._creating = {}
		super().tearDown()

	def channel_for(self, key) :
		return self.guild.get_channel(ConfigData().get_int(GUILD_ID, key))


# ============================================================
# Auto setup
# ============================================================

class TestAutoSetup(SetupTestCase) :

	def test_creates_every_channel(self) :
		report = run(BotSetup.auto(self.guild))
		for step in CHANNEL_STEPS :
			channel = self.channel_for(step.key)
			self.assertIsNotNone(channel, step.key)
			self.assertEqual(channel.name, step.name)
			self.assertEqual(channel.fake_category.name, CATEGORY_NAMES[step.section])
			self.assertIsInstance(channel, discord.ForumChannel if step.forum else discord.TextChannel)
		roleplay = BotSetup.roleplay_channels(self.guild)
		self.assertEqual([channel.name for channel in roleplay], [ROLEPLAY_CHANNEL])
		self.assertEqual(sorted(report.created), sorted([step.key for step in CHANNEL_STEPS] +
		                                                [ConfigMapping.XP_CHANNELS]))
		self.assertEqual(sorted(category.name for category in self.guild.categories), sorted(CATEGORY_NAMES.values()))
		# The "should this be a roleplay channel?" prompt stays quiet for every channel setup makes.
		self.assertTrue(all(self.guild.quiet))

	def test_category_permissions(self) :
		staff_role = FakeRole("Mods", discord.Permissions(manage_messages=True))
		self.guild.roles.append(staff_role)
		run(BotSetup.auto(self.guild))
		review = self.channel_for(ConfigMapping.CHARACTER_REVIEW)
		self.assertFalse(review.fake_overwrites[self.guild.default_role].view_channel)
		self.assertTrue(review.fake_overwrites[staff_role].view_channel)
		characters = self.channel_for(ConfigMapping.CHARACTER)
		self.assertFalse(characters.fake_overwrites[self.guild.default_role].send_messages)
		# The bot never locks itself out of what it made.
		for channel in (review, characters) :
			self.assertTrue(channel.fake_overwrites[self.guild.me].send_messages)
			self.assertTrue(channel.fake_overwrites[self.guild.me].view_channel)

	def test_running_twice_creates_nothing_new(self) :
		run(BotSetup.auto(self.guild))
		count = len(self.guild.channels)
		report = run(BotSetup.auto(self.guild))
		self.assertEqual(report.created, [])
		self.assertEqual(len(self.guild.channels), count)

	def test_keeps_configured_and_reuses_default_names(self) :
		sync_server(self.guild)
		own_forum = self.guild.add(FakeForum, "our-characters")
		ConfigData().add_key(GUILD_ID, ConfigMapping.CHARACTER, own_forum.id, overwrite=True)
		bot_log = self.guild.add(FakeText, "bot-log")
		tavern = self.guild.add(FakeText, ROLEPLAY_CHANNEL)
		report = run(BotSetup.auto(self.guild))
		self.assertEqual(self.channel_for(ConfigMapping.CHARACTER), own_forum)
		self.assertEqual(self.channel_for(ConfigMapping.MODLOG), bot_log)
		self.assertEqual(BotSetup.roleplay_channels(self.guild), [tavern])
		self.assertIn(ConfigMapping.CHARACTER, report.kept)
		self.assertIn(ConfigMapping.MODLOG, report.kept)
		self.assertNotIn(ConfigMapping.XP_CHANNELS, report.created)
		self.assertEqual(len([channel for channel in self.guild.loose if channel.name == "bot-log"]), 1)

	def test_forums_fall_back_to_text_channels(self) :
		self.guild = FakeGuild(forums=False)
		run(BotSetup.auto(self.guild))
		self.assertIsInstance(self.channel_for(ConfigMapping.CHARACTER), discord.TextChannel)
		self.assertIsInstance(self.channel_for(ConfigMapping.GEAR_FORUM), discord.TextChannel)

	def test_bot_overwrite_only_grants_what_the_bot_has(self) :
		permissions = discord.Permissions.all()
		permissions.manage_webhooks = False
		self.guild = FakeGuild(permissions=permissions)
		overwrite = BotSetup.bot_overwrite(self.guild)
		self.assertIsNone(overwrite.manage_webhooks)
		self.assertTrue(overwrite.send_messages)

	def test_plan_description(self) :
		sync_server(self.guild)
		self.guild.add(FakeText, "level-ups")
		text = BotSetup.describe_plan(self.guild)
		self.assertIn("#character-review", text)
		self.assertIn(f"#{ROLEPLAY_CHANNEL}", text)
		self.assertIn("Level-ups:", text)
		self.assertNotIn("#level-ups,", text)

	def test_missing_permissions(self) :
		self.guild = FakeGuild(permissions=discord.Permissions(view_channel=True))
		self.assertEqual(BotSetup.missing_auto_permissions(self.guild), ["manage_channels", "manage_roles"])


class TestQuietWindow(SetupTestCase) :

	def test_prompt_comes_back_after_the_window(self) :
		async def scenario() :
			with patch("classes.setup.BotSetup.QUIET_SECONDS", 0) :
				async with BotSetup.creating(GUILD_ID) :
					self.assertTrue(BotSetup.is_creating(GUILD_ID))
				await asyncio.sleep(0.01)
			return BotSetup.is_creating(GUILD_ID)

		self.assertFalse(run(scenario()))


# ============================================================
# Settings, checks and the summary
# ============================================================

class TestSettingsAndChecks(SetupTestCase) :

	def setUp(self) :
		super().setUp()
		sync_server(self.guild)

	def test_text_only_settings_refuse_forums(self) :
		forum = self.guild.add(FakeForum, "reviews")
		ConfigData().add_key(GUILD_ID, ConfigMapping.CHARACTER_REVIEW, forum.id, overwrite=True)
		review = next(step for step in CHANNEL_STEPS if step.key == ConfigMapping.CHARACTER_REVIEW)
		self.assertIsNone(BotSetup.current(self.guild, review))

	def test_settings(self) :
		self.assertEqual(BotSetup.current_setting(GUILD_ID, ConfigMapping.PROXY_OUTSIDE_RP), TOGGLE_OFF)
		BotSetup.set_setting(GUILD_ID, ConfigMapping.PROXY_OUTSIDE_RP, TOGGLE_ON)
		self.assertEqual(BotSetup.current_setting(GUILD_ID, ConfigMapping.PROXY_OUTSIDE_RP), TOGGLE_ON)
		self.assertEqual(BotSetup.current_setting(GUILD_ID, ConfigMapping.ECONOMY), "economy")
		BotSetup.set_setting(GUILD_ID, ConfigMapping.ECONOMY, "free")
		self.assertEqual(ConfigData().get_key(GUILD_ID, ConfigMapping.ECONOMY), "free")
		with self.assertRaises(ValueError) :
			BotSetup.set_setting(GUILD_ID, ConfigMapping.ECONOMY, "barter")

	def test_problems_before_and_after(self) :
		problems = BotSetup.problems(self.guild)
		self.assertTrue(any("character review" in problem for problem in problems))
		self.assertTrue(any("no roleplay channels" in problem for problem in problems))
		run(BotSetup.auto(self.guild))
		self.assertEqual(BotSetup.problems(self.guild), [])
		roleplay = BotSetup.roleplay_channels(self.guild)[0]
		roleplay.allowed = discord.Permissions.all()
		roleplay.allowed.manage_webhooks = False
		self.assertTrue(any(roleplay.mention in problem and "Manage Webhooks" in problem
		                    for problem in BotSetup.problems(self.guild)))

	def test_summary(self) :
		report = run(BotSetup.auto(self.guild))
		embed = BotSetup.summary(self.guild, report)
		self.assertEqual(embed.title, "Setup finished")
		self.assertIn("*(new)*", embed.description)
		self.assertEqual([field.name for field in embed.fields], ["Next"])
		self.assertIn("/armory import", embed.fields[0].value)


# ============================================================
# Guided setup, with the answers scripted
# ============================================================

class ScriptedSetup :
	"""Builds a GuidedSetup whose steps are answered from a list instead of by buttons."""

	@staticmethod
	def make(guild, answers) :
		from classes.setup.GuidedSetup import GuidedSetup, SetupEnded
		from views.buttons.SetupSteps import CANCEL

		class Scripted(GuidedSetup) :
			def __init__(self) :
				interaction = SimpleNamespace(guild=guild, user=SimpleNamespace(id=USER_ID, name="tester"))
				super().__init__(SimpleNamespace(), interaction)
				self.answers = list(answers)
				self.prompts = []
				# The result of the previous answer, which the real ask shows above each step.
				self.notes = []
				self.ended = None

			async def ask(self, content, view) :
				self.prompts.append(content)
				self.notes.append(self.note)
				self.note = None
				answer, extra = self.answers.pop(0)
				if answer == CANCEL :
					await self.end("cancelled")
					raise SetupEnded()
				view.answer = answer
				if isinstance(extra, list) :
					view.picked = extra
				elif isinstance(extra, dict) :
					view.chosen.update(extra)
				return view

			async def end(self, content, embed=None) :
				self.ended = (content, embed)

		return Scripted()


class TestGuidedSetup(SetupTestCase) :

	def setUp(self) :
		super().setUp()
		from views.buttons import SetupSteps
		self.steps = SetupSteps

	def answers_for_channels(self, answer) :
		return [(answer, None)] * len(CHANNEL_STEPS)

	@patch("classes.setup.GuidedSetup.Queue")
	def test_create_everything_and_save_settings(self, queue) :
		steps = self.steps
		answers = self.answers_for_channels(steps.CREATE) + [(steps.CREATE, None)] + [
			(steps.SAVE, {ConfigMapping.STAT_METHOD : "rolled"}),
			(steps.SKIP, {ConfigMapping.ECONOMY : "free"}),
			(steps.SKIP, None),
		]
		setup = ScriptedSetup.make(self.guild, answers)
		run(setup.run())
		for step in CHANNEL_STEPS :
			self.assertIsNotNone(self.channel_for(step.key), step.key)
		self.assertEqual(len(BotSetup.roleplay_channels(self.guild)), 1)
		self.assertEqual(ConfigData().get_key(GUILD_ID, ConfigMapping.STAT_METHOD), "rolled")
		# Skipped pages save nothing, even when a menu was changed.
		self.assertEqual(ConfigData().get_key(GUILD_ID, ConfigMapping.ECONOMY), "economy")
		self.assertIsNotNone(setup.ended[1])
		self.assertIn("Step 1 of", setup.prompts[0])
		self.assertTrue(setup.notes[1].startswith("✅ Created"))

	@patch("classes.setup.GuidedSetup.Queue")
	@patch("classes.setup.GuidedSetup.Progression")
	def test_picking_channels(self, progression, queue) :
		steps = self.steps
		review = self.guild.add(FakeText, "staff-review")
		forum = self.guild.add(FakeForum, "a-forum")
		tavern = self.guild.add(FakeText, "tavern")
		answers = [(steps.PICK, [SimpleNamespace(id=review.id)]), (steps.PICK, [SimpleNamespace(id=forum.id)])] + \
		          [(steps.SKIP, None)] * (len(CHANNEL_STEPS) - 2) + \
		          [(steps.PICK, [SimpleNamespace(id=tavern.id), SimpleNamespace(id=forum.id)])] + \
		          [(steps.SKIP, None)] * 3
		setup = ScriptedSetup.make(self.guild, answers)
		run(setup.run())
		self.assertEqual(self.channel_for(ConfigMapping.CHARACTER_REVIEW), review)
		# The bot log only takes text channels.
		self.assertIsNone(self.channel_for(ConfigMapping.MODLOG))
		self.assertTrue(setup.notes[2].startswith("⚠️"))
		self.assertEqual(BotSetup.roleplay_channels(self.guild), [tavern, forum])
		self.assertEqual(queue.return_value.add.call_count, 2)

	def test_cancel_keeps_what_was_set(self) :
		steps = self.steps
		answers = [(steps.CREATE, None), (steps.CANCEL, None)]
		setup = ScriptedSetup.make(self.guild, answers)
		run(setup.run())
		self.assertIsNotNone(self.channel_for(ConfigMapping.CHARACTER_REVIEW))
		self.assertEqual(setup.ended, ("cancelled", None))

	def test_pack_import(self) :
		steps = self.steps
		answers = self.answers_for_channels(steps.SKIP) + [(steps.SKIP, None)] * 3 + [(f"{steps.PACK}fantasy", None)]
		setup = ScriptedSetup.make(self.guild, answers)
		run(setup.run())
		self.assertGreater(len(GearItemTransactions().get_all(GUILD_ID)), 0)
		self.assertIn("Imported", setup.ended[0])
