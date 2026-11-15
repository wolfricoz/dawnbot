"""Legendary characters: staff give the status to a character, which doubles its stat limits (10 becomes 20, a species'
13 becomes 26), gives it LEGENDARY_POINTS extra points to spend (5 by default) and one extra ability slot.

Removing the status lowers stats above the normal limits and returns those points, then takes the legendary points back:
from unspent points first, then from the highest stats.
"""
from datetime import datetime, timezone

from classes.characters.SpeciesRules import SpeciesRules
from classes.characters.Special import STATS, Special
from classes.kernel.ConfigData import ConfigData
from database.database import Characters
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.SpeciesTransactions import SpeciesTransactions
from resources.configs.ConfigMapping import ConfigMapping, defaults


class Legendary :

	# ============================================================
	@staticmethod
	def points(guild_id: int) -> int :
		value = ConfigData().get_int(guild_id, ConfigMapping.LEGENDARY_POINTS)
		return max(0, value if value is not None else defaults[ConfigMapping.LEGENDARY_POINTS])

	# ============================================================
	@staticmethod
	def grant(character: Characters, actor_uid: int) -> tuple[Characters | None, str] :
		"""Makes a character legendary. @return: the updated character (None when it already was) and a message."""
		if character.legendary :
			return None, f"{character.name} is already legendary."
		points = Legendary.points(character.guild_id)
		updated = CharacterTransactions().update(character.id, legendary=True, legendary_points=points,
		                                         legendary_by=actor_uid, legendary_at=datetime.now(timezone.utc),
		                                         unspent_points=character.unspent_points + points)
		return updated, (f"🌟 {character.name} is now legendary: stat limits are doubled, {points} extra point"
		                 f"{'s' if points != 1 else ''} to spend and one extra ability slot.")

	# ============================================================
	@staticmethod
	def removal(character: Characters) -> tuple[dict[str, int], int] :
		"""What removing the status does: the new stats, and the new unspent points."""
		rules = Special.rules(character.guild_id)
		limits = SpeciesRules.limits(SpeciesTransactions().get(character.species_id), rules)
		stats = {stat : int(getattr(character, stat)) for stat in STATS}
		unspent = int(character.unspent_points)
		for stat in STATS :
			high = limits[stat][1]
			if stats[stat] > high :
				unspent += stats[stat] - high
				stats[stat] = high
		owed = int(character.legendary_points or 0)
		taken = min(owed, unspent)
		unspent -= taken
		owed -= taken
		while owed > 0 :
			stat = max(STATS, key=lambda name : (stats[name] - limits[name][0], stats[name]))
			if stats[stat] <= limits[stat][0] :
				break
			stats[stat] -= 1
			owed -= 1
		return stats, unspent

	# ============================================================
	@staticmethod
	def remove(character: Characters) -> tuple[Characters | None, str] :
		if not character.legendary :
			return None, f"{character.name} is not legendary."
		stats, unspent = Legendary.removal(character)
		changed = [f"{stat.capitalize()} {getattr(character, stat)} → {value}" for stat, value in stats.items()
		           if value != getattr(character, stat)]
		updated = CharacterTransactions().update(character.id, legendary=False, legendary_points=0, legendary_by=None,
		                                         legendary_at=None, unspent_points=unspent, **stats)
		text = f"{character.name} is no longer legendary. Unspent points: {unspent}."
		if changed :
			text += " Lowered: " + ", ".join(changed) + "."
		return updated, text
