from sqlalchemy import Select, update

from database.database import CharacterGear
from database.transactions.DatabaseTransactions import DatabaseTransactions

OWNED = "owned"
LOST = "lost"
BROKEN = "broken"
SOLD = "sold"
# A consumable used up in a fight.
USED = "used"
STATUSES = [OWNED, LOST, BROKEN, SOLD, USED]
# Crafting materials stack in one entry (see classes/economy/Crafting.py).
MATERIAL = "material"

# Columns update() accepts as keyword arguments.
FIELDS = ["equipped", "status", "changed_by", "price_paid", "proficiency", "quantity", "quality", "name", "slot",
          "condition", "ammo_die"]


class CharacterGearTransactions(DatabaseTransactions) :
	"""The gear characters own. Lost, broken, sold and used items are kept with their status, as history."""

	# ============================================================
	def add(self, character_id: int, gear_item_id: int | None, name: str, kind: str, source: str, price_paid: int,
	        changed_by: int | None = None, quantity: int = 1) -> CharacterGear | None :
		"""Adds an item. Materials stack: a character's owned entry of the same material gets the quantity added."""
		with self.createsession() as session :
			if kind == MATERIAL and gear_item_id is not None :
				stack = session.scalar(Select(CharacterGear).where(CharacterGear.character_id == character_id,
				                                                   CharacterGear.gear_item_id == gear_item_id,
				                                                   CharacterGear.status == OWNED))
				if stack is not None :
					stack.quantity = (stack.quantity or 1) + quantity
					self.commit(session)
					return stack
			entry = CharacterGear(character_id=character_id, gear_item_id=gear_item_id, name=name, kind=kind,
			                      source=source, price_paid=price_paid, changed_by=changed_by, status=OWNED,
			                      equipped=False, quantity=max(1, quantity))
			session.add(entry)
			self.commit(session)
			return entry if entry.id is not None else None

	# ============================================================
	def get(self, entry_id: int) -> CharacterGear | None :
		with self.createsession() as session :
			return session.scalar(Select(CharacterGear).where(CharacterGear.id == entry_id))

	# ============================================================
	def get_all(self, character_id: int, include_gone: bool = False) -> list[CharacterGear] :
		"""The character's gear, oldest first; include_gone adds lost, sold and used items."""
		with self.createsession() as session :
			query = Select(CharacterGear).where(CharacterGear.character_id == character_id)
			if not include_gone :
				query = query.where(CharacterGear.status == OWNED)
			return list(session.scalars(query.order_by(CharacterGear.id)).all())

	# ============================================================
	def update(self, entry_id: int, **fields) -> CharacterGear | None :
		with self.createsession() as session :
			entry = session.scalar(Select(CharacterGear).where(CharacterGear.id == entry_id))
			if entry is None :
				return None
			for key, value in fields.items() :
				if key in FIELDS :
					setattr(entry, key, value)
			self.commit(session)
			return entry

	# ============================================================
	def equip(self, entry_id: int, only_one_of_kind: bool) -> CharacterGear | None :
		"""Equips an item; with only_one_of_kind, every other item of its kind the character owns is unequipped."""
		entry = self.get(entry_id)
		if entry is None :
			return None
		with self.createsession() as session :
			if only_one_of_kind :
				session.execute(update(CharacterGear).where(CharacterGear.character_id == entry.character_id,
				                                            CharacterGear.kind == entry.kind,
				                                            CharacterGear.id != entry.id).values(equipped=False))
			session.execute(update(CharacterGear).where(CharacterGear.id == entry.id).values(equipped=True))
			self.commit(session)
		return self.get(entry_id)

	# ============================================================
	def equipped(self, character_id: int, kind: str) -> list[CharacterGear] :
		with self.createsession() as session :
			return list(session.scalars(Select(CharacterGear).where(CharacterGear.character_id == character_id,
			                                                        CharacterGear.kind == kind,
			                                                        CharacterGear.status == OWNED,
			                                                        CharacterGear.equipped.is_(True))
			                            .order_by(CharacterGear.id)).all())

	# ============================================================
	def delete(self, entry_id: int) -> bool :
		with self.createsession() as session :
			entry = session.scalar(Select(CharacterGear).where(CharacterGear.id == entry_id))
			if entry is None :
				return False
			session.delete(entry)
			self.commit(session)
			return True
