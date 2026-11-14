"""The DM interview that creates or edits a character, one question at a time.

Everything a player answers is saved in their draft (the drafts table) right away, so an interview has no time limit
and survives restarts. This module holds the questions and the rules; it never talks to Discord. The caller sends
the returned text to the player and acts on the outcome (see CharacterFlow).

A draft walks through its queue of steps:
  name, trigger, avatar          asked for every new character
  field:<id>                     one per question on the server's sheet
  stat_method, stats             how the SPECIAL stats are set, and their values
  summary                        the answers so far; from here the player changes answers or submits
"""
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from classes.characters.Card import Card
from classes.characters.Edits import Edits
from classes.characters.ImageStorage import ImageError, ImageStorage
from classes.characters.Sheet import INFO, Sheet
from classes.characters.Special import POINT_BUY, ROLLED, STATS, Special
from classes.kernel.ConfigData import ConfigData
from database.database import Characters, Drafts
from database.transactions.CharacterInfoTransactions import CharacterInfoTransactions
from database.transactions.CharacterTransactions import CharacterTransactions, PENDING
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.SheetFieldTransactions import SheetFieldTransactions
from resources.configs.ConfigMapping import ConfigMapping

CREATE = "create"
EDIT = "edit"
RESPEC = "respec"

# Outcomes of an answer that ends the interview; the outcomes of Edits.submit are used as well.
CREATED = "created"
CANCELLED = "cancelled"

# Webhook names can be 80 characters, and Discord refuses these words in them.
NAME_LIMIT = 80
FORBIDDEN_NAME_PARTS = ["discord", "clyde"]
TRIGGER_LIMIT = 50
# The word that stands for the player's message when they describe their prefix and suffix.
PLACEHOLDER = "text"
SUMMARY_VALUE_LIMIT = 150

STAT_ORDER = ", ".join(stat.capitalize() for stat in STATS)


@dataclass
class Reply :
	"""What to tell the player, and what happened when the interview ended."""
	text: str
	finished: bool = False
	outcome: str | None = None
	character: Characters | None = None
	# Stored images that are no longer used and should be removed from storage.
	discard_images: list[int] = field(default_factory=list)


