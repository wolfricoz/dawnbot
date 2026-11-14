import logging
import re

import discord

from classes.kernel.ConfigData import ConfigData
from classes.kernel.ServerSync import sync_server
from resources.configs.ConfigMapping import ConfigMapping


class RoleplayChannelButton(discord.ui.DynamicItem[discord.ui.Button],
                            template=r"rpchannel:(?P<answer>yes|no):(?P<channel_id>\d+)") :
	"""Yes / No on the "add this new channel to the roleplay channels?" question in the modlog.

	The channel id is part of the button's id, so the buttons keep working after a restart (registered with
	bot.add_dynamic_items in setup_hook).
	"""

	def __init__(self, answer: str, channel_id: int) :
		super().__init__(discord.ui.Button(
			label="Yes, add it" if answer == "yes" else "No",
			style=discord.ButtonStyle.success if answer == "yes" else discord.ButtonStyle.secondary,
			custom_id=f"rpchannel:{answer}:{channel_id}"))
		self.answer = answer
		self.channel_id = channel_id

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]) :
		return cls(match["answer"], int(match["channel_id"]))

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		if interaction.user.guild_permissions.manage_messages :
			return True
		await interaction.response.send_message("You need the Manage Messages permission to answer this.",
		                                        ephemeral=True)
		return False

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		guild = interaction.guild
		channel = guild.get_channel(self.channel_id)
		if channel is None :
			return await interaction.response.edit_message(
				content=f"{interaction.message.content}\n-# The channel no longer exists.", view=None)
		if self.answer == "yes" :
			sync_server(guild)
			ConfigData().add_to_list(guild.id, ConfigMapping.XP_CHANNELS, channel.id)
			logging.info(f"{interaction.user.name} added #{channel.name} to the roleplay channels of {guild.name}")
			note = f"✅ {interaction.user.mention} added {channel.mention} to the roleplay channels."
		else :
			note = f"{interaction.user.mention} left {channel.mention} out of the roleplay channels."
		await interaction.response.edit_message(content=f"{interaction.message.content}\n{note}", view=None,
		                                        allowed_mentions=discord.AllowedMentions.none())


# ============================================================
def prompt_view(channel_id: int) -> discord.ui.View :
	view = discord.ui.View(timeout=None)
	view.add_item(RoleplayChannelButton("yes", channel_id))
	view.add_item(RoleplayChannelButton("no", channel_id))
	return view
