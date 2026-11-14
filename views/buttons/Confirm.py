import discord
from discord_py_utilities.messages import send_response


class Confirm(discord.ui.View) :
	"""Confirm / cancel buttons that only the user who started the action can press."""

	def __init__(self, user_id: int, confirm_label: str = "Confirm", timeout: float = 120) :
		super().__init__(timeout=timeout)
		self.user_id = user_id
		self.value: bool | None = None
		self.confirm.label = confirm_label

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		if interaction.user.id != self.user_id :
			await send_response(interaction, "Only the person who ran the command can answer this.", ephemeral=True)
			return False
		return True

	# ============================================================
	async def _answer(self, interaction: discord.Interaction, value: bool) :
		self.value = value
		for item in self.children :
			item.disabled = True
		await interaction.response.edit_message(view=self)
		self.stop()

	# ============================================================
	@discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
	async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) :
		await self._answer(interaction, True)

	# ============================================================
	@discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
	async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) :
		await self._answer(interaction, False)


# ============================================================
async def ask(interaction: discord.Interaction, message: str, confirm_label: str = "Confirm") -> bool :
	"""Asks once; True only when the user presses confirm before the buttons time out."""
	view = Confirm(interaction.user.id, confirm_label)
	if interaction.response.is_done() :
		await interaction.followup.send(message, view=view, ephemeral=True)
	else :
		await interaction.response.send_message(message, view=view, ephemeral=True)
	await view.wait()
	return view.value is True


# ============================================================
async def double_confirm(interaction: discord.Interaction, first: str, second: str) -> bool :
	"""Asks twice, with separate messages and buttons, before a destructive action."""
	if not await ask(interaction, first) :
		return False
	return await ask(interaction, second, confirm_label="Yes, I'm sure")
