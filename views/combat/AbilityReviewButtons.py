import discord

from classes.combat.AbilityFlow import AbilityFlow
from views.buttons.ReviewButtons import REASON_LIMIT


class AbilityDenyReason(discord.ui.Modal, title="Deny") :
	"""Asks the reviewer why; the reason is sent to the creator."""
	reason = discord.ui.TextInput(label="Reason (sent to the player)", style=discord.TextStyle.paragraph,
	                              max_length=REASON_LIMIT, required=True)

	async def on_submit(self, interaction: discord.Interaction) :
		await AbilityFlow.decide(interaction, approve=False, reason=self.reason.value)


class AbilityReviewButtons(discord.ui.View) :
	"""Approve / Deny under an ability's or magic school's review card."""

	# Persistent: registered with bot.add_view in setup_hook; the record is found through the card's message id.

	def __init__(self) :
		super().__init__(timeout=None)

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		if interaction.user.guild_permissions.manage_messages :
			return True
		await interaction.response.send_message("You need the Manage Messages permission to review.", ephemeral=True)
		return False

	# ============================================================
	@discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="ability_review_approve")
	async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) :
		await AbilityFlow.decide(interaction, approve=True)

	# ============================================================
	@discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="ability_review_deny")
	async def deny(self, interaction: discord.Interaction, button: discord.ui.Button) :
		await interaction.response.send_modal(AbilityDenyReason())
