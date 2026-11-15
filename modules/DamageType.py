"""The server's damage types: what each type's strong hits add (bleeding, ignoring DT, arcing, ...). Weapons, spells
and abilities each have one."""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat import Conditions
from classes.combat.DamageTypes import ALWAYS, ARC, CLEANSE, CONDITION, DamageTypes, IGNORE_DT, NONE, STRONG_HIT
from database.transactions.DamageTypeTransactions import DamageTypeTransactions
from views.buttons.Confirm import ask
from views.combat.Pickers import reply

EFFECT_CHOICES = [Choice(name="A condition on the target", value=CONDITION),
                  Choice(name="Ignores DT for that hit", value=IGNORE_DT),
                  Choice(name="Arcs to another enemy for half the damage", value=ARC),
                  Choice(name="Healing removes a condition", value=CLEANSE), Choice(name="Nothing", value=NONE)]
CONDITION_CHOICES = [Choice(name=Conditions.label(name), value=name) for name in Conditions.HARMFUL]
TRIGGER_CHOICES = [Choice(name="On a strong hit", value=STRONG_HIT), Choice(name="Always", value=ALWAYS)]


@app_commands.guild_only()
class DamageType(commands.GroupCog, name="DamageType", group_name="damagetype") :
	"""Damage types and what their strong hits do."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _names(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=name, value=name) for name in DamageTypes.names(interaction.guild_id)
		        if current.lower() in name.lower()][:25]

	# ============================================================
	@staticmethod
	def effect(kind: str, condition: str | None, turns: int | None) -> tuple[dict | None, str | None] :
		effect = {"kind" : kind}
		if kind == CONDITION :
			effect |= {"condition" : condition, "turns" : turns or 1}
		problem = DamageTypes.check_effect(effect)
		return (None, problem) if problem else (effect, None)

	# ============================================================
	@app_commands.command(name="list")
	async def list_types(self, interaction: discord.Interaction) :
		"""
		Lists the server's damage types and what each adds. A strong hit beats the target's AC by 5 or more (or the
		target fails its save by 5 or more); a crit is always a strong hit.
		"""
		lines = [f"**{entry['name']}** ({DamageTypes.trigger_text(entry['trigger'])}): "
		         f"{DamageTypes.describe(entry['effect'])}" for entry in DamageTypes.table(interaction.guild_id).values()]
		await interaction.response.send_message(embed=discord.Embed(title="Damage types", description="\n".join(lines),
		                                                            color=discord.Color.dark_orange()),
		                                        ephemeral=True)

	# ============================================================
	@app_commands.command(name="add")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(effect=EFFECT_CHOICES, condition=CONDITION_CHOICES, trigger=TRIGGER_CHOICES)
	async def add(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 50], effect: Choice[str],
	              condition: Choice[str] = None, turns: app_commands.Range[int, 1, 5] = None,
	              trigger: Choice[str] = None, description: app_commands.Range[str, 1, 500] = None) :
		"""
		Adds a damage type. `effect` is what a strong hit adds: a `condition` for some `turns`, ignoring DT, arcing to
		another enemy, or (for healing) removing a condition. `trigger` is usually a strong hit.

		**Permissions:**
		- `Manage Server`
		"""
		DamageTypes.ensure(interaction.guild_id)
		data, problem = self.effect(effect.value, condition.value if condition else None, turns)
		if problem :
			return await reply(interaction, problem)
		record = DamageTypeTransactions().add(interaction.guild_id, name.strip(), effect=data, description=description,
		                                      trigger=trigger.value if trigger else STRONG_HIT)
		if record is None :
			return await reply(interaction, f"There already is a damage type called {name}.")
		logging.info(f"{interaction.user.name} added damage type {record.name} in {interaction.guild.name}")
		await reply(interaction, f"Added **{record.name}**: {DamageTypes.describe(data)}.")

	# ============================================================
	@app_commands.command(name="edit")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(effect=EFFECT_CHOICES, condition=CONDITION_CHOICES, trigger=TRIGGER_CHOICES)
	@app_commands.autocomplete(name=_names)
	async def edit(self, interaction: discord.Interaction, name: str, effect: Choice[str] = None,
	               condition: Choice[str] = None, turns: app_commands.Range[int, 1, 5] = None,
	               trigger: Choice[str] = None, description: app_commands.Range[str, 1, 500] = None) :
		"""
		Changes a damage type's effect, trigger or description. Renaming isn't possible, because weapons and
		abilities refer to types by name.

		**Permissions:**
		- `Manage Server`
		"""
		record = DamageTypeTransactions().find(interaction.guild_id, name)
		if record is None :
			return await reply(interaction, f"There is no damage type called {name}.")
		current = record.effect or {}
		kind = effect.value if effect else current.get("kind", NONE)
		data, problem = self.effect(kind, condition.value if condition else current.get("condition"),
		                            turns or current.get("turns"))
		if problem :
			return await reply(interaction, problem)
		updates = {"effect" : data}
		if trigger :
			updates["trigger"] = trigger.value
		if description :
			updates["description"] = description
		DamageTypeTransactions().update(record.id, **updates)
		await reply(interaction, f"Updated **{record.name}**: {DamageTypes.describe(data)}.")

	# ============================================================
	@app_commands.command(name="remove")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=_names)
	async def remove(self, interaction: discord.Interaction, name: str) :
		"""
		Removes a damage type. Weapons and abilities that use it keep its name but get no effect.

		**Permissions:**
		- `Manage Server`
		"""
		record = DamageTypeTransactions().find(interaction.guild_id, name)
		if record is None :
			return await reply(interaction, f"There is no damage type called {name}.")
		DamageTypeTransactions().delete(record.id)
		await reply(interaction, f"Removed **{record.name}**.")

	# ============================================================
	@app_commands.command(name="reset")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def reset(self, interaction: discord.Interaction) :
		"""
		Replaces the server's damage types with the default set.

		**Permissions:**
		- `Manage Server`
		"""
		if not await ask(interaction, "Replace all damage types with the defaults? Your own types and changes are "
		                              "lost.", "Reset") :
			return
		DamageTypes.reset(interaction.guild_id)
		await interaction.followup.send("The damage types are back to the defaults.", ephemeral=True)


async def setup(bot) :
	await bot.add_cog(DamageType(bot))
