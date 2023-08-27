import json
import os
from abc import ABC, abstractmethod

import discord

from components.xpcalculations import xpCalculations


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
            "Name": guildname,
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
        if os.path.exists(f"jsons/{guildid}.json"):
            with open(f"jsons/{guildid}.json") as f:
                data = json.load(f)
                for x in data[key]:
                    if x == channel.id:
                        await interaction.followup.send("Failed to add channel! forum already in config")
                        break
                else:
                    data[key].append(channel.id)
                    await interaction.followup.send(f"channel added to {key}")
                    async for message in channel.history():
                        await xpCalculations.calculate(message, session)

            with open(f"jsons/{guildid}.json", 'w') as f:
                json.dump(data, f, indent=4)

    @staticmethod
    @abstractmethod
    async def addforum(guildid, interaction, channel: discord.ForumChannel, key, session):
        if os.path.exists(f"jsons/{guildid}.json"):
            with open(f"jsons/{guildid}.json") as f:
                data = json.load(f)
                for x in data[key]:
                    if x == channel.id:
                        await interaction.followup.send("Failed to add channel! forum already in config")
                        break
                else:
                    data[key].append(channel.id)
                    await interaction.followup.send(f"channel added to {key}")
                    for thread in channel.threads:
                        async for message in thread.history():
                            await xpCalculations.calculate(message, session)
                    for athread in channel.archived_threads():
                        async for message in athread.history():
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
    async def get(guildid: int, key):
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
                "Name": data.get('Name', None),
                "channels": data.get('channels', []),
                "announcement": data.get("announcement", None),
                "xp_gain": data.get("xp_gain", 1)
            }
        with open(f'jsons/{guildid}.json', 'w') as f:
            json.dump(newdictionary, f, indent=4)
