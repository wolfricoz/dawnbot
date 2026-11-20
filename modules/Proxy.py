"""Posting as characters. Members post as a character by starting or ending a message with its prefix or
suffix, or with /character autoproxy. Right-click a post and choose Apps > Edit as character to edit it, react
with ❌ to delete it, or react with ❓ to find out who wrote it.
"""
import logging

import discord
from discord import app_commands
from discord.ext import commands

from classes.characters.Special import Special
from classes.progression.Progression import Progression
from classes.proxy.Compose import Compose, MESSAGE_LIMIT
from classes.proxy.WebhookManager import WebhookManager
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.ProxyTransactions import ProxyTransactions


class EditPost(discord.ui.Modal, title="Edit message") :
	"""The new text of a message posted as a character; its reply line, if any, is kept."""

	def __init__(self, message: discord.Message, webhook: discord.Webhook, first_message_id: int,
	             language_text: str | None = None, character=None) :
		super().__init__()
		self.message = message
		self.webhook = webhook
		self.first_message_id = first_message_id
		# A post in a language is edited as written (with its {Language} markers) and scrambled again.
		self.character = character if language_text is not None else None
		self.reply, self.old_text = Compose.strip_reply_line(message.content)
		if language_text is not None :
			self.old_text = language_text
		limit = MESSAGE_LIMIT - (len(self.reply) + 1 if self.reply else 0)
		self.text = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, default=self.old_text,
		                                 max_length=limit, required=True)
		self.add_item(self.text)

	async def on_submit(self, interaction: discord.Interaction) :
		new_text = self.text.value
		posted = new_text
		if self.character is not None :
			from classes.language.LanguageFlow import LanguageFlow

			posted, segments, problem = LanguageFlow.prepare(self.character, new_text)
			if problem :
				return await interaction.response.send_message(problem, ephemeral=True)
			LanguageFlow.save(self.first_message_id, self.character, segments or [])
		content = f"{self.reply}\n{posted}" if self.reply else posted
		thread = self.message.channel if isinstance(self.message.channel, discord.Thread) else discord.utils.MISSING
		try :
			await self.webhook.edit_message(self.message.id, content=content, thread=thread,
			                                allowed_mentions=Compose.kept_mentions(self.message))
		except discord.HTTPException as e :
			logging.warning(f"Editing proxied message {self.message.id} failed: {e}")
			return await interaction.response.send_message("I could not edit that message.", ephemeral=True)
		ProxyTransactions().adjust_length(self.first_message_id, len(new_text) - len(self.old_text))
		await interaction.response.send_message("Edited.", ephemeral=True)


@app_commands.guild_only()
class Proxy(commands.GroupCog, name="Proxy", group_name="proxy") :
	def __init__(self, bot: commands.Bot) :
		self.bot = bot
		self.edit_menu = app_commands.ContextMenu(name="Edit as character", callback=self.edit_post)
		self.bot.tree.add_command(self.edit_menu)

	# ============================================================
	async def cog_unload(self) :
		self.bot.tree.remove_command(self.edit_menu.name, type=self.edit_menu.type)

	# ============================================================
	async def edit_post(self, interaction: discord.Interaction, message: discord.Message) :
		"""Edits a message you posted as one of your characters."""
		entry = ProxyTransactions().get(message.id)
		if entry is None or entry.deleted :
			return await interaction.response.send_message("That is not a message posted as a character.",
			                                               ephemeral=True)
		if entry.uid != interaction.user.id :
			return await interaction.response.send_message("Only the person who wrote it can edit it.", ephemeral=True)
		try :
			webhook = await WebhookManager().find(self.bot, message.channel, message.webhook_id)
		except discord.HTTPException :
			webhook = None
		if webhook is None :
			return await interaction.response.send_message("I can no longer edit that message.", ephemeral=True)
		from classes.language.LanguageFlow import LanguageFlow

		language_text = LanguageFlow.edit_text(message.id, interaction.guild_id)
		character = None
		if language_text is not None :
			if len(ProxyTransactions().get_post(message.id)) > 1 :
				return await interaction.response.send_message("A long post in a language can't be edited; delete it "
				                                               "and post it again.", ephemeral=True)
			character = CharacterTransactions().get_by_id(entry.character_id)
			if character is None :
				language_text = None
		await interaction.response.send_modal(EditPost(message, webhook, entry.first_message_id, language_text,
		                                               character))

	# ============================================================
	@app_commands.command(name="recalculate")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def recalculate(self, interaction: discord.Interaction, member: discord.Member = None) :
		"""
		Recalculates the XP of every character on the server (or one member's characters) from the posts the bot
		made for them, using the current XP settings. Deleted posts and posts outside the roleplay channels do not
		count. A character never loses a level, but its XP can go down. Currency is not changed.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		characters = CharacterTransactions().get_in_guild(interaction.guild_id, member.id if member else None)
		changed = []
		for character in characters :
			lengths = ProxyTransactions().counted_lengths(character.id)
			xp = sum(Progression.xp_for_length(interaction.guild_id, length) for length in lengths)
			if xp == character.xp :
				continue
			updated, gained = Special.set_xp(character, xp)
			changed.append(f"**{character.name}** (<@{character.uid}>): {character.xp} → {updated.xp} XP"
			               + (f", now level {updated.level}" if gained else ""))
		logging.info(f"{interaction.user.name} recalculated character XP in {interaction.guild.name}")
		summary = f"Checked {len(characters)} characters; {len(changed)} changed."
		lines = "\n".join(changed[:30]) + (f"\n…and {len(changed) - 30} more" if len(changed) > 30 else "")
		await interaction.followup.send(f"{summary}\n{lines}".strip()[:2000],
		                                allowed_mentions=discord.AllowedMentions.none())


async def setup(bot) :
	await bot.add_cog(Proxy(bot))
