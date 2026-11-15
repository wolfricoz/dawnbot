"""Abilities and spells players build from the effect catalog: creating and editing them (staff review them),
browsing the catalog, learning and forgetting. Players can't write their own rules: every ability is a tier, a stat and
a list of catalog effects, magic for spells and physical for abilities. Active abilities cost their tier's base AP
plus their effects' costs; passives lower the character's AP every turn. The rules live in classes/combat/Effects.py,
EffectCatalog.py, PassiveCatalog.py, Abilities.py and Passives.py."""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Access import Access
from classes.characters.ForumPost import ForumPost
from classes.combat import Abilities as AbilityRules
from classes.combat import EffectCatalog, Effects, PassiveCatalog, Passives
from classes.combat.AbilityFlow import AbilityFlow
from classes.combat.AutoComplete import AutoComplete
from classes.combat.DamageTypes import DamageTypes
from classes.combat.Rules import STATS
from classes.combat.SheetAbilities import SheetAbilities
from database.database import Abilities
from database.transactions.AbilityTransactions import APPROVED, AbilityTransactions, DRAFT, PASSIVE, PENDING
from database.transactions.CharacterTransactions import APPROVED as CHARACTER_APPROVED, CharacterTransactions
from views.combat.Pickers import Field, Form, reply

KIND_CHOICES = [Choice(name="Spell (magic effects, needs a magic school)", value=AbilityRules.SPELL),
                Choice(name="Ability (physical effects)", value=AbilityRules.ABILITY)]
TIER_CHOICES = [Choice(name=f"{tier.capitalize()} ({Effects.base_dice(tier)}, "
                            f"{'unlimited' if Effects.uses(tier) is None else Effects.uses(tier)} uses, "
                            f"{Effects.base_ap(tier)} AP + effects, up to {Effects.max_effects(tier)} effects)",
                       value=tier) for tier in Effects.TIERS]
STAT_CHOICES = [Choice(name=stat.capitalize(), value=stat) for stat in STATS]
PASSIVE_TIER_CHOICES = [Choice(name=f"{tier.capitalize()} ({size} of to hit, AC, damage...; up to "
                                    f"{Passives.MAX_EFFECTS[tier]} effect{'s' if Passives.MAX_EFFECTS[tier] > 1 else ''})",
                               value=tier)
                        for tier, size in ((Passives.WEAK, "+1"), (Passives.NORMAL, "+2"), (Passives.STRONG, "+3"))]
REALM_CHOICES = [Choice(name="Magic (spells)", value=Effects.MAGIC),
                 Choice(name="Physical (abilities)", value=Effects.PHYSICAL)]
EFFECT_HELP = "An effect from the catalog (see /ability effects); type to search"
ACTIVE_HELP = {
	"kind"        : "Spell (magic effects) or ability (physical effects)",
	"tier"        : "Sets the dice, uses per fight, base AP and how many effects it can hold",
	"effect1"     : EFFECT_HELP,
	"effect2"     : EFFECT_HELP,
	"effect3"     : EFFECT_HELP,
	"effect4"     : EFFECT_HELP,
	"effect5"     : EFFECT_HELP,
	"damage_type" : "For effects that take the ability's own damage type (Bolt, Strike...)",
	"stat"        : "Abilities: the stat it rolls with (spells use their school's)",
	"school"      : "Spells: the magic school (sets the stat)",
}
PASSIVE_HELP = {
	"kind"        : "Spell passive (magic effects, 1 spell slot) or ability passive (physical effects, 2 slots)",
	"tier"        : "Weak, Normal or Strong: the size of each effect (at most one Strong ability or passive)",
	"effect1"     : "A passive effect from the catalog (see /ability effects passive:True)",
	"effect2"     : "A second passive effect (Normal and Strong)",
	"effect3"     : "A third passive effect (Strong)",
	"target"      : "For effects you aim: a damage type, or melee, ranged, magic, physical, any",
	"stack_limit" : "Stacks: how many stacks it can hold (1 to 30; default 2/3/5 by tier)",
	"school"      : "Spell passives: the magic school",
}
PASSIVE_EDIT_HELP = {key : text for key, text in PASSIVE_HELP.items() if key != "kind"}
TEXT_LIMIT = 1000
EMBED_LIMIT = 4000


