import discord

from classes.species.SpeciesFlow import SpeciesFlow
from views.buttons.ReviewButtons import REASON_LIMIT


class SpeciesDenyReason(discord.ui.Modal, title="Deny") :
	"""Asks the reviewer why; the reason is sent to the species' creator."""
	reason = discord.ui.TextInput(label="Reason (sent to the player)", style=discord.TextStyle.paragraph,
	                              max_length=REASON_LIMIT, required=True)

	async def on_submit(self, interaction: discord.Interaction) :
		await SpeciesFlow.decide(interaction, approve=False, reason=self.reason.value)


class SpeciesReviewButtons(discord.ui.View) :
	"""Approve / Deny under a species' review card. Persistent: registered with bot.add_view in setup_hook."""

	def __init__(self) :
		super().__init__(timeout=None)

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		if interaction.user.guild_permissions.manage_messages :
			return True
		await interaction.response.send_message("You need the Manage Messages permission to review species.",
		                                        ephemeral=True)
		return False

	# ============================================================
	@discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="species_review_approve")
	async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) :
		await SpeciesFlow.decide(interaction, approve=True)

	# ============================================================
	@discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="species_review_deny")
	async def deny(self, interaction: discord.Interaction, button: discord.ui.Button) :
		await interaction.response.send_modal(SpeciesDenyReason())