class Interview :

	# == starting ==

	# ============================================================
	@staticmethod
	def start(uid: int, guild_id: int, guild_name: str, kind: str,
	          character: Characters | None = None) -> tuple[Drafts | None, str] :
		"""Starts an interview and returns its draft with the first message to send.

		Returns (None, why) when the user is already in an interview.
		"""
		existing = DraftTransactions().get(uid)
		if existing is not None :
			return None, Interview.busy_text(existing)

		answers = {"guild_name" : guild_name, "fields" : {}}
		if character is not None :
			answers |= {
				"name"      : character.name,
				"prefix"    : character.prefix,
				"suffix"    : character.suffix,
				"avatar_id" : character.avatar_id,
				"fields"    : {str(key) : value for key, value in
				               CharacterInfoTransactions().get_answers(character.id).items()},
			}
		if kind == RESPEC :
			answers["stat_method"] = POINT_BUY
			answers["budget"] = sum(getattr(character, stat) for stat in STATS) + character.unspent_points
		answers["queue"] = Interview._queue(guild_id, kind, answers)

		draft = DraftTransactions().create(uid, guild_id, kind, answers["queue"][0],
		                                   target_id=character.id if character else None, answers=answers)
		intro = {
			CREATE : f"**Creating a character on {guild_name}**\n"
			         f"I'll ask you some questions, one at a time. There is no time limit: every answer is saved, so "
			         f"you can stop and come back later.\n"
			         f"Type **back** for the previous question, **skip** to leave an optional question empty, or "
			         f"**cancel** to stop.",
			EDIT   : f"**Editing {character.name if character else ''} on {guild_name}**",
			RESPEC : f"**Changing the SPECIAL stats of {character.name if character else ''} on {guild_name}**\n"
			         f"Staff review a respec before it applies. Type **cancel** to stop.",
		}[kind]
		return draft, f"{intro}\n\n{Interview.prompt(draft)}"

	# ============================================================
	@staticmethod
	def busy_text(draft: Drafts) -> str :
		answers = draft.answers or {}
		what = {CREATE : "creating a character", EDIT : f"editing {answers.get('name', 'a character')}",
		        RESPEC : f"changing the stats of {answers.get('name', 'a character')}"}.get(draft.kind, "an interview")
		return (f"You are still {what} on {answers.get('guild_name', 'another server')}. Finish it in our DMs, or "
		        f"type **cancel** there to stop it, before starting something new.")

	# ============================================================
	@staticmethod
	def _queue(guild_id: int, kind: str, answers: dict) -> list[str] :
		"""The steps this interview walks through, decided once when it starts."""
		if kind == RESPEC :
			return ["stats", "summary"]
		if kind == EDIT :
			# Only questions that became required since the character was made are asked up front.
			missing = Sheet.missing_required(guild_id, answers["fields"])
			return [f"field:{sheet_field.id}" for sheet_field in missing] + ["summary"]
		steps = ["name", "trigger"]
		if ImageStorage.configured() :
			steps.append("avatar")
		steps += [f"field:{sheet_field.id}" for sheet_field in Sheet.questions(guild_id)]
		if len(Special.rules(guild_id).methods) > 1 :
			steps.append("stat_method")
		return steps + ["stats", "summary"]

	# == asking ==

	# ============================================================
	@staticmethod
	def prompt(draft: Drafts) -> str :
		"""The message that asks for the draft's current step."""
		answers = draft.answers
		step = draft.step
		if step == "name" :
			text = "**What is your character's name?**"
			if answers.get("name") :
				text += f"\nCurrently: {answers['name']}"
			return text
		if step == "trigger" :
			text = (f"**How will you speak as {answers.get('name', 'your character')}?**\n"
			        f"Send an example message, with the word `{PLACEHOLDER}` where your message goes. What you put "
			        f"before it becomes the prefix, what you put after it the suffix.\n"
			        f"`Aria: {PLACEHOLDER}` means you write `Aria: Hello there`.\n"
			        f"`{PLACEHOLDER} -a` means you write `Hello there -a`.\n"
			        f"`[{PLACEHOLDER}]` means you write `[Hello there]`.")
			if answers.get("prefix") or answers.get("suffix") :
				text += f"\nCurrently: {Card.trigger_text(answers.get('prefix'), answers.get('suffix'))}"
			return text
		if step == "avatar" :
			text = (f"**Send a picture for {answers.get('name', 'your character')}.**\n"
			        f"Upload an image here (PNG, JPG, WEBP or GIF, up to 8 MB).")
			if answers.get("avatar_id") :
				text += "\nYou already sent one; a new image replaces it."
			return text
		if step.startswith("field:") :
			return Interview._field_prompt(draft)
		if step == "stat_method" :
			rules = Special.rules(draft.guild_id)
			return (f"**How do you want to set your SPECIAL stats?**\n"
			        f"1. **buy**: every stat starts at {rules.base} and you get {rules.bonus} extra points to spend. "
			        f"You can lower a stat to free up points.\n"
			        f"2. **roll**: I roll seven values and you decide which stat gets which. The total is never "
			        f"higher than buying gives you, and you can reroll as often as you like.\n"
			        f"Type **buy** or **roll**.")
		if step == "stats" :
			return Interview._stats_prompt(draft)
		return Interview._summary(draft)

	# ============================================================
	@staticmethod
	def _field_prompt(draft: Drafts) -> str :
		fields = SheetFieldTransactions().get_all(draft.guild_id)
		index = next((i for i, sheet_field in enumerate(fields) if f"field:{sheet_field.id}" == draft.step), None)
		if index is None :
			return "That question is no longer on the sheet. Type **skip** to continue."
		current = fields[index]
		lines = []
		# The notes right above this question, and its section heading when it is the first question under it.
		notes = []
		for earlier in reversed(fields[:index]) :
			if earlier.type != INFO :
				break
			notes.insert(0, earlier)
		previous = fields[index - len(notes) - 1] if index - len(notes) - 1 >= 0 else None
		if current.section and (previous is None or previous.section != current.section) :
			lines.append(f"__**{current.section}**__")
		for note in notes :
			lines.append(f"*{note.label}*\n{note.help or ''}".strip())
		lines.append(Sheet.describe(current))
		answer = draft.answers["fields"].get(str(current.id))
		if answer :
			lines.append(f"Current answer: {Interview._shorten(answer)}")
		return "\n".join(lines)

	# ============================================================
	@staticmethod
	def _budget(draft: Drafts) -> int :
		return draft.answers.get("budget") or Special.rules(draft.guild_id).budget

	# ============================================================
	@staticmethod
	def _stats_prompt(draft: Drafts) -> str :
		rules = Special.rules(draft.guild_id)
		method = draft.answers.get("stat_method") or rules.methods[0]
		if method == ROLLED :
			Interview._ensure_roll(draft)
			return (f"**Your SPECIAL roll:** {', '.join(str(value) for value in draft.rolled_values)}\n"
			        f"Decide which stat gets which value: send the seven values in this order:\n"
			        f"{STAT_ORDER}\n"
			        f"Type **reroll** to roll again (rerolls so far: {draft.rerolls}).")
		budget = Interview._budget(draft)
		if draft.kind == RESPEC :
			intro = f"You have **{budget}** points to divide over your stats."
		else :
			intro = (f"Every stat starts at {rules.base} and you have {rules.bonus} extra points, so **{budget}** "
			         f"points in total. Lower a stat to free up points for another.")
		return (f"**Set your SPECIAL stats.**\n{intro} Every stat has to be between {rules.minimum} and "
		        f"{rules.maximum}.\n"
		        f"Send seven numbers in this order:\n{STAT_ORDER}\n"
		        f"For example: `{' '.join(str(rules.base) for _ in STATS)}`. Points you do not spend are kept for later.")

	# ============================================================
	@staticmethod
	def _ensure_roll(draft: Drafts) -> None :
		if draft.rolled_values is None :
			draft.rolled_values = Special.roll(Special.rules(draft.guild_id))
			DraftTransactions().save(draft)

	# ============================================================
	@staticmethod
	def _shorten(value: str, limit: int = SUMMARY_VALUE_LIMIT) -> str :
		value = " ".join(str(value).split())
		return value if len(value) <= limit else f"{value[:limit - 1]}…"

	# ============================================================
	@staticmethod
	def _summary_items(draft: Drafts) -> list[tuple[str, str, str]] :
		"""The answers on the summary as (step to change it, label, value)."""
		answers = draft.answers
		items = []
		if draft.kind != RESPEC :
			items.append(("name", "Name", answers.get("name") or "not set"))
			items.append(("trigger", "Speaks with", Card.trigger_text(answers.get("prefix"), answers.get("suffix"))))
			if ImageStorage.configured() :
				items.append(("avatar", "Picture", "set" if answers.get("avatar_id") else "not set"))
			for sheet_field in Sheet.questions(draft.guild_id) :
				value = answers["fields"].get(str(sheet_field.id))
				items.append((f"field:{sheet_field.id}", sheet_field.label,
				              Interview._shorten(value) if value else "not answered"))
		if draft.kind != EDIT :
			stats = answers.get("stats")
			value = "not set"
			if stats :
				value = Special.summary(stats)
				if answers.get("stat_method") == ROLLED :
					value += f" (rolled, {draft.rerolls} rerolls)"
			first = "stat_method" if "stat_method" in answers.get("queue", []) else "stats"
			items.append((first, "SPECIAL", value))
		return items

	# ============================================================
	@staticmethod
	def _problems(draft: Drafts) -> list[str] :
		"""What still stops this draft from being submitted."""
		answers = draft.answers
		problems = []
		if draft.kind != RESPEC :
			if not answers.get("name") :
				problems.append("a name")
			if not answers.get("prefix") and not answers.get("suffix") :
				problems.append("a prefix or suffix")
			if draft.kind == CREATE and ImageStorage.configured() and not answers.get("avatar_id") :
				problems.append("a picture")
			problems += [sheet_field.label for sheet_field in Sheet.missing_required(draft.guild_id, answers["fields"])]
		if draft.kind != EDIT and not answers.get("stats") :
			problems.append("SPECIAL stats")
		return problems

	# ============================================================
	@staticmethod
	def _summary(draft: Drafts) -> str :
		lines = ["**Summary**"]
		for number, (_, label, value) in enumerate(Interview._summary_items(draft), start=1) :
			lines.append(f"{number}. **{label}:** {value}")
		problems = Interview._problems(draft)
		if problems :
			lines.append(f"\nStill needed: {', '.join(problems)}.")
		send = "apply your changes" if draft.kind == EDIT else "send it to staff"
		lines.append(f"\nType a number to change that answer, **submit** to {send}, or **cancel** to stop.")
		return "\n".join(lines)

	# == answering ==

	# ============================================================
	@staticmethod
	async def answer(draft: Drafts, text: str, attachments: list | None = None,
	                 store_image: Callable[[object], Awaitable[int]] | None = None) -> Reply :
		"""Handles one message from the player and returns what to send back.

		attachments are the message's uploads; store_image saves one and returns its stored image id, or raises
		ImageError.
		"""
		text = (text or "").strip()
		command = text.lower()
		answers = draft.answers
		if command == "cancel" :
			return Interview._cancel(draft)
		if command == "back" :
			return Interview._back(draft)

		step = draft.step
		problem = None
		if command == "skip" and not step.startswith("field:") :
			return Reply("This one cannot be skipped. Type **back** to return to the previous question."
			             if step != "summary" else "Type the number of an answer to change it, **submit**, or **cancel**.")
		if step == "summary" :
			if command == "submit" :
				return Interview._submit(draft)
			items = Interview._summary_items(draft)
			if command.isdigit() and 1 <= int(command) <= len(items) :
				draft.step = items[int(command) - 1][0]
				answers["returning"] = True
				DraftTransactions().save(draft)
				return Reply(Interview.prompt(draft))
			return Reply("Type the number of an answer to change it, **submit**, or **cancel**.")
		elif step == "name" :
			problem = Interview._answer_name(draft, text)
		elif step == "trigger" :
			problem = Interview._answer_trigger(draft, text)
		elif step == "avatar" :
			return await Interview._answer_avatar(draft, attachments or [], store_image)
		elif step.startswith("field:") :
			problem = Interview._answer_field(draft, text, command)
		elif step == "stat_method" :
			problem = Interview._answer_method(draft, command)
		elif step == "stats" :
			if command == "reroll" and answers.get("stat_method") == ROLLED :
				draft.rolled_values = Special.roll(Special.rules(draft.guild_id))
				draft.rerolls += 1
				DraftTransactions().save(draft)
				return Reply(Interview.prompt(draft))
			problem = Interview._answer_stats(draft, text)

		if problem :
			return Reply(problem)
		Interview._advance(draft)
		return Reply(Interview.prompt(draft))

	# ============================================================
	@staticmethod
	def _advance(draft: Drafts) -> None :
		"""Moves to the next step: back to the summary after changing one answer from it, else along the queue."""
		answers = draft.answers
		queue = answers["queue"]
		if draft.step == "stat_method" :
			draft.step = "stats"
		elif answers.pop("returning", False) or draft.step not in queue :
			draft.step = "summary"
		else :
			draft.step = queue[min(queue.index(draft.step) + 1, len(queue) - 1)]
		if draft.step == "summary" :
			answers.pop("returning", None)
		DraftTransactions().save(draft)

	# ============================================================
	@staticmethod
	def _back(draft: Drafts) -> Reply :
		answers = draft.answers
		queue = answers["queue"]
		if draft.step == "summary" :
			return Reply("You are at the summary. Type a number to change that answer.\n\n" + Interview.prompt(draft))
		if draft.step == "stats" and "stat_method" in queue and len(Special.rules(draft.guild_id).methods) > 1 :
			draft.step = "stat_method"
		elif answers.get("returning") or draft.step not in queue :
			answers.pop("returning", None)
			draft.step = "summary"
		elif queue.index(draft.step) == 0 :
			return Reply("This is the first question.\n\n" + Interview.prompt(draft))
		else :
			draft.step = queue[queue.index(draft.step) - 1]
		DraftTransactions().save(draft)
		return Reply(Interview.prompt(draft))

	# ============================================================
	@staticmethod
	def _new_images(draft: Drafts) -> list[int] :
		"""The picture uploaded during this interview, unless it is the character's current one."""
		avatar_id = draft.answers.get("avatar_id")
		if avatar_id is None :
			return []
		if draft.target_id is not None :
			character = CharacterTransactions().get_by_id(draft.target_id)
			if character is not None and character.avatar_id == avatar_id :
				return []
		return [avatar_id]

	# ============================================================
	@staticmethod
	def _cancel(draft: Drafts) -> Reply :
		images = Interview._new_images(draft)
		DraftTransactions().delete(draft.uid)
		return Reply("Cancelled. Nothing was changed.", finished=True, outcome=CANCELLED, discard_images=images)

	# ============================================================
	@staticmethod
	def check_name(name: str, uid: int, guild_id: int, exclude_id: int | None = None) -> str | None :
		"""Why a character name is refused, or None when it is fine."""
		if not name :
			return "Please send a name."
		if len(name) > NAME_LIMIT :
			return f"That name is {len(name)} characters long; the limit is {NAME_LIMIT}."
		if "\n" in name :
			return "A name has to fit on one line."
		for part in FORBIDDEN_NAME_PARTS :
			if part in name.lower() :
				return f"Discord does not allow names with \"{part}\" in them. Please pick another."
		other = CharacterTransactions().get(uid, guild_id, name)
		if other is not None and other.id != exclude_id :
			return f"You already have a character called {other.name} on this server."
		return None

	# ============================================================
	@staticmethod
	def parse_trigger(text: str) -> tuple[str | None, str | None] | None :
		"""Splits an example like `Aria: text` into (prefix, suffix); None when it has no single placeholder."""
		lowered = text.lower()
		if lowered.count(PLACEHOLDER) != 1 :
			return None
		index = lowered.index(PLACEHOLDER)
		prefix = text[:index].strip() or None
		suffix = text[index + len(PLACEHOLDER) :].strip() or None
		return prefix, suffix

	# ============================================================
	@staticmethod
	def check_trigger(text: str, uid: int, guild_id: int,
	                  exclude_id: int | None = None) -> tuple[tuple[str | None, str | None] | None, str | None] :
		"""Reads a prefix and suffix from an example message.

		@return: ((prefix, suffix), None) when it is fine, otherwise (None, why it was refused).
		"""
		parsed = Interview.parse_trigger(text.strip().strip("`"))
		if parsed is None :
			return None, (f"Please send an example with the word `{PLACEHOLDER}` in it exactly once, like "
			              f"`Aria: {PLACEHOLDER}`.")
		prefix, suffix = parsed
		if not prefix and not suffix :
			return None, f"Put something before or after `{PLACEHOLDER}`, like `Aria: {PLACEHOLDER}`."
		if len(prefix or "") > TRIGGER_LIMIT or len(suffix or "") > TRIGGER_LIMIT :
			return None, f"A prefix or suffix can be at most {TRIGGER_LIMIT} characters."
		if CharacterTransactions().trigger_taken(uid, guild_id, prefix, suffix, exclude_id) :
			return None, "Another of your characters on this server already uses that. Please pick something else."
		return parsed, None

	# ============================================================
	@staticmethod
	def _answer_name(draft: Drafts, text: str) -> str | None :
		problem = Interview.check_name(text, draft.uid, draft.guild_id, draft.target_id)
		if problem is None :
			draft.answers["name"] = text
		return problem

	# ============================================================
	@staticmethod
	def _answer_trigger(draft: Drafts, text: str) -> str | None :
		parsed, problem = Interview.check_trigger(text, draft.uid, draft.guild_id, draft.target_id)
		if parsed is not None :
			draft.answers["prefix"], draft.answers["suffix"] = parsed
		return problem

	# ============================================================
	@staticmethod
	async def _answer_avatar(draft: Drafts, attachments: list, store_image) -> Reply :
		"""Stores the uploaded picture and moves on; a picture it replaces is handed back to be removed."""
		if not attachments :
			return Reply("Please upload an image as a file in this chat.")
		if store_image is None :
			return Reply("Pictures cannot be saved right now. Please try again later.")
		previous = Interview._new_images(draft)
		try :
			draft.answers["avatar_id"] = await store_image(attachments[0])
		except ImageError as e :
			return Reply(str(e))
		Interview._advance(draft)
		return Reply(Interview.prompt(draft), discard_images=previous)

	# ============================================================
	@staticmethod
	def _answer_field(draft: Drafts, text: str, command: str) -> str | None :
		field_id = draft.step.split(":", 1)[1]
		sheet_field = SheetFieldTransactions().get(int(field_id))
		if sheet_field is None or sheet_field.guild_id != draft.guild_id :
			# The question was removed from the sheet while the player was answering.
			draft.answers["fields"].pop(field_id, None)
			return None
		if command == "skip" :
			if sheet_field.required :
				return "This question is required, so it cannot be skipped."
			draft.answers["fields"].pop(field_id, None)
			return None
		value, problem = Sheet.check(sheet_field, text)
		if problem is None :
			draft.answers["fields"][field_id] = value
		return problem

	# ============================================================
	@staticmethod
	def _answer_method(draft: Drafts, command: str) -> str | None :
		methods = {"1" : POINT_BUY, "buy" : POINT_BUY, "point-buy" : POINT_BUY, "point buy" : POINT_BUY,
		           "2" : ROLLED, "roll" : ROLLED, "rolled" : ROLLED}
		method = methods.get(command)
		if method is None or method not in Special.rules(draft.guild_id).methods :
			return "Type **buy** or **roll**."
		if draft.answers.get("stat_method") != method :
			draft.answers.pop("stats", None)
		draft.answers["stat_method"] = method
		return None

	# ============================================================
	@staticmethod
	def _answer_stats(draft: Drafts, text: str) -> str | None :
		rules = Special.rules(draft.guild_id)
		method = draft.answers.get("stat_method") or rules.methods[0]
		values = Special.parse(text)
		if values is None :
			return f"Please send exactly seven whole numbers, in this order:\n{STAT_ORDER}"
		if method == ROLLED :
			Interview._ensure_roll(draft)
			problem = Special.check_assignment(values, draft.rolled_values)
		else :
			problem = Special.check_values(values, rules, Interview._budget(draft))
		if problem is None :
			draft.answers["stat_method"] = method
			draft.answers["stats"] = Special.as_dict(values)
		return problem

	# == submitting ==

	# ============================================================
	@staticmethod
	def _submit(draft: Drafts) -> Reply :
		problems = Interview._problems(draft)
		if problems :
			return Reply(f"Not everything is filled in yet. Still needed: {', '.join(problems)}.\n\n"
			             + Interview.prompt(draft))
		if draft.kind == CREATE :
			return Interview._submit_create(draft)
		character = CharacterTransactions().get_by_id(draft.target_id) if draft.target_id else None
		if character is None :
			DraftTransactions().delete(draft.uid)
			return Reply("That character no longer exists, so nothing was changed.", finished=True,
			             outcome=CANCELLED, discard_images=Interview._new_images(draft))
		changes = Interview._changes(draft, character)
		outcome, character, unused = Edits.submit(character, changes)
		DraftTransactions().delete(draft.uid)
		text = {
			"unchanged"   : "Nothing was changed.",
			"applied"     : f"Your changes to {character.name} are saved.",
			"resubmitted" : f"{character.name} was updated and sent to staff for review. I'll message you when they "
			                f"have looked at it.",
			"review"      : f"Your changes to {character.name} were sent to staff for review. Until they are "
			                f"approved, {character.name} stays as it was.",
		}[outcome]
		return Reply(text, finished=True, outcome=outcome, character=character, discard_images=unused)

	# ============================================================
	@staticmethod
	def _changes(draft: Drafts, character: Characters) -> dict :
		"""What the draft's answers change on the character it edits."""
		answers = draft.answers
		if draft.kind == RESPEC :
			current = {stat : getattr(character, stat) for stat in STATS}
			return {"stats" : answers["stats"]} if answers["stats"] != current else {}
		changes = {}
		for key in ("name", "prefix", "suffix", "avatar_id") :
			if answers.get(key) != getattr(character, key) :
				changes[key] = answers.get(key)
		current = {str(key) : value for key, value in CharacterInfoTransactions().get_answers(character.id).items()}
		fields = {}
		for sheet_field in Sheet.questions(draft.guild_id) :
			key = str(sheet_field.id)
			if answers["fields"].get(key) != current.get(key) :
				fields[key] = answers["fields"].get(key)
		if fields :
			changes["fields"] = fields
		return changes

	# ============================================================
	@staticmethod
	def _submit_create(draft: Drafts) -> Reply :
		answers = draft.answers
		cap = ConfigData().get_int(draft.guild_id, ConfigMapping.CHARACTER_CAP)
		if CharacterTransactions().count_active(draft.uid, draft.guild_id) >= cap :
			return Reply(f"You already have {cap} characters on {answers.get('guild_name', 'this server')}, which is "
			             f"the limit there. Delete one first, then type **submit** again.")
		# Another character can have taken the name or the prefix and suffix since they were answered.
		problem = Interview.check_name(answers["name"], draft.uid, draft.guild_id)
		if problem is None and CharacterTransactions().trigger_taken(draft.uid, draft.guild_id, answers.get("prefix"),
		                                                             answers.get("suffix")) :
			problem = "Another of your characters on this server now uses that prefix and suffix."
		if problem :
			return Reply(f"{problem}\n\n{Interview.prompt(draft)}")

		stats = answers["stats"]
		leftover = Interview._budget(draft) - sum(stats.values()) if answers.get("stat_method") == POINT_BUY else 0
		character = CharacterTransactions().add(
			draft.uid, draft.guild_id, answers["name"], state=PENDING, prefix=answers.get("prefix"),
			suffix=answers.get("suffix"), avatar_id=answers.get("avatar_id"), stat_method=answers.get("stat_method"),
			rerolls=draft.rerolls if answers.get("stat_method") == ROLLED else 0, unspent_points=max(0, leftover),
			currency=ConfigData().get_int(draft.guild_id, ConfigMapping.STARTING_CURRENCY) or 0, **stats)
		if character is None :
			return Reply(f"Something went wrong while saving {answers['name']}. Please type **submit** again.")
		labels = {str(sheet_field.id) : sheet_field.label for sheet_field in Sheet.questions(draft.guild_id)}
		for field_id, value in answers["fields"].items() :
			if field_id in labels and value :
				CharacterInfoTransactions().set_answer(character.id, int(field_id), labels[field_id], value)
		DraftTransactions().delete(draft.uid)
		return Reply(f"**{character.name}** was sent to the staff of {answers.get('guild_name', 'the server')} for "
		             f"review. I'll message you when they have looked at it.",
		             finished=True, outcome=CREATED, character=character)
