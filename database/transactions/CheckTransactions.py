from datetime import datetime

from sqlalchemy import Select

from database.database import CheckRolls, Checks
from database.transactions.DatabaseTransactions import DatabaseTransactions

FIELDS = ["message_id", "title", "stat", "dc", "kind", "visibility", "modifier", "allowed", "opposed", "helps",
          "state", "expires_at", "closed_at"]
ROLL_FIELDS = ["side", "natural", "total", "outcome", "helped_by", "details"]


class CheckTransactions(DatabaseTransactions) :
	"""Checks members called and the rolls made on them."""

	# ============================================================
	def create(self, guild_id: int, channel_id: int, caller_uid: int, stat: str, **fields) -> Checks | None :
		with self.createsession() as session :
			record = Checks(guild_id=guild_id, channel_id=channel_id, caller_uid=caller_uid, stat=stat,
			                **{key : value for key, value in fields.items() if key in FIELDS})
			record.allowed = record.allowed or {}
			record.helps = record.helps or []
			record.modifier = record.modifier or 0
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def get(self, check_id: int | None) -> Checks | None :
		if check_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Checks).where(Checks.id == check_id))

	# ============================================================
	def update(self, check_id: int, **fields) -> Checks | None :
		with self.createsession() as session :
			record = session.scalar(Select(Checks).where(Checks.id == check_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if key in FIELDS :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def expired(self, now: datetime) -> list[Checks] :
		"""Open checks whose time ran out."""
		with self.createsession() as session :
			return list(session.scalars(Select(Checks).where(Checks.state == "open", Checks.expires_at.is_not(None),
			                                                 Checks.expires_at <= now)).all())

	# == rolls ==

	# ============================================================
	def rolls(self, check_id: int) -> list[CheckRolls] :
		"""The rolls made on a check, in the order they were made."""
		with self.createsession() as session :
			return list(session.scalars(Select(CheckRolls).where(CheckRolls.check_id == check_id)
			                            .order_by(CheckRolls.id)).all())

	# ============================================================
	def add_roll(self, check_id: int, character_id: int | None, uid: int, name: str, stat: str,
	             **fields) -> CheckRolls | None :
		"""Records a roll. Returns None when the character already rolled on this check."""
		with self.createsession() as session :
			if character_id is not None and session.scalar(
					Select(CheckRolls).where(CheckRolls.check_id == check_id,
					                         CheckRolls.character_id == character_id)) is not None :
				return None
			record = CheckRolls(check_id=check_id, character_id=character_id, uid=uid, name=name[:255], stat=stat,
			                    **{key : value for key, value in fields.items() if key in ROLL_FIELDS})
			record.details = record.details or {}
			record.side = record.side or 0
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None
