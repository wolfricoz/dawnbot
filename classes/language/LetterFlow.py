"""Letters (design/roleplay-tools.md, section 14): writing, delivery after a delay, the inbox, replies, reports and
interception. Letters are private: staff only read one that was reported, or intercepted where a server turned
interception on (Rico's call)."""
import logging
from datetime import datetime, timedelta, timezone

import discord

from classes.kernel import RoleplaySettings
from classes.kernel.ConfigData import ConfigData
from classes.language.LanguageFlow import LanguageFlow
from classes.world import Calendar
from database.database import Characters, Letters
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.LanguageTransactions import LanguageTransactions
from database.transactions.WorldTransactions import WorldTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import reply

IN_TRANSIT = "in_transit"
HELD = "held"
DELIVERED = "delivered"
RETURNED = "returned"
DESTROYED = "destroyed"
EXPRESS_HOURS = 1
COURIER = "courier"
LETTER_COLOUR = discord.Colour.from_rgb(222, 196, 145)


class LetterForm(discord.ui.Modal) :
	"""A letter's subject and text."""

	def __init__(self, title: str, on_submit, subject: str | None = None) :
		super().__init__(title=title[:45])
		self.handler = on_submit
		self.subject = discord.ui.TextInput(label="Subject", max_length=200, default=subject)
		self.body = discord.ui.TextInput(label="Letter", style=discord.TextStyle.paragraph, max_length=4000)
		self.add_item(self.subject)
		self.add_item(self.body)

	# ============================================================
	async def on_submit(self, interaction: discord.Interaction) :
		await self.handler(interaction, self.subject.value, self.body.value)


