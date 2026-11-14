"""Changes to an existing character, and whether they wait for a staff review before they apply.

A set of changes is a dict with any of these keys:
  name, prefix, suffix, avatar_id   the new value
  fields                            {sheet field id (as text): new answer, or None to clear it}
  extras                            the full new list of the player's own fields, [{"key", "value"}]
  stats                             {stat: value} for all seven stats (a respec)
"""
from classes.characters.Special import STATS, Special
from classes.kernel.ConfigData import ConfigData
from database.database import Characters
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions, PENDING
from database.transactions.SheetFieldTransactions import SheetFieldTransactions
from resources.configs.ConfigMapping import ConfigMapping

# What each REAPPROVAL_ON_EDIT mode sends to review. A respec is always reviewed.
LORE_KEYS = {"name", "avatar_id", "fields"}
ALL_KEYS = LORE_KEYS | {"prefix", "suffix", "extras"}
REVIEWED = {"none" : set(), "lore" : LORE_KEYS, "all" : ALL_KEYS}

# Outcomes of submit()
UNCHANGED = "unchanged"
APPLIED = "applied"
RESUBMITTED = "resubmitted"
REVIEW = "review"


class Edits :

	# ============================================================
	@staticmethod
	def split(guild_id: int, changes: dict) -> tuple[dict, dict] :
		"""Splits changes into those that apply right away and those that wait for a review."""
		mode = str(ConfigData().get_key(guild_id, ConfigMapping.REAPPROVAL_ON_EDIT)).lower()
		reviewed = REVIEWED.get(mode, LORE_KEYS) | {"stats"}
		direct = {key : value for key, value in changes.items() if key not in reviewed}
		review = {key : value for key, value in changes.items() if key in reviewed}
		return direct, review

	# ============================================================
	@staticmethod
	def apply(character: Characters, changes: dict) -> tuple[Characters, list[int]] :
		"""Writes changes to the character.

		@return: the updated character and the ids of stored images that are no longer used.
		"""
		unused_images = []
		updates = {}
		if "name" in changes :
			other = CharacterTransactions().get(character.uid, character.guild_id, changes["name"])
			# The name can have been taken while the change was waiting; the character then keeps its own.
			if other is None or other.id == character.id :
				updates["name"] = changes["name"]
		for key in ("prefix", "suffix") :
			if key in changes :
				updates[key] = changes[key]
		if "avatar_id" in changes and changes["avatar_id"] != character.avatar_id :
			if character.avatar_id is not None :
				unused_images.append(character.avatar_id)
			updates["avatar_id"] = changes["avatar_id"]
		if "stats" in changes :
			stats = {stat : int(changes["stats"][stat]) for stat in STATS}
			# A respec moves points around; what is left of the character's total stays unspent.
			total = sum(getattr(character, stat) for stat in STATS) + character.unspent_points
			updates.update(stats)
			updates["unspent_points"] = max(0, total - sum(stats.values()))
		if updates :
			character = CharacterTransactions().update(character.id, **updates)

		if "fields" in changes :
			labels = {str(field.id) : field.label for field in SheetFieldTransactions().get_all(character.guild_id)}
			for field_id, value in changes["fields"].items() :
				# A question that was removed from the sheet in the meantime is skipped.
				if str(field_id) in labels :
					CharacterInfoTransactions().set_answer(character.id, int(field_id), labels[str(field_id)], value)
		if "extras" in changes :
			CharacterInfoTransactions().replace_extras(character.id, changes["extras"])
		return character, unused_images

	# ============================================================
	@staticmethod
	def queue(character: Characters, changes: dict) -> tuple[Characters, list[int]] :
		"""Adds changes to the ones already waiting for review; a newer change to the same thing replaces the older.

		@return: the updated character and the ids of stored images that are no longer used.
		"""
		pending = dict(character.pending_changes or {})
		unused_images = []
		if "avatar_id" in changes and pending.get("avatar_id") not in (None, changes["avatar_id"]) :
			unused_images.append(pending["avatar_id"])
		if "fields" in changes :
			changes = changes | {"fields" : (pending.get("fields") or {}) | changes["fields"]}
		pending.update(changes)
		return CharacterTransactions().update(character.id, pending_changes=pending), unused_images

	# ============================================================
	@staticmethod
	def discard(character: Characters) -> tuple[Characters, list[int]] :
		"""Drops the changes waiting for review (a denied edit).

		@return: the updated character and the ids of stored images that are no longer used.
		"""
		pending = character.pending_changes or {}
		unused_images = []
		if pending.get("avatar_id") not in (None, character.avatar_id) :
			unused_images.append(pending["avatar_id"])
		return CharacterTransactions().update(character.id, pending_changes=None, review_message_id=None), unused_images

	# ============================================================
	@staticmethod
	def submit(character: Characters, changes: dict) -> tuple[str, Characters, list[int]] :
		"""Applies a player's changes, or sends them to review, depending on the character's state and the server.

		A character that is still pending or was denied is under review as a whole, so its changes apply at once and
		it goes (back) to pending.
		@return: the outcome (UNCHANGED, APPLIED, RESUBMITTED or REVIEW), the updated character, and the ids of
		stored images that are no longer used.
		"""
		if character.state != APPROVED :
			character, unused = Edits.apply(character, changes)
			character = CharacterTransactions().update(character.id, state=PENDING)
			return RESUBMITTED, character, unused
		if not changes :
			return UNCHANGED, character, []
		direct, review = Edits.split(character.guild_id, changes)
		character, unused = Edits.apply(character, direct)
		if not review :
			return APPLIED, character, unused
		character, replaced = Edits.queue(character, review)
		return REVIEW, character, unused + replaced

	# ============================================================
	@staticmethod
	def describe(character: Characters, changes: dict) -> str :
		"""The changes as text for the review card: what the character has now and what it would become."""
		lines = []
		if "name" in changes :
			lines.append(f"**Name:** {character.name} → {changes['name']}")
		for key in ("prefix", "suffix") :
			if key in changes :
				lines.append(f"**{key.capitalize()}:** `{getattr(character, key) or 'none'}` → `{changes[key] or 'none'}`")
		if "avatar_id" in changes :
			lines.append("**Avatar:** a new picture (shown on this card)")
		if "stats" in changes :
			old = Special.summary({stat : getattr(character, stat) for stat in STATS})
			lines.append(f"**SPECIAL (respec):** {old} → {Special.summary(changes['stats'])}")
		if "fields" in changes :
			labels = {str(field.id) : field.label for field in SheetFieldTransactions().get_all(character.guild_id)}
			for field_id, value in changes["fields"].items() :
				label = labels.get(str(field_id))
				if label is None :
					continue
				if value in (None, "") :
					lines.append(f"**{label}:** removed")
				elif len(value) > 80 or "\n" in value :
					lines.append(f"**{label}**\n{value}")
				else :
					lines.append(f"**{label}:** {value}")
		if "extras" in changes :
			lines.append("\n**__Extra fields (new list)__**")
			if not changes["extras"] :
				lines.append("none")
			for extra in changes["extras"] :
				if len(extra["value"]) > 80 or "\n" in extra["value"] :
					lines.append(f"**{extra['key']}**\n{extra['value']}")
				else :
					lines.append(f"**{extra['key']}:** {extra['value']}")
		return "\n".join(lines)
