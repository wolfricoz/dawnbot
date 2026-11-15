"""Abilities and spells players build: creating and editing them (staff review them), browsing, learning and
forgetting. The rules live in classes/combat/Abilities.py."""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Access import Access
from classes.characters.ForumPost import ForumPost
from classes.combat import Abilities as AbilityRules
from classes.combat import Conditions
from classes.combat.AbilityFlow import AbilityFlow
from classes.combat.AutoComplete import AutoComplete
from classes.combat.DamageTypes import DamageTypes
from classes.combat.Rules import STATS
from database.database import Abilities
from database.transactions.AbilityTransactions import APPROVED, AbilityTransactions, PENDING
from database.transactions.CharacterTransactions import APPROVED as CHARACTER_APPROVED, CharacterTransactions
from views.combat.Pickers import Field, Form, reply

KIND_CHOICES = [Choice(name="Spell (needs a magic school)", value=AbilityRules.SPELL),
                Choice(name="Ability", value=AbilityRules.ABILITY)]
TIER_CHOICES = [Choice(name=f"{tier.capitalize()} ({AbilityRules.TIER_DATA[tier][1]}, "
                            f"{'unlimited' if AbilityRules.uses(tier) is None else AbilityRules.uses(tier)} uses, "
                            f"{AbilityRules.ap(tier)} AP)", value=tier) for tier in AbilityRules.TIERS]
EFFECT_CHOICES = [Choice(name="Damage (attack roll)", value=AbilityRules.DAMAGE),
                  Choice(name="Heal an ally", value=AbilityRules.HEAL),
                  Choice(name="Condition on an enemy (save)", value=AbilityRules.CONDITION),
                  Choice(name="Shield an ally", value=AbilityRules.SHIELD),
                  Choice(name="Boost an ally", value=AbilityRules.BOOST)]
STAT_CHOICES = [Choice(name=stat.capitalize(), value=stat) for stat in STATS]
CONDITION_CHOICES = [Choice(name=f"{Conditions.label(name)}: {Conditions.DEFINITIONS[name][2]}"[:100], value=name)
                     for name in Conditions.HARMFUL + AbilityRules.BOOSTS]
SECONDARY_CHOICES = [Choice(name=f"{Conditions.label(name)}: {Conditions.DEFINITIONS[name][2]}"[:100], value=name)
                     for name in Conditions.HARMFUL]
TEXT_LIMIT = 1000


# ============================================================
def value_of(choice) :
	return choice.value if isinstance(choice, Choice) else choice


