import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from components import database
from sqlalchemy.orm import Session
from components.configmaker import guildconfiger
database.database().create()
session = Session(database.engine)
load_dotenv('.env')
token = os.getenv('TOKEN')
PREFIX = os.getenv('PREFIX')
# declares the bots intent
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
activity = discord.Activity(type=discord.ActivityType.watching, name="over RMR")
bot = commands.Bot(command_prefix=PREFIX, case_insensitive=False, intents=intents, activity=activity)

@bot.event
async def on_ready():
    dev = bot.get_channel(1141714483312599200)
    await dev.send("Dawnbot online and ready.")

    for guild in bot.guilds:
        await guildconfiger.create(guild.id, guild.name)
        await guildconfiger.updateconfig(guild.id)
        for member in guild.members:
            query = session.query(database.Users).filter_by(uid=member.id).first()
            if query is not None:
                continue
            user = database.Users(uid=member.id)
            session.add(user)
            session.commit()

    await bot.tree.sync()
    print("Commands synced, start up _done_")

@bot.event
async def setup_hook():
    bot.lobbyages = bot.get_channel(454425835064262657)
    for filename in os.listdir("modules"):

        if filename.endswith('.py'):
            await bot.load_extension(f"modules.{filename[:-3]}")
            print({filename[:-3]})
        else:
            print(f'Unable to load {filename[:-3]}')

@bot.command(aliases=["cr", "reload"])
@commands.is_owner()
async def cogreload(ctx):
    filesloaded = []
    for filename in os.listdir("modules"):
        if filename.endswith('.py'):
            await bot.reload_extension(f"modules.{filename[:-3]}")
            filesloaded.append(filename[:-3])
    fp = ', '.join(filesloaded)
    await ctx.send(f"Modules loaded: {fp}")
    await bot.tree.sync()


# runs the bot with the token
bot.run(token)
