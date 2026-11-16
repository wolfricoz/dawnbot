"""Abilities and magic schools outside fights: creating them, staff review, the post in the ability forum, the
standard schools, and learning and forgetting abilities."""
import logging

import discord

from classes.characters.Access import Access, Requirement
from classes.characters.CharacterFlow import CharacterFlow
from classes.combat import Abilities as AbilityRules, EffectCatalog, Effects, PassiveCatalog, Passives, Rules
from classes.combat.DamageTypes import DamageTypes
from classes.kernel.ConfigData import ConfigData
from database.database import Abilities, Characters, MagicSchools
from database.transactions.AbilityTransactions import ACTIVE, APPROVED, AbilityTransactions, DENIED, PASSIVE, PENDING
from database.transactions.TagRuleTransactions import TagRuleTransactions
from resources.configs.ConfigMapping import ConfigMapping

THREAD_NAME_LIMIT = 100
MESSAGE_LIMIT = 2000
TEXT_LIMIT = 1000


class AbilityFlow :

	# == who may create ==

	# ============================================================
	@staticmethod
	def creation_problem(guild_id: int, staff: bool) -> str | None :
		mode = str(ConfigData().get_key(guild_id, ConfigMapping.ABILITY_CREATION) or "everyone").lower()
		if mode == "off" :
			return "Creating abilities and schools is turned off on this server."
		if mode == "staff" and not staff :
			return "Only staff can create abilities and schools on this server."
		return None

	# == schools ==

	# ============================================================
	@staticmethod
	def ensure_schools(guild_id: int) -> None :
		"""Gives a server the standard schools the first time its schools are used."""
		transactions = AbilityTransactions()
		if any(school.standard for school in transactions.schools(guild_id)) :
			return
		for name, stat, description in AbilityRules.STANDARD_SCHOOLS :
			if transactions.find_school(guild_id, name) is None :
				transactions.add_school(guild_id, name, casting_stat=stat, description=description, state=APPROVED,
				                        standard=True)

	# ============================================================
	@staticmethod
	def schools(guild_id: int, approved_only: bool = True) -> list[MagicSchools] :
		AbilityFlow.ensure_schools(guild_id)
		return AbilityTransactions().schools(guild_id, [APPROVED] if approved_only else None)

	# == abilities ==

	# ============================================================
	@staticmethod
	def find_effects(names: list[str | None], passive: bool) -> tuple[list[Effects.Effect], str | None] :
		"""Catalog effects by key or name (empty options left out), or the first name that isn't one."""
		catalog = PassiveCatalog if passive else EffectCatalog
		found = []
		for name in names :
			if not name :
				continue
			effect = catalog.find(name)
			if effect is None :
				kind = "passive effect" if passive else "effect"
				return [], f"There is no {kind} called {name}. See /ability effects."
			found.append(effect)
		return found, None

	# ============================================================
	@staticmethod
	def check(guild_id: int, kind: str, tier: str, effect_names: list[str | None], stat: str | None,
	          damage_type: str | None, school: MagicSchools | None) -> tuple[dict | None, str | None] :
		"""Checks an active ability's parts. @return: the values to store (stat, type name and effects corrected), or
		the problem."""
		if kind == AbilityRules.SPELL :
			if school is None or school.state != APPROVED :
				return None, "A spell needs an approved magic school (see /school list)."
			stat = school.casting_stat
		if stat not in Rules.STATS :
			return None, "Pick the stat the ability uses."
		effects, problem = AbilityFlow.find_effects(effect_names, passive=False)
		if problem :
			return None, problem
		problem = AbilityRules.check_active(kind, tier, effects, school.casting_stat if school else None, stat)
		if problem :
			return None, problem
		names = DamageTypes.names(guild_id)
		typeless = [effect.name for effect in effects
		            if effect.mechanic in (Effects.ATTACK, Effects.BLAST, Effects.COMPANION)
		            and not effect.params.get("type")]
		if damage_type :
			matched = next((name for name in names if name.lower() == damage_type.lower()), None)
			if matched is None :
				return None, "Pick one of the server's damage types (see /damagetype list)."
			damage_type = matched
		elif typeless :
			return None, f"{', '.join(typeless)} takes the ability's damage type; pick one with damage_type."
		return {"kind" : kind, "tier" : tier, "stat" : stat, "damage_type" : damage_type,
		        "school_id" : school.id if school else None, "effects" : AbilityRules.store(effects),
		        "activation" : ACTIVE}, None

	# ============================================================
	@staticmethod
	def check_passive(guild_id: int, kind: str, tier: str, effect_names: list[str | None], target: str | None,
	                  limit: int | None, school: MagicSchools | None = None) -> tuple[dict | None, str | None] :
		"""Checks a passive's parts. @return: the values to store, or the problem."""
		if kind == AbilityRules.SPELL and (school is None or school.state != APPROVED) :
			return None, "A passive spell needs an approved magic school (see /school list)."
		effects, problem = AbilityFlow.find_effects(effect_names, passive=True)
		if problem :
			return None, problem
		names = DamageTypes.names(guild_id)
		target, problem = Passives.check(kind, tier, effects, target, limit, names)
		if problem :
			return None, problem
		is_type = bool(target) and target.lower() in {name.lower() for name in names}
		return {"kind" : kind, "tier" : tier, "stat" : school.casting_stat if school else "endurance",
		        "damage_type" : target if is_type else None, "school_id" : school.id if school else None,
		        "effects" : AbilityRules.store(effects, target, limit), "activation" : PASSIVE}, None

	# ============================================================
	@staticmethod
	def summary(ability: Abilities) -> str :
		return AbilityRules.summary(ability.kind, ability.tier, ability.stat, ability.effects, ability.damage_type,
		                            ability.activation == PASSIVE)

	# ============================================================
	@staticmethod
	def short(ability: Abilities) -> str :
		return AbilityRules.short(ability.kind, ability.tier, ability.effects, ability.activation == PASSIVE)

	# ============================================================
	@staticmethod
	def embed(ability: Abilities) -> discord.Embed :
		embed = discord.Embed(title=ability.name[:256], description=(ability.description or "")[:4000],
		                      color=discord.Color.purple())
		embed.add_field(name="Rules", value=AbilityFlow.summary(ability)[:1024], inline=False)
		embed.add_field(name="Realm", value="Magic" if ability.kind == AbilityRules.SPELL else "Physical")
		school = AbilityTransactions().school(ability.school_id)
		if school is not None :
			embed.add_field(name="School", value=school.name)
		if ability.flavor :
			embed.add_field(name="Flavor (settled by the GM)", value=ability.flavor[:1024], inline=False)
		if ability.creator_uid :
			embed.add_field(name="Created by", value=f"<@{ability.creator_uid}>")
		if ability.state != APPROVED :
			embed.set_footer(text=ability.state.capitalize())
		return embed

	# ============================================================
	@staticmethod
	def school_embed(school: MagicSchools) -> discord.Embed :
		embed = discord.Embed(title=school.name[:256], description=(school.description or "")[:4000],
		                      color=discord.Color.dark_purple())
		embed.add_field(name="Casting stat", value=school.casting_stat.capitalize())
		embed.add_field(name="Kind", value="Standard" if school.standard else "Player-made")
		if school.creator_uid :
			embed.add_field(name="Created by", value=f"<@{school.creator_uid}>")
		if school.state != APPROVED :
			embed.set_footer(text=school.state.capitalize())
		return embed

	# ============================================================
	@staticmethod
	def requirements(ability: Abilities) -> list[Requirement] :
		return [Requirement(rule.kind, rule.value) for rule in TagRuleTransactions().for_tags(ability.tag_ids or [])]

	# ============================================================
	@staticmethod
	def learn_problem(character: Characters, ability: Abilities, access: Access | None) -> str | None :
		"""Why the character can't learn the ability, or None."""
		if ability.guild_id != character.guild_id :
			return "That ability is not from this server."
		if ability.state != APPROVED :
			return f"{ability.name} has not been approved yet."
		if access is not None :
			# Reputation tags on the ability's post read this character's standing.
			locked = access.for_character(character.id).check(AbilityFlow.requirements(ability))
			if locked :
				return f"{ability.name} {locked}."
		known = AbilityTransactions().known(character.id)
		if any(other.id == ability.id for _, other in known) :
			return f"{character.name} already knows {ability.name}."
		problem = AbilityRules.check_learn([(other.kind, other.tier, link.event, other.activation == PASSIVE)
		                                    for link, other in known], ability.kind, ability.tier,
		                                   bool(character.legendary), ability.activation == PASSIVE)
		if problem :
			return problem
		return AbilityFlow.ap_problem(character, ability, [other for _, other in known])

	# ============================================================
	@staticmethod
	def missing_weapons(character: Characters, ability: Abilities) -> list[str] :
		"""The weapons an ability's techniques need that the character doesn't own (fists always count)."""
		from classes.gear.Gear import Gear, WEAPON

		needs = Effects.requirements(AbilityRules.active_effects(ability.effects))
		if not needs :
			return []
		owned = [dict(Rules.UNARMED)]
		for entry, item in Gear.inventory(character.id) :
			if entry.kind == WEAPON :
				owned.append(Rules.normalise_weapon(item.combat if item is not None else {}) | {"name" : entry.name})
		return [Rules.needs_label(need) for need in needs if not any(Rules.meets(weapon, need) for weapon in owned)]

	# ============================================================
	@staticmethod
	def character_ap(character: Characters, known: list[Abilities]) -> int :
		"""The AP the character has each turn after its approved passives take theirs."""
		special = {stat : int(getattr(character, stat) or 0) for stat in Rules.STATS}
		penalty = sum(Passives.ap_cost(other.tier, AbilityRules.passive_effects(other.effects)) for other in known
		              if other.activation == PASSIVE and other.state == APPROVED)
		return Rules.ap_max(special) - penalty

	# ============================================================
	@staticmethod
	def ap_problem(character: Characters, ability: Abilities, known: list[Abilities]) -> str | None :
		"""Why the character's AP can't carry the ability: an active one it could never pay for, or a passive that
		would leave it with fewer than Passives.AP_FLOOR AP."""
		have = AbilityFlow.character_ap(character, known)
		if ability.activation == PASSIVE :
			cost = Passives.ap_cost(ability.tier, AbilityRules.passive_effects(ability.effects))
			if have - cost < Passives.AP_FLOOR :
				return (f"{ability.name} takes {cost} AP every turn, which would leave {character.name} with "
				        f"{have - cost} (at least {Passives.AP_FLOOR} must remain).")
			return None
		cost = AbilityRules.ap(ability.tier, ability.effects)
		if cost > have :
			return f"{ability.name} costs {cost} AP and {character.name} only has {have} AP a turn."
		return None

	# == review ==

	# ============================================================
	@staticmethod
	async def post_review(bot: discord.Client, record: Abilities | MagicSchools) -> bool :
		from views.combat.AbilityReviewButtons import AbilityReviewButtons

		guild = bot.get_guild(record.guild_id)
		if guild is None :
			return False
		channel = await ConfigData().get_channel(guild, ConfigMapping.CHARACTER_REVIEW)
		if channel is None :
			return False
		school = isinstance(record, MagicSchools)
		kind = "magic school" if school else record.kind
		embed = AbilityFlow.school_embed(record) if school else AbilityFlow.embed(record)
		try :
			await channel.send(embed=embed)
			card = await channel.send(f"<@{record.creator_uid}> submitted the {kind} **{record.name}** for review.",
			                          view=AbilityReviewButtons(), allowed_mentions=discord.AllowedMentions.none())
		except discord.HTTPException as e :
			logging.warning(f"Could not post the review of {kind} {record.id} in {guild.name}: {e}")
			return False
		if school :
			AbilityTransactions().update_school(record.id, review_message_id=card.id)
		else :
			AbilityTransactions().update(record.id, review_message_id=card.id)
		return True

	# ============================================================
	@staticmethod
	async def decide(interaction: discord.Interaction, approve: bool, reason: str | None = None) -> None :
		if not interaction.response.is_done() :
			await interaction.response.defer()
		transactions = AbilityTransactions()
		record = transactions.get_by_review_message(interaction.message.id)
		school = record is None
		if school :
			record = transactions.school_by_review_message(interaction.message.id)
		if record is None or record.state != PENDING :
			await interaction.message.edit(view=None)
			return await interaction.followup.send("This review is no longer open.", ephemeral=True)
		kind = "magic school" if school else record.kind
		update = transactions.update_school if school else transactions.update
		notes = []
		if approve :
			record = update(record.id, state=APPROVED, review_message_id=None)
			verdict = f"✅ Approved by {interaction.user.mention}"
			dm = f"Your {kind} **{record.name}** on {interaction.guild.name} was approved."
			if not school and not await AbilityFlow.sync_post(interaction.client, record) \
					and ConfigData().get_int(record.guild_id, ConfigMapping.ABILITY_FORUM) is not None :
				notes.append("I could not post the ability in the ability forum; check that I can post there.")
		else :
			record = update(record.id, state=DENIED, review_message_id=None)
			verdict = f"❌ Denied by {interaction.user.mention}: {reason}"
			dm = (f"Your {kind} **{record.name}** on {interaction.guild.name} was not approved.\n**Reason:** {reason}\n"
			      + ("You can change it with `/ability edit`, which sends it back for review." if not school else ""))
		if record.creator_uid :
			try :
				user = interaction.guild.get_member(record.creator_uid) or \
				       await interaction.client.fetch_user(record.creator_uid)
			except discord.HTTPException :
				user = None
			if user is None or not await CharacterFlow.send_dm(user, dm) :
				notes.append(f"I could not DM <@{record.creator_uid}>, so please let them know.")
		await interaction.message.edit(content=f"{interaction.message.content}\n{verdict}"[:MESSAGE_LIMIT], view=None,
		                               allowed_mentions=discord.AllowedMentions.none())
		if notes :
			await interaction.followup.send("\n".join(notes), ephemeral=True)

	# == the ability forum ==

	# ============================================================
	@staticmethod
	async def sync_post(bot: discord.Client, ability: Abilities) -> bool :
		"""Creates or updates the ability's post in ABILITY_FORUM. False when there is none or posting failed."""
		guild = bot.get_guild(ability.guild_id)
		if guild is None :
			return False
		embed = AbilityFlow.embed(ability)
		try :
			if ability.forum_message_id :
				target = None
				if ability.forum_thread_id :
					target = guild.get_channel_or_thread(ability.forum_thread_id)
					if target is None :
						try :
							target = await guild.fetch_channel(ability.forum_thread_id)
						except discord.HTTPException :
							target = None
				else :
					target = await ConfigData().get_channel(guild, ConfigMapping.ABILITY_FORUM, optional=True)
				if target is not None :
					try :
						await (await target.fetch_message(ability.forum_message_id)).edit(embed=embed)
						return True
					except discord.NotFound :
						pass
			channel = await ConfigData().get_channel(guild, ConfigMapping.ABILITY_FORUM, optional=True)
			if channel is None :
				return False
			if isinstance(channel, discord.ForumChannel) :
				created = await channel.create_thread(name=ability.name[:THREAD_NAME_LIMIT], embed=embed)
				AbilityTransactions().update(ability.id, forum_thread_id=created.thread.id,
				                             forum_message_id=created.message.id,
				                             tag_ids=[tag.id for tag in created.thread.applied_tags])
			else :
				message = await channel.send(embed=embed)
				AbilityTransactions().update(ability.id, forum_thread_id=None, forum_message_id=message.id)
			return True
		except discord.HTTPException as e :
			logging.warning(f"Posting ability {ability.id} in {guild.name} failed: {e}")
			return False
