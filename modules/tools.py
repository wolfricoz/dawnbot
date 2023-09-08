import random

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands


class Tools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dice", description="rolls a dice for you!")
    @app_commands.choices(modifier=[
        Choice(name=+5, value=5),
        Choice(name=+4, value=4),
        Choice(name=+3, value=3),
        Choice(name=+2, value=2),
        Choice(name=+1, value=1),
        Choice(name=0, value=0),
        Choice(name=-1, value=-1),
        Choice(name=-2, value=-2),
        Choice(name=-3, value=-3),
        Choice(name=-4, value=-4),
        Choice(name=-5, value=-5),
    ])
    async def dice(self, interaction: discord.Interaction, dicetype: int, title: str = "No goal given.",
                   amount: int = 1, modifier: Choice[int] = 0):
        await interaction.response.defer(thinking=False, ephemeral=True)
        if dicetype < 2:
            interaction.followup.send("Please choose a dice with at least 2 sides!")
            return
        if dicetype > 1000:
            interaction.followup.send("Please choose a dice with less than 1000 sides!")
            return
        if amount > 50:
            interaction.followup.send("you can roll up to 50 dice!")
            return
        x = 0
        results = []
        while x < amount:
            x += 1
            result = random.randint(1, dicetype)
            mod_result = result + modifier.value
            results.append(mod_result)

        rm = map(str, results)
        t = ", ".join(rm)
        counted = sum(results)
        await interaction.followup.send(f"The dice has been cast..")
        embed = discord.Embed(title=title,
                              description=f"You roll {amount}d{dicetype}{'+' if modifier.value >= 0 else ''}{modifier.name}: {t} \n(total: {counted})")
        embed.set_footer(text=f"{interaction.user.nick}")

        await interaction.channel.send(f"{interaction.user.mention}", embed=embed)

    @app_commands.command(name="coinflip", description="flips a coin for you!")
    async def coin(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=False, ephemeral=True)
        r = random.randint(1, 2)
        await interaction.followup.send(f"The coin has been cast..")
        if r == 1:
            await interaction.channel.send(f"Heads!")
        else:
            await interaction.channel.send(f"Tails!")


async def setup(bot):
    await bot.add_cog(Tools(bot))
