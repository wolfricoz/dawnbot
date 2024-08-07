import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

import components.database as db
from components.configMaker import guildconfiger
from components.currencyCalculations import currencyCalculations
from components.databaseEvents import TransactionController, xpTransactions, currencyTransactions
from components.xpCalculations import xpCalculations


class xpEvents(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="recount")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def recount(self, interaction: discord.Interaction):
        key = "channels"
        if interaction.user.id != 188647277181665280:
            await interaction.response.send_message("You do not have permission to use this command")
            return
        await interaction.response.defer()
        count = 0
        message = await interaction.channel.send(f"Resetting users")
        for user in interaction.guild.members:
            TransactionController.delete_user(user.id, interaction.guild.id)
            TransactionController.add_user(user.id, interaction.guild.id)
            count += 1
        await message.edit(content=f"Reset {count} users, starting to calculate currency and xp now")
        channelids = await guildconfiger.get(interaction.guild.id, "channels")
        for channelid in channelids:
            channel = interaction.guild.get_channel(channelid)

            if channel is None:
                print(f"channel {channelid} not found")
                continue
            await message.edit(content=f"Calculating {channel.mention}")
            if isinstance(channel, discord.TextChannel):
                await guildconfiger.addchannel(interaction.guild.id, interaction, channel, key, only_calculate=True)
            if isinstance(channel, discord.ForumChannel):
                await guildconfiger.addforum(interaction.guild.id, interaction, channel, key, only_calculate=True)
            if isinstance(channel, discord.Thread):
                continue
            await interaction.channel.send(f"Finished calculating {channel.mention}", silent=True)
        await interaction.channel.send("Finished recounting")

    @app_commands.command(name="checkxp")
    @app_commands.checks.has_permissions()
    async def checkxp(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = TransactionController.get_user(interaction.user.id, guildid=interaction.guild.id)
        roleid, rankinfo = TransactionController.get_lowest_role(interaction.guild, user)
        role = interaction.guild.get_role(roleid)
        if rankinfo is None:
            rankinfo = user.xp

        embed = discord.Embed(title=f"{interaction.user.name}'s level",
                              description=f"You need {rankinfo - user.xp} to reach {role.name}")
        embed.set_footer(text=f"Current xp: {user.xp}. You've sent {user.messages} messages")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="setxp")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setxp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        await interaction.response.defer(ephemeral=True)
        xpTransactions.set_xp(member.id, interaction.guild.id, xp)
        await interaction.followup.send(f"xp of {member.mention} set to {xp}")

    @app_commands.command(name="addxp")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def addxp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        await interaction.response.defer(ephemeral=True)
        xpTransactions.add_xp(member.id, interaction.guild.id, xp)
        await interaction.followup.send(f"added {xp} to {member.mention}")

    @app_commands.command(name="removexp")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def removexp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        await interaction.response.defer(ephemeral=True)
        xpTransactions.remove_xp(member.id, interaction.guild.id, xp)
        await interaction.followup.send(f"Removed {xp} from {member.mention}")

    # textchannels
    @commands.Cog.listener("on_message")
    async def on_channel_message(self, message: discord.Message):
        if message.channel.type != discord.ChannelType.text:
            return
        if message.author.bot:
            return
        channels = await guildconfiger.get(message.guild.id, "channels")
        if message.channel.id not in channels:
            return
        if await xpCalculations.check_size(message) is False:
            try:
                await message.author.send(f"Your message is too short, please make it longer than 300 characters. No XP has been awarded and your post has been removed.\n {message.content}")
            except discord.Forbidden:
                await message.channel.send(
                        f"{message.author.mention} Your message is too short, please make it longer than 300 characters. No XP has been awarded and your post has been removed. **The bot could not DM you, please open your dms.**\n {message.content}")
            await message.delete()
            return
        await currencyCalculations.calculate(message)
        announcement = await guildconfiger.get(message.guild.id, "announcement")
        new_rank, remroles = await xpCalculations.check_roles(message)
        if new_rank is None or remroles is None:
            return
        await message.author.remove_roles(*remroles)
        lvlch = self.bot.get_channel(announcement)
        await lvlch.send(f"Congratulations {message.author.mention}, you've leveled up to {new_rank}")
        await message.author.add_roles(new_rank)

    # forums
    # Rewrite this to check if the thread is part of forum,
    @commands.Cog.listener("on_message")
    async def on_forum_message(self, message: discord.Message):
        if message.channel.type != discord.ChannelType.public_thread:
            return
        # print("forum/thread")
        if message.author.bot:
            return
        channels = await guildconfiger.get(message.guild.id, "channels")
        if message.channel.id not in channels:
            if message.channel.parent_id not in channels:
                return
            await guildconfiger.addthread(message.guild.id, message.channel, "channels")
        if await xpCalculations.check_size(message) is False:
            try:
                await message.author.send(f"Your message is too short, please make it longer than 300 characters. No XP has been awarded and your post has been removed.\n {message.content}")
            except discord.Forbidden:
                await message.channel.send(
                        f"{message.author.mention} Your message is too short, please make it longer than 300 characters. No XP has been awarded and your post has been removed. **The bot could not DM you, please open your dms.**\n {message.content}")
            await message.delete()
            return
        announcement = await guildconfiger.get(message.guild.id, "announcement")
        new_rank, remroles = await xpCalculations.check_roles(message)
        if new_rank is None or remroles is None:
            return
        await message.author.remove_roles(*remroles)
        lvlch = self.bot.get_channel(announcement)
        await lvlch.send(f"Congratulations {message.author.mention}, you've leveled up to {new_rank}")
        await message.author.add_roles(new_rank)


async def setup(bot):
    await bot.add_cog(xpEvents(bot))
