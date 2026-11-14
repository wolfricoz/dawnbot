import logging

import discord
from discord.ext import commands

from classes.characters.CharacterFlow import CharacterFlow
from classes.species.SpeciesFlow import SpeciesFlow
from classes.species.SpeciesInterview import KINDS as SPECIES_KINDS
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.SpeciesTransactions import SpeciesTransactions


class InterviewListener(commands.Cog) :
	"""Passes DMs to the character or species interview of the member who sent them, and keeps species in step with
	the tags on their forum posts."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@commands.Cog.listener("on_message")
	async def on_message(self, message: discord.Message) :
		if message.guild is not None or message.author.bot :
			return
		try :
			draft = DraftTransactions().get(message.author.id)
			if draft is None :
				return
			if draft.kind in SPECIES_KINDS :
				await SpeciesFlow.handle_dm(self.bot, message, draft)
			else :
				await CharacterFlow.handle_dm(self.bot, message)
		except Exception as e :
			logging.error(f"Interview of {message.author.id} failed: {e}", exc_info=True)
			await CharacterFlow.send_dm(message.author,
			                            "Something went wrong on my side. Your answers so far are saved; please send "
			                            "that again in a moment.")

	# ============================================================
	@commands.Cog.listener("on_raw_thread_update")
	async def on_raw_thread_update(self, payload: discord.RawThreadUpdateEvent) :
		"""Stores the tags of a species' post, which decide who may pick the species."""
		# An update that does not mention the tags (a rename, archiving) must not clear them.
		if "applied_tags" not in payload.data :
			return
		species = SpeciesTransactions().get_by_thread(payload.thread_id)
		if species is None :
			return
		tag_ids = sorted(int(tag_id) for tag_id in payload.data["applied_tags"])
		if tag_ids != sorted(species.tag_ids or []) :
			SpeciesTransactions().update(species.id, tag_ids=tag_ids)

	# ============================================================
	@commands.Cog.listener("on_raw_thread_delete")
	async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent) :
		"""The species keeps working without its post, and keeps the restrictions its tags gave it."""
		species = SpeciesTransactions().get_by_thread(payload.thread_id)
		if species is not None :
			SpeciesTransactions().update(species.id, forum_thread_id=None, forum_message_id=None)


async def setup(bot) :
	await bot.add_cog(InterviewListener(bot))