@app_commands.guild_only()
class Ability(commands.GroupCog, name="Ability", group_name="ability") :
	"""Build spells and abilities, and teach them to your characters."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# == autocomplete ==

	# ============================================================
	async def _types(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=name, value=name) for name in DamageTypes.names(interaction.guild_id)
		        if current.lower() in name.lower()][:25]

	# ============================================================
	async def _schools(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=f"{school.name} ({school.casting_stat})"[:100], value=school.name)
		        for school in AbilityFlow.schools(interaction.guild_id) if current.lower() in school.name.lower()][:25]

	# ============================================================
	async def _abilities(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""Approved abilities, plus the member's own."""
		return [Choice(name=ability.name[:100], value=ability.name[:100])
		        for ability in AbilityTransactions().get_all(interaction.guild_id)
		        if (ability.state == APPROVED or ability.creator_uid == interaction.user.id)
		        and current.lower() in ability.name.lower()][:25]

	# ============================================================
	async def _known(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		name = interaction.namespace.character
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name) if name else None
		if character is None :
			return []
		return [Choice(name=ability.name[:100], value=ability.name[:100])
		        for _, ability in AbilityTransactions().known(character.id)
		        if current.lower() in ability.name.lower()][:25]

	# == creating ==

	# ============================================================
	async def _submit(self, interaction: discord.Interaction, ability: Abilities, created: bool) -> None :
		if not await AbilityFlow.post_review(self.bot, ability) :
			return await reply(interaction, f"Saved **{ability.name}**, but I could not reach the review channel, so "
			                                f"staff haven't seen it. Please let them know.")
		verb = "submitted" if created else "sent back for review"
		await reply(interaction, f"**{ability.name}** is {verb}: {AbilityFlow.summary(ability)}. Staff will review it.")

	# ============================================================
	@app_commands.command(name="create", description="Builds a new spell or ability; staff review it")
	@app_commands.choices(kind=KIND_CHOICES, tier=TIER_CHOICES, effect=EFFECT_CHOICES, stat=STAT_CHOICES,
	                      condition=CONDITION_CHOICES, secondary=SECONDARY_CHOICES)
	@app_commands.autocomplete(damage_type=_types, school=_schools)
	async def create(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100], kind: Choice[str],
	                 tier: Choice[str], effect: Choice[str], damage_type: str = None, stat: Choice[str] = None,
	                 school: str = None, condition: Choice[str] = None, secondary: Choice[str] = None,
	                 area: bool = False) :
		"""
		Builds a spell or ability from parts, which the bot then resolves in fights:

		- `kind`: a spell needs a magic `school`, and uses the school's stat; an ability uses the `stat` you pick.
		- `tier`: Cantrip (1d6, unlimited), Weak (2d6, 3 uses), Normal (3d6, 2 uses) or Strong (4d8, 1 use) per fight.
		- `effect`: damage (an attack roll), heal, a `condition` on an enemy (they save against it), a shield, or a
		  boost (Inspired or Regenerating).
		- `damage_type`: its effect triggers on a strong hit (see /damagetype list). Healing uses Restoration.
		- `area`: up to 3 targets with half the dice. `secondary`: a damage ability also applies a condition on a
		  hit, for one dice step less.

		After the options, a form asks for the description and any flavor the GM handles. Staff review it in the
		review channel.
		"""
		problem = AbilityFlow.creation_problem(interaction.guild_id, interaction.user.guild_permissions.manage_messages)
		if problem :
			return await reply(interaction, problem)
		if AbilityTransactions().find(interaction.guild_id, name.strip()) is not None :
			return await reply(interaction, f"There already is an ability called {name}.")
		school_record = AbilityTransactions().find_school(interaction.guild_id, school) if school else None
		values, problem = AbilityFlow.check(interaction.guild_id, kind.value, tier.value, effect.value,
		                                    value_of(stat), damage_type, value_of(condition), value_of(secondary), area,
		                                    school_record)
		if problem :
			return await reply(interaction, problem)

		async def described(form_interaction: discord.Interaction, fields: list[str]) :
			await form_interaction.response.defer(ephemeral=True)
			ability = AbilityTransactions().add(interaction.guild_id, name.strip(), creator_uid=interaction.user.id,
			                                    description=fields[0].strip() or None,
			                                    flavor=fields[1].strip() or None, state=PENDING, **values)
			if ability is None :
				return await reply(form_interaction, f"There already is an ability called {name}.")
			logging.info(f"{interaction.user.name} created ability {ability.id} in {interaction.guild.name}")
			await self._submit(form_interaction, ability, created=True)

		await interaction.response.send_modal(Form(name[:45], [
			Field("Description", "What it looks like and does in the story", long=True, max_length=TEXT_LIMIT),
			Field("Flavor the GM handles (optional)", "Extra effects outside the rules", long=True, required=False,
			      max_length=TEXT_LIMIT)], described))

	# ============================================================
	@app_commands.command(name="edit", description="Changes one of your abilities; it goes back to review")
	@app_commands.choices(tier=TIER_CHOICES, effect=EFFECT_CHOICES, stat=STAT_CHOICES, condition=CONDITION_CHOICES,
	                      secondary=SECONDARY_CHOICES)
	@app_commands.autocomplete(name=_abilities, damage_type=_types, school=_schools)
	async def edit(self, interaction: discord.Interaction, name: str, new_name: app_commands.Range[str, 1, 100] = None,
	               tier: Choice[str] = None, effect: Choice[str] = None, damage_type: str = None,
	               stat: Choice[str] = None, school: str = None, condition: Choice[str] = None,
	               secondary: Choice[str] = None, area: bool = None, clear_condition: bool = False,
	               clear_secondary: bool = False) :
		"""
		Changes an ability you created (staff can change any). Options you leave out stay as they are; a form lets
		you change the description and flavor. The ability goes back to staff for review, and can't be used in
		fights until it is approved again.
		"""
		ability = AbilityTransactions().find(interaction.guild_id, name)
		if ability is None :
			return await reply(interaction, f"There is no ability called {name}.")
		staff = interaction.user.guild_permissions.manage_messages
		if ability.creator_uid != interaction.user.id and not staff :
			return await reply(interaction, "Only its creator or staff can change an ability.")
		if new_name and new_name.strip().lower() != ability.name.lower() and \
				AbilityTransactions().find(interaction.guild_id, new_name.strip()) is not None :
			return await reply(interaction, f"There already is an ability called {new_name}.")
		school_record = AbilityTransactions().find_school(interaction.guild_id, school) if school else \
			AbilityTransactions().school(ability.school_id)
		values, problem = AbilityFlow.check(
			interaction.guild_id, ability.kind, value_of(tier) or ability.tier, value_of(effect) or ability.effect,
			value_of(stat) or ability.stat, damage_type or ability.damage_type,
			None if clear_condition else (value_of(condition) or ability.condition),
			None if clear_secondary else (value_of(secondary) or ability.secondary),
			ability.area if area is None else area, school_record)
		if problem :
			return await reply(interaction, problem)

		async def described(form_interaction: discord.Interaction, fields: list[str]) :
			await form_interaction.response.defer(ephemeral=True)
			updated = AbilityTransactions().update(ability.id, name=(new_name or ability.name).strip(),
			                                       description=fields[0].strip() or None,
			                                       flavor=fields[1].strip() or None, state=PENDING, **values)
			logging.info(f"{interaction.user.name} edited ability {ability.id} in {interaction.guild.name}")
			await self._submit(form_interaction, updated, created=False)

		await interaction.response.send_modal(Form((new_name or ability.name)[:45], [
			Field("Description", default=ability.description, long=True, max_length=TEXT_LIMIT),
			Field("Flavor the GM handles (optional)", default=ability.flavor, long=True, required=False,
			      max_length=TEXT_LIMIT)], described))

	# == browsing ==

	# ============================================================
	@app_commands.command(name="list", description="Lists the server's abilities and spells")
	async def list_abilities(self, interaction: discord.Interaction, mine: bool = False) :
		"""
		Lists the approved abilities and spells anyone can learn (tags on their forum posts can restrict them).
		With `mine`, lists the ones you created, whatever their review state.
		"""
		abilities = AbilityTransactions().get_all(interaction.guild_id)
		if mine :
			abilities = [ability for ability in abilities if ability.creator_uid == interaction.user.id]
		else :
			abilities = [ability for ability in abilities if ability.state == APPROVED]
		lines = [f"**{ability.name}**: {AbilityFlow.summary(ability)}"
		         + (f" · *{ability.state}*" if ability.state != APPROVED else "") for ability in abilities]
		text = "\n".join(lines)[:4000] or "No abilities yet. Build one with /ability create."
		await interaction.response.send_message(embed=discord.Embed(title="Abilities", description=text,
		                                                            color=discord.Color.purple()), ephemeral=True)

	# ============================================================
	@app_commands.command(name="view", description="Shows an ability or spell")
	@app_commands.autocomplete(name=_abilities)
	async def view(self, interaction: discord.Interaction, name: str) :
		"""
		Shows an ability: its rules, school, description and flavor.
		"""
		ability = AbilityTransactions().find(interaction.guild_id, name)
		if ability is None or (ability.state != APPROVED and ability.creator_uid != interaction.user.id
		                       and not interaction.user.guild_permissions.manage_messages) :
			return await reply(interaction, f"There is no ability called {name}.")
		await interaction.response.send_message(embed=AbilityFlow.embed(ability), ephemeral=True)

	# == learning ==

	# ============================================================
	@app_commands.command(name="learn", description="Teaches one of your characters an ability")
	@app_commands.autocomplete(character=AutoComplete().approved_character, ability=_abilities)
	async def learn(self, interaction: discord.Interaction, character: str, ability: str) :
		"""
		Teaches your character an approved ability. Spellcasters know at most 6 spells (1 Cantrip, 2 Weak, 2 Normal,
		1 Strong); other characters at most 3 abilities (1 Strong). A character can't have both spells and abilities,
		unless an event granted them. Legendary characters get one extra slot.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None or record.state != CHARACTER_APPROVED :
			return await reply(interaction, f"You have no approved character called {character}.")
		found = AbilityTransactions().find(interaction.guild_id, ability)
		if found is None :
			return await reply(interaction, f"There is no ability called {ability}.")
		problem = AbilityFlow.learn_problem(record, found, Access.of(interaction.user))
		if problem :
			return await reply(interaction, problem)
		AbilityTransactions().learn(record.id, found.id)
		logging.info(f"{interaction.user.name}'s character {record.id} learned ability {found.id}")
		await reply(interaction, f"{record.name} learned **{found.name}**.")
		await ForumPost.sync(self.bot, record)

	# ============================================================
	@app_commands.command(name="forget", description="Makes one of your characters forget an ability")
	@app_commands.autocomplete(character=AutoComplete().character, ability=_known)
	async def forget(self, interaction: discord.Interaction, character: str, ability: str) :
		"""
		Removes an ability from your character, freeing its slot. Event abilities can only be taken away by a GM.
		"""
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None :
			return await reply(interaction, f"You have no character called {character}.")
		known = [(link, item) for link, item in AbilityTransactions().known(record.id)
		         if item.name.lower() == ability.lower()]
		if not known :
			return await reply(interaction, f"{record.name} doesn't know {ability}.")
		link, item = known[0]
		if link.event :
			return await reply(interaction, f"{item.name} was granted by an event; a GM can take it away.")
		AbilityTransactions().forget(record.id, item.id)
		await reply(interaction, f"{record.name} forgot **{item.name}**.")
		if record.state == CHARACTER_APPROVED :
			await ForumPost.sync(self.bot, record)


async def setup(bot) :
	await bot.add_cog(Ability(bot))
