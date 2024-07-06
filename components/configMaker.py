import json
import os
from abc import ABC, abstractmethod

import discord

from components.xpCalculations import xpCalculations


class guildconfiger(ABC):

    @staticmethod
    @abstractmethod
    async def create(guildid, guildname):
        try:
            os.mkdir("jsons")
        except:
            pass
        "Creates the config"
        dictionary = {
            "Name"    : guildname,
            "channels": [],
        }
        json_object = json.dumps(dictionary, indent=4)
        if os.path.exists(f"jsons/{guildid}.json"):
            with open(f"jsons/template.json", "w") as outfile:
                outfile.write(json_object)
        else:
            with open(f"jsons/{guildid}.json", "w") as outfile:
                outfile.write(json_object)
                print(f"config created for {guildid}")

    @staticmethod
    @abstractmethod
    async def edit_value(guildid, newvalue, key):
        if os.path.exists(f"jsons/{guildid}.json"):
            with open(f"jsons/{guildid}.json") as f:
                data = json.load(f)
                data[key] = newvalue
            with open(f"jsons/{guildid}.json", 'w') as f:
                json.dump(data, f, indent=4)

    @staticmethod
    @abstractmethod
    async def addchannel(guildid, interaction, channel: discord.TextChannel, key, session):
        if not os.path.exists(f"jsons/{guildid}.json"):
            await guildconfiger.create(guildid, interaction.guild.name)
        with open(f"jsons/{guildid}.json") as f:
            data = json.load(f)
            if channel.id in data[key]:
                await interaction.followup.send("Failed to add channel! Channel already in config")
            else:
                data[key].append(channel.id)
                await interaction.followup.send(f"Channel added to {key}")
                async for message in channel.history():
                    await xpCalculations.calculate(message, session)
                for thread in channel.threads:
                    async for m in thread.history():
                        await xpCalculations.calculate(m, session)

        with open(f"jsons/{guildid}.json", 'w') as f:
            json.dump(data, f, indent=4)

    @staticmethod
    @abstractmethod
    async def addforum(guildid, interaction, channel: discord.ForumChannel, key, session):
        if not os.path.exists(f"jsons/{guildid}.json"):
            await guildconfiger.create(guildid, interaction.guild.name)
        with open(f"jsons/{guildid}.json") as f:
            data = json.load(f)
            if channel.id in data[key]:
                await interaction.followup.send("Failed to add channel! forum already in config")
            data[key].append(channel.id)
            await interaction.followup.send(f"channel added to {key}")
            await guildconfiger.addthreads(guildid, interaction, channel, key, session)

        with open(f"jsons/{guildid}.json", 'w') as f:
            json.dump(data, f, indent=4)

    @staticmethod
    @abstractmethod
    async def addthreads(guildid, interaction, channel: discord.ForumChannel, key, session, checkhistory: bool = True):
        if not os.path.exists(f"jsons/{guildid}.json"):
            await guildconfiger.create(guildid, interaction.guild.name)
        with open(f"jsons/{guildid}.json") as f:
            data = json.load(f)
            threads = 0
            for thread in channel.threads:
                if thread.id in data[key]:
                    continue
                data[key].append(channel.id)
                threads += 1
                if not checkhistory:
                    continue
                async for message in thread.history():
                    await xpCalculations.calculate(message, session)
        with open(f"jsons/{guildid}.json", 'w') as f:
            json.dump(data, f, indent=4)
        await interaction.followup.send(f"added {threads} threads to config")

    @staticmethod
    @abstractmethod
    async def addthread(guildid, thread: discord.Thread, key, session, checkhistory: bool = True):
        if not os.path.exists(f"jsons/{guildid}.json"):
            await guildconfiger.create(guildid, thread.guild.name)
        with open(f"jsons/{guildid}.json") as f:
            data = json.load(f)
            if thread.id in data[key]:
                return
            data[key].append(thread.id)
            if checkhistory:
                async for message in thread.history():
                    await xpCalculations.calculate(message, session)
        with open(f"jsons/{guildid}.json", 'w') as f:
            json.dump(data, f, indent=4)

    @staticmethod
    @abstractmethod
    async def remchannel(guildid: int, channelid: int, key):
        if os.path.exists(f"jsons/{guildid}.json"):
            with open(f"jsons/{guildid}.json") as f:
                data = json.load(f)
                data[key].remove(channelid)
            with open(f"jsons/{guildid}.json", 'w') as f:
                json.dump(data, f, indent=4)

    @staticmethod
    @abstractmethod
    async def get(guildid: int, key) -> str | list | int:
        if os.path.exists(f"jsons/{guildid}.json"):
            with open(f"jsons/{guildid}.json") as f:
                data = json.load(f)
                return data[key]

    @staticmethod
    @abstractmethod
    async def updateconfig(guildid):
        with open(f'jsons/{guildid}.json', 'r+') as file:
            data = json.load(file)
            newdictionary = {
                "Name"        : data.get('Name', None),
                "channels"    : data.get('channels', []),
                "announcement": data.get("announcement", None),
                "xp_gain"     : data.get("xp_gain", 1),
                "timeline"    : data.get("timeline", ""),
                "character"   : data.get("character", ""),
                "modlog"      : data.get("modlog", ""),
            }
        with open(f'jsons/{guildid}.json', 'w') as f:
            json.dump(newdictionary, f, indent=4)
