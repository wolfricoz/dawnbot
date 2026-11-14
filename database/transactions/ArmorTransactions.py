from sqlalchemy import Select

from database.database import Armors, Characters
from database.transactions.DatabaseTransactions import DatabaseTransactions


class ArmorTransactions(DatabaseTransactions) :
	"""Armor sets. Names are stored lowercase and are unique in practice."""

	# ============================================================
	def get_all(self) -> list[Armors] :
		with self.createsession() as session :
			return list(session.scalars(Select(Armors)).all())

	# ============================================================
	def get(self, name: str) -> Armors | None :
		with self.createsession() as session :
			return session.scalar(Select(Armors).where(Armors.name == name.lower()))

	# ============================================================
	def add(self, name: str, hp: int, ac: int, hitchance: int = 0, modifier: str = "none") -> Armors | None :
		"""Returns None when an armor set with that name already exists."""
		with self.createsession() as session :
			if self.get(name) is not None :
				return None
			armor = Armors(name=name.lower(), hp=hp, ac=ac, hitchance=hitchance,
			               modifier=modifier.lower() if modifier else None)
			session.add(armor)
			self.commit(session)
			return armor

	# ============================================================
	def update(self, name: str, hp: int = None, ac: int = None, hitchance: int = None,
	           modifier: str = None) -> Armors | None :
		"""Updates the given fields; None leaves a field unchanged."""
		with self.createsession() as session :
			armor = session.scalar(Select(Armors).where(Armors.name == name.lower()))
			if armor is None :
				return None
			for field, value in {"hp" : hp, "ac" : ac, "hitchance" : hitchance, "modifier" : modifier}.items() :
				if value is not None :
					setattr(armor, field, value)
			self.commit(session)
			return armor

	# ============================================================
	def delete(self, name: str) -> bool :
		"""Refuses (returns False) while characters still wear the armor; the ORM would otherwise silently clear their
		armor, which breaks their attack rolls."""
		with self.createsession() as session :
			armor = session.scalar(Select(Armors).where(Armors.name == name.lower()))
			if armor is None :
				return False
			if session.scalar(Select(Characters.id).where(Characters.armor == armor.id).limit(1)) is not None :
				return False
			session.delete(armor)
			self.commit(session)
			return True
