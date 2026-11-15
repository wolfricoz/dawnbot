"""Abilities and spells players build: creating and editing them (staff review them), browsing, learning and
forgetting. Active abilities are used on a turn; passive abilities are always on and take two ability slots. The rules
live in classes/combat/Abilities.py and classes/combat/Passives.py."""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Access import Access
from classes.characters.ForumPost import ForumPost
from classes.combat import Abilities as AbilityRules
from classes.combat import Conditions, Passives
from classes.combat.AbilityFlow import AbilityFlow
from classes.combat.AutoComplete import AutoComplete
from classes.combat.DamageTypes import DamageTypes
from classes.combat.Rules import STATS
from database.database import Abilities
from database.transactions.AbilityTransactions import APPROVED, AbilityTransactions, PASSIVE, PENDING
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
PASSIVE_TIER_CHOICES = [Choice(name=f"{tier.capitalize()} ({index} of to hit, AC, damage...)", value=tier)
                        for tier, index in ((Passives.WEAK, "+1"), (Passives.NORMAL, "+2"), (Passives.STRONG, "+3"))]
PASSIVE_TYPE_CHOICES = [
	Choice(name="Bonus: always +to hit, damage, AC, DT, HP, AP or Sequence", value=Passives.BONUS),
	Choice(name="Resistance: less damage from a damage type, magic or physical", value=Passives.RESIST),
	Choice(name="Immunity: a condition never takes hold (Normal)", value=Passives.IMMUNE),
	Choice(name="Trigger: regenerate, last stand, strong hits add a condition, counter", value=Passives.TRIGGER),
	Choice(name="Aura: standing allies get a bonus", value=Passives.AURA),
	Choice(name="Stacks: each hit taken (e.g. by magic) adds a growing bonus", value=Passives.STACKS)]
FIELD_CHOICES = [Choice(name=Passives.FIELD_LABELS[field], value=field) for field in Passives.FIELDS]
TRIGGER_CHOICES = [Choice(name="Regenerate: heals at the start of each turn", value=Passives.REGENERATE),
                   Choice(name="Last stand: stays at 1 HP instead of going down", value=Passives.LAST_STAND),
                   Choice(name="On a strong hit: adds the condition", value=Passives.ON_STRONG_HIT),
                   Choice(name="Counter: hits back at melee attackers that miss", value=Passives.COUNTER)]
