from datetime import datetime

from sqlalchemy import Select, func

from database.database import CharacterReputation, CraftProjects, Downtime, Factions, JobClaims, Jobs, Recipes, \
	ReputationLog, StudyProgress
from database.transactions.DatabaseTransactions import DatabaseTransactions


class EconomyTransactions(DatabaseTransactions) :
	"""Factions and standing, jobs and claims, downtime, language study, recipes and crafting projects."""

	# == generic ==

	# ============================================================
	def _get(self, model, record_id: int | None) :
		if record_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(model).where(model.id == record_id))

	# ============================================================
	def _add(self, model, **fields) :
		with self.createsession() as session :
			record = model(**{key : value for key, value in fields.items() if hasattr(model, key)})
			session.add(record)
			self.commit(session)
			return record if record.id is not None else None

	# ============================================================
	def _update(self, model, record_id: int, **fields) :
		with self.createsession() as session :
			record = session.scalar(Select(model).where(model.id == record_id))
			if record is None :
				return None
			for key, value in fields.items() :
				if hasattr(model, key) and key != "id" :
					setattr(record, key, value)
			self.commit(session)
			return record

	# ============================================================
	def _delete(self, model, record_id: int) -> bool :
		with self.createsession() as session :
			record = session.scalar(Select(model).where(model.id == record_id))
			if record is None :
				return False
			session.delete(record)
			self.commit(session)
			return True

	# ============================================================
	def _find(self, model, guild_id: int, name: str) :
		with self.createsession() as session :
			return session.scalar(Select(model).where(model.guild_id == guild_id,
			                                          func.lower(model.name) == (name or "").strip().lower()))

	# == factions ==

	# ============================================================
	def factions(self, guild_id: int) -> list[Factions] :
		with self.createsession() as session :
			return list(session.scalars(Select(Factions).where(Factions.guild_id == guild_id)
			                            .order_by(func.lower(Factions.name))).all())

	# ============================================================
	def faction(self, faction_id: int | None) -> Factions | None :
		return self._get(Factions, faction_id)

	# ============================================================
	def find_faction(self, guild_id: int, name: str) -> Factions | None :
		return self._find(Factions, guild_id, name)

	# ============================================================
	def add_faction(self, guild_id: int, name: str, **fields) -> Factions | None :
		if self.find_faction(guild_id, name) is not None :
			return None
		return self._add(Factions, guild_id=guild_id, name=name, rivals=fields.pop("rivals", []), **fields)

	# ============================================================
	def update_faction(self, faction_id: int, **fields) -> Factions | None :
		return self._update(Factions, faction_id, **fields)

	# ============================================================
	def delete_faction(self, faction_id: int) -> bool :
		return self._delete(Factions, faction_id)

	# ============================================================
	def standing(self, character_id: int, faction_id: int) -> int :
		with self.createsession() as session :
			value = session.scalar(Select(CharacterReputation.value).where(
				CharacterReputation.character_id == character_id, CharacterReputation.faction_id == faction_id))
			return int(value or 0)

	# ============================================================
	def standings(self, character_id: int) -> dict[int, int] :
		with self.createsession() as session :
			rows = session.execute(Select(CharacterReputation.faction_id, CharacterReputation.value)
			                       .where(CharacterReputation.character_id == character_id)).all()
			return {faction_id : value for faction_id, value in rows}

	# ============================================================
	def set_standing(self, character_id: int, faction_id: int, value: int, change: int, reason: str,
	                 actor_uid: int | None) -> None :
		with self.createsession() as session :
			record = session.scalar(Select(CharacterReputation).where(CharacterReputation.character_id == character_id,
			                                                          CharacterReputation.faction_id == faction_id))
			if record is None :
				session.add(CharacterReputation(character_id=character_id, faction_id=faction_id, value=value))
			else :
				record.value = value
			if change :
				session.add(ReputationLog(character_id=character_id, faction_id=faction_id, amount=change,
				                          reason=reason[:32], actor_uid=actor_uid))
			self.commit(session)

	# == jobs ==

	# ============================================================
	def add_job(self, guild_id: int, **fields) -> Jobs | None :
		return self._add(Jobs, guild_id=guild_id, **fields)

	# ============================================================
	def job(self, job_id: int | None) -> Jobs | None :
		return self._get(Jobs, job_id)

	# ============================================================
	def update_job(self, job_id: int, **fields) -> Jobs | None :
		return self._update(Jobs, job_id, **fields)

	# ============================================================
	def jobs(self, guild_id: int, states: tuple[str, ...] = ("open", "taken")) -> list[Jobs] :
		with self.createsession() as session :
			return list(session.scalars(Select(Jobs).where(Jobs.guild_id == guild_id, Jobs.state.in_(states))
			                            .order_by(Jobs.id)).all())

	# ============================================================
	def overdue_jobs(self, now: datetime) -> list[Jobs] :
		with self.createsession() as session :
			return list(session.scalars(Select(Jobs).where(Jobs.state.in_(("open", "taken")),
			                                               Jobs.deadline.is_not(None), Jobs.deadline <= now)).all())

	# ============================================================
	def claims(self, job_id: int, states: tuple[str, ...] = ("claimed", "waiting")) -> list[JobClaims] :
		with self.createsession() as session :
			return list(session.scalars(Select(JobClaims).where(JobClaims.job_id == job_id,
			                                                    JobClaims.state.in_(states))
			                            .order_by(JobClaims.id)).all())

	# ============================================================
	def add_claim(self, job_id: int, character_id: int, uid: int, state: str) -> JobClaims | None :
		return self._add(JobClaims, job_id=job_id, character_id=character_id, uid=uid, state=state)

	# ============================================================
	def update_claim(self, claim_id: int, **fields) -> JobClaims | None :
		return self._update(JobClaims, claim_id, **fields)

	# == downtime ==

	# ============================================================
	def downtime_on(self, character_id: int, day: str) -> Downtime | None :
		with self.createsession() as session :
			return session.scalar(Select(Downtime).where(Downtime.character_id == character_id, Downtime.day == day))

	# ============================================================
	def add_downtime(self, character_id: int, day: str, activity: str, outcome: str, details: dict) -> Downtime | None :
		if self.downtime_on(character_id, day) is not None :
			return None
		return self._add(Downtime, character_id=character_id, day=day, activity=activity, outcome=outcome,
		                 details=details)

	# ============================================================
	def study(self, character_id: int, language_id: int) -> int :
		with self.createsession() as session :
			value = session.scalar(Select(StudyProgress.points).where(StudyProgress.character_id == character_id,
			                                                          StudyProgress.language_id == language_id))
			return int(value or 0)

	# ============================================================
	def set_study(self, character_id: int, language_id: int, points: int) -> None :
		with self.createsession() as session :
			record = session.scalar(Select(StudyProgress).where(StudyProgress.character_id == character_id,
			                                                    StudyProgress.language_id == language_id))
			if record is None :
				session.add(StudyProgress(character_id=character_id, language_id=language_id, points=points))
			else :
				record.points = points
			self.commit(session)

	# == crafting ==

	# ============================================================
	def recipes(self, guild_id: int) -> list[Recipes] :
		with self.createsession() as session :
			return list(session.scalars(Select(Recipes).where(Recipes.guild_id == guild_id)
			                            .order_by(func.lower(Recipes.name))).all())

	# ============================================================
	def recipe(self, recipe_id: int | None) -> Recipes | None :
		return self._get(Recipes, recipe_id)

	# ============================================================
	def find_recipe(self, guild_id: int, name: str) -> Recipes | None :
		return self._find(Recipes, guild_id, name)

	# ============================================================
	def add_recipe(self, guild_id: int, name: str, **fields) -> Recipes | None :
		if self.find_recipe(guild_id, name) is not None :
			return None
		return self._add(Recipes, guild_id=guild_id, name=name, **fields)

	# ============================================================
	def update_recipe(self, recipe_id: int, **fields) -> Recipes | None :
		return self._update(Recipes, recipe_id, **fields)

	# ============================================================
	def delete_recipe(self, recipe_id: int) -> bool :
		return self._delete(Recipes, recipe_id)

	# ============================================================
	def projects(self, character_id: int, state: str = "working") -> list[CraftProjects] :
		with self.createsession() as session :
			return list(session.scalars(Select(CraftProjects).where(CraftProjects.character_id == character_id,
			                                                        CraftProjects.state == state)
			                            .order_by(CraftProjects.id)).all())

	# ============================================================
	def project(self, project_id: int | None) -> CraftProjects | None :
		return self._get(CraftProjects, project_id)

	# ============================================================
	def add_project(self, character_id: int, recipe_id: int, reserved: list) -> CraftProjects | None :
		return self._add(CraftProjects, character_id=character_id, recipe_id=recipe_id, reserved=reserved,
		                 days_done=0, masterwork=False, state="working")

	# ============================================================
	def update_project(self, project_id: int, **fields) -> CraftProjects | None :
		return self._update(CraftProjects, project_id, **fields)
