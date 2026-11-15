"""The steps of /config setup guided: one ephemeral message that each answer edits into the next step.

Every answer is a fresh component interaction whose token lasts 15 minutes, so the walkthrough keeps working however
long it takes in total; a single step times out after STEP_TIMEOUT.
"""
import discord
from discord_py_utilities.messages import send_response

STEP_TIMEOUT = 600

PICK = "pick"
CREATE = "create"
SKIP = "skip"
SAVE = "save"
CANCEL = "cancel"
PACK = "pack:"


class StepView(discord.ui.View) :
	"""Buttons and selects for one step. Only the user who started setup can answer."""

	def __init__(self, user_id: int) :
		super().__init__(timeout=STEP_TIMEOUT)
		self.user_id = user_id
		# What was answered (PICK, CREATE, ...), None when the step timed out.
		self.answer: str | None = None
		# The channels picked in a select.
		self.picked: list = []
		# The interaction of the answer; the next step is shown through it.
		self.interaction: discord.Interaction | None = None

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		if interaction.user.id != self.user_id :
			await send_response(interaction, "Only the person who started setup can answer this.", ephemeral=True)
			return False
		return True

	# ============================================================
	async def finish(self, interaction: discord.Interaction, answer: str, picked: list | None = None) :
		self.answer = answer
		self.picked = picked or []
		self.interaction = interaction
		await interaction.response.defer()
		self.stop()

	# ============================================================
	def button(self, label: str, answer: str, style=discord.ButtonStyle.secondary, row: int = 4) :
		button = discord.ui.Button(label=label[:80], style=style, row=row)

		async def callback(interaction: discord.Interaction) :
			await self.finish(interaction, answer)

		button.callback = callback
		self.add_item(button)
		return button

	# ============================================================
	def add_skip_and_cancel(self, skip_label: str = "Skip") :
		self.button(skip_label, SKIP)
		self.button("Cancel setup", CANCEL, discord.ButtonStyle.danger)


class ChannelStepView(StepView) :
	"""Pick a channel, let the bot create (or reuse) one, or skip."""

	def __init__(self, user_id: int, channel_types: list[discord.ChannelType], create_label: str | None,
	             multiple: bool = False, skip_label: str = "Skip") :
		super().__init__(user_id)
		select = discord.ui.ChannelSelect(channel_types=channel_types, min_values=1, max_values=25 if multiple else 1,
		                                  placeholder="Pick channels" if multiple else "Pick a channel", row=0)

		async def callback(interaction: discord.Interaction) :
			await self.finish(interaction, PICK, list(select.values))

		select.callback = callback
		self.add_item(select)
		if create_label :
			self.button(create_label, CREATE, discord.ButtonStyle.primary)
		self.add_skip_and_cancel(skip_label)


class SettingsStepView(StepView) :
	"""One select per setting, preset to the current value; nothing is saved until Save is pressed."""

	def __init__(self, user_id: int, settings: list[tuple[str, dict[str, str], str]]) :
		"""
		:param settings: (key, {value: label}, current value) per setting, at most four.
		"""
		super().__init__(user_id)
		self.chosen: dict[str, str] = {key : current for key, _, current in settings}
		for row, (key, labels, current) in enumerate(settings) :
			self.add_item(self.select(key, labels, current, row))
		self.button("Save and continue", SAVE, discord.ButtonStyle.success)
		self.add_skip_and_cancel("Keep as is")

	# ============================================================
	def select(self, key: str, labels: dict[str, str], current: str, row: int) -> discord.ui.Select :
		options = [discord.SelectOption(label=label[:100], value=value, default=value == current)
		           for value, label in labels.items()]
		select = discord.ui.Select(options=options, min_values=1, max_values=1, row=row)

		async def callback(interaction: discord.Interaction) :
			self.chosen[key] = select.values[0]
			# Keep the pick shown when the message is redrawn.
			for option in select.options :
				option.default = option.value == select.values[0]
			await interaction.response.edit_message(view=self)

		select.callback = callback
		return select


class PackStepView(StepView) :
	"""A button per gear pack, or skip."""

	def __init__(self, user_id: int, packs: list[tuple[str, str]]) :
		super().__init__(user_id)
		# Four rows of buttons above the skip/cancel row.
		for index, (name, title) in enumerate(packs[:20]) :
			self.button(f"Import {title}", f"{PACK}{name}", discord.ButtonStyle.primary, row=index // 5)
		self.add_skip_and_cancel()
