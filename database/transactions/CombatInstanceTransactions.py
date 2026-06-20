from sqlalchemy import select

from database.DatabaseController import DatabaseTransactions
from database.database import CombatInstances


class CombatInstanceTransactions(DatabaseTransactions):


	# Fetch the current instance or create one
	def get(self):
		pass

	def get_all(self, active_only=True):
		with self.createsession() as session:
			if active_only:
				return session.scalars(select(CombatInstances).where(CombatInstances.active == True)).all()
			return session.scalars(select(CombatInstances)).all()

	# Create instance
	def create(self, channel_id: int = None, combat_type: str = "encounter"):
		with self.createsession() as session:
			record = CombatInstances(channel_id=channel_id, combat_type=combat_type)
			session.add(record)
			self.commit(session)
			return record

	def update(self):
		pass
	def delete(self):
		pass
	# instances are set per channel.
	def setchannelinstance(self):
		pass

	def getchannelinstance(self):
		pass