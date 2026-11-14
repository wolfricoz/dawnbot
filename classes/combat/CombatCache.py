"""In-memory copy of armor and weapons, used by autocomplete and combat rolls.

Every write goes through the database transactions first and then refreshes the affected part of the cache, so the
cache never holds data the database does not. Callers get copies of the entries; mutating them never touches the
cache. Characters are not cached: they change in too many places, so they are always read from the database.
"""
import copy
import logging

from classes.characters.Special import STATS
from classes.kernel.Queue import Singleton
from database.database import Characters
from database.transactions.ArmorTransactions import ArmorTransactions
from database.transactions.WeaponTransactions import WeaponTransactions

# What a character fights in while it has no armor equipped, and the values an armor set's catalog entry leaves out.
DEFAULT_ARMOR = {"id" : None, "name" : "unarmored", "hp" : 75, "ap" : 25, "ac" : 12, "hitchance" : 0,
                 "modifier" : None}


class CombatCache(metaclass=Singleton) :
	# {name: {"id", "hp", "ac", "hitchance", "modifier"}}
	armor: dict[str, dict] = {}
	# {name: {"dice", "modifier", "hitmodifier"}}
	weapons: dict[str, dict] = {}

	# ============================================================
	def load_all(self) :
		self.load_armor()
		self.load_weapons()
		logging.info(f"Combat cache loaded: {len(self.armor)} armor sets, {len(self.weapons)} weapons")

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
	@staticmethod
	def equipped_armor(character: Characters) -> dict :
		"""The armor a character fights in: its equipped armor set, with the numbers from the catalog's combat
		values; anything the catalog leaves out (or no armor at all) uses the default armor."""
		from classes.gear.Gear import Gear

		armor = copy.deepcopy(DEFAULT_ARMOR)
		worn = Gear.equipped_armor(character.id)
		if worn is None :
			return armor
		entry, item = worn
		armor["name"] = entry.name
		if item is not None :
			for key in ("hp", "ap", "ac", "hitchance") :
				if isinstance((item.combat or {}).get(key), int) :
					armor[key] = item.combat[key]
		return armor

	# ============================================================
	@staticmethod
	def combatant(character: Characters) -> dict :
		"""A character as combat uses it: its name, its seven stats and the armor it fights in."""
		return {"id" : character.id, "name" : character.name, "armor" : CombatCache.equipped_armor(character),
		        **{stat : getattr(character, stat) for stat in STATS}}

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
