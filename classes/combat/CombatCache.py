"""In-memory copy of armor, weapons and characters, used by autocomplete and combat rolls.

Every write goes through the database transactions first and then refreshes the affected part of the cache, so the
cache never holds data the database does not. Callers get copies of the entries; mutating them never touches the
cache.
"""
import copy
import logging

from classes.kernel.Queue import Singleton
from database.transactions.ArmorTransactions import ArmorTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.WeaponTransactions import WeaponTransactions


class CombatCache(metaclass=Singleton) :
	# {name: {"id", "hp", "ac", "hitchance", "modifier"}}
	armor: dict[str, dict] = {}
	# {name: {"dice", "modifier", "hitmodifier"}}
	weapons: dict[str, dict] = {}
	# {user_id: {name: {stats..., "armor": armor id}}}
	characters: dict[int, dict[str, dict]] = {}

	# ============================================================
	def load_all(self) :
		self.load_armor()
		self.load_weapons()
		self.load_characters()
		logging.info(
			f"Combat cache loaded: {len(self.armor)} armor sets, {len(self.weapons)} weapons, {sum(len(c) for c in self.characters.values())} characters")

	# ============================================================
	def load_armor(self) -> dict :
		self.armor = {
			armor.name.lower() : {
				"id"        : armor.id,
				"hp"        : armor.hp,
				"ac"        : armor.ac,
				"hitchance" : armor.hitchance,
				"modifier"  : armor.modifier,
			} for armor in ArmorTransactions().get_all()
		}
		return self.armor

	# ============================================================
	def load_weapons(self) -> dict :
		self.weapons = {
			weapon.name : {
				"dice"        : weapon.dice,
				"modifier"    : weapon.modifier,
				"hitmodifier" : weapon.hitmodifier or 0,
			} for weapon in WeaponTransactions().get_all()
		}
		return self.weapons

	# ============================================================
	def load_characters(self) -> dict :
		characters = {}
		for character in CharacterTransactions().get_every_character() :
			characters.setdefault(character.uid, {})[character.name] = {
				"prestige"     : character.prestige,
				"strength"     : character.strength,
				"perception"   : character.perception,
				"endurance"    : character.endurance,
				"charisma"     : character.charisma,
				"intelligence" : character.intelligence,
				"agility"      : character.agility,
				"luck"         : character.luck,
				"armor"        : character.armor,
			}
		self.characters = characters
		return self.characters

	# == reads (copies) ==

	# ============================================================
	def get_armor(self, name: str) -> dict | None :
		armor = self.armor.get(name.lower())
		return copy.deepcopy(armor)

	# ============================================================
	def get_armor_by_id(self, armor_id: int) -> dict | None :
		for name, armor in self.armor.items() :
			if armor["id"] == armor_id :
				return copy.deepcopy(armor) | {"name" : name}
		return None

	# ============================================================
	def get_weapon(self, name: str) -> dict | None :
		return copy.deepcopy(self.weapons.get(name.lower()))

	# ============================================================
	def get_user_characters(self, user_id: int) -> dict[str, dict] :
		return copy.deepcopy(self.characters.get(user_id, {}))

	# ============================================================
	def get_character(self, user_id: int, name: str) -> dict | None :
		return copy.deepcopy(self.characters.get(user_id, {}).get(name.lower()))

	# == writes ==

	# ============================================================
	def create_armor(self, name: str, hp: int, ac: int, hitchance: int = 0, modifier: str = "none") :
		armor = ArmorTransactions().add(name, hp, ac, hitchance, modifier)
		self.load_armor()
		return armor

	# ============================================================
	def update_armor(self, name: str, **fields) :
		armor = ArmorTransactions().update(name, **fields)
		self.load_armor()
		return armor

	# ============================================================
	def remove_armor(self, name: str) -> bool :
		ArmorTransactions().delete(name)
		self.load_armor()
		# The delete is refused while characters still wear the armor; report what actually happened.
		return name.lower() not in self.armor

	# ============================================================
	def create_weapon(self, name: str, dice: str, modifier: str, hitmodifier: int = 0) :
		weapon = WeaponTransactions().add(name, dice, modifier, hitmodifier)
		self.load_weapons()
		return weapon

	# ============================================================
	def update_weapon(self, name: str, **fields) :
		weapon = WeaponTransactions().update(name, **fields)
		self.load_weapons()
		return weapon

	# ============================================================
	def remove_weapon(self, name: str) -> bool :
		WeaponTransactions().delete(name)
		self.load_weapons()
		return name.lower() not in self.weapons

	# ============================================================
	def create_character(self, user_id: int, guild_id: int, name: str, armor: str, **stats) :
		"""Returns None when the armor does not exist or the user already has a character with that name."""
		armor_data = self.get_armor(armor)
		if armor_data is None :
			return None
		character = CharacterTransactions().add(user_id, guild_id, name, armor_data["id"], **stats)
		self.load_characters()
		return character

	# ============================================================
	def update_character(self, user_id: int, name: str, armor: str = None, **stats) :
		armor_id = None
		if armor is not None :
			armor_data = self.get_armor(armor)
			if armor_data is None :
				return None
			armor_id = armor_data["id"]
		character = CharacterTransactions().update(user_id, name, armor_id, **stats)
		self.load_characters()
		return character

	# ============================================================
	def remove_character(self, user_id: int, name: str) -> bool :
		removed = CharacterTransactions().delete(user_id, name)
		self.load_characters()
		return removed
