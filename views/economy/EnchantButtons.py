"""Approve / Deny under a magic item design's review card. They carry the design's id, so they keep working after a
restart (registered with bot.add_dynamic_items in setup_hook)."""
import discord

from views.buttons.ReviewButtons import REASON_LIMIT


class EnchantButton(discord.ui.DynamicItem[discord.ui.Button],
                    template=r"enchant:(?P<design>\d+):(?P<action>approve|deny)") :

	def __init__(self, design_id: int, action: str) :
		style = discord.ButtonStyle.success if action == "approve" else discord.ButtonStyle.danger
		super().__init__(discord.ui.Button(label=action.capitalize(), style=style,
		                                   custom_id=f"enchant:{design_id}:{action}"))
		self.design_id = design_id
		self.action = action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(int(match["design"]), match["action"])

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		if interaction.user.guild_permissions.manage_messages :
			return True
		await interaction.response.send_message("You need the Manage Messages permission to review.", ephemeral=True)
		return False

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		from modules.Enchant import decide

		if self.action == "approve" :
			return await decide(interaction, self.design_id, approve=True)
		design_id = self.design_id

		class Reason(discord.ui.Modal, title="Deny") :
			reason = discord.ui.TextInput(label="Reason (sent to the player)", style=discord.TextStyle.paragraph,
			                              max_length=REASON_LIMIT, required=True)

			async def on_submit(self, modal_interaction: discord.Interaction) :
				await decide(modal_interaction, design_id, approve=False, reason=self.reason.value)

		await interaction.response.send_modal(Reason())


# ============================================================
def review_view(design_id: int) -> discord.ui.View :
	view = discord.ui.View(timeout=None)
	view.add_item(EnchantButton(design_id, "approve"))
	view.add_item(EnchantButton(design_id, "deny"))
	return view
