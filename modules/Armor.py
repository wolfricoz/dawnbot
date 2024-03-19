import logging

import discord
from discord import app_commands
from discord.ext import commands

from components.autocomplete import autocomplete
from components.databaseEvents import CombatSystem


class armor(commands.GroupCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create", description="creates an armor set")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create(self, interaction: discord.Interaction, name: str, hp: int, ac: int, hitchance: int = 0, modifier: str = "None") -> None:
        """
        Create an armor set
        :param modifier:
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
        logging.info(f"Armor set {name} created by {interaction.user.name}")
        await interaction.response.send_message(f"Armor set {name} created")

    @app_commands.command(name="delete", description="deletes an armor set")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.autocomplete(name=autocomplete().armor)
    async def delete(self, interaction: discord.Interaction, name: str) -> None:
        """
        Delete an armor set
        :param interaction:
        :param name:
        """
        armors = CombatSystem().armor
        if name.lower() not in armors.keys():
            await interaction.response.send_message(f"Armor set {name} does not exist")
            return
        CombatSystem().remove_armor(name)
        logging.info(f"Armor set {name} deleted by {interaction.user.name}")
        await interaction.response.send_message(f"Armor set {name} deleted")

    @app_commands.command(name="list", description="lists all armor sets")
    async def list(self, interaction: discord.Interaction) -> None:
        """
        List all armor sets
        :param interaction:
        """
        armors = CombatSystem().armor
        embed = discord.Embed(title="Armor sets")
        for x in armors.keys():
            embed.add_field(name=x, value=f"HP: {armors[x]['hp']}\n"
                                          f"AC: {armors[x]['ac']}\n"
                                          f"Hit chance: {armors[x]['hitchance']}\n"
                                          f"Modifier: {armors[x]['modifier']}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="edit", description="edits an armor set")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.autocomplete(name=autocomplete().armor)
    async def edit(self, interaction: discord.Interaction, name: str, hp: int = None, ac: int = None, hitchance: int = None, modifier: str = None) -> None:
        """
        Edit an armor set
        :param interaction:
        :param name:
        :param hp:
        :param ac:
        :param hitchance:
        :param modifier:
        """
        armors = CombatSystem().armor
        if name.lower() not in armors.keys():
            await interaction.response.send_message(f"Armor set {name} does not exist")
            return
        if hp is not None:
            armors[name]['hp'] = hp
        if ac is not None:
            armors[name]['ac'] = ac
        if hitchance is not None:
            armors[name]['hitchance'] = hitchance
        if modifier is not None:
            armors[name]['modifier'] = modifier
        CombatSystem().update_armor(name, armors[name]['hp'], armors[name]['ac'], armors[name]['hitchance'], armors[name]['modifier'])
        logging.info(f"Armor set {name} edited by {interaction.user.name}")
        await interaction.response.send_message(f"Armor set {name} edited")


async def setup(bot):
    await bot.add_cog(armor(bot))
