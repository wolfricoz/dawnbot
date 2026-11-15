"""The species and occupations a member can pick for a character."""
from dataclasses import dataclass

from classes.characters.Access import Access
from classes.kernel.ConfigData import ConfigData
from database.database import Occupations, Species
from database.transactions.OccupationTransactions import OccupationTransactions
from database.transactions.SpeciesTransactions import APPROVED, SpeciesTransactions

DEFAULT_SPECIES = "Human"
DEFAULT_SPECIES_TEXT = "Ordinary people, with no changes to the SPECIAL stats."
# Config row that marks a server's default species as created, so an owner who removes it does not get it back.
SEEDED_KEY = "SPECIES_SEEDED"


@dataclass
class OccupationChoice :
	occupation: Occupations
	holders: int
	# Why the member cannot pick it right now, or None.
	locked: str | None

	@property
	def label(self) -> str :
		limit = self.occupation.max_holders
		return f"{self.occupation.name} ({self.holders}/{limit if limit is not None else '∞'})"


class Choices :

	# == species ==

	# ============================================================
	@staticmethod
	def ensure_default_species(guild_id: int) -> bool :
		"""Gives a server the default species the first time it is seen. The server must be in the servers table."""
		if ConfigData().get_guild(guild_id).get(SEEDED_KEY) :
			return False
		added = False
		if SpeciesTransactions().find(guild_id, DEFAULT_SPECIES) is None :
			added = SpeciesTransactions().add(guild_id, DEFAULT_SPECIES, state=APPROVED,
			                                  description=DEFAULT_SPECIES_TEXT) is not None
		ConfigData().add_key(guild_id, SEEDED_KEY, "yes", overwrite=True)
		return added

	# ============================================================
	@staticmethod
	def species(guild_id: int, access: Access) -> list[Species] :
		"""The approved species the member may pick; restricted ones they do not qualify for are left out."""
		available = []
		for species in SpeciesTransactions().get_all(guild_id, states=[APPROVED]) :
			requirements = Access.for_species(species)
			if access.staff or (not Access.hidden(requirements) and access.check(requirements) is None) :
				available.append(species)
		return available

	# == occupations ==

	# ============================================================
	@staticmethod
	def occupations(guild_id: int, access: Access, character_id: int | None = None) -> list[OccupationChoice] :
		"""Every occupation of the server, with how many hold it and whether the member can pick it.

		character_id is the character being edited; it does not count against the occupation it already holds.
		"""
		choices = []
		# Faction requirements read the character's standing (a new character's is 0 everywhere).
		access = access.for_character(character_id)
		for occupation in OccupationTransactions().get_all(guild_id) :
			holders = len(OccupationTransactions().holders(occupation.id, exclude_character=character_id))
			locked = access.check(Access.for_occupation(occupation))
			if locked is None and not Choices.has_room(occupation, holders) :
				locked = "is full"
			choices.append(OccupationChoice(occupation, holders, locked))
		return choices

	# ============================================================
	@staticmethod
	def has_room(occupation: Occupations, holders: int) -> bool :
		return occupation.max_holders is None or holders < occupation.max_holders

	# ============================================================
	@staticmethod
	def room_for(occupation_id: int | None, character_id: int | None = None) -> bool :
		"""Whether the occupation has a place left for the character (which does not count against itself)."""
		occupation = OccupationTransactions().get(occupation_id)
		if occupation is None :
			return True
		holders = len(OccupationTransactions().holders(occupation.id, exclude_character=character_id))
		return Choices.has_room(occupation, holders)
