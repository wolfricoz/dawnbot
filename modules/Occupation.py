import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Access import Access
from classes.characters.Choices import Choices
from classes.characters.ForumPost import ForumPost
from classes.kernel.ServerSync import sync_server
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from views.buttons.Confirm import ask


@app_commands.guild_only()
class Occupation(commands.GroupCog, name="Occupation", group_name="occupation") :


	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _names(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=occupation.name, value=occupation.name)
		        for occupation in OccupationTransactions().get_all(interaction.guild_id)
		        if current.lower() in occupation.name.lower()][:25]

	# ============================================================
	async def _characters(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		member = interaction.namespace.member
		if member is None :
			return []
		return [Choice(name=character.name, value=character.name)
		        for character in CharacterTransactions().get_all(member.id, interaction.guild_id)
		        if current.lower() in character.name.lower()][:25]

	# ============================================================
	@app_commands.command(name="add")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def add(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100],
	              limit: app_commands.Range[int, 1, 1000] = None, description: app_commands.Range[str, 1, 1000] = None,
	              min_level: app_commands.Range[int, 1, 1000] = None, role: discord.Role = None,
	              staff_only: bool = False) :
		"""
		Adds an occupation. Leave out `limit` for no limit on how many characters can hold it. `min_level` is the
		server level a member needs (the number of level roles they have reached), `role` a role they need;
		`staff_only` ones are only given out with /occupation assign.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		sync_server(interaction.guild)
		occupation = OccupationTransactions().add(interaction.guild_id, name, max_holders=limit,
		                                          description=description, min_level=min_level,
		                                          role_id=role.id if role else None, staff_only=staff_only)
		if occupation is None :
			return await interaction.followup.send(f"There already is an occupation called {name}.")
		logging.info(f"{interaction.user.name} added occupation {name} in {interaction.guild.name}")
		await interaction.followup.send(f"Added the occupation {name}.")

	# ============================================================
	@app_commands.command(name="edit")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=_names)
	async def edit(self, interaction: discord.Interaction, name: str, new_name: app_commands.Range[str, 1, 100] = None,
	               limit: app_commands.Range[int, 1, 1000] = None, no_limit: bool = False,
	               description: app_commands.Range[str, 1, 1000] = None,
	               min_level: app_commands.Range[int, 0, 1000] = None, role: discord.Role = None,
	               no_role: bool = False, staff_only: bool = None) :
		"""
		Changes an occupation; options you leave out keep their value. Use `no_limit` or `no_role` to remove the
		limit or the role, and min_level 0 to remove the level. Lowering the limit below the number of holders takes
		nobody's occupation away; it only stops new characters from picking it.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		occupation = OccupationTransactions().find(interaction.guild_id, name)
		if occupation is None :
			return await interaction.followup.send(f"There is no occupation called {name}.")
		if new_name and new_name.lower() != occupation.name.lower() \
				and OccupationTransactions().find(interaction.guild_id, new_name) is not None :
			return await interaction.followup.send(f"There already is an occupation called {new_name}.")
		updates = {"name" : new_name, "description" : description, "staff_only" : staff_only}
		updates = {key : value for key, value in updates.items() if value is not None}
		if no_limit :
			updates["max_holders"] = None
		elif limit is not None :
			updates["max_holders"] = limit
		if min_level is not None :
			updates["min_level"] = min_level or None
		if no_role :
			updates["role_id"] = None
		elif role is not None :
			updates["role_id"] = role.id
		OccupationTransactions().update(occupation.id, **updates)
		await interaction.followup.send(f"Updated {new_name or occupation.name}.")

	# ============================================================
	@app_commands.command(name="remove")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=_names)
	async def remove(self, interaction: discord.Interaction, name: str) :
		"""
		Removes an occupation. Characters that hold it are left without an occupation.

		**Permissions:**
		- `Manage Server`
		"""
		occupation = OccupationTransactions().find(interaction.guild_id, name)
		if occupation is None :
			return await interaction.response.send_message(f"There is no occupation called {name}.", ephemeral=True)
		holders = OccupationTransactions().holders(occupation.id)
		question = f"Remove the occupation **{occupation.name}**?"
		if holders :
			question += f" {len(holders)} character{'s hold' if len(holders) != 1 else ' holds'} it and will have none."
		if not await ask(interaction, question, "Remove") :
			return
		OccupationTransactions().delete(occupation.id)
		for character in holders :
			# Changes waiting for review that would give the removed occupation are dropped from the request.
			pending = dict(character.pending_changes or {})
			if pending.get("occupation_id") == occupation.id :
				pending.pop("occupation_id")
				CharacterTransactions().update(character.id, pending_changes=pending or None)
			await ForumPost.sync(self.bot, CharacterTransactions().get_by_id(character.id))
		logging.info(f"{interaction.user.name} removed occupation {occupation.name} in {interaction.guild.name}")
		await interaction.followup.send(f"Removed {occupation.name}.", ephemeral=True)

	# ============================================================
	@app_commands.command(name="move")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=_names)
	async def move(self, interaction: discord.Interaction, name: str, position: app_commands.Range[int, 1, 100]) :
		"""
		Moves an occupation to another position in the list; position 1 shows first.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		if not OccupationTransactions().move(interaction.guild_id, name, position) :
			return await interaction.followup.send(f"There is no occupation called {name}.")
		await interaction.followup.send(f"Moved {name} to position {position}.")

	# ============================================================
	@app_commands.command(name="list")
	async def list_occupations(self, interaction: discord.Interaction) :
		"""
		Lists the occupations, how many characters hold each and how many can, and which ones you cannot pick.
		"""
		await interaction.response.defer(ephemeral=True)
		choices = Choices.occupations(interaction.guild_id, Access.of(interaction.user))
		if not choices :
			return await interaction.followup.send("This server has no occupations.")
		lines = []
		for choice in choices :
			line = f"**{choice.label}**"
			if choice.locked :
				line += f" (unavailable: {choice.locked})"
			if choice.occupation.description :
				line += f"\n-# {choice.occupation.description[:200]}"
			lines.append(line)
		await interaction.followup.send(embed=discord.Embed(title="Occupations", description="\n".join(lines)[:4000]))

	# ============================================================
	@app_commands.command(name="assign")
	@app_commands.checks.has_permissions(manage_messages=True)
	@app_commands.autocomplete(character=_characters, occupation=_names)
	async def assign(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                 occupation: str = None) :
		"""
		Gives a member's character an occupation, or takes it away when you leave `occupation` out. This applies at
		once, without a review, and works for staff-only occupations and full ones too.

		**Permissions:**
		- `Manage Messages`
		"""
		await interaction.response.defer(ephemeral=True)
		record = CharacterTransactions().get(member.id, interaction.guild_id, character)
		if record is None :
			return await interaction.followup.send(f"{member.display_name} has no character called {character}.")
		target = None
		if occupation is not None :
			target = OccupationTransactions().find(interaction.guild_id, occupation)
			if target is None :
				return await interaction.followup.send(f"There is no occupation called {occupation}.")
		note = ""
		if target is not None and not Choices.room_for(target.id, record.id) :
			note = f" {target.name} is now over its limit."
		updated = CharacterTransactions().update(record.id, occupation_id=target.id if target else None)
		await ForumPost.sync(self.bot, updated)
		logging.info(f"{interaction.user.name} set the occupation of character {record.id} to "
		             f"{target.name if target else 'none'}")
		what = f"is now {target.name}" if target else "no longer has an occupation"
		await interaction.followup.send(f"{record.name} {what}.{note}")


async def setup(bot) :
	await bot.add_cog(Occupation(bot))
