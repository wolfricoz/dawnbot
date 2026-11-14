import asyncio
import unittest
from types import SimpleNamespace

import discord

from classes.setup.Safeguards import MAX_MEMBERS, human_member_count, template_error
from classes.setup.ServerSetup import SEPARATOR, ServerSetup
from database.transactions.ArchiveTransactions import ArchiveTransactions
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.TemplateTransactions import TemplateTransactions
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID


# ============================================================
# Fakes: just enough of discord.py's guild/category/channel for ServerSetup
# ============================================================

class FakeCategory :
	def __init__(self, guild, name, position=0) :
		self.guild, self.name, self.position, self.channels = guild, name, position, []
		self.id = id(self)

	async def delete(self, reason=None) :
		self.guild.categories.remove(self)


class FakeChannel :
	def __init__(self, guild, name, category=None, everyone_view=None) :
		self.guild, self.name, self.category = guild, name, None
		self.id = id(self)
		self.type = discord.ChannelType.text
		self.position = 0
		self.everyone_view = everyone_view
		self.move(category)

	def move(self, category) :
		if self.category is not None :
			self.category.channels.remove(self)
		self.category = category
		if category is not None :
			category.channels.append(self)

	def overwrites_for(self, role) :
		return SimpleNamespace(view_channel=self.everyone_view)

	async def edit(self, category=None, name=None, reason=None) :
		self.move(category)
		self.name = name

	async def set_permissions(self, role, view_channel=None, reason=None) :
		self.everyone_view = view_channel

	async def delete(self, reason=None) :
		self.move(None)


class FakeGuild :
	def __init__(self) :
		self.id = GUILD_ID
		self.name = "Test server"
		self.categories = []
		self.default_role = object()

	async def create_category(self, name, reason=None) :
		category = FakeCategory(self, name, len(self.categories))
		self.categories.append(category)
		return category


def run(coroutine) :
	return asyncio.run(coroutine)


# ============================================================
# Tests
# ============================================================

class TestArchiveNames(unittest.TestCase) :

	def test_category_goes_first(self) :
		self.assertEqual(ServerSetup.archived_name("Rp Channels", "tavern"), f"rp-channels{SEPARATOR}tavern")
		self.assertEqual(ServerSetup.parse_archived_name(f"rp-channels{SEPARATOR}tavern"), ("rp-channels", "tavern"))

	def test_names_without_prefix(self) :
		self.assertEqual(ServerSetup.archived_name(None, "general"), "general")
		self.assertEqual(ServerSetup.parse_archived_name("general"), (None, "general"))

	def test_long_names_fit_discord(self) :
		self.assertLessEqual(len(ServerSetup.archived_name("c" * 100, "x" * 100)), 100)


class TestSafeguards(unittest.TestCase) :

	@staticmethod
	def interaction(user_id, owner_id, humans, bots=1, member_count=None) :
		members = [SimpleNamespace(bot=False)] * humans + [SimpleNamespace(bot=True)] * bots
		guild = SimpleNamespace(owner_id=owner_id, members=members,
		                        member_count=member_count if member_count is not None else len(members))
		return SimpleNamespace(user=SimpleNamespace(id=user_id), guild=guild)

	def test_only_the_owner(self) :
		self.assertIsNotNone(template_error(self.interaction(1, 2, humans=1)))
		self.assertIsNone(template_error(self.interaction(2, 2, humans=1)))

	def test_member_limit_ignores_bots(self) :
		self.assertIsNone(template_error(self.interaction(2, 2, humans=MAX_MEMBERS, bots=5)))
		self.assertIsNotNone(template_error(self.interaction(2, 2, humans=MAX_MEMBERS + 1)))

	def test_incomplete_member_cache_counts_high(self) :
		interaction = self.interaction(2, 2, humans=3, bots=1, member_count=50)
		self.assertEqual(human_member_count(interaction.guild), 49)
		self.assertIsNotNone(template_error(interaction))


