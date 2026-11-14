import discord
from discord.ext import commands

from database.transactions.GearItemTransactions import GearItemTransactions


class GearListener(commands.Cog) :
	"""Keeps the gear catalog in step with the tags on the items' posts in the gear forum."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@staticmethod
	def tags_changed(item, data: dict) -> list[int] | None :
		"""The tag ids on a thread update, sorted, when they differ from the item's; None when nothing changed."""
		if "applied_tags" not in data :
			return None
		tag_ids = sorted(int(tag_id) for tag_id in data.get("applied_tags") or [])
		return tag_ids if tag_ids != sorted(item.tag_ids or []) else None

	# ============================================================
	@commands.Cog.listener("on_raw_thread_update")
	async def on_raw_thread_update(self, payload: discord.RawThreadUpdateEvent) :
		"""Stores the tags of an item's post, which decide who may buy it (see /tagrule)."""
		item = GearItemTransactions().get_by_thread(payload.thread_id)
		if item is None :
			return
		tag_ids = self.tags_changed(item, payload.data)
		if tag_ids is not None :
			GearItemTransactions().update(item.id, tag_ids=tag_ids)

	# ============================================================
	@commands.Cog.listener("on_raw_thread_delete")
	async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent) :
		"""The item stays in the catalog without its post, and keeps the restrictions its tags gave it."""
		item = GearItemTransactions().get_by_thread(payload.thread_id)
		if item is not None :
			GearItemTransactions().update(item.id, forum_thread_id=None, forum_message_id=None)


async def setup(bot) :
	await bot.add_cog(GearListener(bot))
