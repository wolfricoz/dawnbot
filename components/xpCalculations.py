import os
from abc import ABC, abstractmethod
import json

import discord

from components.databaseEvents import TransactionController, xpTransactions


class xpCalculations(ABC):
    @staticmethod
    @abstractmethod
    async def calculate(message):
        if os.path.exists(f"jsons/{message.guild.id}.json"):
            with open(f"jsons/{message.guild.id}.json") as f:
                data = json.load(f)
                xp_gain = data.get("xp_gain", 5)
        # Checks if user is in database, if not; user is added.
        user = TransactionController.get_user(message.author.id)
        # Checks message length and converts it into XP
        gained_xp = round(len(message.content) / xp_gain)
        print(f"{message.author} has gained experience: {gained_xp}")
        xpTransactions.add_xp(message.author.id, gained_xp)
        role = TransactionController.get_highest_role(message.guild, user)
        return role

    @staticmethod
    @abstractmethod
    async def check_size(message: discord.Message):
        if len(message.content) <= 50 and message.mentions:
            return True

        if len(message.content) <= 300 and message.author.guild_permissions.manage_messages is False:
            return False
        return True

    @staticmethod
    @abstractmethod
    async def check_roles(message: discord.Message):
        if len(message.content) <= 50:
            return None, None
        role = await xpCalculations.calculate(message)
        new_rank = message.guild.get_role(role)
        remroles = TransactionController.get_roles(message.guild)
        for remrole in remroles.copy():
            if remrole is new_rank:
                remroles.remove(remrole)
                continue
            if remrole not in message.author.roles:
                remroles.remove(remrole)
                continue
        if new_rank in message.author.roles and not remroles or new_rank is None and not remroles:
            return None, None
        return new_rank, remroles
