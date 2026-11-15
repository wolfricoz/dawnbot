"""Fights in the database: creating them, loading them as plain data (classes/combat/State.py) and saving them back."""
from sqlalchemy import Select, delete, func

from classes.combat.State import Combatant, ENDED, Fight, OPEN_STATES, Side
from database.database import CombatEntities, CombatInstances, CombatLog, CombatSides
from database.transactions.DatabaseTransactions import DatabaseTransactions

INSTANCE_FIELDS = ["guid", "guild_id", "channel_id", "thread_id", "board_message_id", "gm_uid", "co_gms", "kind",
                   "state", "pacing", "lethal", "round", "order", "turn_index", "deadline", "paused_seconds", "title",
                   "winner_side_id", "late_join", "invites", "pending", "challenge", "idle_pinged"]
ENTITY_FIELDS = ["side_id", "kind", "name", "stats", "character_id", "uid", "bestiary_id", "controller", "behavior",
                 "hp", "hp_max", "ap", "ap_max", "ac", "dt", "sequence", "conditions", "ability_uses", "acted",
                 "idle_turns", "state", "death_successes", "death_failures", "last_attacker_id", "weapon_key",
                 "position", "lethal_ok"]
JSON_DEFAULTS = {"co_gms" : list, "order" : list, "invites" : dict, "pending" : list, "idle_pinged" : list,
                 "conditions" : list, "ability_uses" : dict, "stats" : dict}


