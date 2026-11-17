"""The server's bestiary: NPCs and monsters GMs add to fights. Managed by staff (Manage Messages).

An entry has its own stat block from a difficulty preset, or SPECIAL with catalog weapons and armor, derived like a
character. /bestiary import copies a genre pack's bestiary, or the old global npcs and monsters tables. The rules live
in classes/combat/BestiaryFlow.py.
"""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.BestiaryFlow import BestiaryFlow
from classes.combat.DamageTypes import DamageTypes
from classes.combat.Engine import BEHAVIORS
from classes.combat.Loadout import PRESETS, preset_text
from classes.gear.Gear import ARMOR, WEAPON
from classes.gear.Legacy import Legacy
from classes.gear.Packs import Packs
from database.transactions.BestiaryTransactions import BestiaryTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from views.combat.Pickers import reply

PRESET_CHOICES = [Choice(name=f"{preset.capitalize()} ({preset_text(preset)})"[:100], value=preset)
                  for preset in PRESETS]
BEHAVIOR_CHOICES = [Choice(name=behavior.capitalize(), value=behavior) for behavior in BEHAVIORS]
OPTION_HELP = {
	"preset"          : "Starting numbers; the options you fill in replace them",
	"hp"              : "Hit points",
	"ac"              : "Armor class",
	"dt"              : "Damage threshold, taken off every hit",
	"to_hit"          : "Added to its attack rolls (and its abilities)",
	"damage"          : "Its attack's damage dice, like 2d6",
	"damage_type"     : "Its attack's damage type",
	"attack_name"     : "What its attack is called, like Claws",
	"ap"              : "Action points per turn (attacks cost 3)",
	"sequence"        : "Turn order; characters have 2 x Perception",
	"behavior"        : "What it does when it acts on its own",
	"abilities"       : "Approved abilities it can use, separated by commas",
	"reward_xp"       : "XP it is worth to the winners",
	"reward_currency" : "Currency it is worth to the winners",
	"special"         : "Optional SPECIAL, like 6 5 5 4 4 7 5 or str 6, agi 7: derives HP, AC, AP and Sequence",
	"level"           : "With SPECIAL: its level (HP per level, level bonus)",
	"weapons"         : "With SPECIAL: catalog weapons it fights with, separated by commas",
	"armor"           : "With SPECIAL: the catalog armor it wears",
}
LEGACY = "legacy"


