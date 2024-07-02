import asyncio
import logging
import random

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands, tasks

from components.configmaker import guildconfiger


class Tools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.unarchiver.start()

    def cog_unload(self):
        self.unarchiver.cancel()

    @app_commands.command(name="endscene", description="ends the scene")
    async def endscene(self, interaction: discord.Interaction, rpenddate: str, title: str = None):
        await interaction.response.defer(thinking=False, ephemeral=True)
        message: discord.Message = await interaction.channel.send(f"{interaction.user.mention} ended the scene.")
        channel = self.bot.get_channel(int(await guildconfiger.get(interaction.guild.id, "timeline")))
        await channel.send(f"{f'# {title}' if title is not None else ''}\n"
                           f"Author: {interaction.user.mention}\n"
                           f"Link to final message: {message.jump_url}\n"
                           f"In roleplay date: {rpenddate}\n"
                           f"Brief summary of what happened: (Post below!)")

    @app_commands.command(name="dice", description="rolls a dice for you!")
    @app_commands.choices(modifier=[Choice(name=str(x), value=x) for x in range(-10, 11)])
    async def dice(self, interaction: discord.Interaction, dicetype: int, modifier: Choice[int] = 0, title: str = "No goal given.",
                   amount: int = 1, ):
        logging.debug(f"{interaction.user.name} rolled dicetype: {dicetype}, modifier: {modifier}, title: {title}, amount: {amount}")
        if isinstance(modifier, Choice):
            modifier = modifier.value
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
        text_results = []
        if dicetype >= 100:
            modifier *= 3
        while x < amount:
            x += 1
            result = random.randint(1, dicetype)
            mod_result = result + modifier
            results.append(mod_result)
            text_result = f"{result + modifier} ({result}+{modifier})"
            text_results.append(text_result)

        rm = map(str, results)
        t = ", ".join(rm)
        ts = ", ".join(text_results)
        counted = sum(results)
        await interaction.followup.send(f"The dice has been cast..")
        embed = discord.Embed(title=title,
                              description=f"You roll {amount}d{dicetype}{'+' if modifier >= 0 else ''}{modifier}: {ts} \n(total: {counted})")
        embed.set_footer(text=f"{interaction.user.name}")

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


    @app_commands.command(name="purge", description="purges inactive users")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def purge(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(1248728538920652860)
        count = 0
        for member in interaction.guild.members:
            if role in member.roles:
                invite = await interaction.channel.create_invite(max_age=86400, max_uses=1)
                await asyncio.sleep(1)
                await member.send("You have been purged from the server due to inactivity. If you wish to rejoin, please use the invite link."
                                  f"{invite.url}")
                await member.kick(reason="purged due to inactivity")
                count += 1
        await interaction.followup.send(f"{count} members have been purged.")

    @tasks.loop(hours=72)
    async def unarchiver(self):
        "makes all posts active again"
        for x in self.bot.guilds:
            for channel in x.channels:
                if channel.type == discord.ChannelType.forum:
                    async for post in channel.archived_threads():
                        message = await post.send("bump")
                        await asyncio.sleep(1)
                        await message.delete()

    @unarchiver.before_loop  # it's called before the actual task runs
    async def before_checkactiv(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Tools(bot))