# ============================================================
def value_of(choice) :
	return choice.value if isinstance(choice, Choice) else choice


# ============================================================
def effect_choice(effect: Effects.Effect) -> Choice[str] :
	tier = f" · {effect.tier.capitalize()}+" if effect.tier not in (Effects.CANTRIP, Passives.WEAK) else ""
	return Choice(name=f"{effect.name} · {effect.cost:+d} AP{tier} · {effect.text}"[:100], value=effect.key)


@app_commands.guild_only()
class Ability(commands.GroupCog, name="Ability", group_name="ability") :
	"""Build spells and abilities from the effect catalog, and teach them to your characters."""

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
	def _context(self, interaction: discord.Interaction) -> tuple[str | None, str | None] :
		"""The kind and tier typed so far, or the ones of the ability being edited."""
		kind, tier = interaction.namespace.kind, interaction.namespace.tier
		if (kind is None or tier is None) and interaction.namespace.name :
			ability = AbilityTransactions().find(interaction.guild_id, interaction.namespace.name)
			if ability is not None :
				kind, tier = kind or ability.kind, tier or ability.tier
		return kind, tier

	# ============================================================
	async def _effects(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""Active effects that fit the kind (magic for spells, physical for abilities) and the tier."""
		kind, tier = self._context(interaction)
		realm = Effects.realm_of(kind) if kind else None
		found = [effect for effect in EffectCatalog.search(current, realm)
		         if tier not in Effects.TIERS or Effects.tier_index(tier) >= Effects.tier_index(effect.tier)]
		return [effect_choice(effect) for effect in found[:25]]

	# ============================================================
	async def _passive_effects(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		kind, tier = self._context(interaction)
		realm = Effects.realm_of(kind) if kind else None
		found = [effect for effect in PassiveCatalog.search(current, realm)
		         if tier not in Passives.TIERS or Passives.index(tier) >= Passives.index(
				effect.tier if effect.tier in Passives.TIERS else Passives.WEAK)]
		return [effect_choice(effect) for effect in found[:25]]

	# ============================================================
	async def _targets(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""Scopes and sources for passives: melee, ranged, magic, physical, any and the server's damage types."""
		names = [Passives.MELEE, Passives.RANGED, Effects.MAGIC, Effects.PHYSICAL, Passives.ANY]
		names += DamageTypes.names(interaction.guild_id)
		return [Choice(name=name, value=name) for name in names if current.lower() in name.lower()][:25]

	# ============================================================
	async def _categories(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		categories = PassiveCatalog.CATEGORIES if interaction.namespace.passive else EffectCatalog.CATEGORIES
		return [Choice(name=name, value=name) for name in categories if current.lower() in name.lower()][:25]

	# == creating ==

	# ============================================================
	async def _submit(self, interaction: discord.Interaction, ability: Abilities, created: bool) -> None :
		if not await AbilityFlow.post_review(self.bot, ability) :
			return await reply(interaction, f"Saved **{ability.name}**, but I could not reach the review channel, so "
			                                f"staff haven't seen it. Please let them know.")
		verb = "submitted" if created else "sent back for review"
		await reply(interaction, f"**{ability.name}** is {verb}. Staff will review it.\n"
		                         f"{AbilityFlow.summary(ability)}"[:2000])

	# ============================================================
	def _form(self, title: str, ability: Abilities | None, save) -> Form :
		return Form(title[:45], [
			Field("Description", "What it looks like and does in the story",
			      default=ability.description if ability else None, long=True, max_length=TEXT_LIMIT),
			Field("Flavor the GM handles (optional)", "Extra effects outside the rules",
			      default=ability.flavor if ability else None, long=True, required=False, max_length=TEXT_LIMIT)],
			save)

	# ============================================================
	def _may_edit(self, interaction: discord.Interaction, ability: Abilities | None, name: str) -> str | None :
		if ability is None :
			return f"There is no ability called {name}."
		if ability.creator_uid != interaction.user.id and not interaction.user.guild_permissions.manage_messages :
			return "Only its creator or staff can change an ability."
		return None

	# ============================================================
	def _new_name_problem(self, interaction: discord.Interaction, ability: Abilities, new_name: str | None) -> str | None :
		if new_name and new_name.strip().lower() != ability.name.lower() and \
				AbilityTransactions().find(interaction.guild_id, new_name.strip()) is not None :
			return f"There already is an ability called {new_name}."
		return None

	# ============================================================
	@app_commands.command(name="create", description="Builds a spell or ability from catalog effects; staff review it")
	@app_commands.choices(kind=KIND_CHOICES, tier=TIER_CHOICES, stat=STAT_CHOICES)
	@app_commands.autocomplete(effect1=_effects, effect2=_effects, effect3=_effects, effect4=_effects,
	                           effect5=_effects, damage_type=_types, school=_schools)
	@app_commands.describe(**ACTIVE_HELP)
	async def create(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100], kind: Choice[str],
	                 tier: Choice[str], effect1: str, effect2: str = None, effect3: str = None, effect4: str = None,
	                 effect5: str = None, damage_type: str = None, stat: Choice[str] = None, school: str = None) :
		"""
		Builds a spell or ability from effects in the catalog (browse them with /ability effects). The bot resolves
		every effect itself in fights, so there are no free-text powers.

		- `kind`: a spell takes magic effects and needs a magic `school` (which sets its stat); an ability takes
		  physical effects and uses the `stat` you pick.
		- `tier`: Cantrip (1d6, unlimited, up to 2 effects), Weak (2d6, 3 uses, 3 effects), Normal (3d6, 2 uses, 4
		  effects) or Strong (4d8, 1 use, 5 effects). Some effects need a higher tier.
		- `effect1` to `effect5`: what it does. Its AP cost is the tier's base (1, 1, 2, 3) plus every effect's cost;
		  modifiers (area, empowered...) add to it, drawbacks (blood price, reckless...) take 1 off.
		- `damage_type`: for effects that take the ability's own type, like Bolt or Strike.

		A form then asks for the description and any flavor the GM handles. Staff review it in the review channel.
		"""
		problem = AbilityFlow.creation_problem(interaction.guild_id, interaction.user.guild_permissions.manage_messages)
		if problem :
			return await reply(interaction, problem)
		if AbilityTransactions().find(interaction.guild_id, name.strip()) is not None :
			return await reply(interaction, f"There already is an ability called {name}.")
		school_record = AbilityTransactions().find_school(interaction.guild_id, school) if school else None
		values, problem = AbilityFlow.check(interaction.guild_id, kind.value, tier.value,
		                                    [effect1, effect2, effect3, effect4, effect5], value_of(stat), damage_type,
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

		await interaction.response.send_modal(self._form(name, None, described))

	# ============================================================
	@app_commands.command(name="edit", description="Changes one of your abilities (or builds a blank one); it goes "
	                                               "back to review")
	@app_commands.choices(kind=KIND_CHOICES, tier=TIER_CHOICES, stat=STAT_CHOICES)
	@app_commands.autocomplete(name=_abilities, effect1=_effects, effect2=_effects, effect3=_effects,
	                           effect4=_effects, effect5=_effects, damage_type=_types, school=_schools)
	@app_commands.describe(**ACTIVE_HELP)
	async def edit(self, interaction: discord.Interaction, name: str, new_name: app_commands.Range[str, 1, 100] = None,
	               kind: Choice[str] = None, tier: Choice[str] = None, effect1: str = None, effect2: str = None,
	               effect3: str = None, effect4: str = None, effect5: str = None, damage_type: str = None,
	               stat: Choice[str] = None, school: str = None) :
		"""
		Changes an ability you created (staff can change any), including the blank abilities made from old sheet
		answers. Options you leave out stay as they are. Giving any effect replaces the whole effect list with the
		ones you give. The kind can only change while the ability is still blank. A form lets you change the
		description and flavor. The ability goes back to staff for review, and can't be used in fights until it is
		approved again.
		"""
		ability = AbilityTransactions().find(interaction.guild_id, name)
		problem = self._may_edit(interaction, ability, name)
		if problem :
			return await reply(interaction, problem)
		if ability.activation == PASSIVE and ability.state != DRAFT :
			return await reply(interaction, f"{ability.name} is a passive; change it with /ability passive_edit.")
		if kind and ability.state != DRAFT and kind.value != ability.kind :
			return await reply(interaction, "Only a blank ability can change between spell and ability; create a new "
			                                "one instead.")
		problem = self._new_name_problem(interaction, ability, new_name)
		if problem :
			return await reply(interaction, problem)
		picked = [effect1, effect2, effect3, effect4, effect5]
		names = picked if any(picked) else AbilityRules.keys(ability.effects)
		school_record = AbilityTransactions().find_school(interaction.guild_id, school) if school else \
			AbilityTransactions().school(ability.school_id)
		values, problem = AbilityFlow.check(interaction.guild_id, value_of(kind) or ability.kind,
		                                    value_of(tier) or ability.tier, names, value_of(stat) or ability.stat,
		                                    damage_type or ability.damage_type, school_record)
		if problem :
			return await reply(interaction, problem)

		async def described(form_interaction: discord.Interaction, fields: list[str]) :
			await form_interaction.response.defer(ephemeral=True)
			updated = AbilityTransactions().update(ability.id, name=(new_name or ability.name).strip(),
			                                       description=fields[0].strip() or None,
			                                       flavor=fields[1].strip() or None, state=PENDING, **values)
			logging.info(f"{interaction.user.name} edited ability {ability.id} in {interaction.guild.name}")
			await self._submit(form_interaction, updated, created=False)

		await interaction.response.send_modal(self._form(new_name or ability.name, ability, described))

	# == passives ==

	# ============================================================
	@app_commands.command(name="passive", description="Builds a passive (always on, costs AP every turn); staff "
	                                                  "review it")
	@app_commands.choices(kind=KIND_CHOICES, tier=PASSIVE_TIER_CHOICES)
	@app_commands.autocomplete(effect1=_passive_effects, effect2=_passive_effects, effect3=_passive_effects,
	                           target=_targets, school=_schools)
	@app_commands.describe(**PASSIVE_HELP)
	async def passive(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100], kind: Choice[str],
	                  tier: Choice[str], effect1: str, effect2: str = None, effect3: str = None, target: str = None,
	                  stack_limit: app_commands.Range[int, 1, Passives.STACK_LIMIT_MAX] = None, school: str = None) :
		"""
		Builds a passive: always on, never used on a turn, built from passive effects (browse them with
		/ability effects passive:True). It lowers the character's AP every turn, for good, by the cost of its effects
		(one more each at Strong), and nobody can drop below 3 AP this way.

		- `kind`: an ability passive takes physical effects and 2 of a character's 3 ability slots; a spell passive
		  takes magic effects, one spell slot of its tier and a `school`.
		- `tier`: Weak (+1, one effect), Normal (+2, two effects) or Strong (+3, three effects).
		- `target`: for effects you aim, like Specialist or Resilient: a damage type, or melee, ranged, magic,
		  physical or any.
		- `stack_limit`: for stacks effects, how many stacks it can hold (1 to 30).
		"""
		problem = AbilityFlow.creation_problem(interaction.guild_id, interaction.user.guild_permissions.manage_messages)
		if problem :
			return await reply(interaction, problem)
		if AbilityTransactions().find(interaction.guild_id, name.strip()) is not None :
			return await reply(interaction, f"There already is an ability called {name}.")
		school_record = AbilityTransactions().find_school(interaction.guild_id, school) if school else None
		values, problem = AbilityFlow.check_passive(interaction.guild_id, kind.value, tier.value,
		                                            [effect1, effect2, effect3], target, stack_limit, school_record)
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

		await interaction.response.send_modal(self._form(name, None, described))

	# ============================================================
	@app_commands.command(name="passive_edit", description="Changes one of your passives (or turns a blank ability "
	                                                       "into one); it goes back to review")
	@app_commands.choices(tier=PASSIVE_TIER_CHOICES)
	@app_commands.autocomplete(name=_abilities, effect1=_passive_effects, effect2=_passive_effects,
	                           effect3=_passive_effects, target=_targets, school=_schools)
	@app_commands.describe(**PASSIVE_EDIT_HELP)
	async def passive_edit(self, interaction: discord.Interaction, name: str,
	                       new_name: app_commands.Range[str, 1, 100] = None, tier: Choice[str] = None,
	                       effect1: str = None, effect2: str = None, effect3: str = None, target: str = None,
	                       stack_limit: app_commands.Range[int, 0, Passives.STACK_LIMIT_MAX] = None,
	                       school: str = None) :
		"""
		Changes a passive you created (staff can change any), or turns a blank ability from an old sheet answer into a
		passive. Options you leave out stay as they are; giving any effect replaces the effect list. Type `none` as
		`target` to clear it, and set `stack_limit` to 0 to go back to the tier's. It goes back to staff for review
		and doesn't work in fights until it is approved again.
		"""
		ability = AbilityTransactions().find(interaction.guild_id, name)
		problem = self._may_edit(interaction, ability, name)
		if problem :
			return await reply(interaction, problem)
		if ability.activation != PASSIVE and ability.state != DRAFT :
			return await reply(interaction, f"{ability.name} is an active ability; change it with /ability edit.")
		problem = self._new_name_problem(interaction, ability, new_name)
		if problem :
			return await reply(interaction, problem)
		current_target, current_limit = AbilityRules.options(ability.effects)
		picked = [effect1, effect2, effect3]
		names = picked if any(picked) else AbilityRules.keys(ability.effects)
		chosen_target = current_target if target is None else (None if target.strip().lower() in ("none", "-")
		                                                       else target)
		limit = current_limit if stack_limit is None else (stack_limit or None)
		tier_value = value_of(tier) or (ability.tier if ability.tier in Passives.TIERS else Passives.WEAK)
		school_record = AbilityTransactions().find_school(interaction.guild_id, school) if school else \
			AbilityTransactions().school(ability.school_id)
		values, problem = AbilityFlow.check_passive(interaction.guild_id, ability.kind, tier_value, names,
		                                            chosen_target, limit, school_record)
		if problem :
			return await reply(interaction, problem)

		async def described(form_interaction: discord.Interaction, fields: list[str]) :
			await form_interaction.response.defer(ephemeral=True)
			updated = AbilityTransactions().update(ability.id, name=(new_name or ability.name).strip(),
			                                       description=fields[0].strip() or None,
			                                       flavor=fields[1].strip() or None, state=PENDING, **values)
			logging.info(f"{interaction.user.name} edited passive ability {ability.id} in {interaction.guild.name}")
			await self._submit(form_interaction, updated, created=False)

		await interaction.response.send_modal(self._form(new_name or ability.name, ability, described))

	# == browsing ==

	# ============================================================
	@app_commands.command(name="effects", description="Browses the effects spells and abilities are built from")
	@app_commands.choices(realm=REALM_CHOICES)
	@app_commands.autocomplete(category=_categories)
	@app_commands.describe(realm="Magic effects (spells) or physical ones (abilities)",
	                       category="Only one category; leave it out to see the categories",
	                       search="A word to look for, like fire, stun or heal",
	                       passive="Show passive effects instead of active ones")
	async def effects(self, interaction: discord.Interaction, realm: Choice[str] = None, category: str = None,
	                  search: str = None, passive: bool = False) :
		"""
		Browses the effect catalog. Without a category or search it lists the categories and how many effects each
		has; pick one, or search for a word, to see the effects with their AP cost, the lowest tier that can use them
		and what they do. Spells take magic effects, abilities physical ones.
		"""
		catalog = PassiveCatalog if passive else EffectCatalog
		realm_value = value_of(realm)
		if category and category not in catalog.CATEGORIES :
			return await reply(interaction, f"There is no category called {category}.")
		title = "Passive effects" if passive else "Effects"
		if not category and not search :
			lines = []
			for name in catalog.CATEGORIES :
				found = catalog.search("", realm_value, name)
				if found :
					magic = len([effect for effect in found if effect.realm == Effects.MAGIC])
					lines.append(f"**{name}**: {len(found)} ({magic} magic, {len(found) - magic} physical)")
			text = "\n".join(lines) + "\n\nPick a `category` or `search` for a word to see the effects."
			return await interaction.response.send_message(embed=discord.Embed(
				title=title, description=text[:EMBED_LIMIT], color=discord.Color.purple()), ephemeral=True)
		found = catalog.search(search or "", realm_value, category)
		lines = []
		for effect in found :
			tier = f" · {effect.tier.capitalize()}+" if effect.tier not in (Effects.CANTRIP, Passives.WEAK) else ""
			cost = f"-{effect.cost} AP/turn" if passive else f"{effect.cost:+d} AP"
			lines.append(f"**{effect.name}** · {effect.realm} · {cost}{tier}: {effect.text}")
		text, shown = "", 0
		for line in lines :
			if len(text) + len(line) + 1 > EMBED_LIMIT - 80 :
				break
			text += line + "\n"
			shown += 1
		if shown < len(lines) :
			text += f"\n…and {len(lines) - shown} more; narrow it with `category` or `search`."
		embed = discord.Embed(title=f"{title}: {category or search}"[:256], description=text or "Nothing matches.",
		                      color=discord.Color.purple())
		await interaction.response.send_message(embed=embed, ephemeral=True)

	# ============================================================
	@app_commands.command(name="list", description="Lists the server's abilities and spells")
	async def list_abilities(self, interaction: discord.Interaction, mine: bool = False) :
		"""
		Lists the approved abilities and spells anyone can learn (tags on their forum posts can restrict them).
		With `mine`, lists the ones you created, whatever their review state (blank ones need effects first).
		"""
		abilities = AbilityTransactions().get_all(interaction.guild_id)
		if mine :
			abilities = [ability for ability in abilities if ability.creator_uid == interaction.user.id]
		else :
			abilities = [ability for ability in abilities if ability.state == APPROVED]
		lines = [f"**{ability.name}**: {AbilityFlow.short(ability)}"
		         + (f" · *{'blank' if ability.state == DRAFT else ability.state}*" if ability.state != APPROVED else "")
		         for ability in abilities]
		text = "\n".join(lines)[:EMBED_LIMIT] or "No abilities yet. Build one with /ability create."
		await interaction.response.send_message(embed=discord.Embed(title="Abilities", description=text,
		                                                            color=discord.Color.purple()), ephemeral=True)

	# ============================================================
	@app_commands.command(name="view", description="Shows an ability or spell")
	@app_commands.autocomplete(name=_abilities)
	async def view(self, interaction: discord.Interaction, name: str) :
		"""
		Shows an ability: its rules (every effect and what it does), school, description and flavor.
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
		1 Strong; a passive spell takes a slot of its tier); other characters have 3 ability slots, where an active
		ability takes 1 and a passive 2 (at most 1 Strong). A character can't have both spells and abilities, unless
		an event granted them. Legendary characters get one extra slot. An active ability can't cost more AP than the
		character has, and passives can't leave it with fewer than 3 AP.
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
		Removes an ability from your character, freeing its slot (and the AP a passive took). Event abilities can only
		be taken away by a GM.
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

	# == old sheets ==

	# ============================================================
	@app_commands.command(name="import_sheets", description="Turns old free-text sheet abilities into blank "
	                                                        "abilities (staff)")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def import_sheets(self, interaction: discord.Interaction) :
		"""
		Abilities, spells and weapons can only come from the bot's own systems now. This removes the free-text
		Magics, Abilities, Weapon proficiencies, Shield and Magic school questions from the server's sheet, and goes
		through every character's old answers:

		- each spell or ability written there becomes a blank ability with that name, linked to the character. It
		  does nothing in fights until its owner builds it with `/ability edit` (or `/ability passive_edit`) and staff
		  approve it;
		- weapons written there can't be made automatically, so the owner is told to get them from the shop or a GM
		  and set their proficiency with `/gear proficiency`.

		Owners get a DM listing what was found. The old answers stay saved but no longer show on cards or posts.
		Running it again only handles answers it hasn't seen.
		"""
		await interaction.response.defer(ephemeral=True)
		report = await SheetAbilities.convert(self.bot, interaction.guild)
		await interaction.followup.send(report.text()[:2000], ephemeral=True)


async def setup(bot) :
	await bot.add_cog(Ability(bot))
