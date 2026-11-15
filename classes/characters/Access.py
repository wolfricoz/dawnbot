"""Who a member is, as far as restrictions care: their roles, their server level and whether they are staff.

A member's server level is the number of the server's level roles their XP has reached (see /config roles), so with
level roles at 100, 500 and 2000 XP, a member with 600 XP is level 2.
"""
from dataclasses import dataclass, field

import discord

from database.database import Occupations, Species
from database.transactions.ExperienceTransactions import ExperienceTransactions
from database.transactions.LevelTransactions import LevelTransactions
from database.transactions.TagRuleTransactions import TagRuleTransactions

ROLE = "role"
LEVEL = "level"
STAFF_ONLY = "staff_only"
# Hidden from members altogether; only staff give it out (used for event gear and species).
EVENT = "event"
# A character's standing with a faction (value: faction id x 10 + tier index, see classes/economy/FactionFlow.py).
REPUTATION = "reputation"
KINDS = [ROLE, LEVEL, STAFF_ONLY, EVENT, REPUTATION]


# ============================================================
def reputation_value(faction_id: int, tier: str) -> int :
	from classes.economy.FactionFlow import TIERS

	return int(faction_id) * 10 + TIERS.index(tier)


# ============================================================
def reputation_parts(value: int) -> tuple[int, str] :
	"""(faction id, tier) of a reputation requirement."""
	from classes.economy.FactionFlow import TIERS

	faction_id, tier_index = divmod(int(value or 0), 10)
	return faction_id, TIERS[min(tier_index, len(TIERS) - 1)]


@dataclass
class Requirement :
	kind: str
	value: int | None = None


@dataclass
class Access :
	role_ids: set[int] = field(default_factory=set)
	level: int = 0
	staff: bool = False
	# A character's standing with factions ({faction id: value}); without one, standing counts as 0 (a new
	# character's), so reputation requirements above Neutral lock.
	standings: dict | None = None

	# ============================================================
	def for_character(self, character_id: int | None) -> "Access" :
		"""This access with a character's standings (a new character's, all 0, when character_id is None)."""
		from dataclasses import replace

		from database.transactions.EconomyTransactions import EconomyTransactions

		standings = EconomyTransactions().standings(character_id) if character_id else {}
		return replace(self, standings=standings)

	# ============================================================
	@staticmethod
	def server_level(guild_id: int, xp: int) -> int :
		return sum(1 for level in LevelTransactions().get_all(guild_id) if level.xp_required <= xp)

	# ============================================================
	@staticmethod
	def of(member: discord.Member) -> "Access" :
		xp = ExperienceTransactions().get(member.id, member.guild.id).xp
		return Access(role_ids={role.id for role in member.roles}, level=Access.server_level(member.guild.id, xp),
		              staff=member.guild_permissions.manage_messages)

	# ============================================================
	def to_dict(self) -> dict :
		return {"roles" : sorted(self.role_ids), "level" : self.level, "staff" : self.staff}

	# ============================================================
	@staticmethod
	def from_dict(data: dict | None) -> "Access" :
		data = data or {}
		return Access(role_ids=set(data.get("roles", [])), level=data.get("level", 0), staff=data.get("staff", False))

	# ============================================================
	def check(self, requirements: list[Requirement]) -> str | None :
		"""Why the member does not meet the requirements, or None when they do. Staff meet every requirement."""
		if self.staff :
			return None
		for requirement in requirements :
			if requirement.kind == ROLE and requirement.value not in self.role_ids :
				return f"needs the <@&{requirement.value}> role"
			if requirement.kind == LEVEL and self.level < (requirement.value or 0) :
				return f"needs server level {requirement.value}"
			if requirement.kind in (STAFF_ONLY, EVENT) :
				return "is only given out by staff"
			if requirement.kind == REPUTATION :
				problem = Access.reputation_problem(requirement.value, self.standings)
				if problem :
					return problem
		return None

	# ============================================================
	@staticmethod
	def reputation_problem(value: int, standings: dict | None) -> str | None :
		from classes.economy.FactionFlow import meets
		from database.transactions.EconomyTransactions import EconomyTransactions

		faction_id, tier = reputation_parts(value)
		if meets((standings or {}).get(faction_id, 0), tier) :
			return None
		faction = EconomyTransactions().faction(faction_id)
		return f"needs {tier.capitalize()} standing with {faction.name if faction else 'a faction'}"

	# ============================================================
	@staticmethod
	def hidden(requirements: list[Requirement]) -> bool :
		return any(requirement.kind == EVENT for requirement in requirements)

	# ============================================================
	@staticmethod
	def for_species(species: Species) -> list[Requirement] :
		return [Requirement(rule.kind, rule.value) for rule in TagRuleTransactions().for_tags(species.tag_ids or [])]

	# ============================================================
	@staticmethod
	def for_gear(item) -> list[Requirement] :
		"""The requirements of a catalog item, from the tags on its post in the gear forum."""
		return [Requirement(rule.kind, rule.value) for rule in TagRuleTransactions().for_tags(item.tag_ids or [])]

	# ============================================================
	@staticmethod
	def for_occupation(occupation: Occupations) -> list[Requirement] :
		requirements = []
		if occupation.role_id :
			requirements.append(Requirement(ROLE, occupation.role_id))
		if occupation.min_level :
			requirements.append(Requirement(LEVEL, occupation.min_level))
		if occupation.staff_only :
			requirements.append(Requirement(STAFF_ONLY))
		if getattr(occupation, "faction_id", None) and getattr(occupation, "faction_tier", None) :
			requirements.append(Requirement(REPUTATION, reputation_value(occupation.faction_id,
			                                                             occupation.faction_tier)))
		return requirements
