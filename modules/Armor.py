import discord
from discord import app_commands
from discord.ext import commands

from components.databaseEvents import CombatSystem


class armor(commands.GroupCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create", description="creates an armor set")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create(self, interaction: discord.Interaction, name: str, hp: int, ac: int, hitchance: int, modifier: str = None) -> None:
        """
        Create an armor set
        :param interaction:
        :param name:
        :param hp:
        :param ac:
        :param hitchance:
        """
        armors = CombatSystem().armor
        if name.lower() in armors.keys():
            await interaction.response.send_message(f"Armor set {name} already exists")
            return
        CombatSystem().create_armor(name, hp, ac, hitchance, modifier)
        await interaction.response.send_message(f"Armor set {name} created")


async def setup(bot):
    await bot.add_cog(armor(bot))
