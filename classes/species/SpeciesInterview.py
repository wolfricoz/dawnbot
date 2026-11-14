"""The DM interview that creates or changes a species, and what approving or denying one does.

Like the character interview, every answer is saved in the player's draft (kind species or species_edit), so it has
no time limit. This module holds the questions and the rules; SpeciesFlow sends the messages.
"""
from dataclasses import dataclass

from classes.characters.Interview import FORBIDDEN_NAME_PARTS, Reply, STAT_ORDER
from classes.characters.SpeciesRules import HIGHEST, LOWEST, SpeciesRules
from classes.characters.Special import STATS, Special
from database.database import Drafts, Species
from database.transactions.DraftTransactions import DraftTransactions
from database.transactions.SpeciesTransactions import APPROVED, DENIED, PENDING, SpeciesTransactions

CREATE = "species"
EDIT = "species_edit"
KINDS = (CREATE, EDIT)

CREATED = "created"
REVIEW = "review"
CANCELLED = "cancelled"

NAME_LIMIT = 100
TEXT_LIMIT = 1500
STEPS = ["name", "description", "benefits", "drawbacks", "maximums", "minimums", "modifiers", "summary"]
LABELS = {"name" : "Name", "description" : "Description", "benefits" : "Benefits", "drawbacks" : "Drawbacks",
          "maximums" : "Highest values", "minimums" : "Lowest values", "modifiers" : "Starting changes"}
TEXT_STEPS = ("description", "benefits", "drawbacks")
STAT_STEPS = ("maximums", "minimums", "modifiers")


@dataclass
class Definition :
	"""A species as the player described it: its texts and its seven maximums, minimums and starting changes."""
	name: str
	description: str
	benefits: str
	drawbacks: str
	maximums: list[int]
	minimums: list[int]
	modifiers: list[int]


