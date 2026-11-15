"""/config setup guided: walks staff through the channels and main settings, one step per screen.

Every answer is saved straight away, so cancelling (or a step timing out) keeps what was set, and running setup again
picks up from there: steps show the current value and can keep it.
"""
import logging

import discord

from classes.gear.GearPost import GearPost
from classes.gear.Packs import Packs
from classes.kernel.Queue import Queue
from classes.kernel.ServerSync import sync_server
from classes.progression.Progression import Progression
from classes.setup.BotSetup import BotSetup, CHANNEL_STEPS, ChannelStep, ROLEPLAY_CHANNEL, SETTING_LABELS, \
	SETTING_PAGES, SetupReport
from classes.support.PermissionNotice import humanise
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.buttons.SetupSteps import CANCEL, CREATE, ChannelStepView, PACK, PICK, PackStepView, SAVE, \
	SettingsStepView, StepView

INTRO = ("Let's set up the roleplay features. Every step can be skipped, and each answer is saved straight away, "
         "so you can stop at any time and run `/config setup` again later.")
ROLEPLAY_DESCRIPTION = ("Text channels and forums where roleplay happens. Posts there earn XP (and currency for "
                        "posts made as a character), and members can post as their characters there. Threads count "
                        "with their channel. Messages shorter than 300 characters are removed there.")


class SetupEnded(Exception) :
	"""The walkthrough stopped: cancelled or timed out. The user has been told."""


