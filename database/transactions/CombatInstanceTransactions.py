from sqlalchemy import select

from data.stats.combatcalculations import CombatCalculations
from database.DatabaseController import DatabaseTransactions
from database.database import Characters, CombatInstanceEntities, CombatInstances, Monsters, Npcs
from modules.Armor import armor


class CombatInstanceTransactions(DatabaseTransactions):


	# Fetch the current instance or create one
	def get(self):
		pass

	def get_all(self, active_only=True):
		with self.createsession() as session:
			if active_only:
				return session.scalars(select(CombatInstances).where(CombatInstances.active == True)).unique().all()
			return session.scalars(select(CombatInstances)).unique().all()

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

	def get_channel_instance(self, channel_id: int) :
		with self.createsession() as session :
			instance = session.scalars(select(CombatInstances).where(
				CombatInstances.channel_id == channel_id,
				CombatInstances.active == True
			)).first()
			return instance


	def add_entity(self, instance_id: int, entity: Characters | Npcs | Monsters):
		with self.createsession() as session:
			entity_type = None
			if isinstance(entity, Characters) :
				# build the stats here
				calculations = CombatCalculations({"base_hp": entity.armor_data.hp})
				entity_type = "character"

				# create the entity
				record = CombatInstanceEntities(
					instance_id=instance_id,
					user_uid=entity.uid,
					character_id=entity.id,
					current_hp=calculations.calculate_hp(entity.endurance),
					current_ap=entity.armor_data.ap,
					ac=entity.armor_data.ac,
					entity_type=entity_type
				)
				session.add(record)

			if isinstance(entity, Npcs) :
				entity_type = "npc"
				raise NotImplementedError
			if isinstance(entity, Monsters) :
				entity_type = "monster"
				raise NotImplementedError
			if not entity_type:
				return False

			# commit the data
			self.commit(session)

		return