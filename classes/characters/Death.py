"""A character's death in a lethal fight, and staff bringing one back. Posting and messages are the caller's job.

A dead character gets its own status: it stops posting (proxying only uses approved characters), frees its place under
the cap and in its occupation, and keeps its sheet, experience, gear and currency. Its forum post is locked.
"""
from database.database import Characters
from database.transactions.AutoproxyTransactions import AutoproxyTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions, DEAD


class Death :

	# ============================================================
	@staticmethod
	def die(character: Characters) -> tuple[Characters | None, str | None] :
		"""Marks a character dead. @return: the updated character, or None and why it was refused."""
		if character.state == DEAD :
			return None, f"{character.name} is already dead."
		AutoproxyTransactions().clear_character(character.id)
		updated = CharacterTransactions().update(character.id, state=DEAD, pending_changes=None,
		                                         review_message_id=None)
		return updated, None

	# ============================================================
	@staticmethod
	def resurrect(character: Characters) -> tuple[Characters | None, str | None] :
		"""Brings a dead character back as approved (a staff decision, so it skips review)."""
		if character.state != DEAD :
			return None, f"{character.name} is not dead."
		return CharacterTransactions().update(character.id, state=APPROVED), None
