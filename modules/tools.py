import asyncio
import random

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands, tasks


class Tools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.unarchiver.start()

    def cog_unload(self):
        self.unarchiver.cancel()

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
    async def dice(self, interaction: discord.Interaction, dicetype: int, modifier: Choice[int], title: str = "No goal given.",
                   amount: int = 1, ):
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
        mod = modifier.value
        if dicetype >= 100:
            mod = modifier.value * 10
        print(mod)
        while x < amount:
            x += 1
            result = random.randint(1, dicetype)
            mod_result = result + mod
            results.append(mod_result)

        rm = map(str, results)
        t = ", ".join(rm)
        counted = sum(results)
        await interaction.followup.send(f"The dice has been cast..")
        embed = discord.Embed(title=title,
                              description=f"You roll {amount}d{dicetype}{'+' if modifier.value >= 0 else ''}{mod}: {t} \n(total: {counted})")
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

    @app_commands.command()
    async def unarchive(self, interaction: discord.Interaction, channel:discord.ForumChannel):
        await interaction.response.defer(thinking=False, ephemeral=True)
        async for post in await channel.archived_threads():
            print(post.name)
            message = await post.send("bump")
            await asyncio.sleep(1)
            await message.delete()
        await interaction.response.send("Done")

    @tasks.loop(hours=24)
    async def unarchiver(self):
        "makes all posts active again"
        for x in self.bot.guilds:
            for channel in x.channels:
                print(channel.name)
                if channel.type == discord.ForumChannel:
                    async for post in channel.archived_threads():
                        print(post.name)
                        message = await post.send("bump")
                        await asyncio.sleep(1)
                        await message.delete()

    # @unarchiver.before_loop  # it's called before the actual task runs
    # async def before_checkactiv(self):
    #     await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Tools(bot))
