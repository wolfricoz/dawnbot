"""The Discord side of characters: running interviews in DMs, posting review cards and acting on the decisions.

The rules live in Interview, Edits and Review; this module sends what they decide.
"""
import logging

import discord

from classes.characters.Access import Access
from classes.characters.Card import Card, MESSAGE_LIMIT, chunk_text
from classes.characters.Choices import Choices
from classes.characters.Edits import APPLIED, Edits, RESUBMITTED, REVIEW
from classes.characters.ForumPost import ForumPost
from classes.characters.ImageStorage import ImageStorage
from classes.characters.Interview import CREATED, IMPORT, Interview
from classes.characters.Review import CHANGES, Review
from classes.kernel.ConfigData import ConfigData
from database.database import Characters
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from resources.configs.ConfigMapping import ConfigMapping

# The longest text file read as an answer; Discord turns a long pasted message into a message.txt upload.
TEXT_FILE_LIMIT = 100_000

DMS_CLOSED = ("I could not send you a DM. Please allow direct messages from this server (Privacy Settings in the "
              "server menu) and try again.")


class CharacterFlow :

	# ============================================================
	@staticmethod
	async def respond(interaction: discord.Interaction, text: str) -> None :
		"""Answers an interaction privately, whether or not it was deferred or answered before."""
		if interaction.response.is_done() :
			await interaction.followup.send(text, ephemeral=True)
		else :
			await interaction.response.send_message(text, ephemeral=True)

	# == DMs ==

	# ============================================================
	@staticmethod
	async def send_dm(user: discord.abc.Messageable, text: str) -> bool :
		"""Sends text as one or more DMs. False when the user's DMs are closed."""
		return await CharacterFlow._send(user, text) is not None

	# ============================================================
	@staticmethod
	async def _send(user: discord.abc.Messageable, text: str,
	                view: discord.ui.View | None = None) -> discord.Message | None :
		"""Sends text as one or more DMs, with view under the last one; returns that last message, or None when the
		user's DMs are closed. If Discord refuses the view, the text goes without it."""
		chunks = chunk_text(text, MESSAGE_LIMIT)
		message = None
		try :
			for index, chunk in enumerate(chunks) :
				if index == len(chunks) - 1 and view is not None :
					try :
						message = await user.send(chunk, view=view)
						continue
					except discord.Forbidden :
						raise
					except discord.HTTPException as e :
						logging.warning(f"Discord refused the interview controls for {user}: {e}")
				message = await user.send(chunk)
			return message
		except discord.Forbidden :
			return None
		except discord.HTTPException as e :
			logging.warning(f"Could not DM {user}: {e}")
			return None

	# ============================================================
	@staticmethod
	async def send_question(user: discord.abc.Messageable, text: str) -> bool :
		"""Sends an interview message with the buttons and menus of the user's current question (character or
		species interview), and remembers it so the next answer can take them off again. False when DMs are closed."""
		from views.buttons import InterviewControls

		draft = DraftTransactions().get(user.id)
		view = InterviewControls.view(draft) if draft is not None else None
		message = await CharacterFlow._send(user, text, view)
		if message is not None and view is not None and message.components :
			draft.answers["controls_message"] = message.id
			DraftTransactions().save(draft)
		return message is not None

	# ============================================================
	@staticmethod
	async def strip_controls(user: discord.User | discord.Member, message_id: int | None) -> None :
		"""Takes the buttons and menus off an earlier question once it has been answered."""
		if not message_id :
			return
		try :
			channel = user.dm_channel or await user.create_dm()
			await channel.get_partial_message(message_id).edit(view=None)
		except discord.HTTPException :
			pass

	# ============================================================
	@staticmethod
	async def begin(interaction: discord.Interaction, kind: str, character: Characters | None = None) -> None :
		"""Starts an interview from a slash command and tells the user to continue in their DMs.

		For an import, character is the character on another server; its picture is copied first.
		"""
		avatar_id, source_guild = None, None
		if kind == IMPORT :
			busy = DraftTransactions().get(interaction.user.id)
			if busy is not None :
				return await CharacterFlow.respond(interaction, Interview.busy_text(busy))
			avatar_id = await ImageStorage.copy(interaction.client, character.avatar_id)
			guild = interaction.client.get_guild(character.guild_id)
			source_guild = guild.name if guild else None
		draft, text = Interview.start(interaction.user.id, interaction.guild.id, interaction.guild.name, kind,
		                              character, Access.of(interaction.user), avatar_id, source_guild)
		if draft is None :
			await ImageStorage.delete(interaction.client, avatar_id)
			return await CharacterFlow.respond(interaction, text)
		if not await CharacterFlow.send_question(interaction.user, text) :
			DraftTransactions().delete(interaction.user.id)
			await ImageStorage.delete(interaction.client, avatar_id)
			return await CharacterFlow.respond(interaction, DMS_CLOSED)
		await CharacterFlow.respond(interaction, "I sent you a DM, let's continue there.")
		# A respec starts at the stats step.
		await CharacterFlow.send_stat_picker(interaction.user)

	# ============================================================
	@staticmethod
	async def _text_of(message: discord.Message) -> str :
		"""The message's text; a long paste that Discord turned into a text file is read from that file."""
		if message.content :
			return message.content
		for attachment in message.attachments :
			if (attachment.content_type or "").startswith("text/plain") and attachment.size <= TEXT_FILE_LIMIT :
				try :
					return (await attachment.read()).decode("utf-8", errors="replace")
				except discord.HTTPException :
					return ""
		return ""

	# ============================================================
	@staticmethod
	async def handle_dm(bot: discord.Client, message: discord.Message) -> None :
		"""Feeds a DM to the user's interview, if they are in one."""
		draft = DraftTransactions().get(message.author.id)
		if draft is None :
			return

		async def store_image(attachment: discord.Attachment) -> int :
			return await ImageStorage.store(bot, attachment)

		images = [attachment for attachment in message.attachments
		          if (attachment.content_type or "").startswith("image/")]
		guild = bot.get_guild(draft.guild_id)
		member = guild.get_member(message.author.id) if guild else None
		access = Access.of(member) if member is not None else None
		step_before = draft.step
		controls = draft.answers.get("controls_message")
		reply = await Interview.answer(draft, await CharacterFlow._text_of(message), images, store_image, access)
		await CharacterFlow.deliver(bot, message.author, reply, step_before, controls)

	# ============================================================
	@staticmethod
	async def answer_text(bot: discord.Client, user: discord.User | discord.Member, draft, text: str,
	                      pressed_message_id: int | None = None) -> None :
		"""Feeds text to the user's character interview as if they typed it (a button or menu press)."""
		step_before = draft.step
		controls = draft.answers.get("controls_message")
		reply = await Interview.answer(draft, text)
		await CharacterFlow.deliver(bot, user, reply, step_before,
		                            controls if controls != pressed_message_id else None)

	# ============================================================
	@staticmethod
	async def send_stat_picker(user: discord.abc.Messageable, step_before: str | None = None) -> None :
		"""Sends the SPECIAL menus when the user's interview has just reached the stats step."""
		from classes.characters import StatPanel
		from views.multiselect import StatPicker

		draft = DraftTransactions().get(user.id)
		if StatPanel.is_open(draft) and step_before != "stats" :
			await StatPicker.send(user, draft)

	# ============================================================
	@staticmethod
	async def deliver(bot: discord.Client, user: discord.User | discord.Member, reply, step_before: str | None,
	                  old_controls: int | None = None) -> None :
		"""Sends the interview's reply and carries out what it decided: removing pictures, posting the review card,
		updating the forum post, or showing the SPECIAL menus for the next question.

		old_controls is the message with the previous question's buttons, which are taken off first.
		"""
		await CharacterFlow.strip_controls(user, old_controls)
		await CharacterFlow.send_question(user, reply.text)
		for image_id in reply.discard_images :
			await ImageStorage.delete(bot, image_id)
		if not reply.finished :
			await CharacterFlow.send_stat_picker(user, step_before)
			return
		if reply.character is None :
			return
		if reply.outcome in (CREATED, RESUBMITTED, REVIEW) :
			if not await CharacterFlow.post_review(bot, reply.character) :
				await CharacterFlow.send_dm(user,
				                            "I could not reach the server's review channel, so staff have not seen "
				                            "this yet. Please let the server's staff know.")
		if reply.outcome in (APPLIED, REVIEW) :
			# Changes that needed no review are already on the character, so its post has to follow.
			await ForumPost.sync(bot, CharacterTransactions().get_by_id(reply.character.id))

	# == review ==

	# ============================================================
	@staticmethod
	async def post_review(bot: discord.Client, character: Characters) -> bool :
		"""Posts the character's review card with Approve and Deny buttons, replacing an earlier card.

		@return: False when the server has no reachable review channel.
		"""
		from views.buttons.ReviewButtons import ReviewButtons

		guild = bot.get_guild(character.guild_id)
		if guild is None :
			return False
		channel = await ConfigData().get_channel(guild, ConfigMapping.CHARACTER_REVIEW)
		if channel is None :
			return False
		try :
			if character.review_message_id :
				await CharacterFlow._close_card(channel, character.review_message_id, "Replaced by a newer submission.")
			avatar_url = await ImageStorage.url(bot, character.avatar_id)
			for embed in Card.embeds(character, avatar_url) :
				await channel.send(embed=embed)

			kind = Review.kind(character)
			if kind == CHANGES :
				changes = character.pending_changes or {}
				chunks = chunk_text(Edits.describe(character, changes), 4000)
				new_avatar = await ImageStorage.url(bot, changes.get("avatar_id")) if "avatar_id" in changes else None
				for index, chunk in enumerate(chunks) :
					embed = discord.Embed(title=f"Requested changes to {character.name}"[:256] if index == 0 else None,
					                      description=chunk, color=discord.Color.orange())
					if index == 0 and new_avatar :
						embed.set_image(url=new_avatar)
					await channel.send(embed=embed)
				header = f"<@{character.uid}> wants to change **{character.name}**."
			else :
				method = {"rolled" : f"rolled, {character.rerolls} rerolls", "point_buy" : "point-buy"}.get(
					character.stat_method, "unknown")
				header = f"<@{character.uid}> submitted **{character.name}** for review. Stats: {method}."
				source = CharacterTransactions().get_by_id(character.imported_from) if character.imported_from else None
				if character.imported_from :
					source_guild = bot.get_guild(source.guild_id) if source else None
					header += f" Copied from {source_guild.name if source_guild else 'another server'}."
				elif character.approved_at is not None :
					header += " They are coming back from retirement."
			card = await channel.send(header, view=ReviewButtons(), allowed_mentions=discord.AllowedMentions.none())
		except discord.HTTPException as e :
			logging.warning(f"Could not post the review of character {character.id} in {guild.name}: {e}")
			return False
		CharacterTransactions().update(character.id, review_message_id=card.id)
		return True

	# ============================================================
	@staticmethod
	async def _close_card(channel, message_id: int, note: str) -> None :
		"""Takes the buttons off an old review card."""
		try :
			message = await channel.fetch_message(message_id)
			await message.edit(content=f"{message.content}\n-# {note}", view=None)
		except discord.HTTPException :
			pass

	# ============================================================
	@staticmethod
	async def withdraw_review(bot: discord.Client, character: Characters, note: str) -> None :
		"""Closes the character's open review card, for example when the character is deleted."""
		if not character.review_message_id :
			return
		guild = bot.get_guild(character.guild_id)
		if guild is None :
			return
		channel = await ConfigData().get_channel(guild, ConfigMapping.CHARACTER_REVIEW, optional=True)
		if channel is not None :
			await CharacterFlow._close_card(channel, character.review_message_id, note)

	# ============================================================
	@staticmethod
	async def decide(interaction: discord.Interaction, approve: bool, reason: str | None = None) -> None :
		"""Carries out a reviewer's decision on the review card the interaction came from."""
		# Posting the character and messaging the player can take longer than Discord waits for an answer.
		if not interaction.response.is_done() :
			await interaction.response.defer()
		character = CharacterTransactions().get_by_review_message(interaction.message.id)
		if character is None or not Review.is_open(character) :
			await interaction.message.edit(view=None)
			return await interaction.followup.send("This review is no longer open.", ephemeral=True)
		bot = interaction.client
		if approve and (waiting := Review.waiting_on(character)) :
			return await interaction.followup.send(waiting, ephemeral=True)
		if approve :
			occupation_id = (character.pending_changes or {}).get("occupation_id", character.occupation_id) \
				if Review.kind(character) == CHANGES else character.occupation_id
			if not Choices.room_for(occupation_id, character.id) :
				occupation = OccupationTransactions().get(occupation_id)
				return await interaction.followup.send(
					f"{occupation.name} is full. Deny this, or raise its limit with `/occupation edit` first.",
					ephemeral=True)
			character, unused, kind = Review.approve(character, interaction.user.id)
			verdict = f"✅ Approved by {interaction.user.mention}"
			dm = (f"Your changes to **{character.name}** on {interaction.guild.name} were approved."
			      if kind == CHANGES else
			      f"**{character.name}** was approved on {interaction.guild.name}. Have fun!")
		else :
			character, unused, kind = Review.deny(character)
			verdict = f"❌ Denied by {interaction.user.mention}: {reason}"
			dm = (f"Your changes to **{character.name}** on {interaction.guild.name} were denied, so "
			      f"{character.name} stays as it was.\n**Reason:** {reason}"
			      if kind == CHANGES else
			      f"**{character.name}** was not approved on {interaction.guild.name}.\n**Reason:** {reason}\n"
			      f"You can change it with `/character edit` on the server and submit it again.")
		for image_id in unused :
			await ImageStorage.delete(bot, image_id)

		notes = []
		if approve and not await ForumPost.sync(bot, character) :
			notes.append("I could not post the character: check that the `character` channel is set with "
			             "`/config singlechannels` and that I can post there.")
		member = interaction.guild.get_member(character.uid)
		try :
			user = member or await bot.fetch_user(character.uid)
		except discord.HTTPException :
			user = None
		if user is None or not await CharacterFlow.send_dm(user, dm) :
			notes.append(f"I could not DM <@{character.uid}>, so please let them know.")

		await interaction.message.edit(content=f"{interaction.message.content}\n{verdict}"[:MESSAGE_LIMIT], view=None,
		                               allowed_mentions=discord.AllowedMentions.none())
		if notes :
			await interaction.followup.send("\n".join(notes), ephemeral=True)