class CombatTransactions(DatabaseTransactions) :

	# == creating ==

	# ============================================================
	def create(self, guild_id: int, gm_uid: int, sides: list[str], **fields) -> Fight | None :
		"""Creates a fight with the named sides."""
		with self.createsession() as session :
			record = CombatInstances(guild_id=guild_id, gm_uid=gm_uid,
			                         **{key : value for key, value in fields.items() if key in INSTANCE_FIELDS})
			for key in ("co_gms", "order", "invites", "pending", "idle_pinged") :
				if getattr(record, key) is None :
					setattr(record, key, JSON_DEFAULTS[key]())
			session.add(record)
			session.flush()
			for position, name in enumerate(sides, start=1) :
				session.add(CombatSides(instance_id=record.id, name=name, position=position))
			instance_id = record.id
			self.commit(session)
		return self.load(instance_id)

	# ============================================================
	def add_side(self, instance_id: int, name: str) -> int | None :
		with self.createsession() as session :
			count = len(session.scalars(Select(CombatSides).where(CombatSides.instance_id == instance_id)).all())
			side = CombatSides(instance_id=instance_id, name=name, position=count + 1)
			session.add(side)
			session.flush()
			side_id = side.id
			self.commit(session)
			return side_id

	# ============================================================
	def add_combatant(self, instance_id: int, combatant: Combatant) -> Combatant | None :
		"""Saves a new combatant and returns it with its id."""
		with self.createsession() as session :
			record = CombatEntities(instance_id=instance_id,
			                        **{key : getattr(combatant, key) for key in ENTITY_FIELDS})
			session.add(record)
			session.flush()
			combatant.id = record.id
			self.commit(session)
		return combatant

	# == loading ==

	# ============================================================
	@staticmethod
	def _fight(session, record: CombatInstances) -> Fight :
		sides = [Side(id=side.id, name=side.name, position=side.position)
		         for side in session.scalars(Select(CombatSides).where(CombatSides.instance_id == record.id)
		                                     .order_by(CombatSides.position, CombatSides.id)).all()]
		combatants = []
		for entity in session.scalars(Select(CombatEntities).where(CombatEntities.instance_id == record.id)
		                              .order_by(CombatEntities.position, CombatEntities.id)).all() :
			values = {key : getattr(entity, key) for key in ENTITY_FIELDS}
			for key, factory in JSON_DEFAULTS.items() :
				if key in values and values[key] is None :
					values[key] = factory()
			combatants.append(Combatant(id=entity.id, **values))
		values = {key : getattr(record, key) for key in INSTANCE_FIELDS}
		for key, factory in JSON_DEFAULTS.items() :
			if key in values and values[key] is None :
				values[key] = factory()
		return Fight(id=record.id, sides=sides, combatants=combatants, **values)

	# ============================================================
	def load(self, instance_id: int | None) -> Fight | None :
		if instance_id is None :
			return None
		with self.createsession() as session :
			record = session.scalar(Select(CombatInstances).where(CombatInstances.id == instance_id))
			return self._fight(session, record) if record is not None else None

	# ============================================================
	def load_by_thread(self, thread_id: int) -> Fight | None :
		"""The fight running in a thread (not ended), or None."""
		with self.createsession() as session :
			record = session.scalar(Select(CombatInstances).where(CombatInstances.thread_id == thread_id,
			                                                      CombatInstances.state.in_(OPEN_STATES))
			                        .order_by(CombatInstances.id.desc()))
			return self._fight(session, record) if record is not None else None

	# ============================================================
	def with_deadlines(self) -> list[int] :
		"""The ids of running fights that have a timer."""
		with self.createsession() as session :
			return list(session.scalars(Select(CombatInstances.id).where(CombatInstances.state == "active",
			                                                             CombatInstances.deadline.is_not(None))).all())

	# ============================================================
	def open_fight_of(self, character_id: int) -> int | None :
		"""The id of a fight the character is still in (one that has not ended), or None."""
		with self.createsession() as session :
			return session.scalar(Select(CombatEntities.instance_id)
			                      .join(CombatInstances, CombatInstances.id == CombatEntities.instance_id)
			                      .where(CombatEntities.character_id == character_id,
			                             CombatEntities.state.not_in(["fled", "dead", "removed"]),
			                             CombatInstances.state.in_(OPEN_STATES)))

	# ============================================================
	def open_fights(self, guild_id: int) -> list[int] :
		with self.createsession() as session :
			return list(session.scalars(Select(CombatInstances.id).where(CombatInstances.guild_id == guild_id,
			                                                             CombatInstances.state.in_(OPEN_STATES))).all())

	# == saving ==

	# ============================================================
	def save(self, fight: Fight) -> None :
		"""Writes the fight, its sides and its combatants back."""
		with self.createsession() as session :
			record = session.scalar(Select(CombatInstances).where(CombatInstances.id == fight.id))
			if record is None :
				return
			for key in INSTANCE_FIELDS :
				setattr(record, key, getattr(fight, key))
			if fight.state == ENDED and record.ended_at is None :
				record.ended_at = func.now()
			sides = {side.id : side for side in
			         session.scalars(Select(CombatSides).where(CombatSides.instance_id == fight.id)).all()}
			for side in fight.sides :
				if side.id in sides :
					sides[side.id].name = side.name
					sides[side.id].position = side.position
			entities = {entity.id : entity for entity in
			            session.scalars(Select(CombatEntities).where(CombatEntities.instance_id == fight.id)).all()}
			for combatant in fight.combatants :
				entity = entities.get(combatant.id)
				if entity is None :
					continue
				for key in ENTITY_FIELDS :
					setattr(entity, key, getattr(combatant, key))
			self.commit(session)

	# ============================================================
	def set_fields(self, instance_id: int, **fields) -> None :
		with self.createsession() as session :
			record = session.scalar(Select(CombatInstances).where(CombatInstances.id == instance_id))
			if record is None :
				return
			for key, value in fields.items() :
				if key in INSTANCE_FIELDS :
					setattr(record, key, value)
			self.commit(session)

	# ============================================================
	def delete(self, instance_id: int) -> None :
		with self.createsession() as session :
			session.execute(delete(CombatInstances).where(CombatInstances.id == instance_id))
			self.commit(session)

	# == log ==

	# ============================================================
	def log(self, instance_id: int, round_number: int, action: str, text: str, actor_id: int | None = None,
	        target_id: int | None = None, details: dict | None = None, snapshot: dict | None = None) -> None :
		with self.createsession() as session :
			session.add(CombatLog(instance_id=instance_id, round=round_number, action=action, text=text,
			                      actor_id=actor_id, target_id=target_id, details=details or {}, snapshot=snapshot))
			self.commit(session)

	# ============================================================
	def logs(self, instance_id: int, limit: int = 20) -> list[CombatLog] :
		with self.createsession() as session :
			return list(reversed(session.scalars(Select(CombatLog).where(CombatLog.instance_id == instance_id)
			                                     .order_by(CombatLog.id.desc()).limit(limit)).all()))

	# ============================================================
	def last_undoable(self, instance_id: int) -> CombatLog | None :
		with self.createsession() as session :
			return session.scalar(Select(CombatLog).where(CombatLog.instance_id == instance_id,
			                                              CombatLog.snapshot.is_not(None))
			                      .order_by(CombatLog.id.desc()))

	# ============================================================
	def delete_logs_from(self, instance_id: int, log_id: int) -> None :
		"""Removes a log entry and everything logged after it."""
		with self.createsession() as session :
			session.execute(delete(CombatLog).where(CombatLog.instance_id == instance_id, CombatLog.id >= log_id))
			self.commit(session)
