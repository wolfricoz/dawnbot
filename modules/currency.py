import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

import components.database as db
from components.configMaker import guildconfiger
from components.databaseEvents import TransactionController, xpTransactions, currencyTransactions
from components.xpCalculations import xpCalculations


class currencyEvents(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="checkcurrency")
    @app_commands.checks.has_permissions()
    async def checkcurrency(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = TransactionController.get_user(interaction.user.id, interaction.guild.id)
        currency = user.currency  # Assuming the user object has a 'currency' attribute

        embed = discord.Embed(title=f"{interaction.user.name}'s currency",
                              description=f"You currently have {currency} currency.")
        embed.set_footer(text=f"Current currency: {currency}.")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setcurrency")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setcurrency(self, interaction: discord.Interaction, member: discord.Member, currency: int):
        await interaction.response.defer(ephemeral=True)
        currencyTransactions.set_currency(member.id, currency)
        await interaction.followup.send(f"Currency of {member.mention} set to {currency}")

    @app_commands.command(name="addcurrency")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def addcurrency(self, interaction: discord.Interaction, member: discord.Member, currency: int):
        await interaction.response.defer(ephemeral=True)
        currencyTransactions.add_currency(member.id, currency)
        await interaction.followup.send(f"Added {currency} to {member.mention}")

    @app_commands.command(name="removecurrency")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def removecurrency(self, interaction: discord.Interaction, member: discord.Member, currency: int):
        await interaction.response.defer(ephemeral=True)
        currencyTransactions.remove_currency(member.id, currency)
        await interaction.followup.send(f"Removed {currency} from {member.mention}")




async def setup(bot):
    await bot.add_cog(currencyEvents(bot))
