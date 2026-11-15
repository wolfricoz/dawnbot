"""Automatic moves: what a combatant does when its player missed the turn, or when it is an automatic NPC.

Players pick an autopilot for each fight (attack the weakest enemy, attack whoever hit them last, defend, or help and
revive allies first); NPCs have a behavior (aggressive, vengeful, random, cautious, support). Attacks use the weapon
with the best expected damage that the remaining AP pays for, and the turn ends with the AP left as AC.
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
		ability = self._offensive_ability(combatant)
		target = self.target(combatant, behavior)
		if target is None :
			return False
		if ability is not None :
			return self._try(lambda : self.engine.resolve_and_use(combatant, ability, target))
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

	# ============================================================
	def _offensive_ability(self, combatant: Combatant) -> dict | None :
		"""An attack ability the combatant can use now, for NPCs (players' autopilot sticks to weapons)."""
		if combatant.controller == PLAYER or C.has(combatant.conditions, C.SILENCED) :
			return None
		for ability in combatant.abilities :
			mechanics = {effect.get("mechanic") for effect in ability.get("effects") or []}
			if self.engine.ability_aim(ability) != FX.ENEMY or not mechanics & {FX.ATTACK, FX.BLAST} :
				continue
			left = self.engine.ability_uses_left(combatant, ability)
			if (left is None or left > 0) and self.engine.ability_ap(ability) <= combatant.ap \
					and not self.engine.weapon_problem(combatant, ability) :
				return ability
		return None

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
