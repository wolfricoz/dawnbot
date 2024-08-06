from discord.ext import commands, tasks

from components.databaseEvents import TransactionController


class Tasks(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.keep_database_alive.start()

    def cog_unload(self):
        self.keep_database_alive.cancel()

    @tasks.loop(hours=1)
    async def keep_database_alive(self):
        TransactionController.keep_alive()


async def setup(bot):
    await bot.add_cog(Tasks(bot))