class TestServerSetup(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.guild = FakeGuild()
		self.ooc = run(self.guild.create_category("OOC"))
		self.rp = run(self.guild.create_category("Rp Channels"))
		self.general = FakeChannel(self.guild, "general", self.ooc)
		self.staff = FakeChannel(self.guild, "staff-only", self.ooc, everyone_view=False)
		self.tavern = FakeChannel(self.guild, "tavern", self.rp, everyone_view=True)

	def test_capture_skips_archives(self) :
		run(self.guild.create_category("archive-01-01-2026"))
		data = ServerSetup.capture(self.guild)
		self.assertEqual([c["name"] for c in data["categories"]], ["OOC", "Rp Channels"])
		self.assertEqual([c["name"] for c in data["categories"][0]["channels"]], ["general", "staff-only"])

	def test_apply_then_restore_round_trip(self) :
		template = {"categories" : [{"name" : "New", "channels" : []}]}
		archived, created = run(ServerSetup.apply(self.guild, template))
		self.assertEqual((archived, created), (3, 0))
		self.assertEqual(sorted(c.name for c in self.guild.categories if not ServerSetup.is_archive(c)), ["New"])
		self.assertEqual(self.staff.name, f"ooc{SEPARATOR}staff-only")
		self.assertTrue(all(c.everyone_view is False for c in (self.general, self.staff, self.tavern)))

		restored, from_name = run(ServerSetup.restore(self.guild))
		self.assertEqual((restored, from_name), (3, 0))
		self.assertEqual((self.staff.name, self.staff.category.name), ("staff-only", "OOC"))
		self.assertEqual(self.tavern.category.name, "Rp Channels")
		# Each channel gets back its own @everyone view setting, so private channels stay private.
		self.assertEqual((self.general.everyone_view, self.staff.everyone_view, self.tavern.everyone_view),
		                 (None, False, True))
		self.assertEqual(self.staff.category, self.general.category)
		self.assertFalse(ServerSetup.archive_categories(self.guild))
		self.assertEqual(ArchiveTransactions().get_all(GUILD_ID), [])

	def test_restore_without_record_uses_name_prefix(self) :
		archive = run(self.guild.create_category("archive-01-01-2026"))
		orphan = FakeChannel(self.guild, f"rp-channels{SEPARATOR}market", archive, everyone_view=False)
		restored, from_name = run(ServerSetup.restore(self.guild, archive))
		self.assertEqual((restored, from_name), (1, 1))
		self.assertEqual((orphan.name, orphan.category), ("market", self.rp))
		# Without a record it is unknown whether the channel was private, so it stays hidden.
		self.assertIs(orphan.everyone_view, False)

	def test_restore_rptools_archive(self) :
		"""rptools archived channels as "archived-<name>" in "archive-..." categories, without their category."""
		archive = run(self.guild.create_category("archive-overflow-01-01-2025"))
		old = FakeChannel(self.guild, "archived-roleplay", archive, everyone_view=False)
		restored, from_name = run(ServerSetup.restore(self.guild))
		self.assertEqual((restored, from_name), (1, 1))
		self.assertEqual((old.name, old.category.name, old.everyone_view), ("roleplay", "Restored", False))
		self.assertNotIn(archive, self.guild.categories)

	def test_archive_overflows_at_fifty(self) :
		for number in range(55) :
			FakeChannel(self.guild, f"channel-{number}", self.rp)
		run(ServerSetup.apply(self.guild, {"categories" : []}))
		self.assertEqual(sorted(len(c.channels) for c in ServerSetup.archive_categories(self.guild)), [8, 50])

	def test_purge(self) :
		run(ServerSetup.apply(self.guild, {"categories" : []}))
		self.assertEqual(run(ServerSetup.purge(self.guild)), 3)
		self.assertEqual(self.guild.categories, [])
		self.assertEqual(ArchiveTransactions().get_all(GUILD_ID), [])


class TestLegacyTemplates(unittest.TestCase) :

	def test_rptools_format_is_converted(self) :
		legacy = {"111" : {"name" : "OOC", "channels" : {"general" : {"type" : 0}, "voice" : {"type" : 2}}},
		          "222" : {"name" : "RP", "channels" : {}}}
		data = ServerSetup.normalize(legacy)
		self.assertEqual(data, {"categories" : [
			{"name" : "OOC", "channels" : [{"name" : "general", "type" : 0}, {"name" : "voice", "type" : 2}]},
			{"name" : "RP", "channels" : []}]})
		self.assertIs(ServerSetup.normalize(data), data)
		self.assertIn("- voice", ServerSetup.describe(legacy))

	def test_apply_accepts_rptools_format(self) :
		guild = FakeGuild()
		created_channels = []

		async def create_channel_stub(guild_, name, channel_type, category=None) :
			created_channels.append((name, category.name))

		import classes.setup.ServerSetup as module
		original = module.create_channel
		module.create_channel = create_channel_stub
		try :
			run(ServerSetup.apply(guild, {"1" : {"name" : "OOC", "channels" : {"general" : {"type" : 0}}}}))
		finally :
			module.create_channel = original
		self.assertEqual(created_channels, [("general", "OOC")])


class TestRptoolsImport(DatabaseTestCase) :

	def test_import_templates(self) :
		import json
		from sqlalchemy import create_engine, text
		from classes.setup.RptoolsImport import import_templates
		source = create_engine("sqlite://")
		legacy = {"1" : {"name" : "OOC", "channels" : {"general" : {"type" : 0}}}}
		with source.begin() as connection :
			connection.execute(text("CREATE TABLE templates (id INTEGER PRIMARY KEY, user_id BIGINT, name TEXT, data TEXT)"))
			connection.execute(text("INSERT INTO templates (user_id, name, data) VALUES (:u, 'basic', :d)"),
			                   {"u" : USER_ID, "d" : json.dumps(legacy)})
		self.assertEqual(import_templates(source), (1, 0))
		self.assertEqual(import_templates(source), (0, 1))
		self.assertEqual(TemplateTransactions().get(USER_ID, "basic").data["categories"][0]["name"], "OOC")


class TestTemplateTransactions(DatabaseTestCase) :

	def test_crud(self) :
		data = {"categories" : [{"name" : "OOC", "channels" : [{"name" : "general", "type" : 0}]}]}
		self.assertIsNotNone(TemplateTransactions().add(USER_ID, "Basic", data))
		self.assertIsNone(TemplateTransactions().add(USER_ID, "basic", data))
		self.assertEqual(TemplateTransactions().get(USER_ID, "BASIC").data, data)
		self.assertEqual((TemplateTransactions().count(USER_ID), TemplateTransactions().get_names(USER_ID)), (1, ["basic"]))
		self.assertTrue(TemplateTransactions().delete(USER_ID, "basic"))
		self.assertFalse(TemplateTransactions().delete(USER_ID, "basic"))


class TestCharacterInfo(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.character = {"id" : self.add_character().id}

	def keys(self) :
		return [info.key for info in CharacterInfoTransactions().get_all(self.character["id"])]

	def test_fields(self) :
		info = CharacterInfoTransactions()
		for key in ["Age", "Looks", "Backstory"] :
			self.assertIsNotNone(info.add(self.character["id"], key, "..."))
		self.assertIsNone(info.add(self.character["id"], "age", "duplicate"))
		self.assertTrue(info.move(self.character["id"], "backstory", 1))
		self.assertEqual(self.keys(), ["Backstory", "Age", "Looks"])
		self.assertEqual(info.edit(self.character["id"], "looks", "tall").value, "tall")
		self.assertTrue(info.remove(self.character["id"], "Backstory"))
		self.assertEqual([i.position for i in info.get_all(self.character["id"])], [1, 2])
		self.assertFalse(info.move(self.character["id"], "missing", 1))

	def test_fields_go_with_the_character(self) :
		CharacterInfoTransactions().add(self.character["id"], "Age", "30")
		CharacterTransactions().delete(self.character["id"])
		self.assertEqual(CharacterInfoTransactions().get_all(self.character["id"]), [])
