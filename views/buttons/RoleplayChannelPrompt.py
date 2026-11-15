import logging
import re

import discord

from classes.kernel.ConfigData import ConfigData
from classes.kernel.ServerSync import sync_server
from resources.configs.ConfigMapping import ConfigMapping


# The channel id is part of the button's id, so the buttons keep working after a restart (registered with
# bot.add_dynamic_items in setup_hook).
class RoleplayChannelButton(discord.ui.DynamicItem[discord.ui.Button],
                            template=r"rpchannel:(?P<answer>yes|no|location):(?P<channel_id>\d+)") :
	"""Yes / No / Set up location on the "add this new channel to the roleplay channels?" question."""

	def __init__(self, answer: str, channel_id: int) :
		labels = {"yes" : ("Yes, add it", discord.ButtonStyle.success),
		          "no" : ("No", discord.ButtonStyle.secondary),
		          "location" : ("Set up location", discord.ButtonStyle.primary)}
		label, style = labels[answer]
		super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"rpchannel:{answer}:{channel_id}",
		                                   emoji="📍" if answer == "location" else None))
		self.answer = answer
		self.channel_id = channel_id

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]) :
		return cls(match["answer"], int(match["channel_id"]))

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		from classes.kernel.GMRole import is_gm

		allowed = is_gm(interaction.user) if self.answer == "location" else \
			interaction.user.guild_permissions.manage_messages
		if allowed :
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
		if self.answer == "location" :
			return await self.set_up_location(interaction, channel)
		if self.answer == "yes" :
			sync_server(guild)
			ConfigData().add_to_list(guild.id, ConfigMapping.XP_CHANNELS, channel.id)
			logging.info(f"{interaction.user.name} added #{channel.name} to the roleplay channels of {guild.name}")
			note = f"✅ {interaction.user.mention} added {channel.mention} to the roleplay channels."
		else :
			note = f"{interaction.user.mention} left {channel.mention} out of the roleplay channels."
		# The location button stays: a channel can become a location whatever the answer.
		location_only = discord.ui.View(timeout=None)
		location_only.add_item(RoleplayChannelButton("location", channel.id))
		await interaction.response.edit_message(content=f"{interaction.message.content}\n{note}", view=location_only,
		                                        allowed_mentions=discord.AllowedMentions.none())


	# ============================================================
	@staticmethod
	async def set_up_location(interaction: discord.Interaction, channel) -> None :
		"""Makes the new channel a location named after it; the rest is filled in with /location set there."""
		from database.transactions.WorldTransactions import WorldTransactions

		location = WorldTransactions().location_of(channel.id)
		if location is None :
			name = channel.name.replace("-", " ").replace("_", " ").title()[:100]
			location = WorldTransactions().save_location(interaction.guild_id, channel.id, name=name)
			logging.info(f"{interaction.user.name} made #{channel.name} a location in {interaction.guild.name}")
		await interaction.response.send_message(f"📍 {channel.mention} is the location **{location.name}**. Use "
		                                        f"/location set in it to add a description, region, climate, "
		                                        f"danger and picture.", ephemeral=True)


# ============================================================
def prompt_view(channel_id: int) -> discord.ui.View :
	view = discord.ui.View(timeout=None)
	view.add_item(RoleplayChannelButton("yes", channel_id))
	view.add_item(RoleplayChannelButton("no", channel_id))
	view.add_item(RoleplayChannelButton("location", channel_id))
	return view
