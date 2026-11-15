"""The rules of scenes (design/roleplay-tools.md, section 2): whose turn it is, what a post does to the order, and when
someone is nudged or skipped. No Discord or database here: participants are anything with id, character_id, uid,
last_post_at and last_nudged_at, given in post order.
"""
from datetime import datetime, timedelta

ORDER = "order"
FREE = "free"
MODES = [ORDER, FREE]
OPEN = "open"
PAUSED = "paused"
ENDED = "ended"
IDLE_GRACE_DAYS = 7


# ============================================================
def aware(moment: datetime | None) -> datetime | None :
	from datetime import timezone

	if moment is None :
		return None
	return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


# ============================================================
def current(participants: list, turn_index: int) :
	"""The participant whose turn it is, or None."""
	if not participants :
		return None
	return participants[turn_index % len(participants)]


# ============================================================
def next_index(participants: list, turn_index: int, away_uids: set[int] | None = None) -> int :
	"""The next participant's index after turn_index, passing over members who are away (unless everyone is)."""
	if not participants :
		return 0
	away_uids = away_uids or set()
	count = len(participants)
	for step in range(1, count + 1) :
		index = (turn_index + step) % count
		if participants[index].uid not in away_uids :
			return index
	return (turn_index + 1) % count


# ============================================================
def first_present(participants: list, turn_index: int, away_uids: set[int] | None = None) -> int :
	"""turn_index, or the next index when the participant there is away."""
	if not participants :
		return 0
	turn_index %= len(participants)
	if participants[turn_index].uid not in (away_uids or set()) :
		return turn_index
	return next_index(participants, turn_index, away_uids)


# ============================================================
def after_post(participants: list, turn_index: int, poster_id, away_uids: set[int] | None = None) -> tuple[
	list, int, bool] :
	"""What a post does in an ordered scene.

	The poster whose turn it is passes the turn on. A post out of turn moves its poster into the current spot, so the
	order adapts to how people post, and it stays the turn of whoever it was (Rico's call): with A B C D and B to
	post, a post by D makes the order A D B C and it is still B's turn.

	@return: the new order, the new turn index, and whether the turn passed on.
	"""
	if not participants :
		return participants, 0, False
	turn_index %= len(participants)
	ids = [participant.id for participant in participants]
	if poster_id not in ids :
		return participants, turn_index, False
	if participants[turn_index].id == poster_id :
		return participants, next_index(participants, turn_index, away_uids), True
	order = [participant for participant in participants if participant.id != poster_id]
	poster = participants[ids.index(poster_id)]
	# Removing someone before the current spot shifts the current participant one to the left.
	if ids.index(poster_id) < turn_index :
		turn_index -= 1
	order.insert(turn_index, poster)
	return order, turn_index + 1, False


# ============================================================
def nudge_due(turn_started_at: datetime | None, last_nudged_at: datetime | None, hours: int, now: datetime) -> bool :
	"""Whether the player whose turn it is should get a reminder: the turn is older than hours and they weren't reminded
	since it started."""
	turn_started_at, last_nudged_at = aware(turn_started_at), aware(last_nudged_at)
	if turn_started_at is None or hours <= 0 :
		return False
	if now - turn_started_at < timedelta(hours=hours) :
		return False
	return last_nudged_at is None or last_nudged_at < turn_started_at


# ============================================================
def skip_due(turn_started_at: datetime | None, hours: int, now: datetime) -> bool :
	turn_started_at = aware(turn_started_at)
	return turn_started_at is not None and hours > 0 and now - turn_started_at >= timedelta(hours=hours)


# ============================================================
def free_nudges(participants: list, hours: int, now: datetime, away_uids: set[int] | None = None) -> list :
	"""In a free scene: the participants every other participant has posted after, whose last post (or joining) is
	older than hours, and who weren't reminded since."""
	away_uids = away_uids or set()
	due = []
	for participant in participants :
		if participant.uid in away_uids :
			continue
		mine = aware(participant.last_post_at) or aware(getattr(participant, "joined_at", None))
		if mine is None or now - mine < timedelta(hours=hours) :
			continue
		others = [aware(other.last_post_at) for other in participants if other.id != participant.id]
		if not others or any(other is None or other <= mine for other in others) :
			continue
		nudged = aware(participant.last_nudged_at)
		if nudged is not None and nudged >= mine :
			continue
		due.append(participant)
	return due


# ============================================================
def idle_state(last_activity: datetime | None, warned_at: datetime | None, idle_days: int, now: datetime) -> str | None :
	"""`warn` when a scene has been quiet for idle_days and wasn't warned, `end` a week after the warning, else None."""
	last_activity, warned_at = aware(last_activity), aware(warned_at)
	if idle_days <= 0 or last_activity is None :
		return None
	if warned_at is not None and warned_at >= last_activity :
		return "end" if now - warned_at >= timedelta(days=IDLE_GRACE_DAYS) else None
	return "warn" if now - last_activity >= timedelta(days=idle_days) else None


# ============================================================
def words(text: str) -> int :
	return len((text or "").split())
