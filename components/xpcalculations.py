import os
from abc import ABC, abstractmethod
import json
from components.databaseEvents import transaction


class xpCalculations(ABC):
    @staticmethod
    @abstractmethod
    async def calculate(message, session):
        if os.path.exists(f"jsons/{message.guild.id}.json"):
            with open(f"jsons/{message.guild.id}.json") as f:
                data = json.load(f)
                xp_gain = data["xp_gain"]
        # Checks if user is in database, if not; user is added.
        user = transaction.get_user(session, message.author.id)
        # Checks message length and converts it into XP
        gained_xp = round(len(message.content) / xp_gain)
        print(f"{message.author} has gained {gained_xp}")
        user.xp += gained_xp
        user.messages += 1
        role = transaction.get_highest_role(session, message.guild, user)
        session.commit()
        return role

