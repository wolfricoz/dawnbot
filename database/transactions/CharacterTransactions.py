from typing import List

from sqlalchemy import select

from database.DatabaseController import DatabaseTransactions
from database.database import Characters


class CharacterTransactions(DatabaseTransactions):

	def get_all(self, user_id: int, guild_id: int) -> List[Characters]:
		with self.createsession() as session:
			return session.scalars(select(Characters).where(Characters.uid == user_id, Characters.guild_id == guild_id)).unique().all()
