import discord

from classes.characters.CharacterFlow import CharacterFlow

REASON_LIMIT = 1000


class DenyReason(discord.ui.Modal, title="Deny") :
	"""Asks the reviewer why; the reason is sent to the player."""
	reason = discord.ui.TextInput(label="Reason (sent to the player)", style=discord.TextStyle.paragraph,
	                              max_length=REASON_LIMIT, required=True)

	async def on_submit(self, interaction: discord.Interaction) :
		await CharacterFlow.decide(interaction, approve=False, reason=self.reason.value)


# Persistent: registered with bot.add_view in setup_hook. The character is found through the card's message id, so the
# buttons keep working after a restart.
class ReviewButtons(discord.ui.View) :
	"""Approve / Deny under a character's review card."""

	def __init__(self) :
		super().__init__(timeout=None)

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		if interaction.user.guild_permissions.manage_messages :
			return True
		await interaction.response.send_message("You need the Manage Messages permission to review characters.",
		                                        ephemeral=True)
		return False

	# ============================================================
	@discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="character_review_approve")
	async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) :
		await CharacterFlow.decide(interaction, approve=True)

	# ============================================================
	@discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="character_review_deny")
	async def deny(self, interaction: discord.Interaction, button: discord.ui.Button) :
		await interaction.response.send_modal(DenyReason())
