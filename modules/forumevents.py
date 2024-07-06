import discord
from discord.ext import commands
from sqlalchemy.orm import Session

import components.database as db
from components.configMaker import guildconfiger

session = Session(bind=db.engine)


class forumEvents(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        modlog = self.bot.get_channel(await guildconfiger.get(thread.guild.id, "modlog"))
        forum = self.bot.get_channel(thread.parent_id)
        await modlog.send(f"new thread in {forum.mention} created by {thread.owner.mention} in {thread.mention}")


async def setup(bot):
    await bot.add_cog(forumEvents(bot))
