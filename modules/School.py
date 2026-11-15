"""Magic schools: the standard ones every server has, and the ones players propose (staff review them)."""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat import Abilities as AbilityRules
from classes.combat.AbilityFlow import AbilityFlow
from database.transactions.AbilityTransactions import APPROVED, AbilityTransactions, PENDING
from views.combat.Pickers import reply

STAT_CHOICES = [Choice(name=stat.capitalize(), value=stat) for stat in AbilityRules.CASTING_STATS]


@app_commands.guild_only()
class School(commands.GroupCog, name="School", group_name="school") :
	"""Magic schools that spells belong to."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _schools(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=school.name[:100], value=school.name[:100])
		        for school in AbilityFlow.schools(interaction.guild_id, approved_only=False)
		        if (school.state == APPROVED or school.creator_uid == interaction.user.id)
		        and current.lower() in school.name.lower()][:25]

	# ============================================================
	@app_commands.command(name="create", description="Proposes a new magic school; staff review it")
	@app_commands.choices(casting_stat=STAT_CHOICES)
	async def create(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 50],
	                 casting_stat: Choice[str], description: app_commands.Range[str, 1, 1000]) :
		"""
		Proposes a magic school. Spells of a school use its casting stat (Intelligence or Charisma) for their rolls.
		Staff review it before spells can use it. Every server also has the standard schools (see /school list).
		"""
		problem = AbilityFlow.creation_problem(interaction.guild_id, interaction.user.guild_permissions.manage_messages)
		if problem :
			return await reply(interaction, problem)
		AbilityFlow.ensure_schools(interaction.guild_id)
		await interaction.response.defer(ephemeral=True)
		school = AbilityTransactions().add_school(interaction.guild_id, name.strip(), casting_stat=casting_stat.value,
		                                          description=description.strip(), creator_uid=interaction.user.id,
		                                          state=PENDING)
		if school is None :
			return await reply(interaction, f"There already is a school called {name}.")
		logging.info(f"{interaction.user.name} proposed magic school {school.id} in {interaction.guild.name}")
		if not await AbilityFlow.post_review(self.bot, school) :
			return await reply(interaction, "Saved, but I could not reach the review channel; please let staff know.")
		await reply(interaction, f"**{school.name}** was sent to staff for review.")

	# ============================================================
	@app_commands.command(name="edit", description="Changes a magic school you proposed")
	@app_commands.choices(casting_stat=STAT_CHOICES)
	@app_commands.autocomplete(name=_schools)
	async def edit(self, interaction: discord.Interaction, name: str, new_name: app_commands.Range[str, 1, 50] = None,
	               casting_stat: Choice[str] = None, description: app_commands.Range[str, 1, 1000] = None) :
		"""
		Changes a magic school you proposed (staff can change any, including the standard ones). A member's change
		sends the school back to staff for review. Changing the casting stat changes it for every spell of the
		school too.
		"""
		staff = interaction.user.guild_permissions.manage_messages
		school = AbilityTransactions().find_school(interaction.guild_id, name)
		if school is None :
			return await reply(interaction, f"There is no school called {name}.")
		if not staff and school.creator_uid != interaction.user.id :
			return await reply(interaction, "You can only change schools you proposed.")
		updates = {}
		if new_name and new_name.strip() != school.name :
			other = AbilityTransactions().find_school(interaction.guild_id, new_name.strip())
			if other is not None and other.id != school.id :
				return await reply(interaction, f"There already is a school called {new_name}.")
			updates["name"] = new_name.strip()
		if casting_stat and casting_stat.value != school.casting_stat :
			updates["casting_stat"] = casting_stat.value
		if description :
			updates["description"] = description.strip()
		if not updates :
			return await reply(interaction, "Nothing to change: fill in at least one option.")
		await interaction.response.defer(ephemeral=True)
		if not staff :
			updates["state"] = PENDING
		updated = AbilityTransactions().update_school(school.id, **updates)
		if "casting_stat" in updates :
			for ability in AbilityTransactions().get_all(interaction.guild_id) :
				if ability.school_id == school.id :
					AbilityTransactions().update(ability.id, stat=updates["casting_stat"])
		logging.info(f"{interaction.user.name} edited magic school {school.id} in {interaction.guild.name}: "
		             f"{', '.join(updates)}")
		if updated.state == PENDING :
			if not await AbilityFlow.post_review(self.bot, updated) :
				return await reply(interaction, "Saved, but I could not reach the review channel; please let staff "
				                                "know.")
			return await reply(interaction, f"**{updated.name}** was changed and sent back to staff for review; its "
			                                f"spells can't be learned until it is approved again.")
		await reply(interaction, f"Updated **{updated.name}**.")

	# ============================================================
	@app_commands.command(name="list", description="Lists the magic schools")
	async def list_schools(self, interaction: discord.Interaction) :
		"""
		Lists the server's magic schools and their casting stats.
		"""
		lines = [f"**{school.name}** ({school.casting_stat.capitalize()})"
		         + (" · standard" if school.standard else "") + (f": {school.description[:120]}" if school.description
		                                                          else "")
		         for school in AbilityFlow.schools(interaction.guild_id)]
		await interaction.response.send_message(embed=discord.Embed(title="Magic schools",
		                                                            description="\n".join(lines)[:4000] or "None.",
		                                                            color=discord.Color.dark_purple()),
		                                        ephemeral=True)

	# ============================================================
	@app_commands.command(name="view", description="Shows a magic school")
	@app_commands.autocomplete(name=_schools)
	async def view(self, interaction: discord.Interaction, name: str) :
		"""
		Shows a magic school and the approved spells that belong to it.
		"""
		school = AbilityTransactions().find_school(interaction.guild_id, name)
		if school is None :
			return await reply(interaction, f"There is no school called {name}.")
		embed = AbilityFlow.school_embed(school)
		spells = [ability.name for ability in AbilityTransactions().get_all(interaction.guild_id, [APPROVED])
		          if ability.school_id == school.id]
		if spells :
			embed.add_field(name="Spells", value=", ".join(spells)[:1024], inline=False)
		await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot) :
	await bot.add_cog(School(bot))