class LetterFlow :

	# ============================================================
	@staticmethod
	def delay(guild: discord.Guild, sender: Characters, recipient: Characters, express: bool) -> timedelta :
		"""How long a letter takes: an hour by express courier; otherwise the route between the characters (when travel
		is on and in-world time flows), or LETTER_DELAY real hours."""
		if express :
			return timedelta(hours=EXPRESS_HOURS)
		hours = RoleplaySettings.number(guild.id, ConfigMapping.LETTER_DELAY)
		if RoleplaySettings.toggle(guild.id, ConfigMapping.TRAVEL) :
			from classes.world.WorldFlow import WorldFlow

			ratio = Calendar.flow_ratio(RoleplaySettings.text(guild.id, ConfigMapping.TIME_FLOW))
			here, there = WorldFlow.where_is(guild, sender.id), WorldFlow.where_is(guild, recipient.id)
			route = WorldTransactions().route(here.id, there.id) if here and there and here.id != there.id else None
			if route is not None and ratio :
				return timedelta(hours=route.hours / ratio)
		return timedelta(hours=hours)

	# ============================================================
	@staticmethod
	async def start(interaction: discord.Interaction, sender_name: str, recipient_id: str, language_name: str | None,
	                express: bool, sealed: bool, reply_to: Letters | None = None,
	                guild: discord.Guild | None = None) -> None :
		# Replies come from the letter's DM, where the interaction has no server.
		guild = guild or interaction.guild
		sender = CharacterTransactions().get(interaction.user.id, guild.id, sender_name)
		if sender is None or sender.state != APPROVED :
			return await reply(interaction, f"You have no approved character called {sender_name}.")
		try :
			recipient = CharacterTransactions().get_by_id(int(recipient_id))
		except (TypeError, ValueError) :
			recipient = None
		if recipient is None or recipient.guild_id != guild.id or recipient.state != APPROVED :
			return await reply(interaction, "Pick the recipient from the list.")
		if recipient.id == sender.id :
			return await reply(interaction, "A character can't write to itself.")
		language = None
		if language_name :
			language = LanguageTransactions().find(guild.id, language_name)
			if language is None :
				return await reply(interaction, f"There is no language called {language_name}.")
			if not language.common and language.id not in LanguageFlow.known(sender) :
				return await reply(interaction, f"{sender.name} doesn't write {language.name}.")
		cost = 0
		if express and ConfigData().get_key(guild.id, ConfigMapping.ECONOMY) == "economy" :
			cost = RoleplaySettings.number(guild.id, ConfigMapping.COURIER_COST)
			if sender.currency < cost :
				name = ConfigData().get_key(guild.id, ConfigMapping.CURRENCY_NAME)
				return await reply(interaction, f"An express courier costs {cost} {name}; {sender.name} has "
				                                f"{sender.currency}.")

		async def written(form_interaction: discord.Interaction, subject: str, body: str) :
			await LetterFlow.send(form_interaction, guild, sender, recipient, subject, body, language, express, sealed,
			                      cost, reply_to)

		title = f"To {recipient.name}"
		if RoleplaySettings.toggle(guild.id, ConfigMapping.LETTER_INTERCEPT) :
			title += " (can be intercepted)"
		subject = f"Re: {reply_to.subject}"[:200] if reply_to else None
		await interaction.response.send_modal(LetterForm(title, written, subject))

	# ============================================================
	@staticmethod
	async def send(interaction: discord.Interaction, guild: discord.Guild, sender: Characters, recipient: Characters,
	               subject: str, body: str, language, express: bool, sealed: bool, cost: int,
	               reply_to: Letters | None) -> None :
		from classes.gear.Gear import Gear
		from classes.world.WorldFlow import WorldFlow

		if cost :
			updated, problem = Gear.change_currency(sender, -cost, COURIER, interaction.user.id,
			                                        note=f"Express letter to {recipient.name}")
			if problem :
				return await reply(interaction, problem)
		deliver_at = datetime.now(timezone.utc) + LetterFlow.delay(guild, sender, recipient, express)
		letter = LanguageTransactions().add_letter(guild.id, from_character_id=sender.id,
		                                           to_character_id=recipient.id, from_uid=interaction.user.id,
		                                           from_name=sender.name, to_name=recipient.name,
		                                           subject=subject[:200], body=body,
		                                           language_id=language.id if language else None, sealed=sealed,
		                                           express=express, world_date=WorldFlow.world_date(guild.id),
		                                           deliver_at=deliver_at, state=IN_TRANSIT,
		                                           reply_to_id=reply_to.id if reply_to else None)
		if letter is None :
			return await reply(interaction, "Something went wrong sending the letter; please try again.")
		warning = "\n-# Letters on this server can be intercepted by GMs." if \
			RoleplaySettings.toggle(guild.id, ConfigMapping.LETTER_INTERCEPT) else ""
		await reply(interaction, f"✉️ {sender.name}'s letter to {recipient.name} is on its way and arrives "
		                         f"<t:{int(deliver_at.timestamp())}:R>.{warning}")

	# == delivery ==

	# ============================================================
	@staticmethod
	def embed(letter: Letters, reader: Characters | None, guild_id: int) -> discord.Embed :
		text = LanguageFlow.letter_text(guild_id, letter.language_id, letter.body, reader)
		embed = discord.Embed(title=f"✉️ {letter.subject}"[:256], description=text[:4096], colour=LETTER_COLOUR)
		embed.set_author(name=f"From {letter.from_name} to {letter.to_name}"[:256])
		notes = []
		if letter.world_date :
			notes.append(f"Written {letter.world_date.get('text')}")
		language = LanguageTransactions().get(letter.language_id)
		if language is not None and not language.common :
			notes.append(f"In {language.name}")
		if letter.sealed :
			notes.append("Seal broken!" if letter.seal_broken else "Sealed")
		if letter.express :
			notes.append("Express")
		embed.set_footer(text=" · ".join(notes)[:2048] or f"Letter #{letter.id}")
		return embed

	# ============================================================
	@staticmethod
	async def deliver_due(bot: discord.Client, now: datetime | None = None) -> None :
		for letter in LanguageTransactions().due_letters(now or datetime.now(timezone.utc)) :
			try :
				await LetterFlow.deliver(bot, letter)
			except Exception as e :
				logging.error(f"Delivering letter {letter.id} failed: {e}", exc_info=True)

	# ============================================================
	@staticmethod
	async def deliver(bot: discord.Client, letter: Letters) -> None :
		from views.letters.LetterButtons import letter_view

		recipient = CharacterTransactions().get_by_id(letter.to_character_id) if letter.to_character_id else None
		if recipient is None or recipient.state != APPROVED :
			LanguageTransactions().update_letter(letter.id, state=RETURNED)
			await LetterFlow._dm(bot, letter.from_uid, f"✉️ Your letter to {letter.to_name} (“{letter.subject}”) came "
			                                           f"back: nobody could deliver it.")
			return
		LanguageTransactions().update_letter(letter.id, state=DELIVERED)
		letter = LanguageTransactions().letter(letter.id)
		embed = LetterFlow.embed(letter, recipient, letter.guild_id)
		sent = await LetterFlow._dm(bot, recipient.uid, f"📬 A letter for **{recipient.name}**:", embed,
		                            letter_view(letter.id))
		if sent :
			return
		guild = bot.get_guild(letter.guild_id)
		channel = await ConfigData().get_channel(guild, ConfigMapping.LETTER_CHANNEL, optional=True) if guild else None
		if channel is not None :
			try :
				await channel.send(f"📬 A letter for **{recipient.name}** (<@{recipient.uid}>). Read it with "
				                   f"/letter inbox.", allowed_mentions=discord.AllowedMentions(users=True))
			except discord.HTTPException :
				pass

	# ============================================================
	@staticmethod
	async def _dm(bot: discord.Client, uid: int, text: str, embed: discord.Embed | None = None,
	              view: discord.ui.View | None = None) -> bool :
		user = bot.get_user(uid)
		try :
			user = user or await bot.fetch_user(uid)
			await user.send(text, embed=embed or discord.utils.MISSING, view=view or discord.utils.MISSING)
			return True
		except discord.HTTPException :
			return False

	# == reading ==

	# ============================================================
	@staticmethod
	def may_read(letter: Letters, uid: int) -> bool :
		"""The recipient's player or the sender's."""
		recipient = CharacterTransactions().get_by_id(letter.to_character_id) if letter.to_character_id else None
		return uid == letter.from_uid or (recipient is not None and recipient.uid == uid)

	# ============================================================
	@staticmethod
	async def read(interaction: discord.Interaction, letter_id: int) -> None :
		letter = LanguageTransactions().letter(letter_id)
		if letter is None or letter.guild_id not in (interaction.guild_id, None) or \
				not LetterFlow.may_read(letter, interaction.user.id) :
			return await reply(interaction, "There is no such letter for you.")
		if letter.state not in (DELIVERED, RETURNED) and interaction.user.id != letter.from_uid :
			return await reply(interaction, "That letter hasn't arrived yet.")
		recipient = CharacterTransactions().get_by_id(letter.to_character_id) if letter.to_character_id else None
		reader = recipient if recipient is not None and recipient.uid == interaction.user.id else None
		if reader is not None and letter.read_at is None :
			LanguageTransactions().update_letter(letter.id, read_at=datetime.now(timezone.utc))
		from views.letters.LetterButtons import letter_view

		view = letter_view(letter.id) if reader is not None else None
		embed = LetterFlow.embed(letter, reader, letter.guild_id) if reader is not None else \
			LetterFlow.embed(letter, CharacterTransactions().get_by_id(letter.from_character_id), letter.guild_id)
		await interaction.response.send_message(embed=embed, view=view or discord.utils.MISSING, ephemeral=True)

	# ============================================================
	@staticmethod
	async def report(interaction: discord.Interaction, letter_id: int) -> None :
		letter = LanguageTransactions().letter(letter_id)
		if letter is None or not LetterFlow.may_read(letter, interaction.user.id) :
			return await reply(interaction, "There is no such letter for you.")
		if letter.reported_at :
			return await reply(interaction, "This letter was already reported.")
		LanguageTransactions().update_letter(letter.id, reported_at=datetime.now(timezone.utc))
		guild = interaction.client.get_guild(letter.guild_id)
		channel = await ConfigData().get_channel(guild, ConfigMapping.MODLOG, optional=True) if guild else None
		if channel is not None :
			embed = LetterFlow.embed(letter, None, letter.guild_id)
			embed.description = letter.body[:4096]
			embed.add_field(name="Reported by", value=f"<@{interaction.user.id}>", inline=True)
			embed.add_field(name="Sender's player", value=f"<@{letter.from_uid}>", inline=True)
			try :
				await channel.send(f"🚩 Letter #{letter.id} was reported.", embed=embed,
				                   allowed_mentions=discord.AllowedMentions.none())
			except discord.HTTPException :
				pass
		await reply(interaction, "Reported to the staff. Thank you.")

	# ============================================================
	@staticmethod
	async def start_reply(interaction: discord.Interaction, letter_id: int) -> None :
		letter = LanguageTransactions().letter(letter_id)
		recipient = CharacterTransactions().get_by_id(letter.to_character_id) if letter and letter.to_character_id \
			else None
		if letter is None or recipient is None or recipient.uid != interaction.user.id :
			return await reply(interaction, "Only the recipient can reply.")
		if letter.from_character_id is None :
			return await reply(interaction, "The sender no longer exists.")
		language = LanguageTransactions().get(letter.language_id)
		known = language is not None and (language.common or language.id in LanguageFlow.known(recipient))
		guild = interaction.client.get_guild(letter.guild_id)
		if guild is None :
			return await reply(interaction, "I'm no longer on that server.")
		await LetterFlow.start(interaction, recipient.name, str(letter.from_character_id),
		                       language.name if known else None, False, letter.sealed, reply_to=letter, guild=guild)

	# == interception ==

	# ============================================================
	@staticmethod
	def transit_lines(guild_id: int) -> list[str] :
		intercept = RoleplaySettings.toggle(guild_id, ConfigMapping.LETTER_INTERCEPT)
		lines = []
		for letter in LanguageTransactions().in_transit(guild_id) :
			held = " · ⏸️ held" if letter.state == HELD else ""
			subject = f" · “{letter.subject}”" if intercept else ""
			lines.append(f"#{letter.id} · {letter.from_name} → {letter.to_name}{subject} · arrives "
			             f"<t:{int(letter.deliver_at.timestamp())}:R>{held}")
		return lines

	# ============================================================
	@staticmethod
	async def intercept(interaction: discord.Interaction, letter_id: int, action: str) -> None :
		if not RoleplaySettings.toggle(interaction.guild_id, ConfigMapping.LETTER_INTERCEPT) :
			return await reply(interaction, "Interception is off on this server (/config roleplay letter_intercept).")
		letter = LanguageTransactions().letter(letter_id)
		if letter is None or letter.guild_id != interaction.guild_id or letter.state not in (IN_TRANSIT, HELD) :
			return await reply(interaction, "There is no such letter in transit.")
		if action == "read" :
			LanguageTransactions().update_letter(letter.id, intercepted_by=interaction.user.id,
			                                     seal_broken=letter.seal_broken or letter.sealed)
			embed = LetterFlow.embed(letter, None, letter.guild_id)
			embed.description = letter.body[:4096]
			return await interaction.response.send_message(embed=embed, ephemeral=True)
		changes = {"intercepted_by" : interaction.user.id}
		if action == "hold" :
			changes["state"] = HELD
		elif action == "deliver" :
			changes |= {"state" : IN_TRANSIT, "deliver_at" : datetime.now(timezone.utc)}
		elif action == "destroy" :
			changes["state"] = DESTROYED
		LanguageTransactions().update_letter(letter.id, **changes)
		await reply(interaction, {"hold" : "⏸️ Held.", "deliver" : "📨 It will be delivered now.",
		                          "destroy" : "🔥 Destroyed; it never arrives."}[action])
