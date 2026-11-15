"""Automatic moves: what a combatant does when its player missed the turn, or when it is an automatic NPC.

Players pick an autopilot for each fight (attack the weakest enemy, attack whoever hit them last, defend, or help and
revive allies first); NPCs have a behavior (aggressive, vengeful, random, cautious, support). Attacks use the weapon
with the best expected damage that the remaining AP pays for, and the turn ends with the AP left as AC.

NPCs also use their abilities: each usable one is scored for the moment (bringing back a downed ally, healing a badly
hurt one, control on the toughest enemy not yet under it, cleansing a controlled ally, damage, a summon, buffs on
whoever lacks them, debuffs, dispels) and the best one is used, on several targets when it reaches them. An NPC doesn't
break its own concentration while that spell still holds something. Players' autopilot sticks to weapons.
"""
from classes.combat import Conditions as C
from classes.combat import Effects as FX
from classes.combat import Items, Rules
from classes.combat.Engine import AP_REVIVE, CAUTIOUS, CombatError, DEFEND, Engine, IDLE_PING, RANDOM, \
	REVENGE, SUPPORT, VENGEFUL
from classes.combat.State import Combatant, PLAYER

CAUTIOUS_DEFEND = 0.3
CAUTIOUS_FLEE = 0.15
SUPPORT_HEAL_BELOW = 0.5
# The most actions one automatic turn takes, as a safety net.
MAX_ACTIONS = 10


