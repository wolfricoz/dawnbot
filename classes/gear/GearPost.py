"""An item's post in the gear forum (GEAR_FORUM): one thread per item in a forum, or one message in a text channel.

The post is optional. Without a gear forum the catalog works the same, but tags (and so tag restrictions) can only be
put on items that have a forum post.
"""
import logging

import discord

from classes.combat import Rules
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
		"""`2d6 + STR · Slashing · STR to hit, +1 · 3 AP · two handed` for weapons, `Medium armor · AC +2 · DT 2` for
		armor. Old values are shown converted."""
		combat = item.combat or {}
		if not combat :
			return ""
		if item.kind == WEAPON :
			weapon = Rules.normalise_weapon(combat)
			damage = weapon["dice"]
			if weapon.get("damage_stat") :
				damage += f" + {Rules.STAT_SHORT[weapon['damage_stat']]}"
			parts = [damage]
			if weapon.get("type") :
				parts.append(weapon["type"])
			hit = f"{Rules.STAT_SHORT.get(weapon['attack_stat'], weapon['attack_stat'])} to hit"
			if weapon.get("hit_mod") :
				hit += f", {weapon['hit_mod']:+d}"
			parts += [hit, weapon["range"], f"{Rules.weapon_ap(weapon)} AP"]
			if weapon.get("properties") :
				parts.append(", ".join(prop.replace("_", " ") for prop in weapon["properties"]))
			return " · ".join(parts)
		armor = Rules.normalise_armor(combat)
		parts = [f"{armor['armor_class'].capitalize()} armor", f"AC {armor['ac']:+d}", f"DT {armor['dt']}"]
		if armor.get("hit_mod") :
			parts.append(f"{armor['hit_mod']:+d} to hit")
		if armor.get("ability_hit_mod") :
			parts.append(f"{armor['ability_hit_mod']:+d} to hit with abilities")
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
