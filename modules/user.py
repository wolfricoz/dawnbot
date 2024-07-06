import discord
from discord import app_commands
from discord.ext import commands

from components.configMaker import guildconfiger
from components.databaseEvents import TransactionController


class User(commands.GroupCog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats")
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = TransactionController.get_user(interaction.user.id, interaction.guild.id)
        roleid, rankinfo = TransactionController.get_lowest_role(interaction.guild, user)
        role = interaction.guild.get_role(roleid)
        currency_name = await guildconfiger.get(interaction.guild.id, "currency_name")
        if rankinfo is None:
            rankinfo = user.xp

        embed = discord.Embed(title=f"{interaction.user.name}'s level\n"
                                    f"Current XP: {user.xp}\n"
                                    f"{currency_name}: {user.currency}\n"
                                    f"Messages sent: {user.messages}\n",
                              description=f"You need {rankinfo - user.xp} to reach {role.name}")
        embed.set_footer(text=f"Current xp: {user.xp}. You've sent {user.messages} messages")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(User(bot))
