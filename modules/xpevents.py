import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import Session
from components.configmaker import guildconfiger
import components.database as db
from components.databaseEvents import transaction
from components.xpcalculations import xpCalculations

session = Session(bind=db.engine)


class xpEvents(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="checkxp")
    @app_commands.checks.has_permissions()
    async def checkxp(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = transaction.get_user(session, interaction.user.id)
        roleid, rankinfo = transaction.get_lowest_role(session, interaction.guild, user)
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
        user = session.scalars(select(db.Users).where(db.Users.uid == member.id)).first()
        if user is None:
            user = db.Users(uid=member.id)
            session.add(user)
        user.xp = xp
        session.commit()
        await interaction.followup.send(f"xp of {member.mention} set to {xp}")

    @app_commands.command(name="addxp")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def addxp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        await interaction.response.defer(ephemeral=True)
        user = session.scalars(select(db.Users).where(db.Users.uid == member.id)).first()
        if user is None:
            user = db.Users(uid=member.id)
            session.add(user)
        user.xp += xp
        session.commit()
        await interaction.followup.send(f"added {xp} to {member.mention}")

    @app_commands.command(name="removexp")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def removexp(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        await interaction.response.defer(ephemeral=True)
        user = session.scalars(select(db.Users).where(db.Users.uid == member.id)).first()
        if user is None:
            user = db.Users(uid=member.id)
            session.add(user)
        user.xp -= xp
        session.commit()
        await interaction.followup.send(f"added {xp} to {member.mention}")

    #textchannels
    @commands.Cog.listener("on_message")
    async def on_channel_message(self, message: discord.Message):
        if message.channel.type != discord.ChannelType.text:
            return
        if message.author.bot:
            return
        channels = await guildconfiger.get(message.guild.id, "channels")

        if message.channel.id not in channels:
            found = False
            for c in channels:
                try:
                    ch = message.guild.get_channel(c)
                    if message.channel in ch.threads:
                        print("found")
                        found = True
                except AttributeError:
                    print(f"[Channel Error] Failed at {c} and removed from config")
                    await guildconfiger.remchannel(message.guild.id, c, "channels")
            if found is False:
                return
        if len(message.content) <= 300 and message.author.guild_permissions.manage_messages is False:
            try:
                await message.author.send(f"Your message is too short, please make it longer than 300 characters. No XP has been awarded and your post has been removed.\n {message.content}")
            except discord.Forbidden:
                await message.channel.send(f"{message.author.mention} Your message is too short, please make it longer than 300 characters. No XP has been awarded and your post has been removed. **The bot could not DM you, please open your dms.**\n {message.content}")
            await message.delete()
            return

        role = await xpCalculations.calculate(message, session)
        new_rank = message.guild.get_role(role)
        if new_rank in message.author.roles or new_rank is None:
            return
        # prepares the list of roles that have to be removed
        remroles = transaction.get_roles(session, message.guild)
        await message.author.remove_roles(*remroles)
        announcement = await guildconfiger.get(message.guild.id, "announcement")
        lvlch = self.bot.get_channel(announcement)
        await lvlch.send(f"Congratulations {message.author.mention}, you've leveled up to {new_rank}")
        await message.author.add_roles(new_rank)

    #forums
    # Rewrite this to check if the thread is part of forum,
    @commands.Cog.listener("on_message")
    async def on_forum_message(self, message: discord.Message):
        if message.channel.type != discord.ChannelType.public_thread:
            return
        # print("forum/thread")
        if message.author.bot:
            return
        channels = await guildconfiger.get(message.guild.id, "channels")

        if message.channel not in channels:
            found = False
            for c in channels:
                try:
                    ch = message.guild.get_channel(c)
                    if message.channel in ch.threads:
                        print("found")
                        found = True
                except AttributeError:
                    print(f"[Channel Error] Failed at {c} and removed from config")
                    await guildconfiger.remchannel(message.guild.id, c, "channels")
            if found is False:
                return
        role = await xpCalculations.calculate(message, session)
        new_rank = message.guild.get_role(role)
        if new_rank in message.author.roles or new_rank is None:
            return
        # prepares the list of roles that have to be removed
        remroles = transaction.get_roles(session, message.guild)
        await message.author.remove_roles(*remroles)
        announcement = await guildconfiger.get(message.guild.id, "announcement")
        lvlch = self.bot.get_channel(announcement)
        await lvlch.send(f"Congratulations {message.author.mention}, you've leveled up to {new_rank}")
        await message.author.add_roles(new_rank)

async def setup(bot):
    await bot.add_cog(xpEvents(bot))
