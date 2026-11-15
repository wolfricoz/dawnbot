import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Card import Card, STATE_LABELS
from classes.combat import SheetAbilities
from classes.characters.CharacterFlow import CharacterFlow
from classes.characters.Edits import APPLIED, Edits, REVIEW
from classes.characters.ForumPost import ForumPost
from classes.characters.GlobalCharacters import GlobalCharacters
from classes.characters.ImageStorage import ImageStorage
from classes.characters.Interview import CREATE, EDIT, IMPORT, RESPEC
from classes.characters.Retirement import Retirement
from classes.characters.Special import STATS, Special
from classes.combat import Rules
from classes.combat.AutoComplete import AutoComplete
from classes.combat.Proficiency import Proficiency
from classes.kernel.ConfigData import ConfigData
from classes.progression.Progression import Progression
from classes.proxy.Matcher import PROXY_CHANNEL_TYPES
from database.database import Characters
from database.transactions.AutoproxyTransactions import AutoproxyTransactions
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions, DEAD, PENDING, RETIRED
from database.transactions.SheetFieldTransactions import SheetFieldTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.buttons.Confirm import ask

# How many extra fields of their own a player can add to one character.
MAX_EXTRA_FIELDS = 25


@app_commands.guild_only()
class Character(commands.GroupCog, name="Character", group_name="character") :
	"""Create and manage your characters. New characters and most changes are reviewed by staff."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# == helpers ==

	# ============================================================
	async def _own_character(self, interaction: discord.Interaction, name: str) -> Characters | None :
		"""The member's character with that name on this server; tells them when there is none."""
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name)
		if character is None :
			await CharacterFlow.respond(interaction, f"You have no character called {name} on this server.")
		return character

	# ============================================================
	async def _send_card(self, interaction: discord.Interaction, character: Characters,
	                     note: str | None = None) -> None :
		avatar_url = await ImageStorage.url(self.bot, character.avatar_id)
		embeds = Card.embeds(character, avatar_url)
		if note :
			embeds[0].set_footer(text=note)
		await interaction.followup.send(embed=embeds[0])
		for embed in embeds[1 :] :
			await interaction.followup.send(embed=embed)

	# == creating and changing ==

	# ============================================================
	@app_commands.command(name="create", description="Creates a character; I ask the questions in your DMs")
	async def create(self, interaction: discord.Interaction) :
		"""
		Starts creating a character. The bot asks its questions in your DMs: a name, how you speak as the character,
		a picture, the server's character sheet and your SPECIAL stats. There is no time limit. When you submit,
		staff review the character before you can use it.
		"""
		await interaction.response.defer(ephemeral=True)
		guild_id = interaction.guild_id
		if ConfigData().get_int(guild_id, ConfigMapping.CHARACTER_REVIEW) is None :
			return await interaction.followup.send(
				"This server has not set up character reviews yet. Staff can set the review channel with "
				"`/config singlechannels` (option `character_review`).")
		cap = ConfigData().get_int(guild_id, ConfigMapping.CHARACTER_CAP)
		if CharacterTransactions().count_active(interaction.user.id, guild_id) >= cap :
			return await interaction.followup.send(
				f"You already have {cap} characters here, which is this server's limit. Delete one first.")
		await CharacterFlow.begin(interaction, CREATE)

	# ============================================================
	@app_commands.command(name="edit", description="Changes a character's answers; I ask in your DMs")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def edit(self, interaction: discord.Interaction, name: str) :
		"""
		Changes one of your characters: its name, prefix and suffix, picture or sheet answers. The bot shows the
		current answers in your DMs and you pick what to change. Depending on the server's settings, changes to an
		approved character wait for staff approval; until then the character stays as it was. A character that was
		denied is sent back to staff when you submit.
		"""
		await interaction.response.defer(ephemeral=True)
		if (character := await self._own_character(interaction, name)) is None :
			return
		if character.state in (RETIRED, DEAD) :
			return await interaction.followup.send(f"{character.name} is {character.state} and cannot be edited.")
		await CharacterFlow.begin(interaction, EDIT, character)

	# ============================================================
	@app_commands.command(name="respec", description="Redistributes a character's SPECIAL points; staff review it")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def respec(self, interaction: discord.Interaction, name: str) :
		"""
		Divides all of a character's SPECIAL points again, including unspent ones. The bot asks for the new stats in
		your DMs. Staff always review a respec before it applies.
		"""
		await interaction.response.defer(ephemeral=True)
		if (character := await self._own_character(interaction, name)) is None :
			return
		if character.state in (RETIRED, DEAD) :
			return await interaction.followup.send(f"{character.name} is {character.state} and cannot be changed.")
		await CharacterFlow.begin(interaction, RESPEC, character)

	# ============================================================
	@app_commands.command(name="spend", description="Spends a character's unspent SPECIAL points on a stat")
	@app_commands.autocomplete(name=AutoComplete().approved_character)
	@app_commands.choices(stat=[Choice(name=stat.capitalize(), value=stat) for stat in STATS])
	async def spend(self, interaction: discord.Interaction, name: str, stat: Choice[str],
	                amount: app_commands.Range[int, 1, 100] = 1) :
		"""
		Spends points your character earned by levelling up. This needs no staff review.
		"""
		await interaction.response.defer(ephemeral=True)
		if (character := await self._own_character(interaction, name)) is None :
			return
		if character.state != APPROVED :
			return await interaction.followup.send(f"{character.name} has to be approved before it can spend points.")
		updated, problem = Special.spend(character, stat.value, amount)
		if updated is None :
			return await interaction.followup.send(problem)
		logging.info(f"{interaction.user.name} spent {amount} on {stat.value} of character {character.id}")
		await ForumPost.sync(self.bot, updated)
		await interaction.followup.send(f"{updated.name}'s {stat.name} is now {getattr(updated, stat.value)}. "
		                                f"Unspent points left: {updated.unspent_points}.")

	# ============================================================
	@app_commands.command(name="delete", description="Deletes a character for good")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def delete(self, interaction: discord.Interaction, name: str) :
		"""
		Deletes one of your characters, with its sheet, picture and post in the character channel. This cannot be
		undone.
		"""
		if (character := await self._own_character(interaction, name)) is None :
			return
		if not await ask(interaction, f"Delete **{character.name}** for good? This cannot be undone.", "Delete") :
			return
		character = CharacterTransactions().get_by_id(character.id)
		if character is None :
			return await interaction.followup.send("That character was already deleted.", ephemeral=True)
		await CharacterFlow.withdraw_review(self.bot, character, "The character was deleted by its player.")
		await ForumPost.remove(self.bot, character)
		for image_id in {character.avatar_id, (character.pending_changes or {}).get("avatar_id")} - {None} :
			await ImageStorage.delete(self.bot, image_id)
		CharacterTransactions().delete(character.id)
		logging.info(f"Character {character.name} ({character.id}) deleted by {interaction.user.name}")
		await interaction.followup.send(f"{character.name} was deleted.", ephemeral=True)

	# ============================================================
	@app_commands.command(name="retire", description="Puts a character aside; it can come back later")
	@app_commands.autocomplete(name=AutoComplete().approved_character)
	async def retire(self, interaction: discord.Interaction, name: str) :
		"""
		Retires one of your approved characters. It stops posting, no longer counts toward the server's character
		limit, and gives up its place in its occupation. Its sheet, experience, gear and currency are kept, and its
		post is locked or removed, depending on the server. Changes waiting for review are dropped. Bring it back with
		/character unretire.
		"""
		if (character := await self._own_character(interaction, name)) is None :
			return
		if not await ask(interaction, f"Retire **{character.name}**? You can bring them back later.", "Retire") :
			return
		character = CharacterTransactions().get_by_id(character.id)
		review_message_id = character.review_message_id if character else None
		updated, unused, problem = Retirement.retire(character) if character else (None, [], "That character is gone.")
		if updated is None :
			return await interaction.followup.send(problem, ephemeral=True)
		if review_message_id :
			await CharacterFlow.withdraw_review(self.bot, character, "The character was retired.")
		for image_id in unused :
			await ImageStorage.delete(self.bot, image_id)
		await ForumPost.retire(self.bot, updated)
		logging.info(f"{interaction.user.name} retired character {updated.id}")
		await interaction.followup.send(f"{updated.name} is retired.", ephemeral=True)

	# ============================================================
	@app_commands.command(name="unretire", description="Brings a retired character back; staff review it again")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def unretire(self, interaction: discord.Interaction, name: str) :
		"""
		Brings one of your retired characters back. It counts toward the server's character limit again and goes
		back to staff for review before it can post.
		"""
		await interaction.response.defer(ephemeral=True)
		if (character := await self._own_character(interaction, name)) is None :
			return
		if ConfigData().get_int(interaction.guild_id, ConfigMapping.CHARACTER_REVIEW) is None :
			return await interaction.followup.send("This server has not set up character reviews yet.")
		updated, note, problem = Retirement.unretire(character)
		if updated is None :
			return await interaction.followup.send(problem)
		if not await CharacterFlow.post_review(self.bot, updated) :
			note = (note + " " if note else "") + "I could not reach the review channel; please let staff know."
		logging.info(f"{interaction.user.name} brought character {updated.id} back from retirement")
		await interaction.followup.send(f"{updated.name} was sent to staff for review."
		                                + (f"\n{note}" if note else ""))

	# ============================================================
	async def _elsewhere(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""The member's characters on other servers, labelled with their server."""
		choices = []
		for character in CharacterTransactions().get_elsewhere(interaction.user.id, interaction.guild_id) :
			guild = self.bot.get_guild(character.guild_id)
			label = f"{character.name} ({guild.name if guild else 'another server'})"
			if current.lower() in label.lower() :
				choices.append(Choice(name=label[:100], value=str(character.id)))
		return choices[:25]

	# ============================================================
	@app_commands.command(name="import", description="Copies one of your characters from another server")
	@app_commands.autocomplete(character=_elsewhere)
	async def import_character(self, interaction: discord.Interaction, character: str) :
		"""
		Copies one of your characters from another server to this one. Its name, prefix and suffix, picture and
		written answers come along; experience, stats, gear and currency start fresh. The bot asks in your DMs for
		what this server needs (species, occupation, missing sheet answers, stats and gear), then staff review it.
		The original stays as it is.
		"""
		await interaction.response.defer(ephemeral=True)
		source = CharacterTransactions().get_by_id(int(character)) if character.isdigit() else None
		if source is None or source.uid != interaction.user.id or source.guild_id == interaction.guild_id :
			return await interaction.followup.send("Pick one of your characters from another server from the list.")
		if ConfigData().get_int(interaction.guild_id, ConfigMapping.CHARACTER_REVIEW) is None :
			return await interaction.followup.send(
				"This server has not set up character reviews yet. Staff can set the review channel with "
				"`/config singlechannels` (option `character_review`).")
		cap = ConfigData().get_int(interaction.guild_id, ConfigMapping.CHARACTER_CAP)
		if CharacterTransactions().count_active(interaction.user.id, interaction.guild_id) >= cap :
			return await interaction.followup.send(
				f"You already have {cap} characters here, which is this server's limit. Delete one first.")
		await CharacterFlow.begin(interaction, IMPORT, source)

	# ============================================================
	@app_commands.command(name="autoproxy", description="Posts everything you type in this channel as a character")
	@app_commands.autocomplete(name=AutoComplete().approved_character)
	async def autoproxy(self, interaction: discord.Interaction, name: str = None) :
		"""
		Posts everything you type in this channel (or thread) as one of your approved characters, without a prefix
		or suffix. Leave the name out to turn it off. A prefix or suffix still picks another character, and a message
		starting with a backslash (\\) is posted as yourself.
		"""
		await interaction.response.defer(ephemeral=True)
		channel = interaction.channel
		if name is None :
			if AutoproxyTransactions().clear(interaction.user.id, channel.id) :
				return await interaction.followup.send("Autoproxy is off in this channel.")
			return await interaction.followup.send("Autoproxy was not on in this channel.")
		if (character := await self._own_character(interaction, name)) is None :
			return
		if character.state != APPROVED :
			return await interaction.followup.send(f"{character.name} has to be approved by staff first.")
		if channel.type not in PROXY_CHANNEL_TYPES :
			return await interaction.followup.send("Characters cannot post in this kind of channel.")
		AutoproxyTransactions().set(interaction.user.id, interaction.guild_id, channel.id, character.id)
		note = ""
		if not Progression.is_tracked(channel) and not ConfigData().get_toggle(interaction.guild_id,
		                                                                        ConfigMapping.PROXY_OUTSIDE_RP) :
			note = "\nThis is not a roleplay channel, so nothing is posted as a character here until staff make it one."
		await interaction.followup.send(f"Everything you type here is now posted as {character.name}. "
		                                f"Use `/character autoproxy` without a name to stop.{note}")

	# == viewing ==

	# ============================================================
	@app_commands.command(name="list", description="Lists your characters on this server")
	async def list_characters(self, interaction: discord.Interaction) :
		"""
		Lists your characters on this server with their review state, level and stats.
		"""
		await interaction.response.defer(ephemeral=True)
		characters = CharacterTransactions().get_all(interaction.user.id, interaction.guild_id)
		elsewhere = GlobalCharacters.visible(interaction.guild, interaction.user.id)
		if not characters and not elsewhere :
			return await interaction.followup.send("You have no characters here yet. Make one with `/character create`.")
		embed = discord.Embed(title="Your characters")
		for character in characters[:25] :
			state = STATE_LABELS.get(character.state, character.state)
			if character.state == APPROVED and character.pending_changes :
				state += ", changes waiting for review"
			if character.is_global :
				state += ", global"
			embed.add_field(name=character.name[:256], inline=False,
			                value=f"{state}\nLevel {character.level} · {Card.stats_text(character)}\n"
			                      f"Speaks with {Card.trigger_text(character.prefix, character.suffix)}")
		for character in elsewhere[:max(0, 25 - len(characters))] :
			embed.add_field(name=character.name[:256], inline=False,
			                value=f"Global, from {GlobalCharacters.home_name(self.bot, character)} (shown here only)\n"
			                      f"Level {character.level} · {Card.stats_text(character)}")
		await interaction.followup.send(embed=embed)

	# ============================================================
	@app_commands.command(name="profile", description="Shows one of your characters")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def profile(self, interaction: discord.Interaction, name: str) :
		"""
		Shows one of your characters: its sheet, SPECIAL stats, level and how you speak as it.
		"""
		await interaction.response.defer()
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name)
		if character is None and (other := GlobalCharacters.find(interaction.guild, interaction.user.id, name)) :
			return await self._send_card(interaction, other, self._global_note(other))
		if (character := await self._own_character(interaction, name)) is None :
			return
		await self._send_card(interaction, character)

	# ============================================================
	def _global_note(self, character: Characters) -> str :
		return (f"Global character from {GlobalCharacters.home_name(self.bot, character)}. It can only post and "
		        f"grow there.")

	# ============================================================
	@app_commands.command(name="show", description="Shows another member's character")
	async def show(self, interaction: discord.Interaction, member: discord.Member, name: str) :
		"""
		Shows another member's approved character. Staff (Manage Messages) can also see characters that are not
		approved yet. On a small server (fewer than 10 members), this also finds the member's global characters from
		their other servers.
		"""
		await interaction.response.defer()
		character = CharacterTransactions().get(member.id, interaction.guild_id, name)
		if character is not None and character.state != APPROVED \
				and not interaction.user.guild_permissions.manage_messages :
			character = None
		if character is None and (other := GlobalCharacters.find(interaction.guild, member.id, name)) :
			return await self._send_card(interaction, other, self._global_note(other))
		if character is None :
			return await interaction.followup.send(f"{member.display_name} has no approved character called {name}.")
		await self._send_card(interaction, character)

	# ============================================================
	@app_commands.command(name="global", description="Lets a character's sheet be seen on your small servers")
	@app_commands.autocomplete(name=AutoComplete().approved_character)
	async def make_global(self, interaction: discord.Interaction, name: str, enabled: bool = True) :
		"""
		Makes one of your approved characters global, or stops it with `enabled` set to false. A global character's
		sheet can be viewed with /character show and /character list on every small server you are in (fewer than 10
		members, bots not counted). It still only posts, grows and is reviewed on this server.
		"""
		await interaction.response.defer(ephemeral=True)
		if (character := await self._own_character(interaction, name)) is None :
			return
		if character.state != APPROVED :
			return await interaction.followup.send(f"{character.name} has to be approved by staff first.")
		CharacterTransactions().update(character.id, is_global=enabled)
		logging.info(f"{interaction.user.name} set character {character.id} global={enabled}")
		if enabled :
			return await interaction.followup.send(
				f"{character.name} is now global: their sheet shows on your small servers (fewer than 10 members). "
				f"They still only post and grow here.")
		await interaction.followup.send(f"{character.name} is no longer global.")

	# == the player's own extra fields ==

	# ============================================================
	async def _change_extras(self, interaction: discord.Interaction, character: Characters, extras: list[dict],
	                         done: str) -> None :
		"""Saves a character's new list of extra fields, through a staff review when the server asks for one."""
		if character.state != APPROVED :
			CharacterInfoTransactions().replace_extras(character.id, extras)
			if character.state == PENDING :
				# Reviewers should decide on what the character looks like now.
				await CharacterFlow.post_review(self.bot, character)
			return await interaction.followup.send(done)
		outcome, character, _ = Edits.submit(character, {"extras" : extras})
		if outcome == REVIEW :
			await CharacterFlow.post_review(self.bot, character)
			return await interaction.followup.send(f"{done} Staff review this change before it shows.")
		if outcome == APPLIED :
			await ForumPost.sync(self.bot, character)
		await interaction.followup.send(done)

	# ============================================================
	@staticmethod
	def _extras(character: Characters) -> list[dict] :
		"""The character's extra fields as they will be once the changes waiting for review are approved."""
		pending = (character.pending_changes or {}).get("extras")
		if character.state == APPROVED and pending is not None :
			return [dict(extra) for extra in pending]
		return [{"key" : info.key, "value" : info.value} for info in
		        CharacterInfoTransactions().get_extras(character.id)]

	# ============================================================
	@staticmethod
	def _find_extra(extras: list[dict], key: str) -> dict | None :
		return next((extra for extra in extras if extra["key"].lower() == key.lower()), None)

	# ============================================================
	@app_commands.command(name="add_info", description="Adds a field of your own to your character")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def add_info(self, interaction: discord.Interaction, name: str, key: app_commands.Range[str, 1, 100],
	                   value: app_commands.Range[str, 1, 4000]) :
		"""
		Adds a field of your own to one of your characters, on top of the server's sheet. Your fields show after the
		sheet, in their own order.
		"""
		await interaction.response.defer(ephemeral=True)
		if (character := await self._own_character(interaction, name)) is None :
			return
		problem = SheetAbilities.reserved_problem(key)
		if problem :
			return await interaction.followup.send(problem)
		extras = self._extras(character)
		taken = [field.label.lower() for field in SheetFieldTransactions().get_all(interaction.guild_id)]
		if self._find_extra(extras, key) is not None or key.lower() in taken :
			return await interaction.followup.send(f"{character.name} already has a field called {key}.")
		if len(extras) >= MAX_EXTRA_FIELDS :
			return await interaction.followup.send(f"A character can have at most {MAX_EXTRA_FIELDS} extra fields.")
		extras.append({"key" : key, "value" : value})
		await self._change_extras(interaction, character, extras, f"Added {key} to {character.name}.")

	# ============================================================
	@app_commands.command(name="edit_info", description="Changes one of your own fields on your character")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def edit_info(self, interaction: discord.Interaction, name: str, key: str,
	                    value: app_commands.Range[str, 1, 4000]) :
		"""
		Changes the value of a field you added yourself. Answers to the server's sheet are changed with
		/character edit.
		"""
		await interaction.response.defer(ephemeral=True)
		if (character := await self._own_character(interaction, name)) is None :
			return
		extras = self._extras(character)
		if (extra := self._find_extra(extras, key)) is None :
			return await interaction.followup.send(f"{character.name} has no extra field called {key}.")
		extra["value"] = value
		await self._change_extras(interaction, character, extras, f"Updated {extra['key']} of {character.name}.")

	# ============================================================
	@app_commands.command(name="remove_info", description="Removes one of your own fields from your character")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def remove_info(self, interaction: discord.Interaction, name: str, key: str) :
		"""
		Removes a field you added yourself.
		"""
		await interaction.response.defer(ephemeral=True)
		if (character := await self._own_character(interaction, name)) is None :
			return
		extras = self._extras(character)
		if (extra := self._find_extra(extras, key)) is None :
			return await interaction.followup.send(f"{character.name} has no extra field called {key}.")
		extras.remove(extra)
		await self._change_extras(interaction, character, extras, f"Removed {extra['key']} from {character.name}.")

	# ============================================================
	@app_commands.command(name="move_info", description="Changes the order of your own fields on your character")
	@app_commands.autocomplete(name=AutoComplete().character)
	async def move_info(self, interaction: discord.Interaction, name: str, key: str,
	                    position: app_commands.Range[int, 1, 100]) :
		"""
		Moves a field you added yourself to another position among your own fields; position 1 shows first.
		"""
		await interaction.response.defer(ephemeral=True)
		if (character := await self._own_character(interaction, name)) is None :
			return
		extras = self._extras(character)
		if (extra := self._find_extra(extras, key)) is None :
			return await interaction.followup.send(f"{character.name} has no extra field called {key}.")
		extras.remove(extra)
		position = max(1, min(position, len(extras) + 1))
		extras.insert(position - 1, extra)
		await self._change_extras(interaction, character, extras,
		                          f"Moved {extra['key']} of {character.name} to position {position}.")


	# ============================================================
	@app_commands.command(name="armor_proficiency", description="Sets the heaviest armor a character is trained in")
	@app_commands.autocomplete(name=AutoComplete().character)
	@app_commands.choices(level=[Choice(name=value.capitalize(), value=value) for value in Rules.ARMOR_CLASSES])
	async def armor_proficiency(self, interaction: discord.Interaction, name: str, level: Choice[str],
	                            member: discord.Member = None) :
		"""
		Sets the heaviest armor your character can wear without a penalty: clothing, light, medium or heavy. Armor
		heavier than this gives -2 to hit for each step. You set it once; after that staff can change it with
		`member`. Until it is set, the "Armor proficiency" answer on the sheet is used, if there is one.
		"""
		await interaction.response.defer(ephemeral=True)
		staff = interaction.user.guild_permissions.manage_messages
		if member is not None and member.id != interaction.user.id :
			if not staff :
				return await interaction.followup.send("Only staff can change another member's character.")
			character = CharacterTransactions().get(member.id, interaction.guild_id, name)
			if character is None :
				return await interaction.followup.send(f"{member.display_name} has no character called {name}.")
		elif (character := await self._own_character(interaction, name)) is None :
			return
		updated, text = Proficiency.set_armor(character, level.value, staff=staff)
		if updated is not None :
			logging.info(f"{interaction.user.name} set armor proficiency {level.value} on character {character.id}")
		await interaction.followup.send(text)

async def setup(bot) :
	await bot.add_cog(Character(bot))
