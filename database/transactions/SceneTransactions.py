from datetime import datetime

from sqlalchemy import Select

from database.database import ChronicleCharacters, Chronicles, SceneParticipants, Scenes, Users
from database.transactions.DatabaseTransactions import DatabaseTransactions

OPEN_STATES = ("open", "paused")


class SceneTransactions(DatabaseTransactions) :
	"""Scenes, their participants, chronicles and members' away dates."""

	# == scenes ==

	# ============================================================
	def create(self, guild_id: int, channel_id: int, title: str, host_uid: int, **fields) -> Scenes | None :
		with self.createsession() as session :
			record = Scenes(guild_id=guild_id, channel_id=channel_id, title=title, host_uid=host_uid,
			                **{key : value for key, value in fields.items() if hasattr(Scenes, key)})
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def get(self, scene_id: int | None) -> Scenes | None :
		if scene_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Scenes).where(Scenes.id == scene_id))

	# ============================================================
	def open_in(self, channel_id: int | None) -> Scenes | None :
		"""The open (or paused) scene in a channel or thread."""
		if channel_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Scenes).where(Scenes.channel_id == channel_id,
			                                           Scenes.state.in_(OPEN_STATES)))

	# ============================================================
	def open_scenes(self) -> list[Scenes] :
		with self.createsession() as session :
			return list(session.scalars(Select(Scenes).where(Scenes.state.in_(OPEN_STATES))).all())

	# ============================================================
	def update(self, scene_id: int, **fields) -> Scenes | None :
		with self.createsession() as session :
			record = session.scalar(Select(Scenes).where(Scenes.id == scene_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if hasattr(Scenes, key) and key != "id" :
					setattr(record, key, value)
			self.commit(session)
			return record

	# == participants ==

	# ============================================================
	def participants(self, scene_id: int, active_only: bool = True) -> list[SceneParticipants] :
		"""In post order."""
		with self.createsession() as session :
			query = Select(SceneParticipants).where(SceneParticipants.scene_id == scene_id)
			if active_only :
				query = query.where(SceneParticipants.state == "active")
			return list(session.scalars(query.order_by(SceneParticipants.position, SceneParticipants.id)).all())

	# ============================================================
	def participant(self, scene_id: int, character_id: int) -> SceneParticipants | None :
		with self.createsession() as session :
			return session.scalar(Select(SceneParticipants).where(SceneParticipants.scene_id == scene_id,
			                                                      SceneParticipants.character_id == character_id))

	# ============================================================
	def add_participant(self, scene_id: int, character_id: int, uid: int, position: int) -> SceneParticipants | None :
		"""Adds a character, or brings one back that left."""
		current = self.participant(scene_id, character_id)
		if current is not None :
			return self.update_participant(current.id, state="active", position=position)
		with self.createsession() as session :
			record = SceneParticipants(scene_id=scene_id, character_id=character_id, uid=uid, position=position,
			                           state="active", posts=0, words=0, skips=0)
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def update_participant(self, participant_id: int, **fields) -> SceneParticipants | None :
		with self.createsession() as session :
			record = session.scalar(Select(SceneParticipants).where(SceneParticipants.id == participant_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if hasattr(SceneParticipants, key) and key != "id" :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def reorder(self, participant_ids: list[int]) -> None :
		"""Gives the participants positions 1, 2, 3... in the order given."""
		with self.createsession() as session :
			for position, participant_id in enumerate(participant_ids, start=1) :
				record = session.scalar(Select(SceneParticipants).where(SceneParticipants.id == participant_id))
				if record is not None :
					record.position = position
			self.commit(session)

	# == away ==

	# ============================================================
	def away_until(self, uid: int) -> datetime | None :
		with self.createsession() as session :
			return session.scalar(Select(Users.away_until).where(Users.uid == uid))

	# ============================================================
	def set_away(self, uid: int, until: datetime | None) -> bool :
		"""Sets (or clears) a member's away date. False when the member isn't in the users table."""
		with self.createsession() as session :
			record = session.scalar(Select(Users).where(Users.uid == uid))
			if record is None :
				record = Users(uid=uid)
				session.add(record)
			record.away_until = until
			self.commit(session)
			return True

	# == chronicles ==

	# ============================================================
	def add_chronicle(self, guild_id: int, title: str, channel_id: int, **fields) -> Chronicles | None :
		with self.createsession() as session :
			record = Chronicles(guild_id=guild_id, title=title, channel_id=channel_id,
			                    **{key : value for key, value in fields.items() if hasattr(Chronicles, key)})
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def chronicle(self, chronicle_id: int | None) -> Chronicles | None :
		if chronicle_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Chronicles).where(Chronicles.id == chronicle_id))

	# ============================================================
	def update_chronicle(self, chronicle_id: int, **fields) -> Chronicles | None :
		with self.createsession() as session :
			record = session.scalar(Select(Chronicles).where(Chronicles.id == chronicle_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if hasattr(Chronicles, key) and key != "id" :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def set_chronicle_characters(self, chronicle_id: int, counts: dict[int, tuple[int, int]]) -> None :
		"""{character_id: (posts, words)}"""
		with self.createsession() as session :
			for character_id, (posts, words) in counts.items() :
				session.add(ChronicleCharacters(chronicle_id=chronicle_id, character_id=character_id, posts=posts,
				                                words=words))
			self.commit(session)

	# ============================================================
	def chronicle_characters(self, chronicle_id: int) -> list[ChronicleCharacters] :
		with self.createsession() as session :
			return list(session.scalars(Select(ChronicleCharacters)
			                            .where(ChronicleCharacters.chronicle_id == chronicle_id)).all())

	# ============================================================
	def chronicles_of(self, character_id: int) -> list[Chronicles] :
		"""The chronicles a character is in, newest first."""
		with self.createsession() as session :
			return list(session.scalars(Select(Chronicles).join(ChronicleCharacters,
			                                                    ChronicleCharacters.chronicle_id == Chronicles.id)
			                            .where(ChronicleCharacters.character_id == character_id)
			                            .order_by(Chronicles.id.desc())).all())
