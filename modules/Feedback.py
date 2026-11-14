import discord
from discord import app_commands
from discord.ext import commands
from discord_py_utilities.messages import send_message, send_response

from data.env.loader import env
from project.data import BOT_NAME, DOCUMENTATION


class Feedback(commands.Cog) :
	"""Feedback for the developer and a link to the documentation."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="feedback", description="Sends feedback to the developer")
	async def feedback(self, interaction: discord.Interaction, feedback: app_commands.Range[str, 1, 1800]) :
		"""
		Sends your feedback to the developer.
		"""
		channel = self.bot.get_channel(int(env('FEEDBACKCHANNEL') or env('DEVCHANNEL', 0)))
		if channel is None :
			return await send_response(interaction, "Feedback can't be delivered right now, please try again later.",
			                           ephemeral=True)
		await send_message(channel, f"Feedback from {interaction.user} ({interaction.user.id}) in "
		                            f"{interaction.guild.name if interaction.guild else 'DMs'}: {feedback}")
		await send_response(interaction, "Feedback submitted! Thank you!", ephemeral=True)

	# ============================================================
	@app_commands.command(name="help", description="Links the help documents")
	async def help(self, interaction: discord.Interaction) :
		"""
		Links the documentation.
		"""
		await send_response(interaction, f"You can read the {BOT_NAME} documentation here: {DOCUMENTATION}",
		                    ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Feedback(bot))
