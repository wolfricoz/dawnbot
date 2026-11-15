"""Crafting (design/roleplay-tools.md, section 13): recipes, ingredients, making things, projects worked on in
downtime, salvage, and masterwork and cursed gear.

A craft rolls the recipe's stat against its DC (+2 when the crafter holds the recipe's occupation). Success makes the
result and uses up the ingredients. Failing by less than 5 loses half of each ingredient (rounded down) and makes
nothing. A bad failure (5 or more, or a fumble) uses them all: a weapon or armor comes out cursed, anything else is
lost, and the recipe's mishap table is rolled. A crit makes a weapon or armor masterwork, and one extra of anything
else (Rico's call). Masterwork gives +1 to hit (weapons) or +1 DT (armor) and sells for half as much again; cursed
gives -1, sells for nothing, and cursed armor can't be taken off until a GM lifts the curse.
"""
import random

from classes.checks import Checks
from classes.combat import Fortune
from classes.combat.Rules import Bonus
from classes.characters.Special import Special
from database.database import CharacterGear, Characters, GearItems, Recipes
from database.transactions.CharacterGearTransactions import CharacterGearTransactions, MATERIAL, OWNED, USED
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions

CRAFTED = "crafted"
SALVAGED = "salvaged"
MASTERWORK = "masterwork"
CURSED = "cursed"
OCCUPATION_BONUS = 2
SUCCESS = "success"
FAILURE = "failure"
BAD = "bad"
CRIT = "crit"
QUALITY_ITEMS = ("weapon", "armor")
# What masterwork and cursed do in a fight. Combat (classes/combat/Loadout.py) adds these to an item's values.
QUALITY_HIT = {MASTERWORK : 1, CURSED : -1}
QUALITY_DT = {MASTERWORK : 1, CURSED : -1}


# ============================================================
def outcome_of(result: Checks.CheckResult) -> str :
	if result.outcome == Checks.CRIT :
		return CRIT
	if result.outcome in (Checks.SUCCESS, Checks.STRONG) :
		return SUCCESS
	if result.outcome in (Checks.BAD, Checks.FUMBLE) :
		return BAD
	return FAILURE


# ============================================================
def adjust_combat(kind: str, combat: dict, quality: str | None) -> dict :
	"""An item's combat values with its crafted quality: hit_mod for weapons, dt for armor."""
	if quality not in (MASTERWORK, CURSED) :
		return combat
	combat = dict(combat or {})
	if kind == "weapon" :
		combat["hit_mod"] = int(combat.get("hit_mod") or 0) + QUALITY_HIT[quality]
	elif kind == "armor" :
		combat["dt"] = max(0, int(combat.get("dt") or 0) + QUALITY_DT[quality])
	return combat


# ============================================================
def parse_ingredients(guild_id: int, text: str) -> tuple[list[dict] | None, str | None] :
	"""`Iron Ingot x2, Leather Strip` → [{"item_id", "amount"}], or None and the problem."""
	found = []
	for part in [piece.strip() for piece in (text or "").split(",") if piece.strip()] :
		name, amount = part, 1
		lower = part.lower()
		for separator in (" x", " ×") :
			if separator in lower and lower.rsplit(separator, 1)[1].strip().isdigit() :
				name, amount = part[:lower.rindex(separator)].strip(), int(lower.rsplit(separator, 1)[1])
				break
		item = GearItemTransactions().find(guild_id, name)
		if item is None :
			return None, f"The catalog has no item called {name}."
		if not 1 <= amount <= 50 :
			return None, f"{name}: an amount is 1 to 50."
		found.append({"item_id" : item.id, "amount" : amount})
	if not found :
		return None, "Give at least one ingredient, like `Iron Ingot x2, Leather Strip`."
	return found, None


# ============================================================
def ingredients_text(ingredients: list[dict]) -> str :
	parts = []
	for ingredient in ingredients or [] :
		item = GearItemTransactions().get(ingredient.get("item_id"))
		name = item.name if item else "?"
		amount = int(ingredient.get("amount") or 1)
		parts.append(f"{name} ×{amount}" if amount > 1 else name)
	return ", ".join(parts) or "nothing"


# ============================================================
def owned(character_id: int) -> dict[int, int] :
	"""How many of each catalog item a character owns (stacks counted by quantity)."""
	counts = {}
	for entry in CharacterGearTransactions().get_all(character_id) :
		if entry.gear_item_id is None :
			continue
		counts[entry.gear_item_id] = counts.get(entry.gear_item_id, 0) + (entry.quantity or 1 if entry.kind == MATERIAL
		                                                                  else 1)
	return counts


