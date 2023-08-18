import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import Session
from components.configmaker import guildconfiger
import components.database as db
from components.databaseEvents import transaction

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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        channels = await guildconfiger.get(message.guild.id, "channels")
        xp_gain = await guildconfiger.get(message.guild.id, "xp_gain")
        if message.channel.id not in channels:
            found = False
            for c in channels:
                if message.channel in self.bot.get_channel(c).threads:
                    print("found")
                    found = True
            if found is False:
                return
        # Checks if user is in database, if not; user is added.
        user = transaction.get_user(session, message.author.id)
        # Checks message length and converts it into XP
        user.xp += round(len(message.content) / xp_gain)
        user.messages += 1
        role = transaction.get_highest_role(session, message.guild, user)
        new_rank = message.guild.get_role(role)
        if new_rank in message.author.roles:
            return
        # prepares the list of roles that have to be removed
        remroles = transaction.get_roles(session, message.guild)
        await message.author.remove_roles(*remroles)
        announcement = await guildconfiger.get(message.guild.id, "announcement")
        lvlch = self.bot.get_channel(announcement)
        await lvlch.send(f"Congratulations {message.author.mention}, you've leveled up to {new_rank}")
        await message.author.add_roles(new_rank)
        session.commit()


async def setup(bot):
    await bot.add_cog(xpEvents(bot))
