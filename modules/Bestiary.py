"""The server's bestiary: NPCs and monsters GMs add to fights. Managed by staff (Manage Messages)."""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat import Rules
from classes.combat.DamageTypes import DamageTypes
from classes.combat.Engine import BEHAVIORS
from classes.combat.Loadout import PRESETS
from database.database import Bestiary as BestiaryEntry
from database.transactions.AbilityTransactions import APPROVED, AbilityTransactions
from database.transactions.BestiaryTransactions import BestiaryTransactions
from views.combat.Pickers import reply

PRESET_CHOICES = [Choice(name=f"{preset.capitalize()} (HP {hp}, AC {ac}, DT {dt}, {to_hit:+d}, {damage}, AP {ap})",
                         value=preset) for preset, (hp, ac, dt, to_hit, damage, ap) in PRESETS.items()]
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
}


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
	@staticmethod
	def values(guild_id: int, current: dict, **options) -> dict :
		"""The entry's fields with the filled-in options applied. Raises ValueError for bad values."""
		values = dict(current)
		for key, value in options.items() :
			if value is None :
				continue
			if isinstance(value, Choice) :
				value = value.value
			if key == "damage" :
				Rules.parse_dice(value)
				value = value.strip().lower()
			elif key == "damage_type" :
				if str(value).strip().lower() in ("", "none", "-") :
					value = None
				else :
					value = next((name for name in DamageTypes.names(guild_id) if name.lower() == value.lower()), None)
					if value is None :
						raise ValueError(f"The server has no damage type called {options[key]}; see /damagetype list.")
			elif key == "abilities" :
				ids = []
				for name in [part.strip() for part in str(value).split(",") if part.strip()] :
					ability = AbilityTransactions().find(guild_id, name)
					if ability is None or ability.state != APPROVED :
						raise ValueError(f"There is no approved ability called {name}.")
					ids.append(ability.id)
				key, value = "ability_ids", ids
			values[key] = value
		return values

	# ============================================================
	@staticmethod
	def describe(entry: BestiaryEntry) -> discord.Embed :
		embed = discord.Embed(title=entry.name[:256], description=(entry.description or "")[:4000],
		                      color=discord.Color.dark_red())
		attack = f"{entry.attack_name}: {entry.damage}, {entry.to_hit:+d} to hit" + \
		         (f" ({entry.damage_type})" if entry.damage_type else "")
		embed.add_field(name="Stats", inline=False,
		                value=f"HP {entry.hp} · AC {entry.ac} · DT {entry.dt} · AP {entry.ap} · Sequence "
		                      f"{entry.sequence}\n{attack}\nBehavior: {entry.behavior} · preset {entry.preset}")
		abilities = [AbilityTransactions().get(ability_id) for ability_id in entry.ability_ids or []]
		if any(abilities) :
			embed.add_field(name="Abilities", value=", ".join(ability.name for ability in abilities if ability)[:1024],
			                inline=False)
		if entry.reward_xp or entry.reward_currency :
			embed.add_field(name="Rewards", value=f"{entry.reward_xp} XP, {entry.reward_currency} currency")
		if entry.avatar_url :
			embed.set_thumbnail(url=entry.avatar_url)
		return embed

	# ============================================================
	@app_commands.command(name="add")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.choices(preset=PRESET_CHOICES, behavior=BEHAVIOR_CHOICES)
	@app_commands.autocomplete(damage_type=_types)
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
	              reward_currency: app_commands.Range[int, 0, 1000000] = None) :
		"""
		Adds an NPC or monster to the bestiary. The `preset` (minion, standard, elite, boss) fills in its numbers;
		the options you fill in replace them. A boss has 14 AP, so it acts about twice as much. GMs add bestiary
		entries to a fight from the board's GM tools.

		**Permissions:**
		- `Manage Messages`
		"""
		hp_value, ac_value, dt_value, to_hit_value, damage_value, ap_value = PRESETS[preset.value]
		base = {"preset" : preset.value, "hp" : hp_value, "ac" : ac_value, "dt" : dt_value, "to_hit" : to_hit_value,
		        "damage" : damage_value, "ap" : ap_value, "sequence" : 10, "behavior" : "aggressive",
		        "attack_name" : "Attack", "ability_ids" : []}
		try :
			values = self.values(interaction.guild_id, base, description=description, hp=hp, ac=ac, dt=dt,
			                     to_hit=to_hit, damage=damage, damage_type=damage_type, attack_name=attack_name, ap=ap,
			                     sequence=sequence, behavior=behavior, abilities=abilities, avatar_url=avatar_url,
			                     reward_xp=reward_xp, reward_currency=reward_currency)
		except ValueError as e :
			return await reply(interaction, str(e))
		entry = BestiaryTransactions().add(interaction.guild_id, name.strip(), creator_uid=interaction.user.id, **values)
		if entry is None :
			return await reply(interaction, f"The bestiary already has {name}.")
		logging.info(f"{interaction.user.name} added bestiary entry {entry.id} in {interaction.guild.name}")
		await interaction.response.send_message(f"Added **{entry.name}** to the bestiary.", embed=self.describe(entry),
		                                        ephemeral=True)

	# ============================================================
	@app_commands.command(name="edit")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.choices(behavior=BEHAVIOR_CHOICES)
	@app_commands.autocomplete(name=_names, damage_type=_types)
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
	               reward_currency: app_commands.Range[int, 0, 1000000] = None) :
		"""
		Changes a bestiary entry; options you leave out keep their value. Type `none` as `abilities` or
		`damage_type` to clear them. NPCs already in a fight keep the numbers they joined with.

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
			values = self.values(interaction.guild_id, {}, description=description, hp=hp, ac=ac, dt=dt,
			                     to_hit=to_hit, damage=damage, damage_type=damage_type, attack_name=attack_name, ap=ap,
			                     sequence=sequence, behavior=behavior, abilities=abilities, avatar_url=avatar_url,
			                     reward_xp=reward_xp, reward_currency=reward_currency)
		except ValueError as e :
			return await reply(interaction, str(e))
		if new_name :
			values["name"] = new_name.strip()
		if not values :
			return await reply(interaction, "Nothing to change: fill in at least one option.")
		updated = BestiaryTransactions().update(entry.id, **values)
		await interaction.response.send_message(f"Updated **{updated.name}**.", embed=self.describe(updated),
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
	@app_commands.command(name="list")
	async def list_entries(self, interaction: discord.Interaction) :
		"""
		Lists the bestiary.
		"""
		lines = [f"**{entry.name}** · {entry.preset} · HP {entry.hp} · AC {entry.ac} · {entry.damage}"
		         for entry in BestiaryTransactions().get_all(interaction.guild_id)]
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
		await interaction.response.send_message(embed=self.describe(entry), ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Bestiary(bot))
