from datetime import datetime

from sqlalchemy import Select, delete, func

from database.database import CharacterGear, Characters, CurrencyTransactions as CurrencyRows, GearItems, Lodgings, \
	MerchantHaggles, Merchants, MerchantStock
from database.transactions.DatabaseTransactions import DatabaseTransactions

MERCHANT_FIELDS = ["name", "description", "avatar_url", "location_ids", "faction_id", "markup", "buys", "pays",
                   "services", "lodging_price", "haggle_dc", "restock", "last_restock", "cycle"]
STOCK_FIELDS = ["quantity", "chance", "price", "in_stock", "available"]


class MerchantTransactions(DatabaseTransactions) :
	"""Merchants, their stock, haggles and lodgings, and buying from a merchant in one step."""

	# == merchants ==

	# ============================================================
	def add(self, guild_id: int, name: str, **fields) -> Merchants | None :
		if self.find(guild_id, name) is not None :
			return None
		with self.createsession() as session :
			merchant = Merchants(guild_id=guild_id, name=name, location_ids=[], buys=[], services=[], markup=1.0,
			                     pays=1.0, lodging_price=0, restock="weekly", cycle=0)
			for key, value in fields.items() :
				if key in MERCHANT_FIELDS and value is not None :
					setattr(merchant, key, value)
			session.add(merchant)
			self.commit(session)
			return merchant

	# ============================================================
	def get(self, merchant_id: int | None) -> Merchants | None :
		if merchant_id is None :
			return None
		with self.createsession() as session :
			return session.scalar(Select(Merchants).where(Merchants.id == merchant_id))

	# ============================================================
	def find(self, guild_id: int, name: str) -> Merchants | None :
		with self.createsession() as session :
			return session.scalar(Select(Merchants).where(Merchants.guild_id == guild_id,
			                                              func.lower(Merchants.name) == name.strip().lower()))

	# ============================================================
	def get_all(self, guild_id: int) -> list[Merchants] :
		with self.createsession() as session :
			return list(session.scalars(Select(Merchants).where(Merchants.guild_id == guild_id)
			                            .order_by(func.lower(Merchants.name))).all())

	# ============================================================
	def every_merchant(self) -> list[Merchants] :
		with self.createsession() as session :
			return list(session.scalars(Select(Merchants)).all())

	# ============================================================
	def update(self, merchant_id: int, **fields) -> Merchants | None :
		with self.createsession() as session :
			merchant = session.scalar(Select(Merchants).where(Merchants.id == merchant_id))
			if merchant is None :
				return None
			for key, value in fields.items() :
				if key in MERCHANT_FIELDS :
					setattr(merchant, key, value)
			self.commit(session)
			return merchant

	# ============================================================
	def delete(self, merchant_id: int) -> bool :
		with self.createsession() as session :
			done = session.execute(delete(Merchants).where(Merchants.id == merchant_id)).rowcount > 0
			self.commit(session)
			return done

	# == stock ==

	# ============================================================
	def stock(self, merchant_id: int) -> list[MerchantStock] :
		with self.createsession() as session :
			return list(session.scalars(Select(MerchantStock).where(MerchantStock.merchant_id == merchant_id)
			                            .order_by(MerchantStock.id)).all())

	# ============================================================
	def stock_entry(self, merchant_id: int, gear_item_id: int) -> MerchantStock | None :
		with self.createsession() as session :
			return session.scalar(Select(MerchantStock).where(MerchantStock.merchant_id == merchant_id,
			                                                  MerchantStock.gear_item_id == gear_item_id))

	# ============================================================
	def set_stock(self, merchant_id: int, gear_item_id: int, **fields) -> MerchantStock :
		"""Adds the item to the merchant's stock or changes it; a new line is in stock straight away."""
		with self.createsession() as session :
			line = session.scalar(Select(MerchantStock).where(MerchantStock.merchant_id == merchant_id,
			                                                  MerchantStock.gear_item_id == gear_item_id))
			if line is None :
				line = MerchantStock(merchant_id=merchant_id, gear_item_id=gear_item_id, chance=100, available=True)
				session.add(line)
			for key, value in fields.items() :
				if key in STOCK_FIELDS :
					setattr(line, key, value)
			self.commit(session)
			return line

	# ============================================================
	def remove_stock(self, merchant_id: int, gear_item_id: int) -> bool :
		with self.createsession() as session :
			done = session.execute(delete(MerchantStock).where(MerchantStock.merchant_id == merchant_id,
			                                                   MerchantStock.gear_item_id == gear_item_id)).rowcount > 0
			self.commit(session)
			return done

	# ============================================================
	def buy(self, stock_id: int, character_id: int, price: int, actor_uid: int | None, note: str) -> \
			tuple[CharacterGear | None, str | None] :
		"""Buys one of a stock line: checks it is there and the character can pay, takes the price, counts it out of
		the stock and adds the item, all in one transaction."""
		with self.createsession() as session :
			line = session.scalar(Select(MerchantStock).where(MerchantStock.id == stock_id).with_for_update())
			if line is None or not line.available or (line.in_stock is not None and line.in_stock <= 0) :
				session.rollback()
				return None, "That isn't in stock right now."
			item = session.scalar(Select(GearItems).where(GearItems.id == line.gear_item_id))
			character = session.scalar(Select(Characters).where(Characters.id == character_id).with_for_update())
			if item is None or character is None :
				session.rollback()
				return None, "That isn't sold any more."
			if character.currency < price :
				session.rollback()
				return None, f"{character.name} has {character.currency}, not enough."
			character.currency -= price
			if line.in_stock is not None :
				line.in_stock -= 1
			entry = None
			if item.kind == "material" :
				entry = session.scalar(Select(CharacterGear).where(CharacterGear.character_id == character_id,
				                                                   CharacterGear.gear_item_id == item.id,
				                                                   CharacterGear.status == "owned"))
				if entry is not None :
					entry.quantity = (entry.quantity or 1) + 1
			if entry is None :
				entry = CharacterGear(character_id=character_id, gear_item_id=item.id, name=item.name, kind=item.kind,
				                      source="merchant", price_paid=price, changed_by=actor_uid, quantity=1,
				                      status="owned", equipped=False, condition="good")
				session.add(entry)
			if price :
				session.add(CurrencyRows(character_id=character_id, guild_id=character.guild_id, amount=-price,
				                         reason="buy", actor_uid=actor_uid, note=note))
			self.commit(session)
			return entry, None

	# ============================================================
	def restock(self, merchant_id: int, lines: list[tuple[int, bool, int | None]], when: datetime) -> Merchants | None :
		"""Saves a restock: each line's (stock id, available, in stock), the time, and a new cycle."""
		with self.createsession() as session :
			merchant = session.scalar(Select(Merchants).where(Merchants.id == merchant_id).with_for_update())
			if merchant is None :
				return None
			for stock_id, available, in_stock in lines :
				line = session.scalar(Select(MerchantStock).where(MerchantStock.id == stock_id))
				if line is not None :
					line.available = available
					line.in_stock = in_stock
			merchant.last_restock = when
			merchant.cycle = (merchant.cycle or 0) + 1
			self.commit(session)
			return merchant

	# == haggles ==

	# ============================================================
	def haggles(self, merchant_id: int, character_id: int, cycle: int) -> list[MerchantHaggles] :
		with self.createsession() as session :
			return list(session.scalars(Select(MerchantHaggles).where(MerchantHaggles.merchant_id == merchant_id,
			                                                          MerchantHaggles.character_id == character_id,
			                                                          MerchantHaggles.cycle == cycle)).all())

	# ============================================================
	def add_haggle(self, merchant_id: int, character_id: int, gear_item_id: int | None, cycle: int, discount: int,
	               refused: bool) -> MerchantHaggles :
		with self.createsession() as session :
			haggle = MerchantHaggles(merchant_id=merchant_id, character_id=character_id, gear_item_id=gear_item_id,
			                         cycle=cycle, discount=discount, refused=refused)
			session.add(haggle)
			self.commit(session)
			return haggle

	# == lodgings ==

	# ============================================================
	def lodging(self, character_id: int, location_id: int) -> Lodgings | None :
		with self.createsession() as session :
			return session.scalar(Select(Lodgings).where(Lodgings.character_id == character_id,
			                                             Lodgings.location_id == location_id))

	# ============================================================
	def lodgings(self, character_id: int) -> list[Lodgings] :
		with self.createsession() as session :
			return list(session.scalars(Select(Lodgings).where(Lodgings.character_id == character_id)).all())

	# ============================================================
	def rent(self, character_id: int, location_id: int, merchant_id: int, paid_until: datetime, price: int,
	         actor_uid: int | None, note: str) -> tuple[Lodgings | None, str | None] :
		"""Pays for a room and moves its paid-until date, in one transaction."""
		with self.createsession() as session :
			character = session.scalar(Select(Characters).where(Characters.id == character_id).with_for_update())
			if character is None :
				return None, "That character no longer exists."
			if character.currency < price :
				session.rollback()
				return None, f"{character.name} has {character.currency}, not enough."
			character.currency -= price
			lodging = session.scalar(Select(Lodgings).where(Lodgings.character_id == character_id,
			                                                Lodgings.location_id == location_id))
			if lodging is None :
				lodging = Lodgings(character_id=character_id, location_id=location_id, merchant_id=merchant_id,
				                   paid_until=paid_until)
				session.add(lodging)
			else :
				lodging.paid_until = paid_until
				lodging.merchant_id = merchant_id
			if price :
				session.add(CurrencyRows(character_id=character_id, guild_id=character.guild_id, amount=-price,
				                         reason="lodging", actor_uid=actor_uid, note=note))
			self.commit(session)
			return lodging, None
