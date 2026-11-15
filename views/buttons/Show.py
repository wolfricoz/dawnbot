"""A Show button under a private result (such as a secret /dice roll) that posts it in the channel for everyone."""
import discord


class ShowView(discord.ui.View) :

	def __init__(self, user_id: int, embed: discord.Embed) :
		# Private messages can only be answered for 15 minutes.
		super().__init__(timeout=840)
		self.user_id = user_id
		self.embed = embed

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		return interaction.user.id == self.user_id

	# ============================================================
	@discord.ui.button(label="Show", style=discord.ButtonStyle.primary, emoji="📢")
	async def show(self, interaction: discord.Interaction, button: discord.ui.Button) :
		self.stop()
		await interaction.response.edit_message(content="📢 Shown in the channel.", view=None)
		await interaction.channel.send(embed=self.embed)
