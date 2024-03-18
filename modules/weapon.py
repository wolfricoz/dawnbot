import discord
from discord import app_commands
from discord.ext import commands

from components.autocomplete import autocomplete
from components.databaseEvents import CombatSystem


class weapon(commands.GroupCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create", description="creates a weapon type")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create(self, interaction: discord.Interaction,
                     name: str,
                     dice: str,
                     modifier: str,
                     hitmodifier: int=None):
        await interaction.response.defer(ephemeral=True)
        weapons = CombatSystem().get_weapons()
        print(weapons.keys())
        if name.lower() in weapons.keys():
            await interaction.followup.send(f"Weapon {name} already exists")
            return
        CombatSystem().create_weapon(name, dice, modifier, hitmodifier)
        await interaction.followup.send(f"Weapon {name} created")

    @app_commands.command(name="delete", description="deletes a weapon type")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.autocomplete(name=autocomplete().weapon)
    async def delete(self, interaction: discord.Interaction,
                     name: str):
        await interaction.response.defer(ephemeral=True)
        weapons = CombatSystem().get_weapons()
        if name.lower() not in weapons.keys():
            await interaction.followup.send(f"Weapon {name} does not exist")
            return
        CombatSystem().remove_weapon(name)
        await interaction.followup.send(f"Weapon {name} deleted")

    @app_commands.command(name="list", description="lists all weapon types")
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        weapons = CombatSystem().get_weapons()
        embed = discord.Embed(title="Weapon types")
        for x in weapons.keys():
            embed.add_field(name=x, value=f"Damage: {weapons[x]['dice']} + {weapons[x]['modifier']} \n Hit modifier: {weapons[x]['hitmodifier']}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="edit", description="edits a weapon type")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.autocomplete(name=autocomplete().weapon)
    async def edit(self, interaction: discord.Interaction,
                   name: str,
                   dice: str = None,
                   modifier: str = None,
                   hitmodifier: int=None):
        await interaction.response.defer(ephemeral=True)
        weapons = CombatSystem().get_weapons()
        if name.lower() not in weapons.keys():
            await interaction.followup.send(f"Weapon {name} does not exist")
            return
        if dice is not None:
            weapons[name]['dice'] = dice
        if modifier is not None:
            weapons[name]['modifier'] = modifier
        if hitmodifier is not None:
            weapons[name]['hitmodifier'] = hitmodifier
        CombatSystem().update_weapon(name, weapons[name]['dice'], weapons[name]['modifier'], weapons[name]['hitmodifier'])
        await interaction.followup.send(f"Weapon {name} updated")

async def setup(bot):
    await bot.add_cog(weapon(bot))
