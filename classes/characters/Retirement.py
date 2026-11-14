"""Retiring a character and bringing it back. Posting and messages are the command's job."""
from classes.characters.Choices import Choices
from classes.kernel.ConfigData import ConfigData
from database.database import Characters
from database.transactions.AutoproxyTransactions import AutoproxyTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions, PENDING, RETIRED
from resources.configs.ConfigMapping import ConfigMapping


class Retirement :

	# ============================================================
	@staticmethod
	def retire(character: Characters) -> tuple[Characters | None, list[int], str | None] :
		"""Retires an approved character: it stops posting, frees its place under the cap and in its occupation, and
		keeps its sheet, experience, gear and currency. Changes waiting for review are dropped.

		@return: the updated character, stored images no longer used (a picture waiting for review), and why it was
		refused, if it was.
		"""
		if character.state != APPROVED :
			return None, [], "Only an approved character can be retired."
		pending = character.pending_changes or {}
		unused = [pending["avatar_id"]] if pending.get("avatar_id") not in (None, character.avatar_id) else []
		AutoproxyTransactions().clear_character(character.id)
		updated = CharacterTransactions().update(character.id, state=RETIRED, pending_changes=None,
		                                         review_message_id=None)
		return updated, unused, None

	# ============================================================
	@staticmethod
	def unretire(character: Characters) -> tuple[Characters | None, str | None, str | None] :
		"""Brings a retired character back. It counts toward the cap again and goes back to staff for review.

		@return: the updated character, a note for the player (its occupation was full and was cleared), and why it
		was refused, if it was.
		"""
		if character.state != RETIRED :
			return None, None, f"{character.name} is not retired."
		cap = ConfigData().get_int(character.guild_id, ConfigMapping.CHARACTER_CAP)
		if CharacterTransactions().count_active(character.uid, character.guild_id) >= cap :
			return None, None, f"You already have {cap} characters here, which is this server's limit."
		note = None
		updates = {"state" : PENDING}
		if character.occupation_id is not None and not Choices.room_for(character.occupation_id, character.id) :
			updates["occupation_id"] = None
			note = "Their occupation is full now, so they come back without one; staff can give them one later."
		return CharacterTransactions().update(character.id, **updates), note, None
