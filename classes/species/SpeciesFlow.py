"""The Discord side of species: the interview in DMs, the review card, the decision and the post in the species
forum."""
import logging

import discord

from classes.characters.Card import MESSAGE_LIMIT
from classes.characters.CharacterFlow import CharacterFlow
from classes.characters.SpeciesRules import SpeciesRules
from classes.characters.Special import Special
from classes.kernel.ConfigData import ConfigData
from classes.species.SpeciesInterview import CREATED, REVIEW, SpeciesInterview
from database.database import Drafts, Species
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.SpeciesTransactions import APPROVED, SpeciesTransactions
from resources.configs.ConfigMapping import ConfigMapping

THREAD_NAME_LIMIT = 100
FIELD_LIMIT = 1024


class SpeciesFlow :

	# ============================================================
	@staticmethod
	def embed(species: Species, data: dict | None = None, title_prefix: str = "") -> discord.Embed :
		"""The species as an embed; data shows changes waiting for review instead of what is saved."""
		data = {"name" : species.name, "description" : species.description, "benefits" : species.benefits,
		        "drawbacks" : species.drawbacks, "stat_limits" : species.stat_limits,
		        "stat_modifiers" : species.stat_modifiers} | (data or {})
		rules = Special.rules(species.guild_id)
		embed = discord.Embed(title=f"{title_prefix}{data['name']}"[:256], description=(data["description"] or "")[:4000],
		                      color=discord.Color.teal())
		if data["benefits"] :
			embed.add_field(name="Benefits", value=data["benefits"][:FIELD_LIMIT], inline=False)
		if data["drawbacks"] :
			embed.add_field(name="Drawbacks", value=data["drawbacks"][:FIELD_LIMIT], inline=False)
		embed.add_field(name="SPECIAL", inline=False,
		                value=SpeciesRules.describe(None, rules, data["stat_limits"], data["stat_modifiers"]))
		if species.creator_uid :
			embed.add_field(name="Created by", value=f"<@{species.creator_uid}>")
		return embed

	# == interview ==

	# ============================================================
	@staticmethod
	async def begin(interaction: discord.Interaction, species: Species | None = None) -> None :
		draft, text = SpeciesInterview.start(interaction.user.id, interaction.guild.id, interaction.guild.name, species)
		if draft is None :
			return await CharacterFlow.respond(interaction, text)
		if not await CharacterFlow.send_question(interaction.user, text) :
			DraftTransactions().delete(interaction.user.id)
			return await CharacterFlow.respond(interaction, "I could not send you a DM. Please allow direct messages "
			                                                "from this server and try again.")
		await CharacterFlow.respond(interaction, "I sent you a DM, let's continue there.")

	# ============================================================
	@staticmethod
	async def handle_dm(bot: discord.Client, message: discord.Message, draft: Drafts) -> None :
		await SpeciesFlow.answer_text(bot, message.author, draft, await CharacterFlow._text_of(message))

	# ============================================================
	@staticmethod
	async def answer_text(bot: discord.Client, user: discord.User | discord.Member, draft: Drafts, text: str,
	                      pressed_message_id: int | None = None) -> None :
		"""Feeds text to the user's species interview (typed, or a button or menu press) and sends the reply."""
		controls = draft.answers.get("controls_message")
		reply = SpeciesInterview.answer(draft, text)
		await CharacterFlow.strip_controls(user, controls if controls != pressed_message_id else None)
		# A species made while creating a character ends by going back to the character, whose question (and its
		# buttons) is part of the reply.
		await CharacterFlow.send_question(user, reply.text)
		if reply.finished and reply.outcome in (CREATED, REVIEW) and reply.species is not None :
			if not await SpeciesFlow.post_review(bot, reply.species) :
				await CharacterFlow.send_dm(user, "I could not reach the server's review channel, so staff have not "
				                                  "seen this yet. Please let the server's staff know.")
		await CharacterFlow.send_stat_picker(user)

	# == review ==

	# ============================================================
	@staticmethod
	async def post_review(bot: discord.Client, species: Species) -> bool :
		from views.buttons.SpeciesReviewButtons import SpeciesReviewButtons

		guild = bot.get_guild(species.guild_id)
		if guild is None :
			return False
		channel = await ConfigData().get_channel(guild, ConfigMapping.CHARACTER_REVIEW)
		if channel is None :
			return False
		try :
			if species.review_message_id :
				await CharacterFlow._close_card(channel, species.review_message_id, "Replaced by a newer submission.")
			if species.state == APPROVED and species.pending_changes :
				await channel.send(embed=SpeciesFlow.embed(species, title_prefix="Now: "))
				await channel.send(embed=SpeciesFlow.embed(species, species.pending_changes, "Requested: "))
				header = f"<@{species.creator_uid}> wants to change the species **{species.name}**."
			else :
				await channel.send(embed=SpeciesFlow.embed(species))
				header = f"<@{species.creator_uid}> submitted the species **{species.name}** for review."
			card = await channel.send(header, view=SpeciesReviewButtons(),
			                          allowed_mentions=discord.AllowedMentions.none())
		except discord.HTTPException as e :
			logging.warning(f"Could not post the review of species {species.id} in {guild.name}: {e}")
			return False
		SpeciesTransactions().update(species.id, review_message_id=card.id)
		return True

	# ============================================================
	@staticmethod
	async def decide(interaction: discord.Interaction, approve: bool, reason: str | None = None) -> None :
		if not interaction.response.is_done() :
			await interaction.response.defer()
		species = SpeciesTransactions().get_by_review_message(interaction.message.id)
		if species is None or not SpeciesInterview.is_open(species) :
			await interaction.message.edit(view=None)
			return await interaction.followup.send("This review is no longer open.", ephemeral=True)
		bot = interaction.client
		changes = species.state == APPROVED
		notes = []
		if approve :
			species = SpeciesInterview.approve(species)
			verdict = f"✅ Approved by {interaction.user.mention}"
			dm = f"Your {'changes to the ' if changes else ''}species **{species.name}** on {interaction.guild.name} " \
			     f"{'were' if changes else 'was'} approved."
			if not await SpeciesFlow.sync_post(bot, species) :
				notes.append("I could not post the species: check that the `species_forum` channel is set with "
				             "`/config singlechannels` and that I can post there.")
		else :
			species = SpeciesInterview.deny(species)
			verdict = f"❌ Denied by {interaction.user.mention}: {reason}"
			dm = (f"Your {'changes to the ' if changes else ''}species **{species.name}** on {interaction.guild.name} "
			      f"{'were' if changes else 'was'} not approved.\n**Reason:** {reason}\n"
			      f"You can change it with `/species edit` and submit it again.")
		if species.creator_uid :
			try :
				user = interaction.guild.get_member(species.creator_uid) or await bot.fetch_user(species.creator_uid)
			except discord.HTTPException :
				user = None
			if user is None or not await CharacterFlow.send_dm(user, dm) :
				notes.append(f"I could not DM <@{species.creator_uid}>, so please let them know.")
		await interaction.message.edit(content=f"{interaction.message.content}\n{verdict}"[:MESSAGE_LIMIT], view=None,
		                               allowed_mentions=discord.AllowedMentions.none())
		if notes :
			await interaction.followup.send("\n".join(notes), ephemeral=True)

	# == the post in the species forum ==

	# ============================================================
	@staticmethod
	async def sync_post(bot: discord.Client, species: Species) -> bool :
		"""Creates or updates the species' post. False when there is no species channel or posting failed."""
		guild = bot.get_guild(species.guild_id)
		if guild is None :
			return False
		embed = SpeciesFlow.embed(species)
		try :
			if species.forum_message_id :
				target = await SpeciesFlow._location(guild, species)
				if target is not None :
					if isinstance(target, discord.Thread) :
						await target.edit(archived=False, name=species.name[:THREAD_NAME_LIMIT])
					try :
						await (await target.fetch_message(species.forum_message_id)).edit(embed=embed)
						return True
					except discord.NotFound :
						pass
			channel = await ConfigData().get_channel(guild, ConfigMapping.SPECIES_FORUM, optional=True)
			if channel is None :
				return False
			if isinstance(channel, discord.ForumChannel) :
				created = await channel.create_thread(name=species.name[:THREAD_NAME_LIMIT], embed=embed)
				SpeciesTransactions().update(species.id, forum_thread_id=created.thread.id,
				                             forum_message_id=created.message.id,
				                             tag_ids=[tag.id for tag in created.thread.applied_tags])
			else :
				message = await channel.send(embed=embed)
				SpeciesTransactions().update(species.id, forum_thread_id=None, forum_message_id=message.id)
			return True
		except discord.HTTPException as e :
			logging.warning(f"Posting species {species.id} in {guild.name} failed: {e}")
			return False

	# ============================================================
	@staticmethod
	async def _location(guild: discord.Guild, species: Species) :
		if species.forum_thread_id :
			thread = guild.get_channel_or_thread(species.forum_thread_id)
			if thread is None :
				try :
					thread = await guild.fetch_channel(species.forum_thread_id)
				except discord.HTTPException :
					return None
			return thread
		return await ConfigData().get_channel(guild, ConfigMapping.SPECIES_FORUM, optional=True)

	# ============================================================
	@staticmethod
	async def remove_post(bot: discord.Client, species: Species) -> None :
		guild = bot.get_guild(species.guild_id)
		if guild is None or not species.forum_message_id :
			return
		try :
			target = await SpeciesFlow._location(guild, species)
			if target is None :
				return
			if species.forum_thread_id :
				await target.delete()
			else :
				await (await target.fetch_message(species.forum_message_id)).delete()
		except discord.HTTPException as e :
			logging.warning(f"Removing the post of species {species.id} failed: {e}")
