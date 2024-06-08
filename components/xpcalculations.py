import os
from abc import ABC, abstractmethod
import json

import discord

from components.databaseEvents import TransactionController


class xpCalculations(ABC):
    @staticmethod
    @abstractmethod
    async def calculate(message, session):
        if os.path.exists(f"jsons/{message.guild.id}.json"):
            with open(f"jsons/{message.guild.id}.json") as f:
                data = json.load(f)
                xp_gain = data["xp_gain"]
        # Checks if user is in database, if not; user is added.
        user = TransactionController.get_user(session, message.author.id)
        # Checks message length and converts it into XP
        gained_xp = round(len(message.content) / xp_gain)
        print(f"{message.author} has gained {gained_xp}")
        user.xp += gained_xp
        user.messages += 1
        role = TransactionController.get_highest_role(session, message.guild, user)
        session.commit()
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
    async def check_roles(message: discord.Message, session):
        if len(message.content) <= 50:
            return None, None
        role = await xpCalculations.calculate(message, session)
        new_rank = message.guild.get_role(role)
        if new_rank in message.author.roles or new_rank is None:
            return None, None
        remroles = TransactionController.get_roles(session, message.guild)
        return new_rank, remroles