HARMFUL_CHOICES = SECONDARY_CHOICES
PASSIVE_HELP = {
	"tier"      : "Weak, Normal or Strong; sets the size (at most one Strong ability or passive)",
	"type"      : "What kind of passive it is",
	"field"     : "Bonus, aura or stacks: what it adds to",
	"target"    : "Bonus: melee, ranged, magic or a damage type. Resistance/stacks: magic, physical, any or a type",
	"trigger"   : "Trigger: when it fires",
	"condition" : "Immunity: the condition it blocks. On a strong hit: the condition it adds",
	"stack_limit" : "Stacks: how many stacks it can hold (1 to 30; default 2/3/5 by tier)",
}
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

	# ============================================================
	async def _targets(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""Scopes and sources for passives: melee, ranged, magic, physical, any and the server's damage types."""
		names = [Passives.MELEE, Passives.RANGED, Passives.MAGIC, Passives.PHYSICAL, Passives.ANY]
		names += DamageTypes.names(interaction.guild_id)
		return [Choice(name=name, value=name) for name in names if current.lower() in name.lower()][:25]

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
		if ability.activation == PASSIVE :
			return await reply(interaction, f"{ability.name} is a passive; change it with /ability passive_edit.")
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

	# == passives ==

	# ============================================================
	def _passive_form(self, title: str, ability: Abilities | None, save) -> Form :
		return Form(title[:45], [
			Field("Description", "What it looks like in the story", default=ability.description if ability else None,
			      long=True, max_length=TEXT_LIMIT),
			Field("Flavor the GM handles (optional)", "Extra effects outside the rules",
			      default=ability.flavor if ability else None, long=True, required=False, max_length=TEXT_LIMIT)],
			save)

	# ============================================================
	@app_commands.command(name="passive", description="Builds a passive ability (always on, 2 slots); staff review it")
	@app_commands.choices(tier=PASSIVE_TIER_CHOICES, type=PASSIVE_TYPE_CHOICES, field=FIELD_CHOICES,
	                      trigger=TRIGGER_CHOICES, condition=HARMFUL_CHOICES)
	@app_commands.autocomplete(target=_targets)
	@app_commands.describe(**PASSIVE_HELP)
	async def passive(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100], tier: Choice[str],
	                  type: Choice[str], field: Choice[str] = None, target: str = None, trigger: Choice[str] = None,
	                  condition: Choice[str] = None,
	                  stack_limit: app_commands.Range[int, 1, Passives.STACK_LIMIT_MAX] = None) :
		"""
		Builds a passive ability: always on, never used on a turn. It takes 2 of a character's 3 ability slots (an
		active ability takes 1), and spellcasters can't learn passives unless an event grants one. The tier sets its
		size: Weak +1, Normal +2, Strong +3.

		- `bonus`: +to hit, damage, AC (within the cap of 18), DT, max HP (+5/10/15), AP (+1/1/2) or Sequence
		  (+2/4/6). To hit and damage can be limited with `target` (melee, ranged, magic or a damage type).
		- `resistance`: hits from `target` (a damage type, magic or physical) do 2/4/6 less damage, at least 1.
		- `immunity` (Normal): the `condition` never takes hold.
		- `trigger`: regenerate (1d4/1d6/1d8 each turn), last stand (Normal once, Strong twice per fight), on a strong
		  hit (adds `condition` for 1/2/3 turns) or counter (1d4/1d6/1d8 to a melee attacker that misses, once a round).
		- `aura`: standing allies get +1/+1/+2 to hit, damage or AC.
		- `stacks`: each hit it takes from `target` (any, magic, physical or a damage type) adds +1 to hit, damage or
		  AC for the rest of the fight, up to `stack_limit` stacks (1 to 30; without it 2/3/5 by tier).
		"""
		problem = AbilityFlow.creation_problem(interaction.guild_id, interaction.user.guild_permissions.manage_messages)
		if problem :
			return await reply(interaction, problem)
		if AbilityTransactions().find(interaction.guild_id, name.strip()) is not None :
			return await reply(interaction, f"There already is an ability called {name}.")
		values, problem = AbilityFlow.check_passive(interaction.guild_id, tier.value, {
			"type" : type.value, "field" : value_of(field), "scope" : target, "trigger" : value_of(trigger),
			"condition" : value_of(condition), "limit" : stack_limit})
		if problem :
			return await reply(interaction, problem)

		async def described(form_interaction: discord.Interaction, fields: list[str]) :
			await form_interaction.response.defer(ephemeral=True)
			ability = AbilityTransactions().add(interaction.guild_id, name.strip(), creator_uid=interaction.user.id,
			                                    description=fields[0].strip() or None,
			                                    flavor=fields[1].strip() or None, state=PENDING, **values)
			if ability is None :
				return await reply(form_interaction, f"There already is an ability called {name}.")
			logging.info(f"{interaction.user.name} created passive ability {ability.id} in {interaction.guild.name}")
			await self._submit(form_interaction, ability, created=True)

		await interaction.response.send_modal(self._passive_form(name, None, described))

	# ============================================================
	@app_commands.command(name="passive_edit", description="Changes one of your passive abilities; it goes back to "
	                                                       "review")
	@app_commands.choices(tier=PASSIVE_TIER_CHOICES, type=PASSIVE_TYPE_CHOICES, field=FIELD_CHOICES,
	                      trigger=TRIGGER_CHOICES, condition=HARMFUL_CHOICES)
	@app_commands.autocomplete(name=_abilities, target=_targets)
	@app_commands.describe(**PASSIVE_HELP)
	async def passive_edit(self, interaction: discord.Interaction, name: str,
	                       new_name: app_commands.Range[str, 1, 100] = None, tier: Choice[str] = None,
	                       type: Choice[str] = None, field: Choice[str] = None, target: str = None,
	                       trigger: Choice[str] = None, condition: Choice[str] = None,
	                       stack_limit: app_commands.Range[int, 0, Passives.STACK_LIMIT_MAX] = None) :
		"""
		Changes a passive ability you created (staff can change any). Options you leave out stay as they are; a form
		lets you change the description and flavor. It goes back to staff for review and doesn't work in fights
		until it is approved again. Type `none` as `target` to remove its limit, and set `stack_limit` to 0 to go back
		to the tier's stack limit.
		"""
		ability = AbilityTransactions().find(interaction.guild_id, name)
		if ability is None :
			return await reply(interaction, f"There is no ability called {name}.")
		if ability.creator_uid != interaction.user.id and not interaction.user.guild_permissions.manage_messages :
			return await reply(interaction, "Only its creator or staff can change an ability.")
		if ability.activation != PASSIVE :
			return await reply(interaction, f"{ability.name} is an active ability; change it with /ability edit.")
		if new_name and new_name.strip().lower() != ability.name.lower() and \
				AbilityTransactions().find(interaction.guild_id, new_name.strip()) is not None :
			return await reply(interaction, f"There already is an ability called {new_name}.")
		current = Passives.normalise(ability.passive)
		scope = current["scope"] if target is None else (None if target.strip().lower() in ("none", "-") else target)
		values, problem = AbilityFlow.check_passive(interaction.guild_id, value_of(tier) or ability.tier, {
			"type" : value_of(type) or current["type"], "field" : value_of(field) or current["field"], "scope" : scope,
			"trigger" : value_of(trigger) or current["trigger"],
			"condition" : value_of(condition) or current["condition"],
			"limit" : current["limit"] if stack_limit is None else (stack_limit or None)})
		if problem :
			return await reply(interaction, problem)

		async def described(form_interaction: discord.Interaction, fields: list[str]) :
			await form_interaction.response.defer(ephemeral=True)
			updated = AbilityTransactions().update(ability.id, name=(new_name or ability.name).strip(),
			                                       description=fields[0].strip() or None,
			                                       flavor=fields[1].strip() or None, state=PENDING, **values)
			logging.info(f"{interaction.user.name} edited passive ability {ability.id} in {interaction.guild.name}")
			await self._submit(form_interaction, updated, created=False)

		await interaction.response.send_modal(self._passive_form(new_name or ability.name, ability, described))

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
		1 Strong); other characters have 3 ability slots, where an active ability takes 1 and a passive 2 (at most 1
		Strong). A character can't have both spells and abilities, unless an event granted them. Legendary characters
		get one extra slot.
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
