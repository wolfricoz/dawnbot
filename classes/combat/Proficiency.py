"""Weapon and armor proficiency: setting them, and the limits.

A character's proficiency with a weapon is stored on its own copy of the weapon. Players set a tier once; after that
only staff change it (/gm gear proficiency). At most two weapons can be Good or Excellent. Armor proficiency is set the
same way, once by the player and afterwards by staff.
"""
from classes.combat import Rules
from database.database import CharacterGear, Characters
from database.transactions.CharacterGearTransactions import CharacterGearTransactions, OWNED
from database.transactions.CharacterTransactions import CharacterTransactions

GOOD_TIERS = {Rules.EXCELLENT, Rules.GOOD}


class Proficiency :

	# ============================================================
	@staticmethod
	def set_weapon(entry: CharacterGear, tier: str, staff: bool = False) -> tuple[CharacterGear | None, str] :
		"""@return: the updated entry (None when refused) and a message."""
		tier = (tier or "").lower()
		if tier not in Rules.PROFICIENCY :
			return None, f"Pick one of: {', '.join(name.capitalize() for name in Rules.PROFICIENCY_ORDER)}."
		if entry.kind != "weapon" :
			return None, "Proficiency is set on weapons; armor proficiency is /character armor_proficiency."
		if entry.status != OWNED :
			return None, f"{entry.name} is {entry.status}."
		if entry.proficiency and not staff :
			return None, (f"{entry.name} is already {entry.proficiency.capitalize()}. A GM can change it with "
			              f"/gm gear proficiency.")
		if tier in GOOD_TIERS :
			others = [other for other in CharacterGearTransactions().get_all(entry.character_id)
			          if other.id != entry.id and other.kind == "weapon" and (other.proficiency or "") in GOOD_TIERS]
			if len(others) >= Rules.MAX_GOOD_WEAPONS :
				return None, (f"A character can be Good or Excellent with at most {Rules.MAX_GOOD_WEAPONS} weapons; "
				              f"already: {', '.join(other.name for other in others)}.")
		updated = CharacterGearTransactions().update(entry.id, proficiency=tier)
		bonus = Rules.proficiency_bonus(tier)
		extra = " and a crit range one wider" if tier == Rules.EXCELLENT else ""
		return updated, f"{entry.name} is now {tier.capitalize()} ({bonus:+d} to hit{extra})."

	# ============================================================
	@staticmethod
	def set_armor(character: Characters, level: str, staff: bool = False) -> tuple[Characters | None, str] :
		level = (level or "").lower()
		if level not in Rules.ARMOR_CLASSES :
			return None, f"Pick one of: {', '.join(Rules.ARMOR_CLASSES)}."
		if character.armor_proficiency and not staff :
			return None, (f"{character.name}'s armor proficiency is already {character.armor_proficiency}; staff can "
			              f"change it.")
		updated = CharacterTransactions().update(character.id, armor_proficiency=level)
		return updated, (f"{character.name} can now wear {level} armor without a penalty (heavier armor is -2 to hit "
		                 f"per step).")

	# ============================================================
	@staticmethod
	def label(entry: CharacterGear) -> str :
		"""How the character handles the weapon, like `Good`; an unset tier fights as Awful."""
		if entry.kind != "weapon" :
			return ""
		return entry.proficiency.capitalize() if entry.proficiency else "No proficiency set"
