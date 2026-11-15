"""Crafting: turn materials into gear, potions and more with a roll, and break gear down for parts.

`/craft make` rolls the recipe's stat against its DC (+2 with its occupation). Success makes the item; failing by less
than 5 loses half the ingredients; a bad failure loses them all and makes cursed gear; a crit makes masterwork gear
(or one extra). Recipes that take days become projects worked on with /downtime. Staff manage recipes with
`/craft recipe` and import the fantasy pack's materials and recipes. See design/roleplay-tools.md, section 13.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.kernel.GMRole import gm_only
from classes.characters.Special import STATS
from classes.combat.AutoComplete import AutoComplete
from classes.economy import Crafting, RecipePacks
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from database.transactions.RollTableTransactions import RollTableTransactions
from views.combat.Pickers import reply

STAT_CHOICES = [Choice(name=stat.capitalize(), value=stat) for stat in STATS]


# ============================================================
async def recipe_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=recipe.name[:100], value=recipe.name[:100])
	        for recipe in EconomyTransactions().recipes(interaction.guild_id)
	        if current.lower() in recipe.name.lower()][:25]


# ============================================================
async def item_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=item.name[:100], value=item.name[:100])
	        for item in GearItemTransactions().get_all(interaction.guild_id) if current.lower() in item.name.lower()][:25]


# ============================================================
async def owned_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	member = getattr(interaction.namespace, "member", None) or interaction.user
	name = interaction.namespace.character or ""
	character = CharacterTransactions().get(member.id, interaction.guild_id, name)
	if character is None :
		return []
	return [Choice(name=f"{entry.name} (#{entry.id})"[:100], value=str(entry.id))
	        for entry in CharacterGearTransactions().get_all(character.id, include_gone=True)
	        if entry.status in ("owned", "broken") and current.lower() in entry.name.lower()][:25]


# ============================================================
async def member_characters(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	member = interaction.namespace.member
	if member is None :
		return []
	return [Choice(name=character.name[:100], value=character.name[:100])
	        for character in CharacterTransactions().get_in_guild(interaction.guild_id, member.id)
	        if current.lower() in character.name.lower()][:25]


# ============================================================
async def pack_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=title[:100], value=name) for name, title in RecipePacks.available()
	        if current.lower() in name][:25]


@app_commands.guild_only()
class Craft(commands.GroupCog, name="Craft", group_name="craft") :
	"""Crafting from recipes, projects worked on in downtime, and salvage."""

	recipe = app_commands.Group(name="recipe", description="The server's crafting recipes (staff)")

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	def _character(self, interaction: discord.Interaction, name: str) :
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name)
		return character if character is not None and character.state == APPROVED else None

	# ============================================================
	@app_commands.command(name="recipes", description="Lists the recipes, and what your character can make")
	@app_commands.autocomplete(character=AutoComplete().approved_character)
	async def recipes(self, interaction: discord.Interaction, character: str = None) :
		"""
		Lists the server's recipes. With a character: ✅ can make it now, ❌ misses ingredients (listed), 🔒 locked.
		"""
		record = self._character(interaction, character) if character else None
		recipes = EconomyTransactions().recipes(interaction.guild_id)
		if not recipes :
			return await reply(interaction, "There are no recipes yet. Staff add them with /craft recipe add or "
			                                "/craft recipe import.")
		lines = []
		for recipe in recipes :
			item = GearItemTransactions().get(recipe.result_item_id)
			days = f" · {recipe.days} days" if recipe.days else ""
			text = f"**{recipe.name}** → {item.name if item else '?'} · {recipe.stat[:3].upper()} DC {recipe.dc}{days}: " \
			       f"{Crafting.ingredients_text(recipe.ingredients)}"
			if record is not None :
				locked = Crafting.lock_reason(record, recipe)
				lacking = Crafting.missing(record.id, recipe)
				mark = f"🔒 ({locked})" if locked else (f"❌ (needs {', '.join(lacking)})" if lacking else "✅")
				text = f"{mark} {text}"
			lines.append(text)
		chunks, current = [], ""
		for line in lines :
			if len(current) + len(line) > 1900 :
				chunks.append(current)
				current = ""
			current += line + "\n"
		chunks.append(current)
		for chunk in chunks[:5] :
			await reply(interaction, chunk)

	# ============================================================
	@app_commands.command(name="make", description="Crafts a recipe")
	@app_commands.autocomplete(character=AutoComplete().approved_character, recipe=recipe_autocomplete)
	async def make(self, interaction: discord.Interaction, character: str, recipe: str) :
		"""
		Crafts a recipe with your character's ingredients. Recipes that take days set the ingredients aside and start
		a project, worked on one roll per day with /downtime spend activity:craft.
		"""
		record = self._character(interaction, character)
		target = EconomyTransactions().find_recipe(interaction.guild_id, recipe)
		if record is None or target is None :
			return await reply(interaction, "Pick one of your approved characters and a recipe.")
		locked = Crafting.lock_reason(record, target)
		if locked :
			return await reply(interaction, f"{target.name} {locked}.")
		lacking = Crafting.missing(record.id, target)
		if lacking :
			return await reply(interaction, f"{record.name} needs {', '.join(lacking)}.")
		if target.days :
			project = Crafting.start_project(record, target)
			return await interaction.response.send_message(
				f"🛠️ {record.name} starts on **{target.name}** (project #{project.id}): {target.days} good days of "
				f"/downtime crafting. The ingredients are set aside.")
		outcome, result, lines = Crafting.make(record, target, interaction.user.id)
		embed = discord.Embed(title=f"🛠️ {record.name} crafts {target.name}", description="\n".join(lines)[:4096],
		                      colour=discord.Colour.dark_gold())
		await interaction.response.send_message(embed=embed)
		if outcome == Crafting.BAD and target.mishap_table_id and interaction.channel is not None :
			table = RollTableTransactions().get(target.mishap_table_id)
			if table is not None :
				from classes.tables.TableFlow import TableFlow

				await TableFlow.post_roll(interaction.channel, table, interaction.user.id, record,
				                          f"💥 A mishap for **{record.name}**:")

	# ============================================================
	@app_commands.command(name="projects", description="Lists your character's crafting projects")
	@app_commands.autocomplete(character=AutoComplete().approved_character)
	async def projects(self, interaction: discord.Interaction, character: str) :
		"""
		Lists the projects your character is working on, with how far along each is.
		"""
		record = self._character(interaction, character)
		if record is None :
			return await reply(interaction, f"You have no approved character called {character}.")
		projects = EconomyTransactions().projects(record.id)
		if not projects :
			return await reply(interaction, f"{record.name} has no projects.")
		lines = []
		for project in projects :
			recipe = EconomyTransactions().recipe(project.recipe_id)
			total = recipe.days if recipe else "?"
			lines.append(f"#{project.id} · **{recipe.name if recipe else '?'}** · day {project.days_done} of {total}"
			             f"{' · ✨ masterwork' if project.masterwork else ''}")
		await reply(interaction, "\n".join(lines))

	# ============================================================
	@app_commands.command(name="salvage", description="Breaks an item down into materials")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=owned_autocomplete)
	async def salvage(self, interaction: discord.Interaction, character: str, item: str) :
		"""
		Breaks an owned or broken item into the materials its catalog entry lists; each one comes out on a coin flip,
		so about half of them. The item is gone afterwards.
		"""
		record = self._character(interaction, character)
		try :
			entry = CharacterGearTransactions().get(int(item))
		except ValueError :
			entry = None
		if record is None or entry is None or entry.character_id != record.id :
			return await reply(interaction, "Pick one of your character's items from the list.")
		got, problem = Crafting.salvage(record, entry)
		if problem :
			return await reply(interaction, problem)
		await interaction.response.send_message(f"🔨 {record.name} salvages **{entry.name}**: "
		                                        f"{', '.join(got) or 'nothing usable'}.")

	# ============================================================
	@app_commands.command(name="uncurse", description="Lifts the curse from a character's item (staff)")
	@gm_only()
	@app_commands.autocomplete(character=member_characters, item=owned_autocomplete)
	async def uncurse(self, interaction: discord.Interaction, member: discord.Member, character: str, item: str) :
		"""
		Makes a cursed item a normal one again.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = CharacterTransactions().get(member.id, interaction.guild_id, character)
		try :
			entry = CharacterGearTransactions().get(int(item))
		except ValueError :
			entry = None
		if record is None or entry is None or entry.character_id != record.id or entry.quality != Crafting.CURSED :
			return await reply(interaction, "Pick a cursed item of that character.")
		updated = Crafting.uncurse(entry)
		await reply(interaction, f"✨ The curse on {record.name}'s {updated.name} is lifted.")

	# == recipes ==

	# ============================================================
	@recipe.command(name="add", description="Adds a recipe")
	@gm_only()
	@app_commands.autocomplete(result=item_autocomplete, tool=item_autocomplete)
	@app_commands.choices(stat=STAT_CHOICES)
	@app_commands.describe(name="The recipe's name", result="The catalog item it makes",
	                       ingredients="Catalog items it uses, like: Iron Ingot x2, Leather Strip",
	                       amount="How many it makes", tool="A catalog item needed but not used up",
	                       stat="The stat it rolls (default Intelligence)", dc="The DC (default 12)",
	                       occupation="An occupation that gives +2", occupation_required="Only that occupation can",
	                       min_level="The lowest level that can make it", days="Days of downtime it takes (0: now)")
	async def recipe_add(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100], result: str,
	                     ingredients: str, amount: app_commands.Range[int, 1, 50] = 1, tool: str = None,
	                     stat: Choice[str] = None, dc: app_commands.Range[int, 1, 40] = 12, occupation: str = None,
	                     occupation_required: bool = False, min_level: app_commands.Range[int, 1, 100] = 1,
	                     days: app_commands.Range[int, 0, 60] = 0) :
		"""
		Adds a recipe. Materials are catalog items of kind material (the fantasy recipe pack brings a set).

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		guild_id = interaction.guild_id
		item = GearItemTransactions().find(guild_id, result)
		if item is None :
			return await reply(interaction, f"The catalog has no item called {result}.")
		parsed, problem = Crafting.parse_ingredients(guild_id, ingredients)
		if problem :
			return await reply(interaction, problem)
		tool_item = GearItemTransactions().find(guild_id, tool) if tool else None
		if tool and tool_item is None :
			return await reply(interaction, f"The catalog has no item called {tool}.")
		job = OccupationTransactions().find(guild_id, occupation) if occupation else None
		if occupation and job is None :
			return await reply(interaction, f"There is no occupation called {occupation}.")
		record = EconomyTransactions().add_recipe(guild_id, name.strip(), result_item_id=item.id, result_amount=amount,
		                                          ingredients=parsed, tool_item_id=tool_item.id if tool_item else None,
		                                          stat=stat.value if stat else "intelligence", dc=dc,
		                                          occupation_id=job.id if job else None,
		                                          occupation_required=occupation_required, min_level=min_level,
		                                          days=days)
		if record is None :
			return await reply(interaction, f"There already is a recipe called {name}.")
		await reply(interaction, f"Added **{record.name}**: {Crafting.ingredients_text(parsed)} → {item.name}.")

	# ============================================================
	@recipe.command(name="remove", description="Removes a recipe")
	@gm_only()
	@app_commands.autocomplete(recipe=recipe_autocomplete)
	async def recipe_remove(self, interaction: discord.Interaction, recipe: str) :
		"""
		Removes a recipe; projects using it are abandoned when next worked on.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = EconomyTransactions().find_recipe(interaction.guild_id, recipe)
		if record is None :
			return await reply(interaction, f"There is no recipe called {recipe}.")
		EconomyTransactions().delete_recipe(record.id)
		await reply(interaction, f"Removed **{record.name}**.")

	# ============================================================
	@recipe.command(name="mishap", description="Sets the roll table a recipe rolls on a bad failure")
	@gm_only()
	@app_commands.autocomplete(recipe=recipe_autocomplete)
	async def recipe_mishap(self, interaction: discord.Interaction, recipe: str, table: str = None) :
		"""
		Sets (or, without a table, clears) the roll table a bad failure on this recipe rolls.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = EconomyTransactions().find_recipe(interaction.guild_id, recipe)
		found = RollTableTransactions().find(interaction.guild_id, table) if table else None
		if record is None or (table and found is None) :
			return await reply(interaction, "Pick a recipe and a roll table.")
		EconomyTransactions().update_recipe(record.id, mishap_table_id=found.id if found else None)
		await reply(interaction, f"{record.name} rolls {found.name} on a bad failure." if found else
		                         f"{record.name} has no mishap table now.")

	# ============================================================
	@recipe.command(name="salvage", description="Sets what salvaging a catalog item gives")
	@gm_only()
	@app_commands.autocomplete(item=item_autocomplete)
	@app_commands.describe(materials="Like: Iron Ingot x2, Leather Strip (empty: can't be salvaged)")
	async def recipe_salvage(self, interaction: discord.Interaction, item: str, materials: str = None) :
		"""
		Sets the materials salvaging an item can give (each comes out on a coin flip).

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = GearItemTransactions().find(interaction.guild_id, item)
		if record is None :
			return await reply(interaction, f"The catalog has no item called {item}.")
		if not materials :
			GearItemTransactions().update(record.id, salvage=None)
			return await reply(interaction, f"{record.name} can't be salvaged now.")
		parsed, problem = Crafting.parse_ingredients(interaction.guild_id, materials)
		if problem :
			return await reply(interaction, problem)
		salvage = {GearItemTransactions().get(part["item_id"]).name : part["amount"] for part in parsed}
		GearItemTransactions().update(record.id, salvage=salvage)
		await reply(interaction, f"Salvaging {record.name} gives up to {Crafting.ingredients_text(parsed)}.")

	# ============================================================
	@recipe.command(name="import", description="Copies a recipe pack's materials and recipes into this server")
	@gm_only()
	@app_commands.autocomplete(pack=pack_autocomplete)
	async def recipe_import(self, interaction: discord.Interaction, pack: str) :
		"""
		Adds the pack's materials to the catalog, its recipes, and salvage lists for the gear it knows. Import the
		matching gear pack first (/armory import), since recipes make catalog items.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		try :
			added, skipped, missing = RecipePacks.import_into(interaction.guild_id, pack)
		except ValueError as e :
			return await reply(interaction, str(e))
		lines = [f"Added {len(added)}: {', '.join(added) or 'nothing'}."]
		if skipped :
			lines.append(f"Already here: {', '.join(skipped)}.")
		if missing :
			lines.append(f"⚠️ Not added, the catalog lacks: {'; '.join(missing)}.")
		await reply(interaction, "\n".join(lines)[:2000])


async def setup(bot) :
	await bot.add_cog(Craft(bot))
