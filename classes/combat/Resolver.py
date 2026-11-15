"""Resolving abilities in a fight: who they can aim at, paying for them, and what each catalog effect does to its
target. A mixin of the Engine (classes/combat/Engine.py), so it uses the engine's dice, saves, damage and conditions.

An ability (as Loadout.ability_data builds it) carries its effects copied from the catalog, its AP, uses, how many
targets it reaches and who it aims at. Effects aimed at the target run once per target, effects on the user once, and
the drawbacks hit the user at the end. See classes/combat/Effects.py for what each mechanic does.
"""
from classes.combat import Conditions as C
from classes.combat import Effects as FX
from classes.combat import Passives as P, Rules
from classes.combat.DamageTypes import ALWAYS, CLEANSE as CLEANSE_KIND, IGNORE_DT, RESTORATION, STRONG_HIT
from classes.combat.State import Combatant, DEAD, FLED, STANDING

CONFUSED_CHANCE = 50
CONCENTRATION_DC = 10


class Resolver :

	# == choosing targets ==

	# ============================================================
	def targetable(self, actor: Combatant, candidates: list[Combatant], offensive: bool) -> list[Combatant] :
		"""Candidates the actor may aim at: nobody banished, nobody who charmed it, and only its taunter while that one
		stands (for attacks and offensive abilities)."""
		found = [candidate for candidate in candidates
		         if candidate.id == actor.id or not C.untargetable(candidate.conditions)]
		if not offensive :
			return found
		charmer = C.source(actor.conditions, C.CHARMED)
		found = [candidate for candidate in found if candidate.id != charmer]
		taunter = C.source(actor.conditions, C.TAUNTED)
		if taunter is not None and any(candidate.id == taunter for candidate in found) :
			found = [candidate for candidate in found if candidate.id == taunter]
		return found

	# ============================================================
	def target_problem(self, actor: Combatant, target: Combatant) -> str | None :
		"""Why the actor can't attack this enemy, or None."""
		if C.untargetable(target.conditions) :
			return f"{target.name} is banished and can't be reached."
		if C.source(actor.conditions, C.CHARMED) == target.id :
			return f"{actor.name} is charmed by {target.name} and can't bring themself to attack."
		taunter = C.source(actor.conditions, C.TAUNTED)
		if taunter is not None and taunter != target.id :
			other = self.fight.combatant(taunter)
			if other is not None and other.standing :
				return f"{actor.name} is taunted and has to go after {other.name}."
		return None

	# ============================================================
	def confusion(self, actor: Combatant, target: Combatant) -> Combatant :
		"""A confused actor's attack or offensive ability goes to a random combatant half of the time."""
		if not C.has(actor.conditions, C.CONFUSED) or self.rng.randint(1, 100) > CONFUSED_CHANCE :
			return target
		others = [other for other in self.fight.combatants
		          if other.standing and other.id != actor.id and not C.untargetable(other.conditions)]
		if not others :
			return target
		chosen = self.rng.choice(others)
		if chosen.id != target.id :
			self.say(f"-# {actor.name} is confused and turns on **{chosen.name}** instead.")
		return chosen

	# == abilities ==

	# ============================================================
	@staticmethod
	def ability_ap(ability: dict) -> int :
		return int(ability.get("ap") or FX.MIN_AP)

	# ============================================================
	@staticmethod
	def ability_aim(ability: dict) -> str :
		return ability.get("aim") or FX.ENEMY

	# ============================================================
	def ability_uses_left(self, actor: Combatant, ability: dict) -> int | None :
		limit = ability.get("uses", FX.uses(ability["tier"]))
		if limit is None :
			return None
		return int(limit) - int(actor.ability_uses.get(str(ability["id"]), 0))

	# ============================================================
	def ability_targets(self, actor: Combatant, ability: dict) -> list[Combatant] :
		"""Who an ability can be aimed at: standing enemies, allies (healing and reviving also reach downed ones), or
		only the user."""
		aim = self.ability_aim(ability)
		if aim == FX.SELF :
			return [actor]
		if aim == FX.ENEMY :
			return self.targetable(actor, self.fight.enemies(actor), offensive=True)
		mechanics = {effect.get("mechanic") for effect in ability.get("effects") or []}
		reaches_down = bool(mechanics & {FX.HEAL, FX.REVIVE})
		allies = [ally for ally in self.fight.allies(actor) if ally.standing or (reaches_down and ally.down)]
		return self.targetable(actor, allies, offensive=False)

	# ============================================================
	def weapon_for(self, actor: Combatant, needs: str | None) -> dict | None :
		"""The best weapon the actor can use that meets a requirement (the highest proficiency), or None."""
		if not needs :
			return None
		matching = [weapon for weapon in self.usable_weapons(actor) if Rules.meets(weapon, needs)]
		if not matching :
			return None
		return max(matching, key=lambda weapon : Rules.proficiency_bonus(weapon.get("proficiency")))

	# ============================================================
	def weapon_problem(self, actor: Combatant, ability: dict) -> str | None :
		"""Why the actor can't use an ability for lack of a weapon (weapon techniques need one), or None."""
		missing = [needs for needs in FX.requirements(ability.get("effects") or [])
		           if self.weapon_for(actor, needs) is None]
		if not missing :
			return None
		labels = " and ".join(Rules.needs_label(needs) for needs in missing)
		if C.has(actor.conditions, C.DISARMED) :
			return f"{ability['name']} needs {labels}, and {actor.name} is disarmed."
		return f"{ability['name']} needs {labels}, and {actor.name} doesn't carry one."

	# ============================================================
	def use_ability(self, actor: Combatant, ability_id, target_ids: list) -> object :
		self.require_turn(actor)
		ability = actor.ability(ability_id)
		if ability is None :
			from classes.combat.Engine import CombatError
			raise CombatError(f"{actor.name} doesn't know that ability.")
		if self.ability_aim(ability) == FX.SELF :
			targets = [actor]
		else :
			limit = int(ability.get("targets") or 1)
			ids = list(dict.fromkeys(target_ids or []))[:limit]
			allowed = {target.id : target for target in self.ability_targets(actor, ability)}
			targets = [allowed[target_id] for target_id in ids if target_id in allowed]
		self._use_ability(actor, ability, targets)
		return self.finish_action(actor)

	# ============================================================
	def resolve_and_use(self, actor: Combatant, ability: dict, targets: Combatant | list[Combatant]) -> None :
		"""Uses an ability on one target or several (up to its limit) without the turn checks (automatic moves)."""
		targets = targets if isinstance(targets, list) else [targets]
		self._use_ability(actor, ability, targets[:max(1, int(ability.get("targets") or 1))])
		self.check_victory()

	# ============================================================
	def _use_ability(self, actor: Combatant, ability: dict, targets: list[Combatant]) -> None :
		from classes.combat.Engine import CombatError

		if C.has(actor.conditions, C.SILENCED) :
			raise CombatError(f"{actor.name} is silenced and can't use abilities.")
		problem = self.weapon_problem(actor, ability)
		if problem :
			raise CombatError(problem)
		left = self.ability_uses_left(actor, ability)
		if left is not None and left <= 0 :
			raise CombatError(f"{ability['name']} has no uses left this fight.")
		if not targets :
			raise CombatError("Pick a target the ability can reach.")
		self._spend(actor, self.ability_ap(ability))
		actor.ability_uses[str(ability["id"])] = int(actor.ability_uses.get(str(ability["id"]), 0)) + 1
		self.say(f"✨ **{actor.name}** uses **{ability['name']}**.")
		focus = None
		if ability.get("concentration") :
			self.end_concentration(actor, f"{actor.name} turns to {ability['name']}")
			focus = {"ability" : ability["id"], "name" : ability["name"], "applied" : []}
		self._focus = focus
		aim = self.ability_aim(ability)
		if aim == FX.ENEMY :
			C.remove(actor.conditions, C.HIDDEN)
		effects = ability.get("effects") or []
		landed = False
		resolved = False
		for target in targets :
			if aim == FX.ENEMY :
				target = self.confusion(actor, target)
			for effect in effects :
				if effect.get("aim") in (FX.ENEMY, FX.ALLY) and target.in_fight :
					resolved = True
					landed = self.resolve_effect(actor, ability, effect, target) or landed
		for effect in effects :
			if effect.get("aim") == FX.SELF and actor.in_fight :
				self.resolve_effect(actor, ability, effect, actor)
		self._focus = None
		if focus is not None and focus["applied"] and actor.standing :
			actor.stats["concentration"] = focus
			self.say(f"-# {actor.name} concentrates on {ability['name']}.")
		self.drawbacks(actor, ability, landed or not resolved or aim != FX.ENEMY)

	# == concentration ==

	# ============================================================
	def track(self, target: Combatant, name: str) -> None :
		"""Remembers a condition the ability being used put on someone, while it needs concentration."""
		focus = getattr(self, "_focus", None)
		if focus is not None :
			focus["applied"].append([target.id, name])

	# ============================================================
	def end_concentration(self, combatant: Combatant, reason: str | None = None) -> None :
		"""Ends the combatant's concentration: what that spell keeps going stops."""
		focus = combatant.stats.pop("concentration", None)
		if not focus :
			return
		ended = []
		for target_id, name in focus.get("applied") or [] :
			target = self.fight.combatant(target_id)
			if target is not None and C.remove(target.conditions, name) :
				C.grant_immunity(target.conditions, name)
				ended.append(f"{target.name} is no longer {C.label(name).lower()}")
		why = f" ({reason})" if reason else ""
		self.say(f"-# {combatant.name}'s concentration on {focus.get('name')} ends{why}"
		         + (f": {'; '.join(ended)}." if ended else "."))

	# ============================================================
	def concentration_check(self, combatant: Combatant, damage: int) -> None :
		"""Damage makes a concentrating caster save (END) against 10 or half the damage; failing, or going down, ends
		it."""
		if not combatant.stats.get("concentration") :
			return
		if not combatant.standing :
			self.end_concentration(combatant, f"{combatant.name} went down")
			return
		dc = max(CONCENTRATION_DC, damage // 2)
		save = self.saving_throw(combatant, "endurance")()
		if save < dc :
			self.end_concentration(combatant, f"END save {save} vs {dc}")

	# ============================================================
	def drawbacks(self, actor: Combatant, ability: dict, landed: bool) -> None :
		"""What the ability's drawbacks do to the user; landed is False when every roll against an enemy failed."""
		kinds = set(ability.get("drawbacks") or [])
		half = Rules.halve_dice(FX.base_dice(ability["tier"]))
		if FX.BLOOD in kinds or (FX.BACKLASH in kinds and not landed) :
			amount, rolls = Rules.roll_dice(half, rng=self.rng)
			reason = "pays in blood" if FX.BLOOD in kinds else "is hit by the backlash"
			self.say(f"-# {actor.name} {reason}: {amount} ({half} {rolls}).")
			self.damage(actor, amount)
		if FX.EXHAUST in kinds :
			C.add(actor.conditions, C.DRAINED, turns=2, value=FX.EXHAUST_AP)
		if FX.RECKLESS in kinds :
			C.add(actor.conditions, C.EXPOSED, turns=1)
		if FX.WEAKEN in kinds :
			C.add(actor.conditions, C.WEAKENED, turns=1)

	# == the numbers an effect uses ==

	# ============================================================
	def effect_dice(self, ability: dict, effect: dict) -> str :
		params = effect.get("params") or {}
		steps = int(params.get("steps") or 0) + int(ability.get("steps") or 0)
		return FX.shift(FX.base_dice(ability["tier"]), steps + FX.effect_steps(effect.get("mechanic"), params))

	# ============================================================
	def effect_turns(self, ability: dict, effect: dict) -> int :
		params = effect.get("params") or {}
		lingering = 1 if FX.LINGERING in (ability.get("modifiers") or []) else 0
		return max(1, FX.turns(ability["tier"]) + int(params.get("turns") or 0) + lingering)

	# ============================================================
	def ability_dc(self, actor: Combatant, ability: dict) -> int :
		precise = FX.PRECISE_BONUS if FX.PRECISE in (ability.get("modifiers") or []) else 0
		focused = 2 if C.has(actor.conditions, C.FOCUSED) else 0
		return 10 + self.mod(actor, ability.get("stat") or "intelligence") + FX.dc_bonus(ability["tier"]) + precise \
		       + focused + P.total(actor.passives, P.DC, P.DC_BONUS)

	# ============================================================
	def type_of(self, ability: dict, effect: dict) -> str | None :
		return (effect.get("params") or {}).get("type") or ability.get("damage_type")

	# ============================================================
	def resolve_effect(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		"""Applies one effect to one target. @return: True when an attack hit or a save failed (for backlash)."""
		mechanic = effect.get("mechanic")
		handler = {FX.ATTACK : self.effect_attack, FX.BLAST : self.effect_blast, FX.AFFLICT : self.effect_afflict,
		           FX.DOOM : self.effect_doom, FX.DISPEL : self.effect_dispel, FX.HEAL : self.effect_heal,
		           FX.SHIELD : self.effect_shield, FX.BOOST : self.effect_boost, FX.CLEANSE : self.effect_cleanse,
		           FX.REVIVE : self.effect_revive, FX.COMPANION : self.effect_companion,
		           FX.ESCAPE : self.effect_escape}.get(mechanic)
		if handler is None :
			return False
		if not target.standing and mechanic not in (FX.HEAL, FX.REVIVE) :
			return False
		return bool(handler(actor, ability, effect, target))

	# ============================================================
	def ability_hit(self, actor: Combatant, ability: dict, target: Combatant, accuracy: int = 0, crit: int = 0,
	                weapon: dict | None = None) :
		"""An ability's attack roll against the target. A weapon technique adds the weapon's proficiency, hit modifier
		and unmet requirements (the stat is still the ability's)."""
		stat = ability.get("stat") or "intelligence"
		magic = bool(ability.get("magic"))
		bonuses = [Rules.Bonus(Rules.STAT_SHORT.get(stat, stat), self.mod(actor, stat)),
		           Rules.Bonus("armor", int((actor.stats.get("armor") or {}).get("ability_hit_mod") or 0))]
		if accuracy :
			bonuses.append(Rules.Bonus("accuracy", accuracy))
		if weapon is not None and "to_hit" not in weapon :
			bonuses += [Rules.Bonus((weapon.get("proficiency") or Rules.AWFUL).capitalize(),
			                        Rules.proficiency_bonus(weapon.get("proficiency"))),
			            Rules.Bonus("weapon", int(weapon.get("hit_mod") or 0)),
			            Rules.Bonus("requirements", int(weapon.get("requirement_penalty") or 0))]
			crit += Rules.weapon_crit_widen(weapon)
		if FX.PRECISE in (ability.get("modifiers") or []) :
			bonuses.append(Rules.Bonus("precise", FX.PRECISE_BONUS))
		bonuses += self.situational(actor, target)
		passive_hit, _ = self.passive_roll(actor, None, magic, False)
		if passive_hit :
			bonuses.append(Rules.Bonus("passives", passive_hit))
		disadvantage = self.crippled(actor, stat) or C.has(actor.conditions, C.CURSED)
		crit_from = int(actor.stats.get("crit_min", 20)) - crit - P.total(actor.passives, P.CRIT, P.CRIT_WIDEN)
		return self.fortune(actor, lambda : Rules.roll_attack(
			bonuses, self.effective_ac(target), crit_from, int(actor.stats.get("fumble_max", 1)),
			disadvantage=disadvantage, confirm_crits=bool(actor.stats.get("confirm_crits")), rng=self.rng),
		                    lambda attack : attack.hit, lambda attack : attack.total)

	# ============================================================
	def ability_damage_bonus(self, actor: Combatant, ability: dict, type_name: str | None) -> int :
		magic = bool(ability.get("magic"))
		_, passive_damage = self.passive_roll(actor, type_name, magic, False)
		return self.mod(actor, ability.get("stat") or "intelligence") + passive_damage + self.damage_conditions(actor)

	# ============================================================
	def deal(self, actor: Combatant, target: Combatant, amount: int, type_name: str | None, magic: bool) -> int :
		"""Ability damage to a target, bounced back at the caster by a reflecting target (spells only)."""
		if magic and C.has(target.conditions, C.REFLECTING) and amount > 0 :
			C.remove(target.conditions, C.REFLECTING)
			back = max(1, amount // 2)
			self.say(f"-# {target.name} reflects {back} back at {actor.name}.")
			self.damage(actor, back, None, type_name=type_name, magic=True)
			amount -= back
		return self.damage(target, amount, actor, type_name=type_name, magic=magic)

	# ============================================================
	def type_trigger(self, type_name: str | None, strong: bool) -> dict | None :
		effect, trigger = self.effect_of(type_name)
		if effect is not None and (trigger == ALWAYS or (trigger == STRONG_HIT and strong)) :
			return effect
		return None

	# == the mechanics ==

	# ============================================================
	def effect_attack(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		params = effect.get("params") or {}
		type_name = self.type_of(ability, effect)
		magic = bool(ability.get("magic"))
		dice = self.effect_dice(ability, effect)
		landed = False
		for number in range(max(1, int(params.get("hits") or 1))) :
			if not target.standing :
				break
			label = f"{effect['name']}{f' #{number + 1}' if int(params.get('hits') or 1) > 1 else ''}"
			if C.has(target.conditions, C.EVASIVE) :
				C.remove(target.conditions, C.EVASIVE)
				self.say(f"→ {label} on {target.name}: evaded.")
				continue
			roll = self.ability_hit(actor, ability, target, int(params.get("accuracy") or 0),
			                        int(params.get("crit") or 0), self.weapon_for(actor, params.get("requires")))
			head = f"→ {label} on {target.name}: {roll.text()}"
			if roll.fumble :
				C.add(actor.conditions, C.EXPOSED, turns=1)
				self.say(f"{head} → **fumble!**")
				continue
			if not roll.hit :
				self.say(f"{head} → miss.")
				continue
			landed = True
			triggered = self.type_trigger(type_name, roll.strong)
			ignore_dt = bool(params.get("ignore_dt")) or bool(triggered and triggered.get("kind") == IGNORE_DT)
			extra = 1 if params.get("execute") and target.hp * 2 <= target.hp_max else 0
			damage = Rules.roll_damage(dice, self.ability_damage_bonus(actor, ability, type_name),
			                           self.effective_dt(target), crit=roll.crit, extra_dice=extra,
			                           ignore_dt=ignore_dt, rng=self.rng)
			verdict = "**crit!**" if roll.crit else ("strong hit" if roll.strong else "hit")
			self.say(f"{head} → {verdict} for **{damage.total}** ({damage.text()}).")
			done = self.deal(actor, target, damage.total, type_name, magic)
			if params.get("drain") and done > 0 :
				healed = self.heal(actor, max(1, done // 2))
				if healed :
					self.say(f"-# {actor.name} drains {healed} HP.")
			self.after_hit(actor, target, done, melee=False)
			if params.get("on_hit") and target.standing :
				name = params["on_hit"]
				if self.inflict(target, name, self.effect_turns(ability, effect), self.condition_amount(ability, name),
				                actor.id) :
					self.say(f"-# {target.name} is {C.label(name).lower()}.")
			if triggered :
				self.apply_type_effect(triggered, target, done, actor, type_name)
			if roll.strong :
				self.strong_hit_triggers(actor, target)
		return landed

	# ============================================================
	def save_against(self, actor: Combatant, ability: dict, target: Combatant, stat: str) -> tuple[bool, bool, str] :
		"""The target's save against the ability's DC. @return: (failed, failed by 5 or more, text)."""
		dc = self.ability_dc(actor, ability)
		save = self.fortune(target, self.saving_throw(target, stat), lambda value : value >= dc, lambda value : value)
		short = Rules.STAT_SHORT.get(stat, stat)
		return save < dc, save <= dc - Rules.STRONG_MARGIN, f"{short} save {save} vs DC {dc}"

	# ============================================================
	def effect_blast(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		params = effect.get("params") or {}
		type_name = self.type_of(ability, effect)
		magic = bool(ability.get("magic"))
		failed, strong, text = self.save_against(actor, ability, target, params.get("save") or "agility")
		dice = self.effect_dice(ability, effect)
		amount, rolls = Rules.roll_dice(dice, self.ability_damage_bonus(actor, ability, type_name), rng=self.rng)
		amount = max(1, amount - self.effective_dt(target))
		if not failed :
			amount = max(1, amount // 2)
		self.say(f"→ {effect['name']} on {target.name}: {text} → {'fails' if failed else 'half'}, **{amount}** "
		         f"({dice} {rolls}).")
		done = self.deal(actor, target, amount, type_name, magic)
		self.after_hit(actor, target, done, melee=False)
		if failed and params.get("on_fail") and target.standing :
			name = params["on_fail"]
			if self.inflict(target, name, self.effect_turns(ability, effect), self.condition_amount(ability, name),
			                actor.id) :
				self.say(f"-# {target.name} is {C.label(name).lower()}.")
		triggered = self.type_trigger(type_name, strong)
		if triggered and failed :
			self.apply_type_effect(triggered, target, done, actor, type_name)
		return failed

	# ============================================================
	def condition_amount(self, ability: dict, name: str, override: int | None = None) -> int | None :
		return FX.tier_amount(ability["tier"], name, override)

	# ============================================================
	def effect_afflict(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		params = effect.get("params") or {}
		name = params.get("condition")
		failed, strong, text = self.save_against(actor, ability, target, params.get("save") or C.save_stat(name))
		if not failed :
			self.say(f"→ {effect['name']}: {target.name} resists ({text}).")
			return False
		if self.inflict(target, name, self.effect_turns(ability, effect),
		                self.condition_amount(ability, name, params.get("amount")), actor.id) :
			self.track(target, name)
			self.say(f"→ {effect['name']}: {target.name} fails ({text}) and is {C.label(name).lower()}.")
		else :
			self.say(f"→ {effect['name']}: {target.name} fails ({text}) but shakes it off.")
		# A save failed by 5 or more is a strong hit: the ability's damage type adds its effect.
		triggered = self.type_trigger(ability.get("damage_type"), strong) if strong else None
		if triggered and triggered.get("kind") not in (IGNORE_DT, CLEANSE_KIND) :
			self.apply_type_effect(triggered, target, 0, actor, ability.get("damage_type"))
		return True

	# ============================================================
	def effect_doom(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		failed, _, text = self.save_against(actor, ability, target, "endurance")
		if not failed :
			self.say(f"→ {effect['name']}: {target.name} resists ({text}).")
			return False
		dice = self.effect_dice(ability, effect)
		amount, _ = Rules.roll_dice(dice, rng=self.rng)
		turns = self.effect_turns(ability, effect)
		if self.inflict(target, C.DOOMED, turns, amount, actor.id) :
			self.track(target, C.DOOMED)
			self.say(f"→ {effect['name']}: {target.name} fails ({text}) and is doomed: {amount} damage in "
			         f"{turns} turn{'s' if turns != 1 else ''}.")
		return True

	# ============================================================
	def effect_dispel(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		removed = [name for name in (C.dispel(target.conditions)
		                             for _ in range(int((effect.get("params") or {}).get("count") or 1))) if name]
		if removed :
			self.say(f"→ {effect['name']}: {target.name} loses {', '.join(C.label(name) for name in removed)}.")
		else :
			self.say(f"→ {effect['name']}: {target.name} has nothing to dispel.")
		return True

	# ============================================================
	def heal_amount(self, actor: Combatant, ability: dict, effect: dict) -> tuple[int, str] :
		dice = self.effect_dice(ability, effect)
		bonus = self.mod(actor, ability.get("stat") or "intelligence") + P.total(actor.passives, P.HEAL_POWER,
		                                                                         P.HEAL_BONUS)
		amount, rolls = Rules.roll_dice(dice, bonus, rng=self.rng)
		return max(1, amount), f"{dice} {rolls} {bonus:+d}"

	# ============================================================
	def effect_heal(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		params = effect.get("params") or {}
		if target.state == DEAD :
			return False
		amount, text = self.heal_amount(actor, ability, effect)
		healed = self.heal(target, amount)
		self.say(f"→ {effect['name']}: {target.name} heals {healed} ({text}).")
		type_name = self.type_of(ability, effect)
		cleansing = params.get("cleanse") or (type_name or "").lower() == RESTORATION.lower() \
		            or (self.type_trigger(type_name, True) or {}).get("kind") == CLEANSE_KIND
		if cleansing :
			removed = C.cleanse(target.conditions)
			if removed :
				self.say(f"-# {target.name} is no longer {C.label(removed).lower()}.")
		if params.get("self_cost") and target.id != actor.id :
			cost = max(1, healed // 2)
			self.say(f"-# {actor.name} pays {cost} HP.")
			self.damage(actor, cost)
		return True

	# ============================================================
	def effect_shield(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		amount, text = self.heal_amount(actor, ability, effect)
		C.add(target.conditions, C.SHIELDED, turns=self.effect_turns(ability, effect) + 1, value=amount)
		self.say(f"→ {effect['name']}: {target.name} is shielded for {amount} ({text}).")
		return True

	# ============================================================
	def effect_boost(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		params = effect.get("params") or {}
		name = params.get("condition") or C.INSPIRED
		amount = self.condition_amount(ability, name, params.get("amount"))
		extra = {}
		if name == C.RIPOSTE :
			extra["dice"] = FX.RIPOSTE_DICE[FX.tier_index(ability["tier"])]
		C.add(target.conditions, name, turns=self.effect_turns(ability, effect), value=amount, **extra)
		if target.id != actor.id or effect.get("aim") != FX.SELF :
			self.track(target, name)
		self.say(f"→ {effect['name']}: {target.name} is {C.label(name).lower()}{f' ({amount})' if amount else ''}.")
		return True

	# ============================================================
	def effect_cleanse(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		count = (effect.get("params") or {}).get("count")
		removed = []
		while count is None or len(removed) < int(count) :
			name = C.cleanse(target.conditions)
			if name is None :
				break
			removed.append(name)
		if removed :
			self.say(f"→ {effect['name']}: {target.name} is no longer "
			         f"{', '.join(C.label(name).lower() for name in removed)}.")
		else :
			self.say(f"→ {effect['name']}: nothing ails {target.name}.")
		return True

	# ============================================================
	def effect_revive(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		if not target.down or target.state == DEAD :
			self.say(f"→ {effect['name']}: {target.name} isn't downed.")
			return False
		amount, text = self.heal_amount(actor, ability, effect)
		target.hp = min(target.hp_max, max(1, amount))
		target.state = STANDING
		target.death_successes = target.death_failures = 0
		target.acted = True
		self.say(f"→ {effect['name']}: **{target.name}** is back on their feet with {target.hp} HP ({text}).")
		return True

	# ============================================================
	def effect_companion(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		dice = self.effect_dice(ability, effect)
		turns = self.effect_turns(ability, effect) + 1
		C.add(actor.conditions, C.COMPANION, turns=turns, dice=dice, type=self.type_of(ability, effect),
		      bonus=self.mod(actor, ability.get("stat") or "intelligence"), label=effect["name"])
		self.track(actor, C.COMPANION)
		self.say(f"→ {effect['name']}: a companion joins {actor.name} for {turns} turns ({dice}).")
		return True

	# ============================================================
	def effect_escape(self, actor: Combatant, ability: dict, effect: dict, target: Combatant) -> bool :
		actor.state = FLED
		actor.acted = True
		self.say(f"→ {effect['name']}: **{actor.name}** leaves the fight.")
		return True

	# == effects on other turns ==

	# ============================================================
	def companion_attack(self, combatant: Combatant) -> None :
		"""A summoned companion attacks a random enemy at the start of its owner's turn."""
		companion = C.get(combatant.conditions, C.COMPANION)
		if companion is None or not combatant.standing :
			return
		enemies = self.targetable(combatant, self.fight.enemies(combatant), offensive=False)
		if not enemies :
			return
		target = self.rng.choice(enemies)
		label = companion.get("label") or "Companion"
		roll = Rules.roll_attack([Rules.Bonus("summoner", int(companion.get("bonus") or 0))],
		                         self.effective_ac(target), rng=self.rng)
		if not roll.hit :
			self.say(f"-# {combatant.name}'s {label} attacks {target.name}: {roll.text()} → miss.")
			return
		damage = Rules.roll_damage(companion.get("dice") or "1d6", 0, self.effective_dt(target), crit=roll.crit,
		                           rng=self.rng)
		self.say(f"-# {combatant.name}'s {label} attacks {target.name}: {roll.text()} → {damage.total} "
		         f"({damage.text()}).")
		self.damage(target, damage.total, combatant, type_name=companion.get("type"))

	# ============================================================
	def after_hit(self, actor: Combatant, target: Combatant, done: int, melee: bool) -> None :
		"""After a hit lands: thorns hurt a melee attacker, lifesteal and vampiric heal the attacker."""
		if melee and actor.standing :
			thorns = C.amount(target.conditions, C.THORNS) + P.total(target.passives, P.THORNS, P.THORNS_DAMAGE)
			if thorns :
				self.say(f"-# {actor.name} takes {thorns} from {target.name}'s thorns.")
				self.damage(actor, thorns)
		if done <= 0 or not actor.standing :
			return
		heal = done // 2 if C.has(actor.conditions, C.VAMPIRIC) else 0
		for passive in P.of_type(actor.passives, P.LIFESTEAL) :
			heal += done // P.LIFESTEAL_DIVISOR[P.index(passive["tier"])]
		if heal :
			healed = self.heal(actor, heal)
			if healed :
				self.say(f"-# {actor.name} drinks {healed} HP from the wound.")

	# ============================================================
	def after_miss(self, defender: Combatant, attacker: Combatant, melee: bool) -> None :
		"""A melee attacker that misses a riposting defender takes its dice."""
		riposte = C.get(defender.conditions, C.RIPOSTE)
		if not melee or riposte is None or not defender.standing or not attacker.standing :
			return
		dice = riposte.get("dice") or "1d4"
		amount, rolls = Rules.roll_dice(dice, rng=self.rng)
		self.say(f"-# {defender.name} ripostes {attacker.name} for {amount} ({dice} {rolls}).")
		self.damage(attacker, amount, defender)