# ============================================================
def missing(character_id: int, recipe: Recipes) -> list[str] :
	"""What the character lacks for a recipe: ingredients and the tool."""
	have = owned(character_id)
	lacking = []
	for ingredient in recipe.ingredients or [] :
		short = int(ingredient.get("amount") or 1) - have.get(ingredient.get("item_id"), 0)
		if short > 0 :
			item = GearItemTransactions().get(ingredient.get("item_id"))
			lacking.append(f"{item.name if item else '?'} ×{short}")
	if recipe.tool_item_id and have.get(recipe.tool_item_id, 0) < 1 :
		tool = GearItemTransactions().get(recipe.tool_item_id)
		lacking.append(f"a {tool.name if tool else 'tool'} (tool)")
	return lacking


# ============================================================
def lock_reason(character: Characters, recipe: Recipes) -> str | None :
	if character.level < (recipe.min_level or 1) :
		return f"needs level {recipe.min_level}"
	if recipe.occupation_required and recipe.occupation_id and character.occupation_id != recipe.occupation_id :
		from database.transactions.OccupationTransactions import OccupationTransactions

		occupation = OccupationTransactions().get(recipe.occupation_id)
		return f"needs the occupation {occupation.name if occupation else '?'}"
	return None


# ============================================================
def consume(character_id: int, item_id: int, amount: int) -> None :
	"""Uses up amount of an item: stacks shrink, other items are marked used."""
	left = amount
	for entry in CharacterGearTransactions().get_all(character_id) :
		if left <= 0 :
			break
		if entry.gear_item_id != item_id :
			continue
		if entry.kind == MATERIAL :
			take = min(left, entry.quantity or 1)
			remaining = (entry.quantity or 1) - take
			CharacterGearTransactions().update(entry.id, quantity=max(0, remaining),
			                                   status=OWNED if remaining > 0 else USED, equipped=False)
			left -= take
		else :
			CharacterGearTransactions().update(entry.id, status=USED, equipped=False)
			left -= 1


# ============================================================
def consume_all(character_id: int, ingredients: list[dict], share: float = 1.0) -> list[dict] :
	"""Uses up a share of each ingredient (rounded down). Returns what was used."""
	used = []
	for ingredient in ingredients or [] :
		amount = int(int(ingredient.get("amount") or 1) * share)
		if amount > 0 :
			consume(character_id, ingredient["item_id"], amount)
			used.append({"item_id" : ingredient["item_id"], "amount" : amount})
	return used


# ============================================================
def give(character: Characters, item: GearItems, amount: int = 1, quality: str | None = None,
         actor_uid: int | None = None) -> list[CharacterGear] :
	"""Adds crafted items: one stack for a material, otherwise one entry each, named after their quality."""
	if item.kind == MATERIAL :
		entry = CharacterGearTransactions().add(character.id, item.id, item.name, item.kind, CRAFTED, item.price,
		                                        actor_uid, quantity=amount)
		return [entry] if entry else []
	made = []
	name = f"{quality.capitalize()} {item.name}"[:100] if quality else item.name
	for _ in range(amount) :
		entry = CharacterGearTransactions().add(character.id, item.id, name, item.kind, CRAFTED, item.price, actor_uid)
		if entry is not None and quality :
			entry = CharacterGearTransactions().update(entry.id, quality=quality)
		if entry is not None :
			made.append(entry)
	return made


# ============================================================
def roll(character: Characters, recipe: Recipes, rng: random.Random | None = None) :
	"""Rolls a craft for a character, with bad-roll protection. Returns (result, first roll when made again)."""
	extras = [Bonus("Occupation", OCCUPATION_BONUS)] if recipe.occupation_id and \
	                                                    character.occupation_id == recipe.occupation_id else []
	stats = Checks.stats_of(character)
	base = Special.rules(character.guild_id).base

	def make() :
		return Checks.roll(stats, recipe.stat or "intelligence", recipe.dc or 12, base, 0, extras, rng)

	return Fortune.for_character(character.id, make, lambda result : result.success, lambda result : result.total)


