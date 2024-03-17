import discord
from discord import app_commands

from components.databaseEvents import CombatSystem


class autocomplete:
    async def weapon(self, interaction: discord.Interaction, current: str):
        data = []
        armors = CombatSystem().weapons
        for x in armors.keys():
            if current.lower() in x.lower():
                data.append(app_commands.Choice(name=x.lower(), value=x.lower()))
        return data

    async def character(self, interaction: discord.Interaction, current: str):
        data = []
        characters = CombatSystem().characters[interaction.user.id]
        for x in characters.keys():
            if current.lower() in x.lower():
                data.append(app_commands.Choice(name=x.lower(), value=x.lower()))
        return data

    async def armor(self, interaction: discord.Interaction, current: str):
        data = []
        armors = CombatSystem().armor
        for x in armors.keys():
            if current.lower() in x.lower():
                data.append(app_commands.Choice(name=x.lower(), value=x.lower()))
        return data