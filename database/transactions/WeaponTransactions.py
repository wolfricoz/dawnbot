from sqlalchemy import Select

from database.database import Weapons
from database.transactions.DatabaseTransactions import DatabaseTransactions


class WeaponTransactions(DatabaseTransactions) :
	"""Weapon types, keyed by their lowercase name."""

	# ============================================================
	def get_all(self) -> list[Weapons] :
		with self.createsession() as session :
			return list(session.scalars(Select(Weapons)).all())

	# ============================================================
	def get(self, name: str) -> Weapons | None :
		with self.createsession() as session :
			return session.scalar(Select(Weapons).where(Weapons.name == name.lower()))

	# ============================================================
	def add(self, name: str, dice: str, modifier: str, hitmodifier: int = 0) -> Weapons | None :
		"""Returns None when a weapon with that name already exists."""
		with self.createsession() as session :
			if self.get(name) is not None :
				return None
			weapon = Weapons(name=name.lower(), dice=dice.lower(), modifier=modifier.lower(),
			                 hitmodifier=hitmodifier or 0)
			session.add(weapon)
			self.commit(session)
			return weapon

	# ============================================================
	def update(self, name: str, dice: str = None, modifier: str = None, hitmodifier: int = None) -> Weapons | None :
		"""Updates the given fields; None leaves a field unchanged."""
		with self.createsession() as session :
			weapon = session.scalar(Select(Weapons).where(Weapons.name == name.lower()))
			if weapon is None :
				return None
			if dice is not None :
				weapon.dice = dice.lower()
			if modifier is not None :
				weapon.modifier = modifier.lower()
			if hitmodifier is not None :
				weapon.hitmodifier = hitmodifier
			self.commit(session)
			return weapon

	# ============================================================
	def delete(self, name: str) -> bool :
		with self.createsession() as session :
			weapon = session.scalar(Select(Weapons).where(Weapons.name == name.lower()))
			if weapon is None :
				return False
			session.delete(weapon)
			self.commit(session)
			return True
