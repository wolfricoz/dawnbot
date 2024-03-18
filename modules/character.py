import discord
from discord import app_commands
from discord.ext import commands

from components.autocomplete import autocomplete
from components.databaseEvents import CombatSystem


class Character(commands.GroupCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot



    @app_commands.command(name="create", description="creates a character")
    @app_commands.autocomplete(armor=autocomplete().armor)
    async def create(self, interaction: discord.Interaction,
                     name: str,
                     armor: str,
                     strength: int,
                     perception: int,
                     endurance: int,
                     charisma: int,
                     intelligence: int,
                     agility: int,
                     extra_points: int = 0):
        await interaction.response.defer(ephemeral=True)
        allocated_points = strength + perception + endurance + charisma + intelligence + agility
        max_points = 12 + extra_points
        if allocated_points > max_points:
            await interaction.followup.send(f"You have too many points allocated, you are allowed a maximum of {max_points} points but you allocated {allocated_points}!")
            return
        CombatSystem().create_character(interaction.user, name.lower(), armor, strength, perception, endurance, charisma, intelligence, agility, extra_points)
        await interaction.followup.send(f"Character {name} created")

    @app_commands.command(name="delete", description="deletes a character")
    async def delete(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        characters = CombatSystem().get_characters()
        if name not in characters[interaction.user.id].keys():
            await interaction.followup.send(f"Character {name} does not exist")
            return
        CombatSystem().remove_character(interaction.user, name)
        await interaction.followup.send(f"Character {name} deleted")

    @app_commands.command(name="list", description="lists all characters")
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        characters = CombatSystem().get_characters()
        embed = discord.Embed(title="Characters")
        for x in characters[interaction.user.id].keys():
            embed.add_field(name=x, value=f"Armor: {characters[interaction.user.id][x]['armor']}\n"
                                          f"Strength: {characters[interaction.user.id][x]['strength']}\n"
                                          f"Perception: {characters[interaction.user.id][x]['perception']}\n"
                                          f"Endurance: {characters[interaction.user.id][x]['endurance']}\n"
                                          f"Charisma: {characters[interaction.user.id][x]['charisma']}\n"
                                          f"Intelligence: {characters[interaction.user.id][x]['intelligence']}\n"
                                          f"Agility: {characters[interaction.user.id][x]['agility']}\n"
                                          f"extra_points: {characters[interaction.user.id][x]['prestige']}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="edit", description="edits a character")
    @app_commands.autocomplete(name=autocomplete().character, armor=autocomplete().armor)
    async def edit(self, interaction: discord.Interaction,
                   name: str,
                   armor: str = None,
                   strength: int = None,
                   perception: int = None,
                   endurance: int = None,
                   charisma: int = None,
                   intelligence: int = None,
                   agility: int = None,
                   extra_points: int = None):
        await interaction.response.defer(ephemeral=True)
        characters = CombatSystem().get_characters()[interaction.user.id]
        if name not in characters.keys():
            await interaction.followup.send(f"Character {name} does not exist")
            return
        if armor is not None:
            characters[name]['armor'] = armor
        if strength is not None:
            characters[name]['strength'] = strength
        if perception is not None:
            characters[name]['perception'] = perception
        if endurance is not None:
            characters[name]['endurance'] = endurance
        if charisma is not None:
            characters[name]['charisma'] = charisma
        if intelligence is not None:
            characters[name]['intelligence'] = intelligence
        if agility is not None:
            characters[name]['agility'] = agility
        if extra_points is not None:
            characters[name]['prestige'] = extra_points
        CombatSystem().update_character(interaction.user, name, armor, strength, perception, endurance, charisma, intelligence, agility, extra_points)
        await interaction.followup.send(f"Character {name} edited")

    @app_commands.command(name="profile", description="shows the profile of a character")
    @app_commands.autocomplete(name=autocomplete().character)
    async def profile(self, interaction: discord.Interaction, name: str):
        characters = CombatSystem().get_characters()[interaction.user.id]
        if name not in characters.keys():
            await interaction.response.send_message(f"Character {name} does not exist")
            return
        character = characters[name]
        armors = CombatSystem().armor
        for y, x in armors.items():
            if x["id"] == character["armor"]:
                character["armor"] = y
                break
        embed = discord.Embed(title=name)
        embed.add_field(name="Armor", value=character["armor"])
        embed.add_field(name="Strength", value=character["strength"])
        embed.add_field(name="Perception", value=character["perception"])
        embed.add_field(name="Endurance", value=character["endurance"])
        embed.add_field(name="Charisma", value=character["charisma"])
        embed.add_field(name="Intelligence", value=character["intelligence"])
        embed.add_field(name="Agility", value=character["agility"])
        embed.add_field(name="extra_points", value=character["prestige"])
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="show", description="look at another person's character")
    async def show(self, interaction: discord.Interaction, member: discord.Member, name: str):
        characters = CombatSystem().get_characters()[member.id]

        if name.lower() not in characters.keys():
            await interaction.response.send_message(f"Character {name} does not exist")
            return
        character = characters[name.lower()]
        armors = CombatSystem().armor
        for y, x in armors.items():
            print(x, y)
            if x["id"] == character["armor"]:
                character["armor"] = y
                break
        embed = discord.Embed(title=name)
        embed.add_field(name="Armor", value=character["armor"])
        embed.add_field(name="Strength", value=character["strength"])
        embed.add_field(name="Perception", value=character["perception"])
        embed.add_field(name="Endurance", value=character["endurance"])
        embed.add_field(name="Charisma", value=character["charisma"])
        embed.add_field(name="Intelligence", value=character["intelligence"])
        embed.add_field(name="Agility", value=character["agility"])
        embed.add_field(name="extra_points", value=character["prestige"])
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Character(bot))
