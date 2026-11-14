"""Server templates and the channel archive.

Applying a template moves every channel that sits in a category into an archive category, hides it from @everyone and
renames it to "<category>・<channel>", so the category it came from stays visible in the name. The exact origin (names
and the channel's own @everyone view setting) is also stored in archived_channels, which /archive restore uses to put
channels back; the name prefix is the fallback when no record exists.
"""
import logging
from datetime import datetime

import discord
from discord.enums import try_enum
from discord_py_utilities.channels import create_channel

from database.transactions.ArchiveTransactions import ArchiveTransactions

ARCHIVE_PREFIX = "archive-"
# Separates the original category from the channel name in an archived channel's name.
SEPARATOR = "・"
# Discord allows 50 channels per category and 100 characters per channel name.
CATEGORY_LIMIT = 50
NAME_LIMIT = 100
CATEGORY_PART_LIMIT = 40


class ServerSetup :

	# == naming ==

	# ============================================================
	@staticmethod
	def is_archive(category: discord.CategoryChannel | None) -> bool :
		return category is not None and category.name.lower().startswith(ARCHIVE_PREFIX)

	# ============================================================
	@staticmethod
	def slug(name: str) -> str :
		"""How Discord writes a name as a text channel name: lowercase, spaces become dashes."""
		return "-".join(name.lower().split())

	# ============================================================
	@staticmethod
	def archived_name(category_name: str | None, channel_name: str) -> str :
		if not category_name :
			return channel_name[:NAME_LIMIT]
		prefix = ServerSetup.slug(category_name)[:CATEGORY_PART_LIMIT]
		return f"{prefix}{SEPARATOR}{channel_name}"[:NAME_LIMIT]

	# ============================================================
	@staticmethod
	def parse_archived_name(name: str) -> tuple[str | None, str] :
		"""Splits an archived channel name into (category slug, channel name); (None, name) when it has no prefix."""
		if SEPARATOR not in name :
			return None, name
		category, channel = name.split(SEPARATOR, 1)
		return category, channel

	# == templates ==

	# ============================================================
	@staticmethod
	def capture(guild: discord.Guild) -> dict :
		"""Snapshot of the guild's categories and their channels, in display order. Archive categories are skipped."""
		categories = []
		for category in sorted(guild.categories, key=lambda c : c.position) :
			if ServerSetup.is_archive(category) :
				continue
			categories.append({
				"name"     : category.name,
				"channels" : [{"name" : channel.name, "type" : channel.type.value}
				              for channel in sorted(category.channels, key=lambda c : c.position)],
			})
		return {"categories" : categories}

	# ============================================================
	@staticmethod
	def describe(data: dict) -> str :
		lines = []
		for category in data.get("categories", []) :
			lines.append(f"**{category['name']}**")
			lines += [f"- {channel['name']}" for channel in category.get("channels", [])]
		return "\n".join(lines) or "This template has no categories."

	# ============================================================
	@staticmethod
	def affected(guild: discord.Guild) -> tuple[list[discord.CategoryChannel], list[discord.abc.GuildChannel]] :
		"""The categories a template replaces and the channels it archives."""
		categories = [category for category in guild.categories if not ServerSetup.is_archive(category)]
		channels = [channel for category in categories for channel in category.channels]
		return categories, channels

	# ============================================================
	@staticmethod
	async def apply(guild: discord.Guild, data: dict) -> tuple[int, int] :
		"""Archives every categorised channel, removes the emptied categories and builds the template.

		@return: (channels archived, channels created)
		"""
		categories, channels = ServerSetup.affected(guild)
		archive = None
		# Counted locally: the channel cache only catches up when Discord's update events arrive.
		room = 0
		for channel in channels :
			if archive is None or room <= 0 :
				archive = await ServerSetup.new_archive_category(guild, exclude=archive)
				room = CATEGORY_LIMIT - len(archive.channels)
			await ServerSetup.archive_channel(channel, archive)
			room -= 1
		for category in categories :
			await category.delete(reason="Template being applied")

		created = 0
		for category_data in data.get("categories", []) :
			category = await guild.create_category(name=category_data["name"], reason="Template being applied")
			for channel_data in category_data.get("channels", []) :
				channel_type = try_enum(discord.ChannelType, channel_data.get("type"))
				await create_channel(guild, channel_data["name"], channel_type, category=category)
				created += 1
		return len(channels), created

	# == archive ==

	# ============================================================
	@staticmethod
	async def new_archive_category(guild: discord.Guild,
	                               exclude: discord.CategoryChannel | None = None) -> discord.CategoryChannel :
		"""Today's archive category, or a numbered overflow one when it is full (or is the excluded, filled one)."""
		base = f"{ARCHIVE_PREFIX}{datetime.now().strftime('%d-%m-%Y')}"
		name = base
		number = 1
		while True :
			existing = discord.utils.get(guild.categories, name=name)
			if existing is None :
				return await guild.create_category(name=name, reason="Archiving channels")
			if existing != exclude and len(existing.channels) < CATEGORY_LIMIT :
				return existing
			number += 1
			name = f"{base}-{number}"

	# ============================================================
	@staticmethod
	async def archive_channel(channel: discord.abc.GuildChannel, archive: discord.CategoryChannel) :
		"""Records where the channel came from, then moves, renames and hides it."""
		guild = channel.guild
		category_name = channel.category.name if channel.category else None
		everyone_view = channel.overwrites_for(guild.default_role).view_channel
		ArchiveTransactions().add(guild.id, channel.id, channel.name, category_name, everyone_view)
		await channel.edit(category=archive, name=ServerSetup.archived_name(category_name, channel.name),
		                   reason="Archived")
		await channel.set_permissions(guild.default_role, view_channel=False, reason="Archived")

	# ============================================================
	@staticmethod
	def archive_categories(guild: discord.Guild) -> list[discord.CategoryChannel] :
		return [category for category in guild.categories if ServerSetup.is_archive(category)]

	# ============================================================
	@staticmethod
	def find_category(guild: discord.Guild, name: str, by_slug: bool = False) -> discord.CategoryChannel | None :
		"""A non-archive category with room left, matched by exact name or by slug."""
		for category in guild.categories :
			if ServerSetup.is_archive(category) or len(category.channels) >= CATEGORY_LIMIT :
				continue
			if category.name == name or (by_slug and ServerSetup.slug(category.name) == name) :
				return category
		return None

	# ============================================================
	@staticmethod
	async def restore_channel(channel: discord.abc.GuildChannel,
	                          created: dict[str, discord.CategoryChannel] | None = None) -> bool :
		"""Puts an archived channel back in its category under its old name.

		:param created: categories this restore already created, by name; the guild's cache may not list them yet.
		@return: True when the exact origin was known (stored record), False when it came from the name prefix, in
		which case the channel follows its new category's visibility.
		"""
		created = {} if created is None else created
		guild = channel.guild
		record = ArchiveTransactions().get(channel.id)
		if record is not None :
			category_name, by_slug = record.category_name, False
			name = record.channel_name
			everyone_view = record.everyone_view
		else :
			category_name, name = ServerSetup.parse_archived_name(channel.name)
			by_slug = True
			everyone_view = None

		category = None
		if category_name :
			category = created.get(category_name) or ServerSetup.find_category(guild, category_name, by_slug=by_slug)
			if category is None :
				category = await guild.create_category(name=category_name, reason="Restoring archived channels")
				created[category_name] = category
		await channel.edit(category=category, name=name, reason="Restored from the archive")
		await channel.set_permissions(guild.default_role, view_channel=everyone_view, reason="Restored from the archive")
		ArchiveTransactions().remove(channel.id)
		logging.info(f"Restored {name} ({channel.id}) in {guild.name} to {category_name}")
		return record is not None

	# ============================================================
	@staticmethod
	async def restore(guild: discord.Guild, archive: discord.CategoryChannel | None = None) -> tuple[int, int] :
		"""Restores every channel in one archive category, or in all of them; empty archive categories are removed.

		@return: (channels restored, of which restored from the name prefix only)
		"""
		archives = [archive] if archive is not None else ServerSetup.archive_categories(guild)
		restored = 0
		from_name = 0
		created = {}
		for category in archives :
			channels = list(category.channels)
			for channel in channels :
				exact = await ServerSetup.restore_channel(channel, created)
				restored += 1
				from_name += 0 if exact else 1
			# Every channel it held has been moved out (a failure raises before this point).
			await category.delete(reason="Archive emptied by restore")
		return restored, from_name

	# ============================================================
	@staticmethod
	async def purge(guild: discord.Guild) -> int :
		"""Deletes every archive category and the channels in it. Cannot be undone.

		@return: the number of channels deleted.
		"""
		deleted = 0
		for category in ServerSetup.archive_categories(guild) :
			for channel in list(category.channels) :
				await channel.delete(reason="Archive purged")
				ArchiveTransactions().remove(channel.id)
				deleted += 1
			await category.delete(reason="Archive purged")
		return deleted
