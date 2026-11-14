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
KINDS = [ROLE, LEVEL, STAFF_ONLY, EVENT]


@dataclass
class Requirement :
	kind: str
	value: int | None = None


@dataclass
class Access :
	role_ids: set[int] = field(default_factory=set)
	level: int = 0
	staff: bool = False

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
		return None

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
	def for_occupation(occupation: Occupations) -> list[Requirement] :
		requirements = []
		if occupation.role_id :
			requirements.append(Requirement(ROLE, occupation.role_id))
		if occupation.min_level :
			requirements.append(Requirement(LEVEL, occupation.min_level))
		if occupation.staff_only :
			requirements.append(Requirement(STAFF_ONLY))
		return requirements
