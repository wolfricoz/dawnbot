import discord
from discord.ext import commands
from sqlalchemy.orm import Session

import components.database as db
from components.configmaker import guildconfiger

session = Session(bind=db.engine)


class forumEvents(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        forum = self.bot.get_channel(await guildconfiger.get(thread.guild.id, "character"))
        modlog = self.bot.get_channel(await guildconfiger.get(thread.guild.id, "modlog"))
        if thread.parent_id != forum.id:
            return
        await modlog.send(f"New character created by {thread.owner.mention} in {thread.mention}")


async def setup(bot):
    await bot.add_cog(forumEvents(bot))