class GuidedSetup :

	def __init__(self, bot: discord.Client, interaction: discord.Interaction) :
		self.bot = bot
		self.guild = interaction.guild
		self.user_id = interaction.user.id
		# The latest interaction; every answer brings a new one, with a fresh 15-minute token.
		self.interaction = interaction
		self.started = False
		self.report = SetupReport()
		# Categories this run created, by section.
		self.made = {}
		# The result of the previous answer, shown above the next step.
		self.note: str | None = None
		self.packs = Packs.available()
		self.total = len(CHANNEL_STEPS) + 1 + len(SETTING_PAGES) + (1 if self.packs else 0)
		self.number = 0

	# ============================================================
	async def run(self) :
		sync_server(self.guild)
		try :
			for step in CHANNEL_STEPS :
				await self.channel_step(step)
			await self.roleplay_step()
			for title, keys in SETTING_PAGES :
				await self.settings_step(title, keys)
			if self.packs :
				await self.pack_step()
		except SetupEnded :
			return
		logging.info(f"{self.interaction.user.name} finished guided setup in {self.guild.name}")
		await self.end(self.note, BotSetup.summary(self.guild, self.report))

	# == showing steps ==

	# ============================================================
	def header(self, title: str, extra: str = "") -> str :
		self.number += 1
		header = f"**Step {self.number} of {self.total}: {title}**{extra}"
		return f"{INTRO}\n\n{header}" if self.number == 1 else header

	# ============================================================
	async def ask(self, content: str, view: StepView) -> StepView :
		"""Shows a step and waits for the answer. Raises SetupEnded when the user cancels or the step times out."""
		if self.note :
			content = f"{self.note}\n\n{content}"
			self.note = None
		if not self.started :
			await self.interaction.response.send_message(content, view=view, ephemeral=True)
			self.started = True
		else :
			await self.interaction.edit_original_response(content=content, embed=None, view=view)
		await view.wait()
		if view.answer is None :
			await self.end("Setup timed out. What you set so far is saved; run `/config setup` to carry on.")
			raise SetupEnded()
		self.interaction = view.interaction
		if view.answer == CANCEL :
			await self.end("Setup cancelled. What you set before cancelling is saved.")
			raise SetupEnded()
		return view

	# ============================================================
	async def end(self, content: str | None, embed: discord.Embed | None = None) :
		try :
			await self.interaction.edit_original_response(content=content, embed=embed, view=None)
		except discord.HTTPException as e :
			logging.info(f"Could not show the end of setup in {self.guild.name}: {e}")

	# ============================================================
	def why_not_create(self) -> str | None :
		"""Why the bot cannot create channels here, or None when it can."""
		if missing := BotSetup.missing_auto_permissions(self.guild) :
			return f"I couldn't create it: I'm missing {', '.join(humanise(missing))}."
		return None

	# == steps ==

	# ============================================================
	async def channel_step(self, step: ChannelStep) :
		current = BotSetup.current(self.guild, step)
		existing = None if current else BotSetup.by_name(self.guild, step)
		lines = [self.header(step.title, " (required)" if step.required else " (optional)"), step.description]
		skip_label = "Skip"
		if current :
			lines.append(f"Currently {current.mention}. Pick another channel, or keep it.")
			create_label = None
			skip_label = "Keep it"
		elif existing :
			lines.append(f"Not set yet. {existing.mention} looks like the one: use it, pick another, or skip.")
			create_label = f"Use #{existing.name}"
		else :
			kind = "forum" if step.forum else "channel"
			lines.append(f"Not set yet. Pick a channel, let me create a #{step.name} {kind}, or skip.")
			create_label = f"Create #{step.name}"
		types = [discord.ChannelType.text] if step.text_only else [discord.ChannelType.text,
		                                                           discord.ChannelType.forum]
		view = await self.ask("\n".join(lines), ChannelStepView(self.user_id, types, create_label,
		                                                       skip_label=skip_label))
		if view.answer == PICK :
			channel = self.guild.get_channel(view.picked[0].id)
			if not BotSetup.fits(step, channel) :
				self.note = f"⚠️ I can't use that channel for {step.title.lower()}; it was left as it was."
				return
			BotSetup.set_channel(self.guild.id, step, channel)
			self.note = f"✅ {step.title} set to {channel.mention}."
		elif view.answer == CREATE :
			if existing is not None :
				BotSetup.set_channel(self.guild.id, step, existing)
				self.note = f"✅ {step.title} set to {existing.mention}."
				return
			if reason := self.why_not_create() :
				self.note = f"⚠️ {reason}"
				return
			try :
				channel = await BotSetup.create(self.guild, step, self.made)
			except discord.HTTPException as e :
				logging.warning(f"Setup could not create {step.name} in {self.guild.name}: {e}")
				self.note = f"⚠️ Discord refused to create #{step.name}: {e.text or e}"
				return
			self.report.created.append(step.key)
			self.note = f"✅ Created {channel.mention} for {step.title.lower()}."

	# ============================================================
	async def roleplay_step(self) :
		roleplay = BotSetup.roleplay_channels(self.guild)
		existing = None
		if not roleplay :
			existing = discord.utils.get(self.guild.text_channels, name=ROLEPLAY_CHANNEL)
		lines = [self.header("Roleplay channels", " (required)"), ROLEPLAY_DESCRIPTION]
		if roleplay :
			lines.append(f"Currently: {', '.join(channel.mention for channel in roleplay)}. Channels you pick are "
			             f"added to these; `/config channel remove` takes one off.")
			create_label = None
		elif existing :
			lines.append(f"None yet. Use {existing.mention}, pick channels, or skip.")
			create_label = f"Use #{existing.name}"
		else :
			lines.append(f"None yet. Pick channels, let me create #{ROLEPLAY_CHANNEL}, or skip.")
			create_label = f"Create #{ROLEPLAY_CHANNEL}"
		view = await self.ask("\n".join(lines), ChannelStepView(
			self.user_id, [discord.ChannelType.text, discord.ChannelType.forum], create_label, multiple=True,
			skip_label="Keep as is" if roleplay else "Skip"))
		if view.answer == PICK :
			added = []
			for picked in view.picked :
				channel = self.guild.get_channel(picked.id)
				if isinstance(channel, (discord.TextChannel, discord.ForumChannel)) and \
						BotSetup.add_roleplay_channel(self.guild.id, channel) :
					# Past messages earn XP too, as with /config channel.
					Queue().add(Progression.count_history(channel), priority=0)
					added.append(channel.mention)
			self.note = (f"✅ Added {', '.join(added)} to the roleplay channels; their history is being counted in "
			             f"the background.") if added else "Those were already roleplay channels."
		elif view.answer == CREATE :
			if existing is not None :
				BotSetup.add_roleplay_channel(self.guild.id, existing)
				Queue().add(Progression.count_history(existing), priority=0)
				self.note = f"✅ {existing.mention} is now a roleplay channel."
				return
			if reason := self.why_not_create() :
				self.note = f"⚠️ {reason}"
				return
			try :
				channel = await BotSetup.create_roleplay_channel(self.guild, self.made)
			except discord.HTTPException as e :
				logging.warning(f"Setup could not create the roleplay channel in {self.guild.name}: {e}")
				self.note = f"⚠️ Discord refused to create #{ROLEPLAY_CHANNEL}: {e.text or e}"
				return
			self.report.created.append(ConfigMapping.XP_CHANNELS)
			self.note = f"✅ Created {channel.mention} as a roleplay channel."

	# ============================================================
	async def settings_step(self, title: str, keys: list[ConfigMapping]) :
		settings = [(key, SETTING_LABELS[key], BotSetup.current_setting(self.guild.id, key)) for key in keys]
		lines = [self.header(title),
		         "Pick what fits your server and save. The menus show the current choice; `/config` can change "
		         "these later."]
		view = await self.ask("\n".join(lines), SettingsStepView(self.user_id, settings))
		if view.answer != SAVE :
			return
		changed = 0
		for key, _, current in settings :
			if view.chosen[key] != current :
				BotSetup.set_setting(self.guild.id, key, view.chosen[key])
				changed += 1
		self.note = f"✅ Saved {changed} setting{'s' if changed != 1 else ''}." if changed else "Nothing changed."

	# ============================================================
	async def pack_step(self) :
		count = len(GearItemTransactions().get_all(self.guild.id))
		lines = [self.header("Gear", " (optional)"),
		         "The shop sells what is in the gear catalog. Import a ready-made pack to fill it (items can be "
		         "edited or removed afterwards, and importing again only adds what is missing), or skip and add gear "
		         "yourself with `/armory add`.",
		         f"The catalog has {count} item{'s' if count != 1 else ''} now."]
		view = await self.ask("\n".join(lines), PackStepView(self.user_id, self.packs))
		if not view.answer.startswith(PACK) :
			return
		name = view.answer[len(PACK) :]
		try :
			added, skipped = Packs.import_into(self.guild.id, name)
		except ValueError as e :
			self.note = f"⚠️ {e}"
			return
		logging.info(f"{self.interaction.user.name} imported gear pack {name} in {self.guild.name} during setup: "
		             f"{len(added)} added, {len(skipped)} skipped")
		self.note = f"✅ Imported {len(added)} item{'s' if len(added) != 1 else ''}"
		self.note += f" ({len(skipped)} were already in the catalog)." if skipped else "."
		if added and GearPost.configured(self.guild.id) :
			Queue().add(self.post_items(added), priority=0)
			self.note += " They are being posted in the gear forum in the background."

	# ============================================================
	async def post_items(self, items: list) :
		failed = 0
		for item in items :
			if not await GearPost.sync(self.bot, item) :
				failed += 1
		if failed :
			logging.warning(f"{failed} gear items could not be posted in {self.guild.name} after setup")
