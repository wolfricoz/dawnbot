"""What approving or denying a review does to a character. Posting cards and messaging players is CharacterFlow's job."""
from classes.characters.Edits import Edits
from database.database import Characters
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions, DENIED, PENDING

# What was under review.
NEW_CHARACTER = "character"
CHANGES = "changes"


class Review :

	# ============================================================
	@staticmethod
	def kind(character: Characters) -> str :
		"""An approved character can only be under review for changes; anything else is reviewed as a whole."""
		return CHANGES if character.state == APPROVED else NEW_CHARACTER

	# ============================================================
	@staticmethod
	def is_open(character: Characters) -> bool :
		"""Whether the character still has something waiting for a decision."""
		if character.state == APPROVED :
			return bool(character.pending_changes)
		return character.state == PENDING

	# ============================================================
	@staticmethod
	def waiting_on(character: Characters) -> str | None :
		"""What has to be approved before this character can be, or None. A player can send a character in with a
		species they made during the interview; that species is reviewed on its own card first."""
		from database.transactions.SpeciesTransactions import APPROVED as SPECIES_APPROVED, SpeciesTransactions

		species_id = character.species_id
		if Review.kind(character) == CHANGES :
			species_id = (character.pending_changes or {}).get("species_id", species_id)
		species = SpeciesTransactions().get(species_id) if species_id else None
		if species is not None and species.state != SPECIES_APPROVED :
			return (f"{character.name}'s species, {species.name}, has not been approved yet. Approve or deny the "
			        f"species on its own card first.")
		return None

	# ============================================================
	@staticmethod
	def approve(character: Characters, reviewer_id: int) -> tuple[Characters, list[int], str] :
		"""Approves a new character, or applies the changes that were waiting.

		@return: the updated character, the ids of stored images that are no longer used, and what was approved.
		"""
		if Review.kind(character) == CHANGES :
			updated, unused = Edits.apply(character, character.pending_changes or {})
			updated = CharacterTransactions().update(updated.id, pending_changes=None, review_message_id=None)
			return updated, unused, CHANGES
		return CharacterTransactions().approve(character.id, reviewer_id), [], NEW_CHARACTER

	# ============================================================
	@staticmethod
	def deny(character: Characters) -> tuple[Characters, list[int], str] :
		"""Denies a new character (it stays the player's to fix and resubmit), or drops the waiting changes.

		@return: the updated character, the ids of stored images that are no longer used, and what was denied.
		"""
		if Review.kind(character) == CHANGES :
			updated, unused = Edits.discard(character)
			return updated, unused, CHANGES
		return CharacterTransactions().update(character.id, state=DENIED, review_message_id=None), [], NEW_CHARACTER