class SpeciesInterview :

	# ============================================================
	@staticmethod
	def _defaults(guild_id: int, species: Species | None) -> dict :
		"""The answers an interview starts from: empty for a new species, the species (with any changes waiting for
		review) for an edit."""
		rules = Special.rules(guild_id)
		if species is None :
			return {"maximums" : [rules.maximum] * len(STATS), "minimums" : [rules.minimum] * len(STATS),
			        "modifiers" : [0] * len(STATS)}
		data = {"name" : species.name, "description" : species.description, "benefits" : species.benefits,
		        "drawbacks" : species.drawbacks, "stat_limits" : species.stat_limits,
		        "stat_modifiers" : species.stat_modifiers} | (species.pending_changes or {})
		limits = SpeciesRules.limits(None, rules, data["stat_limits"])
		modifiers = SpeciesRules.modifiers(None, data["stat_modifiers"])
		return {"name" : data["name"], "description" : data["description"], "benefits" : data["benefits"],
		        "drawbacks" : data["drawbacks"], "maximums" : [limits[stat][1] for stat in STATS],
		        "minimums" : [limits[stat][0] for stat in STATS], "modifiers" : [modifiers[stat] for stat in STATS]}

	# ============================================================
	@staticmethod
	def start(uid: int, guild_id: int, guild_name: str, species: Species | None = None) -> tuple[Drafts | None, str] :
		"""Starts creating a species, or changing one. Returns (None, why) when the user is in another interview."""
		existing = DraftTransactions().get(uid)
		if existing is not None :
			from classes.characters.Interview import Interview
			return None, Interview.busy_text(existing)
		answers = {"guild_name" : guild_name} | SpeciesInterview._defaults(guild_id, species)
		kind = EDIT if species else CREATE
		draft = DraftTransactions().create(uid, guild_id, kind, "summary" if species else "name", answers=answers,
		                                   species_id=species.id if species else None)
		if species is None :
			intro = (f"**Creating a species on {guild_name}**\n"
			         f"Describe your species, then set how it changes the SPECIAL stats. Staff review it, and once "
			         f"approved anyone can play it. Type **back** for the previous question or **cancel** to stop.")
		else :
			intro = f"**Changing the species {species.name} on {guild_name}**\nStaff review the changes."
		return draft, f"{intro}\n\n{SpeciesInterview.prompt(draft)}"

	# == asking ==

	# ============================================================
	@staticmethod
	def prompt(draft: Drafts) -> str :
		answers = draft.answers
		rules = Special.rules(draft.guild_id)
		step = draft.step
		if step == "name" :
			return "**What is the species called?**" + (f"\nCurrently: {answers['name']}" if answers.get("name") else "")
		if step in TEXT_STEPS :
			question = {"description" : "**Describe the species.** What are they like, where do they come from?",
			            "benefits"    : "**What are its benefits?** What can it do that others cannot?",
			            "drawbacks"   : "**What are its drawbacks?** What holds it back?"}[step]
			current = answers.get(step)
			return question + (f"\nCurrently: {SpeciesInterview._shorten(current)}" if current else "")
		if step == "maximums" :
			return (f"**The highest each stat can go for this species.**\n"
			        f"Normally every stat can go up to {rules.maximum}. For every point you raise one, lower another "
			        f"by the same amount (between -2 and 13).\n"
			        f"Send seven numbers in this order:\n{STAT_ORDER}\n"
			        f"Currently: `{' '.join(str(value) for value in answers['maximums'])}`. Type **skip** to keep them.")
		if step == "minimums" :
			return (f"**The lowest each stat can go for this species.**\n"
			        f"Normally every stat can go down to {rules.minimum}. Again, every point one goes up, another goes "
			        f"down.\n"
			        f"Send seven numbers in this order:\n{STAT_ORDER}\n"
			        f"Currently: `{' '.join(str(value) for value in answers['minimums'])}`. Type **skip** to keep them.")
		if step == "modifiers" :
			return (f"**Changes to the starting stats.**\n"
			        f"A new character of this species starts with these added to its stats, for example `1 0 0 0 -1 0 0` "
			        f"for +1 Strength and -1 Intelligence. They have to add up to 0.\n"
			        f"Send seven numbers in this order:\n{STAT_ORDER}\n"
			        f"Currently: `{' '.join(str(value) for value in answers['modifiers'])}`. Type **skip** to keep them.")
		return SpeciesInterview._summary(draft)

	# ============================================================
	@staticmethod
	def _shorten(value: str, limit: int = 150) -> str :
		value = " ".join(str(value).split())
		return value if len(value) <= limit else f"{value[:limit - 1]}…"

	# ============================================================
	@staticmethod
	def definition(draft: Drafts) -> Definition :
		answers = draft.answers
		return Definition(answers.get("name") or "", answers.get("description") or "", answers.get("benefits") or "",
		                  answers.get("drawbacks") or "", answers["maximums"], answers["minimums"],
		                  answers["modifiers"])

	# ============================================================
	@staticmethod
	def stat_changes(draft: Drafts) -> str :
		rules = Special.rules(draft.guild_id)
		definition = SpeciesInterview.definition(draft)
		limits, modifiers = SpeciesRules.to_data(definition.minimums, definition.maximums, definition.modifiers, rules)
		return SpeciesRules.describe(None, rules, limits, modifiers)

	# ============================================================
	@staticmethod
	def _summary(draft: Drafts) -> str :
		answers = draft.answers
		lines = ["**Summary**"]
		for number, step in enumerate(STEPS[:-1], start=1) :
			if step in STAT_STEPS :
				value = f"`{' '.join(str(item) for item in answers[step])}`"
			else :
				value = SpeciesInterview._shorten(answers[step]) if answers.get(step) else "not set"
			lines.append(f"{number}. **{LABELS[step]}:** {value}")
		lines.append(f"\n**What it changes:**\n{SpeciesInterview.stat_changes(draft)}")
		problems = SpeciesInterview._problems(draft)
		if problems :
			lines.append(f"\nStill needed: {', '.join(problems)}.")
		lines.append("\nType a number to change that answer, **submit** to send it to staff, or **cancel** to stop.")
		return "\n".join(lines)

	# ============================================================
	@staticmethod
	def _problems(draft: Drafts) -> list[str] :
		answers = draft.answers
		problems = [LABELS[step].lower() for step in ("name",) + TEXT_STEPS if not answers.get(step)]
		definition = SpeciesInterview.definition(draft)
		balance = SpeciesRules.check_definition(definition.minimums, definition.maximums, definition.modifiers,
		                                        Special.rules(draft.guild_id))
		if balance :
			problems.append(f"balanced stats ({balance})")
		return problems

	# == answering ==

	# ============================================================
	@staticmethod
	def answer(draft: Drafts, text: str) -> Reply :
		text = (text or "").strip()
		command = text.lower()
		answers = draft.answers
		if command == "cancel" :
			DraftTransactions().delete(draft.uid)
			return Reply("Cancelled. Nothing was changed.", finished=True, outcome=CANCELLED)
		if command == "back" :
			if draft.step == "summary" :
				return Reply("You are at the summary. Type a number to change that answer.")
			if answers.pop("returning", False) :
				draft.step = "summary"
			elif draft.step == STEPS[0] :
				return Reply("This is the first question.\n\n" + SpeciesInterview.prompt(draft))
			else :
				draft.step = STEPS[STEPS.index(draft.step) - 1]
			DraftTransactions().save(draft)
			return Reply(SpeciesInterview.prompt(draft))

		step = draft.step
		if step == "summary" :
			if command == "submit" :
				return SpeciesInterview._submit(draft)
			if command.isdigit() and 1 <= int(command) < len(STEPS) :
				draft.step = STEPS[int(command) - 1]
				answers["returning"] = True
				DraftTransactions().save(draft)
				return Reply(SpeciesInterview.prompt(draft))
			return Reply("Type the number of an answer to change it, **submit**, or **cancel**.")

		problem = None
		if step == "name" :
			problem = SpeciesInterview.check_name(draft.guild_id, text, draft.species_id)
			if problem is None :
				answers["name"] = text
		elif step in TEXT_STEPS :
			if not text :
				problem = "Please write something."
			elif len(text) > TEXT_LIMIT :
				problem = f"That is {len(text)} characters; the limit is {TEXT_LIMIT}."
			else :
				answers[step] = text
		elif step in STAT_STEPS :
			if command != "skip" :
				problem = SpeciesInterview._answer_stats(draft, step, text)
		if problem :
			return Reply(problem)
		if answers.pop("returning", False) :
			draft.step = "summary"
		else :
			draft.step = STEPS[STEPS.index(step) + 1]
		DraftTransactions().save(draft)
		return Reply(SpeciesInterview.prompt(draft))

	# ============================================================
	@staticmethod
	def check_name(guild_id: int, name: str, species_id: int | None = None) -> str | None :
		if not name :
			return "Please send a name."
		if len(name) > NAME_LIMIT or "\n" in name :
			return f"A species name has to fit on one line and be at most {NAME_LIMIT} characters."
		if any(part in name.lower() for part in FORBIDDEN_NAME_PARTS) :
			return "Discord does not allow that word in names. Please pick another."
		other = SpeciesTransactions().find(guild_id, name)
		if other is not None and other.id != species_id :
			return f"This server already has a species called {other.name}."
		return None

	# ============================================================
	@staticmethod
	def _answer_stats(draft: Drafts, step: str, text: str) -> str | None :
		values = Special.parse(text)
		if values is None :
			return f"Please send exactly seven whole numbers, in this order:\n{STAT_ORDER}"
		answers = draft.answers
		rules = Special.rules(draft.guild_id)
		# Each step checks only what it decides, so the player is not told about answers they have not reached yet;
		# the summary checks everything together.
		if step == "modifiers" :
			problem = SpeciesRules.check_definition([rules.minimum] * len(STATS), [rules.maximum] * len(STATS), values,
			                                        rules)
		else :
			if any(not LOWEST <= value <= HIGHEST for value in values) :
				return f"Every limit has to be between {LOWEST} and {HIGHEST}."
			normal = rules.maximum if step == "maximums" else rules.minimum
			change = sum(value - normal for value in values)
			problem = None
			if change :
				problem = (f"These go {'up' if change > 0 else 'down'} by {abs(change)} in total. Every point one goes "
				           f"up, another has to go down, so the changes add up to 0.")
			elif step == "minimums" :
				problem = next((f"{stat.capitalize()}'s lowest value ({low}) is above its highest ({high})."
				                for stat, low, high in zip(STATS, values, answers["maximums"]) if low > high), None)
		if problem :
			return problem
		answers[step] = values
		return None

	# == submitting and reviewing ==

	# ============================================================
	@staticmethod
	def _submit(draft: Drafts) -> Reply :
		problems = SpeciesInterview._problems(draft)
		if problems :
			return Reply(f"Not everything is ready yet. Still needed: {', '.join(problems)}.\n\n"
			             + SpeciesInterview.prompt(draft))
		problem = SpeciesInterview.check_name(draft.guild_id, draft.answers["name"], draft.species_id)
		if problem :
			return Reply(f"{problem}\n\n{SpeciesInterview.prompt(draft)}")
		rules = Special.rules(draft.guild_id)
		definition = SpeciesInterview.definition(draft)
		limits, modifiers = SpeciesRules.to_data(definition.minimums, definition.maximums, definition.modifiers, rules)
		data = {"name" : definition.name, "description" : definition.description, "benefits" : definition.benefits,
		        "drawbacks" : definition.drawbacks, "stat_limits" : limits, "stat_modifiers" : modifiers}
		guild_name = draft.answers.get("guild_name", "the server")
		if draft.kind == CREATE :
			species = SpeciesTransactions().add(draft.guild_id, creator_uid=draft.uid, state=PENDING, **data)
			if species is None :
				return Reply("Something went wrong while saving the species. Please type **submit** again.")
			DraftTransactions().delete(draft.uid)
			return Reply(f"**{species.name}** was sent to the staff of {guild_name} for review. I'll message you when "
			             f"they have looked at it.", finished=True, outcome=CREATED, species=species)
		species = SpeciesTransactions().get(draft.species_id)
		DraftTransactions().delete(draft.uid)
		if species is None :
			return Reply("That species no longer exists, so nothing was changed.", finished=True, outcome=CANCELLED)
		if species.state == APPROVED :
			species = SpeciesTransactions().update(species.id, pending_changes=data)
			text = f"Your changes to {species.name} were sent to staff for review."
		else :
			species = SpeciesTransactions().update(species.id, state=PENDING, **data)
			text = f"{species.name} was updated and sent to staff for review."
		return Reply(text, finished=True, outcome=REVIEW, species=species)

	# ============================================================
	@staticmethod
	def is_open(species: Species) -> bool :
		return species.state == PENDING or (species.state == APPROVED and bool(species.pending_changes))

	# ============================================================
	@staticmethod
	def approve(species: Species) -> Species :
		"""Approves a new species, or applies the changes waiting for review."""
		if species.state == APPROVED :
			return SpeciesTransactions().update(species.id, pending_changes=None, review_message_id=None,
			                                    **(species.pending_changes or {}))
		return SpeciesTransactions().update(species.id, state=APPROVED, review_message_id=None)

	# ============================================================
	@staticmethod
	def deny(species: Species) -> Species :
		"""Denies a new species (its creator can change and resubmit it), or drops the waiting changes."""
		if species.state == APPROVED :
			return SpeciesTransactions().update(species.id, pending_changes=None, review_message_id=None)
		return SpeciesTransactions().update(species.id, state=DENIED, review_message_id=None)