class Autopilot :

	def __init__(self, engine: Engine) :
		self.engine = engine
		self.fight = engine.fight

	# ============================================================
	def take_turn(self, combatant: Combatant, idle: bool = False) -> None :
		"""Plays the combatant's whole turn and ends it. idle marks a player who missed the turn."""
		engine = self.engine
		if idle :
			combatant.idle_turns += 1
			engine.say(f"-# {combatant.name} didn't act in time; autopilot takes over.")
			if combatant.idle_turns >= IDLE_PING and combatant.id not in self.fight.idle_pinged :
				self.fight.idle_pinged.append(combatant.id)
				engine.outcome.gm_pings.append(f"{combatant.name} has missed {combatant.idle_turns} turns in a row.")
		behavior = combatant.behavior
		for _ in range(MAX_ACTIONS) :
			if not combatant.standing or combatant.acted or self.fight.state != "active" :
				break
			if not self.act(combatant, behavior) :
				break
		if combatant.standing and not combatant.acted :
			engine.end_turn(combatant, quiet=True)
		elif not combatant.standing :
			combatant.acted = True

	# ============================================================
	def act(self, combatant: Combatant, behavior: str) -> bool :
		"""Takes one action; False when the combatant should end its turn instead."""
		if behavior == DEFEND :
			return False
		if behavior == CAUTIOUS and combatant.hp_max :
			share = combatant.hp / combatant.hp_max
			if share < CAUTIOUS_FLEE :
				return self._try(lambda : self._flee(combatant))
			if share < CAUTIOUS_DEFEND :
				return False
		if behavior == SUPPORT :
			if self._support(combatant) :
				return True
		move = self.ability_move(combatant, behavior)
		if move is not None :
			ability, targets = move
			if self._try(lambda : self.engine.resolve_and_use(combatant, ability, targets)) :
				return True
		target = self.target(combatant, behavior)
		if target is None :
			return False
		weapon = self.weapon(combatant, target)
		if weapon is None :
			return False
		return self._try(lambda : self._attack(combatant, target, weapon))

	# ============================================================
	def _try(self, action) -> bool :
		try :
			action()
			return True
		except CombatError :
			return False

	# ============================================================
	def target(self, combatant: Combatant, behavior: str) -> Combatant | None :
		enemies = self.engine.targetable(combatant, self.fight.enemies(combatant), offensive=True)
		if not enemies :
			return None
		if behavior in (REVENGE, VENGEFUL) :
			attacker = self.fight.combatant(combatant.last_attacker_id)
			if attacker is not None and attacker in enemies :
				return attacker
		if behavior == RANDOM :
			return self.engine.rng.choice(enemies)
		return min(enemies, key=lambda enemy : (enemy.hp, enemy.position, enemy.id))

	# ============================================================
	def weapon(self, combatant: Combatant, target: Combatant) -> dict | None :
		"""The weapon with the best expected damage that the combatant's AP pays for."""
		options = []
		for weapon in self.engine.usable_weapons(combatant) :
			cost = self.engine.attack_cost(combatant, weapon)
			if cost > combatant.ap :
				continue
			value = Rules.expected_damage(combatant.stats, weapon, self.engine.effective_ac(target), target.dt,
			                              combatant.base)
			options.append((value / max(1, cost), value, weapon.get("key") == combatant.weapon_key, weapon))
		if not options :
			return None
		return max(options, key=lambda option : (option[0], option[1], option[2]))[3]

	# ============================================================
	def _attack(self, combatant: Combatant, target: Combatant, weapon: dict) -> None :
		engine = self.engine
		cost = engine.attack_cost(combatant, weapon)
		engine._spend(combatant, cost)
		engine.resolve_attack(combatant, engine.confusion(combatant, target), weapon)
		combatant.weapon_key = weapon.get("key")
		engine.check_victory()

	# ============================================================
	def _flee(self, combatant: Combatant) -> None :
		engine = self.engine
		dc = 10 + len(self.fight.enemies(combatant))
		roll = Rules.roll_attack([Rules.Bonus("AGI", engine.mod(combatant, "agility"))], dc, rng=engine.rng,
		                         fumble_to=0)
		combatant.ap = 0
		if roll.total >= dc :
			combatant.state = "fled"
			combatant.acted = True
			engine.say(f"🏃 **{combatant.name}** flees the fight ({roll.text('DC')}).")
			engine.check_victory()
		else :
			engine.say(f"🏃 **{combatant.name}** tries to flee but is cut off ({roll.text('DC')}).")
			engine.end_turn(combatant, quiet=True)

	# == NPC abilities ==

	# ============================================================
	def usable(self, combatant: Combatant, ability: dict) -> bool :
		"""Whether the combatant can use the ability right now (AP, uses, weapon, not silenced), and wouldn't break
		its own concentration on a spell that still holds something."""
		engine = self.engine
		left = engine.ability_uses_left(combatant, ability)
		if (left is not None and left <= 0) or engine.ability_ap(ability) > combatant.ap :
			return False
		if C.has(combatant.conditions, C.SILENCED) or engine.weapon_problem(combatant, ability) :
			return False
		if ability.get("concentration") and self.concentration_holds(combatant) :
			return False
		return True

	# ============================================================
	def concentration_holds(self, combatant: Combatant) -> bool :
		"""Whether the combatant's concentration still keeps a condition going on someone."""
		focus = combatant.stats.get("concentration") or {}
		for target_id, name in focus.get("applied") or [] :
			target = self.fight.combatant(target_id)
			if target is not None and target.in_fight and C.has(target.conditions, name) :
				return True
		return False

	# ============================================================
	def ability_move(self, combatant: Combatant, behavior: str) -> tuple[dict, list[Combatant]] | None :
		"""The best ability for an NPC to use now and its targets, or None to fall back on weapons. Players' autopilot
		sticks to weapons (and heals with support)."""
		if combatant.controller == PLAYER :
			return None
		best = None
		for ability in combatant.abilities :
			if not self.usable(combatant, ability) :
				continue
			scored = self.score(combatant, ability, behavior)
			if scored is not None and (best is None or scored[0] > best[0]) :
				best = (scored[0], ability, scored[1])
		return (best[1], best[2]) if best else None

	# ============================================================
	def score(self, combatant: Combatant, ability: dict, behavior: str) -> tuple[int, list[Combatant]] | None :
		"""How much the ability is worth right now and whom to aim it at; None when it would do nothing useful."""
		engine = self.engine
		aim = engine.ability_aim(ability)
		limit = int(ability.get("targets") or 1)
		effects = ability.get("effects") or []
		mechanics = {effect.get("mechanic") for effect in effects}
		if aim == FX.SELF :
			return self.score_self(combatant, effects)
		pool = engine.ability_targets(combatant, ability)
		if not pool :
			return None
		if aim == FX.ALLY :
			return self.score_allies(combatant, effects, mechanics, pool, limit)
		return self.score_enemies(combatant, effects, mechanics, pool, limit, behavior)

	# ============================================================
	@staticmethod
	def lasting(effect: dict) -> str | None :
		"""The condition an effect leaves on its target, if any."""
		mechanic = effect.get("mechanic")
		if mechanic == FX.DOOM :
			return C.DOOMED
		if mechanic == FX.COMPANION :
			return C.COMPANION
		if mechanic == FX.SHIELD :
			return C.SHIELDED
		return (effect.get("params") or {}).get("condition")

	# ============================================================
	def score_self(self, combatant: Combatant, effects: list[dict]) -> tuple[int, list[Combatant]] | None :
		value = 0
		for effect in effects :
			mechanic = effect.get("mechanic")
			if mechanic == FX.ESCAPE :
				continue
			if mechanic == FX.HEAL :
				if combatant.hp < combatant.hp_max * SUPPORT_HEAL_BELOW :
					value = max(value, 80)
			elif mechanic == FX.CLEANSE :
				if any(C.has(combatant.conditions, name) for name in C.CONTROL + C.DAMAGE_OVER_TIME) :
					value = max(value, 60)
			elif mechanic == FX.COMPANION :
				if not C.has(combatant.conditions, C.COMPANION) :
					value = max(value, 55)
			elif mechanic in (FX.BOOST, FX.SHIELD) :
				name = self.lasting(effect)
				if name and not C.has(combatant.conditions, name) :
					value = max(value, 45)
		return (value, [combatant]) if value else None

	# ============================================================
	def score_allies(self, combatant: Combatant, effects: list[dict], mechanics: set, pool: list[Combatant],
	                 limit: int) -> tuple[int, list[Combatant]] | None :
		downed = [ally for ally in pool if ally.down]
		hurt = sorted((ally for ally in pool if ally.standing and ally.hp_max
		               and ally.hp < ally.hp_max * SUPPORT_HEAL_BELOW), key=lambda ally : ally.hp / ally.hp_max)
		if downed and mechanics & {FX.HEAL, FX.REVIVE} :
			return 100, downed[:limit]
		if hurt and FX.HEAL in mechanics :
			return 90, hurt[:limit]
		if FX.CLEANSE in mechanics :
			ailing = [ally for ally in pool if ally.standing
			          and any(C.has(ally.conditions, name) for name in C.CONTROL)]
			if ailing :
				return 65, ailing[:limit]
		lasting = [name for name in (self.lasting(effect) for effect in effects
		                             if effect.get("aim") == FX.ALLY) if name]
		if lasting :
			lacking = [ally for ally in pool if ally.standing
			           and not all(C.has(ally.conditions, name) for name in lasting)]
			if FX.SHIELD in mechanics :
				lacking = sorted(lacking, key=lambda ally : ally.hp / max(1, ally.hp_max))
				return (60, lacking[:limit]) if lacking and lacking[0].hp < lacking[0].hp_max * 0.6 else None
			if lacking :
				# Buffs go to the ally who hits hardest first: the one with the most HP left stands longest.
				lacking = sorted(lacking, key=lambda ally : -ally.hp)
				return 45, lacking[:limit]
		return None

	# ============================================================
	def score_enemies(self, combatant: Combatant, effects: list[dict], mechanics: set, pool: list[Combatant],
	                  limit: int, behavior: str) -> tuple[int, list[Combatant]] | None :
		preferred = self.target(combatant, behavior)
		ordered = sorted(pool, key=lambda enemy : (enemy is not preferred, enemy.hp, enemy.id))
		value = 0
		if mechanics & {FX.ATTACK, FX.BLAST} :
			value = 50 + (10 if limit > 1 and len(pool) > 1 else 0)
		for effect in effects :
			name = self.lasting(effect)
			mechanic = effect.get("mechanic")
			if mechanic == FX.DISPEL :
				if any(C.visible(enemy.conditions) and any(C.has(enemy.conditions, helpful) for helpful in C.HELPFUL)
				       for enemy in pool) :
					value = max(value, 35)
				continue
			if mechanic not in (FX.AFFLICT, FX.DOOM) or not name :
				continue
			# Control goes on the toughest enemy that doesn't have it yet (and isn't immune to it).
			open_to = [enemy for enemy in pool if not C.has(enemy.conditions, name) and not C.immune(enemy.conditions,
			                                                                                           name)]
			if not open_to :
				continue
			ordered = sorted(open_to, key=lambda enemy : (-enemy.hp, enemy.id)) + \
			          [enemy for enemy in ordered if enemy not in open_to]
			value = max(value, 70 if name in C.CONTROL or name == C.DOOMED else 40)
		if not value :
			return None
		return value, ordered[:limit]

	# ============================================================
	def _support(self, combatant: Combatant) -> bool :
		"""Revives a downed ally, or heals a hurt one; False when there is nothing to do."""
		engine = self.engine
		downed = [ally for ally in self.fight.allies(combatant, include_self=False) if ally.down]
		if downed and combatant.ap >= AP_REVIVE and not engine.crippled(combatant, "intelligence") :
			return self._try(lambda : engine.revive_now(combatant, downed[0]))
		# Too dim to revive: a healing item still brings the ally back.
		healing = [item for item in combatant.items if item["use"] == Items.HEAL]
		if downed and healing and combatant.ap >= Items.AP_ITEM :
			def use() :
				engine._spend(combatant, Items.AP_ITEM)
				engine.apply_item(combatant, healing[0], downed[0])
			return self._try(use)
		for ability in combatant.abilities :
			mechanics = {effect.get("mechanic") for effect in ability.get("effects") or []}
			if engine.ability_aim(ability) != FX.ALLY or FX.HEAL not in mechanics \
					or C.has(combatant.conditions, C.SILENCED) :
				continue
			left = engine.ability_uses_left(combatant, ability)
			if (left is not None and left <= 0) or engine.ability_ap(ability) > combatant.ap \
					or engine.weapon_problem(combatant, ability) :
				continue
			hurt = [ally for ally in self.fight.allies(combatant)
			        if ally.standing and ally.hp_max and ally.hp / ally.hp_max < SUPPORT_HEAL_BELOW]
			if hurt :
				target = min(hurt, key=lambda ally : ally.hp / ally.hp_max)
				return self._try(lambda : engine.resolve_and_use(combatant, ability, target))
		return False