# ============================================================
def make(character: Characters, recipe: Recipes, actor_uid: int | None = None,
         rng: random.Random | None = None) -> tuple[str, Checks.CheckResult | None, list[str]] :
	"""Crafts a recipe that takes no days. Returns the outcome, the roll and lines saying what happened."""
	item = GearItemTransactions().get(recipe.result_item_id)
	if item is None :
		return FAILURE, None, ["The recipe's result is no longer in the catalog."]
	result, first = roll(character, recipe, rng)
	outcome = outcome_of(result)
	lines = [f"🎲 {result.breakdown()} against DC {recipe.dc}: **{outcome}**"]
	if first is not None :
		lines.append(f"-# {Fortune.note(str(first.total))}")
	quality_item = item.kind in QUALITY_ITEMS
	amount = recipe.result_amount or 1
	if outcome == SUCCESS :
		consume_all(character.id, recipe.ingredients)
		give(character, item, amount, actor_uid=actor_uid)
		lines.append(f"Made **{item.name}**{f' ×{amount}' if amount > 1 else ''}.")
	elif outcome == CRIT :
		consume_all(character.id, recipe.ingredients)
		if quality_item :
			give(character, item, amount, MASTERWORK, actor_uid)
			lines.append(f"✨ Made a **Masterwork {item.name}**!")
		else :
			give(character, item, amount + 1, actor_uid=actor_uid)
			lines.append(f"✨ Made **{item.name}** ×{amount + 1}: one extra!")
	elif outcome == FAILURE :
		used = consume_all(character.id, recipe.ingredients, 0.5)
		lines.append(f"Nothing came of it; lost {ingredients_text(used)}." if used else "Nothing came of it.")
	else :
		consume_all(character.id, recipe.ingredients)
		if quality_item :
			give(character, item, 1, CURSED, actor_uid)
			lines.append(f"💀 It came out wrong: a **Cursed {item.name}**.")
		else :
			lines.append("💀 Ruined: every ingredient is lost.")
	return outcome, result, lines


# ============================================================
def start_project(character: Characters, recipe: Recipes) -> object | None :
	"""Sets the ingredients aside and starts a project."""
	reserved = consume_all(character.id, recipe.ingredients)
	return EconomyTransactions().add_project(character.id, recipe.id, reserved)


# ============================================================
def work(character: Characters, project, actor_uid: int | None = None,
         rng: random.Random | None = None) -> tuple[str, list[str], bool] :
	"""A downtime day on a project: success adds a day (a crit also makes it masterwork), a failure adds nothing, a bad
	failure takes a day back. Returns the outcome, lines, and whether the project is finished."""
	recipe = EconomyTransactions().recipe(project.recipe_id)
	if recipe is None :
		EconomyTransactions().update_project(project.id, state="abandoned")
		return FAILURE, ["The recipe is gone, so the project was abandoned."], False
	result, first = roll(character, recipe, rng)
	outcome = outcome_of(result)
	days, masterwork = project.days_done, project.masterwork
	if outcome in (SUCCESS, CRIT) :
		days += 1
		masterwork = masterwork or outcome == CRIT
	elif outcome == BAD :
		days = max(0, days - 1)
	lines = [f"🎲 {result.breakdown()} against DC {recipe.dc}: **{outcome}** · day {days} of {recipe.days}"]
	if first is not None :
		lines.append(f"-# {Fortune.note(str(first.total))}")
	finished = days >= recipe.days
	EconomyTransactions().update_project(project.id, days_done=days, masterwork=masterwork,
	                                     state="done" if finished else "working")
	if finished :
		item = GearItemTransactions().get(recipe.result_item_id)
		if item is not None :
			quality = MASTERWORK if masterwork and item.kind in QUALITY_ITEMS else None
			give(character, item, recipe.result_amount or 1, quality, actor_uid)
			lines.append(f"✅ Finished: **{(quality.capitalize() + ' ') if quality else ''}{item.name}**.")
	return outcome, lines, finished


# ============================================================
def salvage(character: Characters, entry: CharacterGear, rng: random.Random | None = None) -> tuple[list[str], str | None] :
	"""Breaks an item into the materials its catalog entry lists, each unit kept on a coin flip. Returns what came out,
	or the problem."""
	rng = rng or random
	item = GearItemTransactions().get(entry.gear_item_id)
	if item is None or not item.salvage :
		return [], f"{entry.name} can't be salvaged."
	if entry.status not in (OWNED, "broken") :
		return [], f"{entry.name} is {entry.status}."
	got = []
	for name, amount in item.salvage.items() :
		material = GearItemTransactions().find(character.guild_id, name)
		if material is None :
			continue
		count = sum(rng.random() < 0.5 for _ in range(int(amount)))
		if count :
			give(character, material, count)
			got.append(f"{material.name} ×{count}")
	CharacterGearTransactions().update(entry.id, status=SALVAGED, equipped=False)
	return got, None


# ============================================================
def uncurse(entry: CharacterGear) -> CharacterGear | None :
	name = entry.name[len("Cursed ") :] if entry.name.startswith("Cursed ") else entry.name
	return CharacterGearTransactions().update(entry.id, quality=None, name=name)