@app_commands.guild_only()
@app_commands.default_permissions(manage_messages=True)
class Bestiary(commands.GroupCog, name="Bestiary", group_name="bestiary") :
	"""NPCs and monsters for fights."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _names(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=entry.name[:100], value=entry.name[:100])
		        for entry in BestiaryTransactions().get_all(interaction.guild_id)
		        if current.lower() in entry.name.lower()][:25]

	# ============================================================
	async def _types(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=name, value=name) for name in DamageTypes.names(interaction.guild_id)
		        if current.lower() in name.lower()][:25]

	# ============================================================
	async def _weapons(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return self._catalog(interaction, current, WEAPON)

	# ============================================================
	async def _armor(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return self._catalog(interaction, current, ARMOR)

	# ============================================================
	@staticmethod
	def _catalog(interaction: discord.Interaction, current: str, kind: str) -> list[Choice[str]] :
		"""Catalog names; for a list, the part after the last comma is completed."""
		done, _, typed = current.rpartition(",")
		prefix = f"{done}, " if done else ""
		return [Choice(name=f"{prefix}{item.name}"[:100], value=f"{prefix}{item.name}"[:100])
		        for item in GearItemTransactions().get_all(interaction.guild_id)
		        if item.kind == kind and typed.strip().lower() in item.name.lower()][:25]

	# ============================================================
	async def _sources(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		choices = [Choice(name=f"{title} (genre pack)", value=name) for name, title in Packs.available()]
		choices.append(Choice(name="The old npcs and monsters tables", value=LEGACY))
		return [choice for choice in choices if current.lower() in choice.name.lower()][:25]

	# ============================================================
	@app_commands.command(name="add")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.choices(preset=PRESET_CHOICES, behavior=BEHAVIOR_CHOICES)
	@app_commands.autocomplete(damage_type=_types, weapons=_weapons, armor=_armor)
	@app_commands.describe(**OPTION_HELP)
	async def add(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100], preset: Choice[str],
	              description: app_commands.Range[str, 1, 1000] = None, hp: app_commands.Range[int, 1, 10000] = None,
	              ac: app_commands.Range[int, 1, 30] = None, dt: app_commands.Range[int, 0, 20] = None,
	              to_hit: app_commands.Range[int, -10, 30] = None, damage: app_commands.Range[str, 3, 7] = None,
	              damage_type: str = None, attack_name: app_commands.Range[str, 1, 50] = None,
	              ap: app_commands.Range[int, 1, 40] = None, sequence: app_commands.Range[int, -10, 60] = None,
	              behavior: Choice[str] = None, abilities: app_commands.Range[str, 1, 300] = None,
	              avatar_url: app_commands.Range[str, 1, 500] = None,
	              reward_xp: app_commands.Range[int, 0, 1000000] = None,
	              reward_currency: app_commands.Range[int, 0, 1000000] = None,
	              special: app_commands.Range[str, 1, 100] = None, level: app_commands.Range[int, 1, 50] = None,
	              weapons: app_commands.Range[str, 1, 300] = None, armor: str = None) :
		"""
		Adds an NPC or monster to the bestiary. The `preset` (minion, standard, elite, miniboss, boss) fills in its
		numbers; a miniboss or boss gets 75 HP + 18.75 (miniboss) or 37.5 (boss) per player character it faces, set
		when the fight starts;
		the options you fill in replace them. A boss has 14 AP, so it acts about twice as much. GMs add bestiary
		entries to a fight from the board's GM tools.

		Give it `special` instead (seven numbers, or like `str 6, agi 7`) to build it like a character: HP, AC, AP
		and Sequence come from SPECIAL and `level`, and it fights with catalog `weapons` (Average proficiency) and
		`armor`. Its own attack options are then not used.

		**Permissions:**
		- `Manage Messages`
		"""
		try :
			values = BestiaryFlow.values(interaction.guild_id, BestiaryFlow.preset_values(preset.value),
			                             description=description, hp=hp, ac=ac, dt=dt, to_hit=to_hit, damage=damage,
			                             damage_type=damage_type, attack_name=attack_name, ap=ap, sequence=sequence,
			                             behavior=behavior, abilities=abilities, avatar_url=avatar_url,
			                             reward_xp=reward_xp, reward_currency=reward_currency, special=special,
			                             level=level, weapons=weapons, armor=armor)
		except ValueError as e :
			return await reply(interaction, str(e))
		entry = BestiaryTransactions().add(interaction.guild_id, name.strip(), creator_uid=interaction.user.id, **values)
		if entry is None :
			return await reply(interaction, f"The bestiary already has {name}.")
		logging.info(f"{interaction.user.name} added bestiary entry {entry.id} in {interaction.guild.name}")
		await interaction.response.send_message(f"Added **{entry.name}** to the bestiary.", embed=BestiaryFlow.embed(entry),
		                                        ephemeral=True)

	# ============================================================
	@app_commands.command(name="edit")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.choices(behavior=BEHAVIOR_CHOICES)
	@app_commands.autocomplete(name=_names, damage_type=_types, weapons=_weapons, armor=_armor)
	@app_commands.describe(**{key : text for key, text in OPTION_HELP.items() if key != "preset"})
	async def edit(self, interaction: discord.Interaction, name: str, new_name: app_commands.Range[str, 1, 100] = None,
	               description: app_commands.Range[str, 1, 1000] = None, hp: app_commands.Range[int, 1, 10000] = None,
	               ac: app_commands.Range[int, 1, 30] = None, dt: app_commands.Range[int, 0, 20] = None,
	               to_hit: app_commands.Range[int, -10, 30] = None, damage: app_commands.Range[str, 3, 7] = None,
	               damage_type: str = None, attack_name: app_commands.Range[str, 1, 50] = None,
	               ap: app_commands.Range[int, 1, 40] = None, sequence: app_commands.Range[int, -10, 60] = None,
	               behavior: Choice[str] = None, abilities: app_commands.Range[str, 1, 300] = None,
	               avatar_url: app_commands.Range[str, 1, 500] = None,
	               reward_xp: app_commands.Range[int, 0, 1000000] = None,
	               reward_currency: app_commands.Range[int, 0, 1000000] = None,
	               special: app_commands.Range[str, 1, 100] = None, level: app_commands.Range[int, 1, 50] = None,
	               weapons: app_commands.Range[str, 1, 300] = None, armor: str = None) :
		"""
		Changes a bestiary entry; options you leave out keep their value. Type `none` as `abilities`,
		`damage_type`, `special`, `weapons` or `armor` to clear them; clearing `special` turns it back into a stat
		block. NPCs already in a fight keep the numbers they joined with.

		**Permissions:**
		- `Manage Messages`
		"""
		entry = BestiaryTransactions().find(interaction.guild_id, name)
		if entry is None :
			return await reply(interaction, f"The bestiary has no {name}.")
		if new_name and new_name.strip().lower() != entry.name.lower() and \
				BestiaryTransactions().find(interaction.guild_id, new_name.strip()) is not None :
			return await reply(interaction, f"The bestiary already has {new_name}.")
		if abilities is not None and abilities.strip().lower() in ("none", "-") :
			abilities = ""
		try :
			values = BestiaryFlow.values(interaction.guild_id, {}, description=description, hp=hp, ac=ac, dt=dt,
			                             to_hit=to_hit, damage=damage, damage_type=damage_type, attack_name=attack_name,
			                             ap=ap, sequence=sequence, behavior=behavior, abilities=abilities,
			                             avatar_url=avatar_url, reward_xp=reward_xp, reward_currency=reward_currency,
			                             special=special, level=level, weapons=weapons, armor=armor)
		except ValueError as e :
			return await reply(interaction, str(e))
		if new_name :
			values["name"] = new_name.strip()
		if not values :
			return await reply(interaction, "Nothing to change: fill in at least one option.")
		updated = BestiaryTransactions().update(entry.id, **values)
		await interaction.response.send_message(f"Updated **{updated.name}**.", embed=BestiaryFlow.embed(updated),
		                                        ephemeral=True)

	# ============================================================
	@app_commands.command(name="remove")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(name=_names)
	async def remove(self, interaction: discord.Interaction, name: str) :
		"""
		Removes an entry from the bestiary. NPCs already in a fight stay in it.

		**Permissions:**
		- `Manage Messages`
		"""
		entry = BestiaryTransactions().find(interaction.guild_id, name)
		if entry is None :
			return await reply(interaction, f"The bestiary has no {name}.")
		BestiaryTransactions().delete(entry.id)
		await reply(interaction, f"Removed **{entry.name}** from the bestiary.")

	# ============================================================
	@app_commands.command(name="loot")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(name=_names)
	@app_commands.describe(currency="Currency it drops: dice like 3d10, or a number",
	                       items="Catalog items with a chance and amount, like: Healing Draught 50%, Hedge Knife 10% x2",
	                       clear="Make it drop nothing")
	async def loot(self, interaction: discord.Interaction, name: str, currency: app_commands.Range[str, 1, 20] = None,
	               items: app_commands.Range[str, 1, 500] = None, clear: bool = False) :
		"""
		Sets what an entry drops when it is defeated: currency (dice or a number) and catalog items, each with a
		chance (100% when left out) and an amount. After a fight, the GM presses Loot on the GM panel to roll it,
		winners claim items, and the GM settles who gets what. Options you leave out keep their value.

		**Permissions:**
		- `Manage Messages`
		"""
		from classes.combat import Rules
		from classes.economy import Loot

		entry = BestiaryTransactions().find(interaction.guild_id, name)
		if entry is None :
			return await reply(interaction, f"The bestiary has no {name}.")
		loot = {} if clear else dict(getattr(entry, "loot", None) or {})
		if currency is not None :
			text = currency.strip()
			if not text.isdigit() :
				try :
					Rules.parse_dice(text)
				except ValueError as e :
					return await reply(interaction, str(e))
			loot["currency"] = text
		if items is not None :
			parsed, problem = Loot.parse(interaction.guild_id, items)
			if problem :
				return await reply(interaction, problem)
			loot["items"] = parsed
		BestiaryTransactions().update(entry.id, loot=loot or None)
		await reply(interaction, f"**{entry.name}** drops: {Loot.describe(loot)}.")

	# ============================================================
	@app_commands.command(name="list")
	async def list_entries(self, interaction: discord.Interaction) :
		"""
		Lists the bestiary.
		"""
		lines = [BestiaryFlow.line(entry) for entry in BestiaryTransactions().get_all(interaction.guild_id)]
		await interaction.response.send_message(embed=discord.Embed(
			title="Bestiary", description="\n".join(lines)[:4000] or "Empty. Add NPCs with /bestiary add.",
			color=discord.Color.dark_red()), ephemeral=True)

	# ============================================================
	@app_commands.command(name="view")
	@app_commands.autocomplete(name=_names)
	async def view(self, interaction: discord.Interaction, name: str) :
		"""
		Shows a bestiary entry.
		"""
		entry = BestiaryTransactions().find(interaction.guild_id, name)
		if entry is None :
			return await reply(interaction, f"The bestiary has no {name}.")
		await interaction.response.send_message(embed=BestiaryFlow.embed(entry), ephemeral=True)

	# ============================================================
	@app_commands.command(name="import")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(source=_sources)
	async def import_entries(self, interaction: discord.Interaction, source: str) :
		"""
		Copies NPCs and monsters into the bestiary: a genre pack's ready-made bestiary (import the pack's gear with
		/armory import first, so its fighters get their weapons), or `legacy`, the old global npcs and monsters
		tables. Names the bestiary already has are skipped, so importing again only adds what is missing.

		Old NPCs had HP on the old scale (about 100 for a character), so their HP is scaled down to the new rules;
		check the imported numbers with /bestiary view.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		problems = []
		if source == LEGACY :
			if not (Legacy.exists("npcs") or Legacy.exists("monsters")) :
				return await reply(interaction, "The old npcs and monsters tables are gone (migration 0015 dropped "
				                                "them).")
			added, skipped = BestiaryFlow.import_legacy(interaction.guild_id, interaction.user.id)
		else :
			try :
				added, skipped, problems = BestiaryFlow.import_pack(interaction.guild_id, source, interaction.user.id)
			except ValueError as e :
				return await reply(interaction, str(e))
		logging.info(f"{interaction.user.name} imported bestiary {source} in {interaction.guild.name}: "
		             f"{len(added)} added, {len(skipped)} skipped")
		lines = [f"Added {len(added)} entr{'y' if len(added) == 1 else 'ies'}"
		         + (f": {', '.join(entry.name for entry in added)}" if added else "") + "."]
		if skipped :
			lines.append(f"Skipped (already in the bestiary): {', '.join(skipped)}.")
		lines += problems
		await reply(interaction, "\n".join(lines)[:2000])


async def setup(bot) :
	await bot.add_cog(Bestiary(bot))
