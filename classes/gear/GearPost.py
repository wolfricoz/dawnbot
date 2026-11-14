"""An item's post in the gear forum (GEAR_FORUM): one thread per item in a forum, or one message in a text channel.

The post is optional. Without a gear forum the catalog works the same, but tags (and so tag restrictions) can only be
put on items that have a forum post.
"""
import logging

import discord

from classes.gear.Gear import WEAPON
from classes.gear.GearCard import GearCard
from classes.kernel.ConfigData import ConfigData
from database.database import GearItems
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping

THREAD_NAME_LIMIT = 100
# Discord allows at most this many tags on one forum post.
TAG_LIMIT = 5


class GearPost :

	# ============================================================
	@staticmethod
	def configured(guild_id: int) -> bool :
		"""True when the server has a gear forum set."""
		return ConfigData().get_int(guild_id, ConfigMapping.GEAR_FORUM) is not None

	# ============================================================
	@staticmethod
	def combat_text(item: GearItems) -> str :
		"""`1d8 + Strength damage · +1 to hit` for weapons, `HP 90 · AP 30 · AC 15 · -1 to hit` for armor."""
		combat = item.combat or {}
		if not combat :
			return ""
		if item.kind == WEAPON :
			text = combat.get("dice", "")
			modifier = combat.get("modifier") or ""
			if ":" in modifier :
				kind, stat = modifier.split(":", 1)
				text += f" + {stat.capitalize()}" if kind == "damage" else f" + half {stat.capitalize()} in dice"
			parts = [f"{text} damage".strip()]
			if combat.get("hitmodifier") :
				parts.append(f"{combat['hitmodifier']:+d} to hit")
			return " · ".join(parts)
		parts = [f"{key.upper()} {combat[key]}" for key in ("hp", "ap", "ac") if key in combat]
		if combat.get("hitchance") :
			parts.append(f"{combat['hitchance']:+d} to hit")
		return " · ".join(parts)

	# ============================================================
	@staticmethod
	def card(item: GearItems) -> discord.Embed :
		"""The item's embed (GearCard.embed) with its combat values."""
		embed = GearCard.embed(item)
		combat = GearPost.combat_text(item)
		if combat :
			embed.add_field(name="Combat", value=combat[:1024], inline=False)
		return embed

	# ============================================================
	@staticmethod
	async def sync(bot: discord.Client, item: GearItems) -> bool :
		"""Creates or updates the item's post in the gear forum: edits it in place when it still exists, posts it again
		when it was removed. Returns False, doing nothing, when the server has no gear forum, and False when posting
		failed."""
		if not GearPost.configured(item.guild_id) :
			return False
		guild = bot.get_guild(item.guild_id)
		if guild is None :
			return False
		embed = GearPost.card(item)
		try :
			if item.forum_message_id :
				target = await GearPost._location(guild, item)
				# A forum (when the gear channel changed from a text channel) holds no plain messages.
				if target is not None and hasattr(target, "fetch_message") :
					try :
						if isinstance(target, discord.Thread) :
							await target.edit(archived=False, name=item.name[:THREAD_NAME_LIMIT])
						await (await target.fetch_message(item.forum_message_id)).edit(embed=embed)
						return True
					except discord.NotFound :
						pass
			channel = await ConfigData().get_channel(guild, ConfigMapping.GEAR_FORUM, optional=True)
			if channel is None :
				return False
			if isinstance(channel, discord.ForumChannel) :
				# A post made again gets back the tags the item kept, so its restrictions still show on the post.
				tags = [tag for tag in channel.available_tags if tag.id in (item.tag_ids or [])][:TAG_LIMIT]
				created = await channel.create_thread(name=item.name[:THREAD_NAME_LIMIT], embed=embed,
				                                      applied_tags=tags)
				GearItemTransactions().update(item.id, forum_thread_id=created.thread.id,
				                              forum_message_id=created.message.id)
			elif isinstance(channel, discord.abc.Messageable) :
				message = await channel.send(embed=embed)
				GearItemTransactions().update(item.id, forum_thread_id=None, forum_message_id=message.id)
			else :
				return False
			return True
		except discord.HTTPException as e :
			logging.warning(f"Posting gear item {item.id} in {guild.name} failed: {e}")
			return False

	# ============================================================
	@staticmethod
	async def _location(guild: discord.Guild, item: GearItems) :
		"""Where the item's post is: its thread, or the gear channel when it was posted as a plain message."""
		if item.forum_thread_id :
			thread = guild.get_channel_or_thread(item.forum_thread_id)
			if thread is None :
				try :
					thread = await guild.fetch_channel(item.forum_thread_id)
				except discord.HTTPException :
					return None
			return thread
		return await ConfigData().get_channel(guild, ConfigMapping.GEAR_FORUM, optional=True)

	# ============================================================
	@staticmethod
	async def remove(bot: discord.Client, item: GearItems) -> None :
		"""Deletes the item's post (its whole thread in a forum). Does nothing when it has none."""
		guild = bot.get_guild(item.guild_id)
		if guild is None or not item.forum_message_id :
			return
		try :
			target = await GearPost._location(guild, item)
			if target is None :
				return
			if item.forum_thread_id :
				await target.delete()
			elif hasattr(target, "fetch_message") :
				await (await target.fetch_message(item.forum_message_id)).delete()
		except discord.HTTPException as e :
			logging.warning(f"Removing the post of gear item {item.id} failed: {e}")
