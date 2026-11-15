"""Bad-roll protection: a character that fails STREAK rolls in a row has its next failed roll made again, once, and
the better result counts. Any success resets the count.

The count lives on the character (characters.bad_streak), so it carries across fights. Fight rolls count (attacks,
ability attacks, saves, revive, flee and death rolls), as do /combat attack and /dice rolls made as a character (a
/dice roll is bad when it comes out Poor or a Critical failure). NPCs don't have it.
"""
from typing import Callable, TypeVar

STREAK = 3

Roll = TypeVar("Roll")


# ============================================================
def roll(streak: int, make: Callable[[], Roll], succeeded: Callable[[Roll], bool],
         key: Callable[[Roll], int]) -> tuple[Roll, int, Roll | None] :
	"""Makes a roll with the protection.

	@param streak: the bad rolls in a row so far.
	@param make: makes one roll.
	@param succeeded: whether a roll went well.
	@param key: how good a roll is, to keep the better of two failures.
	@return: the roll that counts, the new streak, and the first roll when it was made again (else None).
	"""
	first = make()
	if succeeded(first) :
		return first, 0, None
	if streak < STREAK :
		return first, streak + 1, None
	second = make()
	chosen = second if succeeded(second) or key(second) > key(first) else first
	return chosen, 0 if succeeded(chosen) else 1, first


# ============================================================
def armed(streak: int | None) -> bool :
	"""Whether the next failed roll will be made again."""
	return int(streak or 0) >= STREAK


# ============================================================
def for_character(character_id: int, make: Callable[[], Roll], succeeded: Callable[[Roll], bool],
                  key: Callable[[Roll], int]) -> tuple[Roll, Roll | None] :
	"""roll() for a character outside a fight, reading and saving its streak.

	@return: the roll that counts, and the first roll when it was made again (else None).
	"""
	from database.transactions.CharacterTransactions import CharacterTransactions

	character = CharacterTransactions().get_by_id(character_id)
	streak = int(getattr(character, "bad_streak", 0) or 0) if character is not None else 0
	result, new_streak, first = roll(streak, make, succeeded, key)
	if character is not None and new_streak != streak :
		CharacterTransactions().update(character_id, bad_streak=new_streak)
	return result, first


# ============================================================
def note(first_text: str) -> str :
	"""The line shown when a roll was made again."""
	return f"🍀 After {STREAK} bad rolls in a row, luck turns: this roll was made again (the first was {first_text})."
