from sqlalchemy import Select, func

from database.database import Templates
from database.transactions.DatabaseTransactions import DatabaseTransactions
from database.transactions.UserTransactions import UserTransactions

# How many templates one user may keep.
MAX_TEMPLATES = 20


class TemplateTransactions(DatabaseTransactions) :
	"""Server templates, owned per user so a template captured in one server can be applied in another."""

	# ============================================================
	def add(self, uid: int, name: str, data: dict) -> Templates | None :
		"""Returns None when the user already has a template with that name."""
		# Templates reference users.uid, so make sure the user is registered.
		UserTransactions().ensure_global(uid)
		with self.createsession() as session :
			if self.get(uid, name) is not None :
				return None
			template = Templates(uid=uid, name=name.lower(), data=data)
			session.add(template)
			self.commit(session)
			return template

	# ============================================================
	def get(self, uid: int, name: str) -> Templates | None :
		with self.createsession() as session :
			return session.scalar(Select(Templates).where(Templates.uid == uid, Templates.name == name.lower()))

	# ============================================================
	def get_names(self, uid: int) -> list[str] :
		with self.createsession() as session :
			return list(session.scalars(Select(Templates.name).where(Templates.uid == uid).order_by(Templates.name)).all())

	# ============================================================
	def count(self, uid: int) -> int :
		with self.createsession() as session :
			return session.scalar(Select(func.count()).select_from(Templates).where(Templates.uid == uid))

	# ============================================================
	def delete(self, uid: int, name: str) -> bool :
		with self.createsession() as session :
			template = session.scalar(Select(Templates).where(Templates.uid == uid, Templates.name == name.lower()))
			if template is None :
				return False
			session.delete(template)
			self.commit(session)
			return True
