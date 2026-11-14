from sqlalchemy import Select

from database.database import Levels
from database.transactions.DatabaseTransactions import DatabaseTransactions


class LevelTransactions(DatabaseTransactions) :
	"""Level roles: a role is awarded once a member reaches its xp_required in that guild."""

	# ============================================================
	def get_all(self, guild_id: int) -> list[Levels] :
		"""All level roles of the guild, lowest requirement first."""
		with self.createsession() as session :
			return list(session.scalars(
				Select(Levels).where(Levels.guildid == guild_id).order_by(Levels.xp_required, Levels.id)).all())

	# ============================================================
	def get(self, role_id: int) -> Levels | None :
		with self.createsession() as session :
			return session.scalar(Select(Levels).where(Levels.role_id == role_id))

	# ============================================================
	def add(self, guild_id: int, role_id: int, xp_required: int) -> Levels | None :
		"""Returns None when the role is already a level role."""
		with self.createsession() as session :
			if self.get(role_id) is not None :
				return None
			level = Levels(guildid=guild_id, role_id=role_id, xp_required=xp_required)
			session.add(level)
			self.commit(session)
			return level

	# ============================================================
	def remove(self, role_id: int) -> bool :
		with self.createsession() as session :
			level = session.scalar(Select(Levels).where(Levels.role_id == role_id))
			if level is None :
				return False
			session.delete(level)
			self.commit(session)
			return True

	# ============================================================
	def update(self, role_id: int, xp_required: int) -> Levels | None :
		with self.createsession() as session :
			level = session.scalar(Select(Levels).where(Levels.role_id == role_id))
			if level is None :
				return None
			level.xp_required = xp_required
			self.commit(session)
			return level

	# ============================================================
	def highest_reached(self, guild_id: int, xp: int) -> int | None :
		"""The role id with the highest requirement the given XP meets, or None."""
		reached = [level for level in self.get_all(guild_id) if xp >= level.xp_required]
		if not reached :
			return None
		return reached[-1].role_id

	# ============================================================
	def next_level(self, guild_id: int, xp: int) -> tuple[int | None, int | None] :
		"""The next role to reach and its requirement.

		When every role is reached this returns the top role with None as requirement; when the guild has no level
		roles at all it returns (None, None).
		"""
		levels = self.get_all(guild_id)
		if not levels :
			return None, None
		for level in levels :
			if xp < level.xp_required :
				return level.role_id, level.xp_required
		return levels[-1].role_id, None
