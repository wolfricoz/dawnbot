"""Every rule that changes a fight: joining, turns and phases, the actions, conditions, downed and dying combatants,
timers, automatic moves, GM tools and the end of the fight.

The engine works on a Fight (classes/combat/State.py) and never touches Discord or the database: the caller loads the
fight, runs one engine call, saves the fight and posts the outcome's lines. Dice and the clock can be passed in, so
tests can control them.

Turns: with async pacing a round is a phase per side (sides act in order of their average Sequence, members in any
order); with live pacing every combatant gets its own turn in Sequence order. A turn starts with conditions ticking and
AP refilling, and ends when the combatant has no AP left, ends it, or the timer runs out (then it gets an automatic
move). AP left at the end of a turn becomes +1 AC each until its next turn.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from classes.combat import Abilities as AbilityRules
from classes.combat import Conditions as C
from classes.combat import Items, Passives as P, Rules
from classes.combat.DamageTypes import ALWAYS, ARC, CLEANSE, CONDITION, IGNORE_DT, RESTORATION, STRONG_HIT
from classes.combat.State import ACTIVE, ASYNC, AUTO, Combatant, DEAD, DOWNED, DYING, ENDED, FLED, Fight, GM, LIVE, \
	PAUSED, PLAYER, REMOVED, SETUP, STABLE, STANDING

AP_HELP = 2
AP_REVIVE = 3
AP_SWITCH = 1
AP_AIMED = 1
HELP_BONUS = 2
REVIVE_DC = 10
FLEE_DC = 10
DEATH_DC = 10
DEATH_DC_CRIPPLED = 12
DEATH_ROLLS = 3
IDLE_PING = 3
MARKED_BONUS = 2
INSPIRED_BONUS = 2
WEAKENED_PENALTY = -2
BLINDED_PENALTY = -4
SLOWED_AC = -2
EXPOSED_AC = -2
DOT_DICE = "1d4"
# A fight where nobody needs to act (only automatic NPCs) runs by itself; this stops it after so many turns.
AUTO_LIMIT = 400
DEFAULT_ASYNC_SECONDS = 12 * 3600
DEFAULT_LIVE_SECONDS = 3 * 60

# Player autopilot settings and NPC behaviors.
WEAKEST = "weakest"
REVENGE = "revenge"
DEFEND = "defend"
SUPPORT = "support"
AGGRESSIVE = "aggressive"
VENGEFUL = "vengeful"
RANDOM = "random"
CAUTIOUS = "cautious"
AUTOPILOTS = [WEAKEST, REVENGE, DEFEND, SUPPORT]
BEHAVIORS = [AGGRESSIVE, VENGEFUL, RANDOM, CAUTIOUS, SUPPORT]


class CombatError(Exception) :
	"""An action that is not allowed; the message is shown to the member."""


@dataclass
class Outcome :
	lines: list[str] = field(default_factory=list)
	# Members to ping because it is now their turn, and GMs to ping about idle players.
	pings: list[int] = field(default_factory=list)
	gm_pings: list[str] = field(default_factory=list)
	ended: bool = False
	# Characters whose death the GM confirmed: {combatant id: character id}.
	deaths: dict = field(default_factory=dict)
	# Consumables (character_gear ids) used up by this action.
	used_items: list = field(default_factory=list)

	# ============================================================
	def add(self, text: str) -> None :
		if text :
			self.lines.append(text)


class Engine :

	def __init__(self, fight: Fight, types: dict[str, dict] | None = None, rng: random.Random | None = None,
	             now: datetime | None = None, async_seconds: int = DEFAULT_ASYNC_SECONDS,
	             live_seconds: int = DEFAULT_LIVE_SECONDS) :
		self.fight = fight
		self.types = types or {}
		self.rng = rng or random.Random()
		self.now = now or datetime.now(timezone.utc)
		self.async_seconds = async_seconds
		self.live_seconds = live_seconds
		self.outcome = Outcome()

	# == helpers ==

	# ============================================================
	def say(self, text: str) -> None :
		self.outcome.add(text)

	# ============================================================
	def mod(self, combatant: Combatant, stat: str) -> int :
		"""A combatant's modifier for a stat. NPCs have none: their ability_mod stands in for every stat."""
		if combatant.stats.get("npc") :
			return int(combatant.stats.get("ability_mod", 0))
		return Rules.modifier(Rules.stat(combatant.special, stat), combatant.base)

	# ============================================================
	def crippled(self, combatant: Combatant, stat: str) -> bool :
		if combatant.stats.get("npc") :
			return False
		return Rules.stat(combatant.special, stat) <= 0

	# ============================================================
	def effective_ac(self, combatant: Combatant) -> int :
		"""AC with unspent AP and conditions; this may go above the cap of 18."""
		value = combatant.ac + C.amount(combatant.conditions, C.GUARD)
		value += self.stacks(combatant, P.AC) + self.aura(combatant, P.AC)
		if C.has(combatant.conditions, C.SLOWED) :
			value += SLOWED_AC
		if C.has(combatant.conditions, C.EXPOSED) :
			value += EXPOSED_AC
		return value

	# ============================================================
	def situational(self, attacker: Combatant, target: Combatant | None) -> list[Rules.Bonus] :
		"""Bonuses from conditions: the attacker's and the target's."""
		bonuses = []
		conditions = attacker.conditions
		if C.has(conditions, C.WEAKENED) :
			bonuses.append(Rules.Bonus("weakened", WEAKENED_PENALTY))
		if C.has(conditions, C.BLINDED) :
			bonuses.append(Rules.Bonus("blinded", BLINDED_PENALTY))
		if C.has(conditions, C.INSPIRED) :
			bonuses.append(Rules.Bonus("inspired", INSPIRED_BONUS))
		if C.has(conditions, C.HELPED) :
			bonuses.append(Rules.Bonus("helped", C.amount(conditions, C.HELPED)))
			C.remove(conditions, C.HELPED)
		if target is not None and C.has(target.conditions, C.MARKED) :
			bonuses.append(Rules.Bonus("marked", MARKED_BONUS))
		return bonuses

	# == passives ==

	# ============================================================
	@staticmethod
	def passive_state(combatant: Combatant, passive: dict) -> dict :
		"""What a passive keeps track of during the fight (stacks, uses, the round it countered)."""
		return combatant.stats.setdefault("passive_state", {}).setdefault(str(passive["id"]), {})

	# ============================================================
	def stacks(self, combatant: Combatant, field: str) -> int :
		return sum(int(self.passive_state(combatant, passive).get("stacks") or 0)
		           for passive in P.of_type(combatant.passives, P.STACKS) if passive.get("field") == field)

	# ============================================================
	def aura(self, combatant: Combatant, field: str) -> int :
		"""The best aura bonus to a field from the combatant's standing allies (its own auras don't count)."""
		best = 0
		for ally in self.fight.allies(combatant, include_self=False) :
			if not ally.standing :
				continue
			for passive in P.of_type(ally.passives, P.AURA) :
				if passive.get("field") == field :
					best = max(best, P.AURA_AMOUNTS[P.index(passive["tier"])])
		return best

	# ============================================================
	def passive_roll(self, actor: Combatant, type_name: str | None, magic: bool, ranged: bool) -> tuple[int, int] :
		"""The to hit and damage the actor's passives, stacks and allies' auras add to this attack."""
		passives = actor.passives
		to_hit = P.roll_bonus(passives, P.TO_HIT, type_name, magic, ranged) + self.stacks(actor, P.TO_HIT) \
		         + self.aura(actor, P.TO_HIT)
		damage = P.roll_bonus(passives, P.DAMAGE, type_name, magic, ranged) + self.stacks(actor, P.DAMAGE) \
		         + self.aura(actor, P.DAMAGE)
		return to_hit, damage

	# ============================================================
	def inflict(self, target: Combatant, name: str, turns: int) -> bool :
		"""Gives the target a harmful condition, unless a passive makes it immune. False when it didn't take hold."""
		if any(passive.get("condition") == name for passive in P.of_type(target.passives, P.IMMUNE)) :
			self.say(f"-# {target.name} is immune to being {C.label(name).lower()}.")
			return False
		return C.add(target.conditions, name, turns=turns)

	# ============================================================
	def strong_hit_triggers(self, actor: Combatant, target: Combatant) -> None :
		for passive in P.triggers(actor.passives, P.ON_STRONG_HIT) :
			name = passive.get("condition")
			if target.standing and name and self.inflict(target, name, P.TRIGGER_TURNS[P.index(passive["tier"])]) :
				self.say(f"-# {passive['name']}: {target.name} is {C.label(name).lower()}.")

	# ============================================================
	def counter(self, defender: Combatant, attacker: Combatant, weapon: dict) -> None :
		"""A defender with a counter passive hits back at a melee attacker that missed it, once per round."""
		if weapon.get("range") == Rules.RANGED or not defender.standing or not attacker.standing :
			return
		for passive in P.triggers(defender.passives, P.COUNTER) :
			state = self.passive_state(defender, passive)
			if state.get("round") == self.fight.round :
				continue
			state["round"] = self.fight.round
			dice = P.TRIGGER_DICE[P.index(passive["tier"])]
			amount, rolls = Rules.roll_dice(dice, rng=self.rng)
			self.say(f"-# {passive['name']}: {defender.name} counters {attacker.name} for {amount} ({dice} {rolls}).")
			self.damage(attacker, amount, defender)
			return

	# ============================================================
	def resist(self, target: Combatant, amount: int, type_name: str | None, magic: bool, ranged: bool) -> int :
		"""Damage after the target's resistances (at least 1 when there was any)."""
		reduction = sum(P.RESIST_AMOUNTS[P.index(passive["tier"])] for passive in P.of_type(target.passives, P.RESIST)
		                if P.matches(passive.get("scope"), type_name, magic, ranged))
		if not reduction or amount <= 0 :
			return amount
		reduced = max(1, amount - reduction)
		if reduced < amount :
			self.say(f"-# {target.name} resists {amount - reduced}.")
		return reduced

	# ============================================================
	def last_stand(self, target: Combatant) -> bool :
		"""Uses a last stand passive to keep the target at 1 HP; False when it has none left."""
		for passive in P.triggers(target.passives, P.LAST_STAND) :
			state = self.passive_state(target, passive)
			used = int(state.get("uses") or 0)
			if used < P.LAST_STAND_USES[P.index(passive["tier"])] :
				state["uses"] = used + 1
				target.hp = 1
				self.say(f"🛡️ {passive['name']}: **{target.name}** refuses to fall and stays at 1 HP.")
				return True
		return False

	# ============================================================
	def gain_stacks(self, target: Combatant, type_name: str | None, magic: bool, ranged: bool) -> None :
		for passive in P.of_type(target.passives, P.STACKS) :
			if not P.matches(passive.get("scope"), type_name, magic, ranged) :
				continue
			state = self.passive_state(target, passive)
			limit = P.max_stacks(passive)
			stacks = int(state.get("stacks") or 0)
			if stacks < limit :
				state["stacks"] = stacks + 1
				self.say(f"-# {passive['name']}: {target.name} gains a stack ({stacks + 1}/{limit}, +{stacks + 1} "
				         f"{P.FIELD_LABELS[passive['field']]}).")

	# ============================================================
	def damage(self, target: Combatant, amount: int, source: Combatant | None = None, type_name: str | None = None,
	           magic: bool = False, ranged: bool = False) -> int :
		"""Deals damage through the target's resistances (hits from a source only) and shield; a target at 0 HP is
		downed, unless a last stand passive keeps it up. A hit can give the target stacks.

		@return: the damage that reached its HP.
		"""
		amount = max(0, int(amount))
		if source is not None :
			amount = self.resist(target, amount, type_name, magic, ranged)
		shield = C.get(target.conditions, C.SHIELDED)
		if shield and amount :
			absorbed = min(int(shield.get("amount") or 0), amount)
			amount -= absorbed
			shield["amount"] = int(shield.get("amount") or 0) - absorbed
			if shield["amount"] <= 0 :
				C.remove(target.conditions, C.SHIELDED)
			if absorbed :
				self.say(f"-# {target.name}'s shield absorbs {absorbed}.")
		target.hp -= amount
		if source is not None :
			target.last_attacker_id = source.id
		if target.hp <= 0 and target.standing and amount > 0 and self.last_stand(target) :
			pass
		elif target.hp <= 0 and target.standing :
			target.hp = 0
			target.state = DOWNED
			target.death_successes = target.death_failures = 0
			C.remove(target.conditions, C.GUARD)
			self.say(f"💀 **{target.name}** is downed!")
		target.hp = max(0, target.hp)
		if source is not None and amount > 0 and target.standing :
			self.gain_stacks(target, type_name, magic, ranged)
		return amount

	# ============================================================
	def heal(self, target: Combatant, amount: int) -> int :
		before = target.hp
		target.hp = min(target.hp_max, target.hp + max(0, int(amount)))
		if target.down and target.hp > 0 :
			target.state = STANDING
			target.death_successes = target.death_failures = 0
			target.acted = True
			self.say(f"✨ **{target.name}** is back on their feet.")
		return target.hp - before

	# == turns ==

	# ============================================================
	def unit(self) -> list[Combatant] :
		"""The combatants whose turn it is (the current side's members, or the current combatant)."""
		fight = self.fight
		if fight.state != ACTIVE or not fight.order or fight.turn_index >= len(fight.order) :
			return []
		current = fight.order[fight.turn_index]
		if fight.pacing == LIVE :
			combatant = fight.combatant(current)
			return [combatant] if combatant is not None and combatant.in_fight else []
		return fight.members(current)

	# ============================================================
	def actors(self) -> list[Combatant] :
		"""The combatants that can act right now."""
		return [combatant for combatant in self.unit() if combatant.standing and not combatant.acted]

	# ============================================================
	def waiting_on(self) -> list[Combatant] :
		"""The actors controlled by people (players and GMs), which the fight waits for."""
		return [combatant for combatant in self.actors() if combatant.controller != AUTO]

	# ============================================================
	def require_turn(self, combatant: Combatant) -> None :
		if self.fight.state == PAUSED :
			raise CombatError("The fight is paused.")
		if self.fight.state != ACTIVE :
			raise CombatError("The fight is not running.")
		if not combatant.standing :
			raise CombatError(f"{combatant.name} is {combatant.state} and can't act.")
		if combatant not in self.actors() :
			raise CombatError(f"It is not {combatant.name}'s turn.")

	# ============================================================
	def turn_order(self) -> list[int] :
		"""This round's order: side ids (async) or combatant ids (live)."""
		fight = self.fight
		if fight.pacing == LIVE :
			combatants = [combatant for combatant in fight.combatants if combatant.in_fight]

			def key(combatant: Combatant) :
				last = C.has(combatant.conditions, C.SLOWED) or self.crippled(combatant, "perception")
				return (last, -combatant.sequence, -Rules.stat(combatant.special, "agility"), combatant.position,
				        combatant.id)

			return [combatant.id for combatant in sorted(combatants, key=key)]
		sides = []
		for side in fight.sides :
			members = fight.members(side.id)
			if not members :
				continue
			standing = [member for member in members if member.standing] or members
			average = sum(member.sequence for member in standing) / len(standing)
			sides.append((-average, side.position, side.id))
		return [side_id for _, _, side_id in sorted(sides)]

	# ============================================================
	def timer(self) -> int :
		return self.live_seconds if self.fight.pacing == LIVE else self.async_seconds

	# ============================================================
	def start(self) -> Outcome :
		fight = self.fight
		if fight.state != SETUP :
			raise CombatError("The fight has already started.")
		sides_with_members = {combatant.side_id for combatant in fight.combatants if combatant.standing}
		if len(sides_with_members) < 2 :
			raise CombatError("A fight needs combatants on at least two sides.")
		fight.state = ACTIVE
		fight.round = 0
		self.say(f"⚔️ **{fight.title}** begins!")
		self.new_round()
		self.settle()
		return self.outcome

	# ============================================================
	def new_round(self) -> None :
		fight = self.fight
		fight.round += 1
		for combatant in fight.combatants :
			if combatant.in_fight :
				combatant.acted = False
		fight.order = self.turn_order()
		fight.turn_index = 0
		self.say(f"**Round {fight.round}**")
		self.begin_unit()

	# ============================================================
	def begin_unit(self) -> None :
		fight = self.fight
		fight.deadline = self.now + timedelta(seconds=self.timer())
		unit = self.unit()
		for combatant in unit :
			self.begin_turn(combatant)
		if fight.state != ACTIVE :
			return
		if fight.pacing == ASYNC and unit :
			side = fight.side(fight.order[fight.turn_index])
			if any(combatant.standing for combatant in unit) :
				self.say(f"__{side.name if side else 'Next side'}'s turn__")
		players = [combatant.uid for combatant in self.waiting_on() if combatant.controller == PLAYER and combatant.uid]
		for uid in players :
			if uid not in self.outcome.pings :
				self.outcome.pings.append(uid)

	# ============================================================
	def begin_turn(self, combatant: Combatant) -> None :
		"""The start of a combatant's turn: guard and exposure end, damage over time and regeneration tick, death rolls
		are made and AP refills."""
		C.remove(combatant.conditions, C.GUARD)
		C.remove(combatant.conditions, C.EXPOSED)
		if combatant.down :
			combatant.acted = True
			if self.fight.lethal and combatant.state == DOWNED :
				self.death_roll(combatant)
			C.count_down(combatant.conditions)
			return
		if not combatant.standing :
			return
		for name in C.DAMAGE_OVER_TIME :
			if C.has(combatant.conditions, name) :
				amount, _ = Rules.roll_dice(DOT_DICE, rng=self.rng)
				self.say(f"🔥 {combatant.name} takes {amount} from {C.label(name).lower()}.")
				self.damage(combatant, amount)
		if C.has(combatant.conditions, C.REGENERATING) and combatant.standing :
			amount, _ = Rules.roll_dice(DOT_DICE, rng=self.rng)
			healed = self.heal(combatant, amount)
			if healed :
				self.say(f"💚 {combatant.name} regenerates {healed} HP.")
		for passive in P.triggers(combatant.passives, P.REGENERATE) :
			if not combatant.standing :
				break
			amount, _ = Rules.roll_dice(P.TRIGGER_DICE[P.index(passive["tier"])], rng=self.rng)
			healed = self.heal(combatant, amount)
			if healed :
				self.say(f"💚 {passive['name']}: {combatant.name} heals {healed} HP.")
		if not combatant.standing :
			combatant.acted = True
			C.count_down(combatant.conditions)
			self.check_victory()
			return
		if C.has(combatant.conditions, C.STUNNED) :
			C.remove(combatant.conditions, C.STUNNED)
			C.add(combatant.conditions, C.STUN_IMMUNE, turns=2)
			combatant.ap = 0
			combatant.acted = True
			C.count_down(combatant.conditions)
			self.say(f"💫 **{combatant.name}** is stunned and loses the turn.")
			return
		combatant.ap = combatant.ap_max
		combatant.acted = False

	# ============================================================
	def end_turn(self, combatant: Combatant, quiet: bool = False) -> None :
		"""Ends a combatant's turn: unspent AP becomes AC until its next turn and conditions count down."""
		if combatant.acted :
			return
		if combatant.standing and combatant.ap > 0 :
			C.add(combatant.conditions, C.GUARD, turns=None, value=combatant.ap)
			if not quiet :
				self.say(f"-# {combatant.name} keeps {combatant.ap} AP as +{combatant.ap} AC.")
		combatant.ap = 0
		combatant.acted = True
		for name in C.count_down(combatant.conditions) :
			self.say(f"-# {combatant.name} is no longer {C.label(name).lower()}.")

	# ============================================================
	def unit_done(self) -> bool :
		return not self.actors()

	# ============================================================
	def advance(self) -> None :
		fight = self.fight
		fight.turn_index += 1
		if fight.turn_index >= len(fight.order) :
			self.new_round()
		else :
			self.begin_unit()

	# ============================================================
	def settle(self) -> None :
		"""Moves the fight on until it needs someone: automatic combatants act, finished turns advance."""
		from classes.combat.Autopilot import Autopilot

		for _ in range(AUTO_LIMIT) :
			if self.fight.state != ACTIVE :
				return
			automatic = [combatant for combatant in self.actors() if combatant.controller == AUTO]
			if automatic :
				Autopilot(self).take_turn(automatic[0])
				self.check_victory()
				continue
			if self.unit_done() :
				self.advance()
				continue
			return
		self.say("-# The fight paused itself after a long run of automatic turns; the GM can resume it.")
		self.pause()

	# ============================================================
	def can_still_act(self, combatant: Combatant) -> bool :
		"""Whether the AP left pays for anything (fleeing and "Other" aside, which take whatever is left)."""
		ap = combatant.ap
		if ap <= 0 :
			return False
		if any(self.attack_cost(combatant, weapon) <= ap for weapon in combatant.weapons) and self.fight.enemies(
				combatant) :
			return True
		allies = self.fight.allies(combatant, include_self=False)
		if ap >= AP_HELP and any(ally.standing for ally in allies) and not self.crippled(combatant, "charisma") :
			return True
		if ap >= AP_REVIVE and any(ally.down for ally in allies) and not self.crippled(combatant, "intelligence") :
			return True
		for ability in combatant.abilities :
			left = self.ability_uses_left(combatant, ability)
			if (left is None or left > 0) and AbilityRules.ap(ability["tier"]) <= ap :
				return True
		return False

	# ============================================================
	def finish_action(self, combatant: Combatant) -> Outcome :
		"""After an action: the turn ends when the AP left pays for nothing, the fight may end, and it moves on."""
		self.check_victory()
		if self.fight.state == ACTIVE and combatant.standing and not combatant.acted \
				and not self.can_still_act(combatant) :
			self.end_turn(combatant)
		if self.fight.state == ACTIVE and not combatant.standing :
			combatant.acted = True
		self.settle()
		return self.outcome

	# ============================================================
	def timeout(self) -> Outcome :
		"""The timer ran out: everyone who still has to act gets an automatic move."""
		from classes.combat.Autopilot import Autopilot

		fight = self.fight
		if fight.state != ACTIVE or fight.deadline is None or fight.deadline > self.now :
			return self.outcome
		self.say("⏰ Time is up.")
		for combatant in list(self.actors()) :
			Autopilot(self).take_turn(combatant, idle=combatant.controller == PLAYER)
			self.check_victory()
			if fight.state != ACTIVE :
				break
		self.settle()
		return self.outcome

	# ============================================================
	def death_roll(self, combatant: Combatant) -> None :
		dc = DEATH_DC_CRIPPLED if self.crippled(combatant, "endurance") else DEATH_DC
		roll = self.rng.randint(1, 20)
		total = roll + self.mod(combatant, "endurance")
		if total >= dc :
			combatant.death_successes += 1
			text = f"succeeds ({total} vs {dc})"
		else :
			combatant.death_failures += 1
			text = f"fails ({total} vs {dc})"
		self.say(f"☠️ {combatant.name} makes a death roll and {text}: {combatant.death_successes} up, "
		         f"{combatant.death_failures} down.")
		if combatant.death_successes >= DEATH_ROLLS :
			combatant.state = STABLE
			self.say(f"{combatant.name} is stable.")
		elif combatant.death_failures >= DEATH_ROLLS :
			combatant.state = DYING
			self.say(f"⚰️ **{combatant.name}** is dying. The GM can confirm the death or spare them.")
			self.outcome.gm_pings.append(f"{combatant.name} is dying.")

	# ============================================================
	def check_victory(self) -> None :
		fight = self.fight
		if fight.state not in (ACTIVE, PAUSED) :
			return
		standing_sides = {combatant.side_id for combatant in fight.combatants if combatant.standing}
		if len(standing_sides) > 1 :
			return
		self.end(next(iter(standing_sides), None))

	# ============================================================
	def end(self, winner_side_id: int | None) -> None :
		fight = self.fight
		fight.state = ENDED
		fight.deadline = None
		fight.paused_seconds = None
		fight.winner_side_id = winner_side_id
		side = fight.side(winner_side_id)
		self.say(f"🏁 The fight is over. **{side.name}** wins!" if side else "🏁 The fight is over. Nobody is left "
		                                                                   "standing.")
		self.outcome.ended = True

	# == actions ==

	# ============================================================
	def _target(self, actor: Combatant, target_id, enemy: bool, standing: bool = True) -> Combatant :
		target = self.fight.combatant(target_id)
		if target is None or not target.in_fight :
			raise CombatError("That target is not in the fight.")
		if enemy and target.side_id == actor.side_id :
			raise CombatError(f"{target.name} is on your side.")
		if not enemy and target.side_id != actor.side_id :
			raise CombatError(f"{target.name} is not on your side.")
		if standing and not target.standing :
			raise CombatError(f"{target.name} is {target.state}.")
		return target

	# ============================================================
	def _spend(self, actor: Combatant, cost: int) -> None :
		if actor.ap < cost :
			raise CombatError(f"That costs {cost} AP and {actor.name} has {actor.ap}.")
		actor.ap -= cost

	# ============================================================
	def attack_cost(self, actor: Combatant, weapon: dict, aimed: bool = False) -> int :
		cost = Rules.weapon_ap(weapon) + (AP_AIMED if aimed else 0)
		if actor.weapon_key and weapon.get("key") != actor.weapon_key :
			cost += AP_SWITCH
		return cost

	# ============================================================
	def effect_of(self, type_name: str | None) -> tuple[dict | None, str | None] :
		"""A damage type's effect and trigger."""
		entry = self.types.get((type_name or "").lower())
		if entry is None :
			return None, None
		return entry.get("effect") or {}, entry.get("trigger")

	# ============================================================
	def apply_type_effect(self, effect: dict | None, target: Combatant, damage_done: int,
	                      source: Combatant, type_name: str) -> None :
		if not effect :
			return
		kind = effect.get("kind")
		if kind == CONDITION and target.standing :
			name = effect.get("condition")
			if self.inflict(target, name, int(effect.get("turns") or 1)) :
				self.say(f"-# {type_name}: {target.name} is {C.label(name).lower()}.")
		elif kind == ARC :
			others = [enemy for enemy in self.fight.enemies(source) if enemy.id != target.id]
			if others and damage_done > 0 :
				other = self.rng.choice(others)
				arc = max(1, damage_done // 2)
				self.say(f"-# {type_name}: it arcs to {other.name} for {arc}.")
				self.damage(other, arc, source, type_name=type_name)

	# ============================================================
	def attack(self, actor: Combatant, target_id, weapon_key: str | None = None, aimed: bool = False) -> Outcome :
		self.require_turn(actor)
		target = self._target(actor, target_id, enemy=True)
		weapon = actor.weapon(weapon_key or actor.weapon_key) or (actor.weapons[0] if actor.weapons else None)
		if weapon is None :
			raise CombatError(f"{actor.name} has no weapon.")
		cost = self.attack_cost(actor, weapon, aimed)
		self._spend(actor, cost)
		self.resolve_attack(actor, target, weapon, aimed)
		actor.weapon_key = weapon.get("key")
		return self.finish_action(actor)

	# ============================================================
	def resolve_attack(self, actor: Combatant, target: Combatant, weapon: dict, aimed: bool = False) -> None :
		bonuses = Rules.weapon_bonuses(actor.stats, weapon, actor.base)
		if aimed :
			bonuses.append(Rules.Bonus("aimed", Rules.AIMED_PENALTY))
		bonuses += self.situational(actor, target)
		ranged = weapon.get("range") == Rules.RANGED
		passive_hit, passive_damage = self.passive_roll(actor, weapon.get("type"), False, ranged)
		if passive_hit :
			bonuses.append(Rules.Bonus("passives", passive_hit))
		disadvantage = ranged and self.crippled(actor, "perception")
		crit_from = int(actor.stats.get("crit_min", 20)) - Rules.weapon_crit_widen(weapon)
		roll = Rules.roll_attack(bonuses, self.effective_ac(target), crit_from, int(actor.stats.get("fumble_max", 1)),
		                         disadvantage=disadvantage, confirm_crits=bool(actor.stats.get("confirm_crits")),
		                         rng=self.rng)
		verb = "takes aim at" if aimed else "attacks"
		head = f"**{actor.name}** {verb} **{target.name}** with {weapon.get('name', 'a weapon')}: {roll.text()}"
		if roll.fumble :
			C.add(actor.conditions, C.EXPOSED, turns=1)
			self.say(f"{head} → **fumble!** {actor.name} is left open (-2 AC).")
			self.counter(target, actor, weapon)
			return
		if not roll.hit :
			self.say(f"{head} → miss.")
			self.counter(target, actor, weapon)
			return
		type_name = weapon.get("type")
		effect, trigger = self.effect_of(type_name)
		triggered = effect is not None and (trigger == ALWAYS or (trigger == STRONG_HIT and roll.strong))
		ignore_dt = aimed or (triggered and effect.get("kind") == IGNORE_DT)
		bonus = Rules.damage_bonus(actor.stats, weapon, actor.base) + passive_damage
		if C.has(actor.conditions, C.WEAKENED) :
			bonus += WEAKENED_PENALTY
		damage = Rules.roll_damage(weapon.get("dice", "1d4"), bonus, target.dt, crit=roll.crit,
		                           extra_dice=1 if aimed else 0, ignore_dt=ignore_dt, rng=self.rng)
		label = "**crit!**" if roll.crit else ("strong hit" if roll.strong else "hit")
		self.say(f"{head} → {label} for **{damage.total}** ({damage.text()}).")
		done = self.damage(target, damage.total, actor, type_name=type_name, ranged=ranged)
		if triggered :
			self.apply_type_effect(effect, target, done, actor, type_name)
		if roll.strong :
			self.strong_hit_triggers(actor, target)

	# ============================================================
	def ability_uses_left(self, actor: Combatant, ability: dict) -> int | None :
		limit = AbilityRules.uses(ability["tier"])
		if limit is None :
			return None
		return limit - int(actor.ability_uses.get(str(ability["id"]), 0))

	# ============================================================
	def ability_targets(self, actor: Combatant, ability: dict) -> list[Combatant] :
		"""Who an ability can be aimed at: standing enemies, or allies (healing also reaches downed allies)."""
		if AbilityRules.offensive(ability["effect"]) :
			return self.fight.enemies(actor)
		if ability["effect"] == AbilityRules.HEAL :
			return [ally for ally in self.fight.allies(actor) if ally.standing or ally.down]
		return [ally for ally in self.fight.allies(actor) if ally.standing]

	# ============================================================
	def use_ability(self, actor: Combatant, ability_id, target_ids: list) -> Outcome :
		self.require_turn(actor)
		ability = actor.ability(ability_id)
		if ability is None :
			raise CombatError(f"{actor.name} doesn't know that ability.")
		limit = AbilityRules.AREA_TARGETS if ability.get("area") else 1
		ids = list(dict.fromkeys(target_ids or []))[:limit]
		allowed = {target.id : target for target in self.ability_targets(actor, ability)}
		targets = [allowed[target_id] for target_id in ids if target_id in allowed]
		self._use_ability(actor, ability, targets)
		return self.finish_action(actor)

	# ============================================================
	def resolve_and_use(self, actor: Combatant, ability: dict, target: Combatant) -> None :
		"""Uses an ability on one target without the turn checks (automatic moves)."""
		self._use_ability(actor, ability, [target])
		self.check_victory()

	# ============================================================
	def _use_ability(self, actor: Combatant, ability: dict, targets: list[Combatant]) -> None :
		if C.has(actor.conditions, C.SILENCED) :
			raise CombatError(f"{actor.name} is silenced and can't use abilities.")
		left = self.ability_uses_left(actor, ability)
		if left is not None and left <= 0 :
			raise CombatError(f"{ability['name']} has no uses left this fight.")
		if not targets :
			raise CombatError("Pick a target the ability can reach.")
		self._spend(actor, AbilityRules.ap(ability["tier"]))
		actor.ability_uses[str(ability["id"])] = int(actor.ability_uses.get(str(ability["id"]), 0)) + 1
		self.say(f"✨ **{actor.name}** uses **{ability['name']}**.")
		for target in targets :
			self.resolve_ability(actor, ability, target)

	# ============================================================
	def resolve_ability(self, actor: Combatant, ability: dict, target: Combatant) -> None :
		effect = ability["effect"]
		stat = ability.get("stat") or "intelligence"
		mod = self.mod(actor, stat)
		tier = ability["tier"]
		dice = AbilityRules.dice(tier, effect, bool(ability.get("area")), ability.get("secondary"))
		type_name = ability.get("damage_type")
		type_effect, trigger = self.effect_of(type_name)
		disadvantage = self.crippled(actor, stat)
		if effect == AbilityRules.DAMAGE :
			bonuses = [Rules.Bonus(Rules.STAT_SHORT.get(stat, stat), mod),
			           Rules.Bonus("armor", int((actor.stats.get("armor") or {}).get("ability_hit_mod") or 0))]
			bonuses += self.situational(actor, target)
			passive_hit, passive_damage = self.passive_roll(actor, type_name, True, False)
			if passive_hit :
				bonuses.append(Rules.Bonus("passives", passive_hit))
			roll = Rules.roll_attack(bonuses, self.effective_ac(target), int(actor.stats.get("crit_min", 20)),
			                         int(actor.stats.get("fumble_max", 1)), disadvantage=disadvantage,
			                         confirm_crits=bool(actor.stats.get("confirm_crits")), rng=self.rng)
			head = f"→ {target.name}: {roll.text()}"
			if roll.fumble :
				C.add(actor.conditions, C.EXPOSED, turns=1)
				self.say(f"{head} → **fumble!**")
				return
			if not roll.hit :
				self.say(f"{head} → miss.")
				return
			triggered = type_effect is not None and (trigger == ALWAYS or (trigger == STRONG_HIT and roll.strong))
			ignore_dt = triggered and type_effect.get("kind") == IGNORE_DT
			bonus = mod + passive_damage + (WEAKENED_PENALTY if C.has(actor.conditions, C.WEAKENED) else 0)
			damage = Rules.roll_damage(dice, bonus, target.dt, crit=roll.crit, ignore_dt=ignore_dt, rng=self.rng)
			label = "**crit!**" if roll.crit else ("strong hit" if roll.strong else "hit")
			self.say(f"{head} → {label} for **{damage.total}** ({damage.text()}).")
			done = self.damage(target, damage.total, actor, type_name=type_name, magic=True)
			secondary = ability.get("secondary")
			if secondary and target.standing and self.inflict(target, secondary, AbilityRules.turns(tier)) :
				self.say(f"-# {target.name} is {C.label(secondary).lower()}.")
			if triggered :
				self.apply_type_effect(type_effect, target, done, actor, type_name)
			if roll.strong :
				self.strong_hit_triggers(actor, target)
			return
		if effect == AbilityRules.CONDITION :
			name = ability.get("condition")
			dc = 10 + mod + AbilityRules.dc_bonus(tier)
			save_stat = C.save_stat(name)
			rolls = [self.rng.randint(1, 20)]
			save = rolls[0] + self.mod(target, save_stat) + int(target.stats.get("save_bonus", 0))
			if save >= dc :
				self.say(f"→ {target.name} resists ({save} vs DC {dc}).")
				return
			strong = save <= dc - Rules.STRONG_MARGIN
			if self.inflict(target, name, AbilityRules.turns(tier)) :
				self.say(f"→ {target.name} fails ({save} vs DC {dc}) and is {C.label(name).lower()}.")
			else :
				self.say(f"→ {target.name} fails ({save} vs DC {dc}) but shakes it off.")
			if strong and type_effect is not None and trigger == STRONG_HIT :
				self.apply_type_effect(type_effect, target, 0, actor, type_name)
			return
		if effect == AbilityRules.HEAL :
			amount, rolls = Rules.roll_dice(dice, mod, rng=self.rng)
			healed = self.heal(target, max(1, amount))
			self.say(f"→ {target.name} heals {healed} ({dice} {rolls} {mod:+d}).")
			if (type_name or RESTORATION).lower() == RESTORATION.lower() or (type_effect or {}).get("kind") == CLEANSE :
				removed = C.cleanse(target.conditions)
				if removed :
					self.say(f"-# {target.name} is no longer {C.label(removed).lower()}.")
			return
		if effect == AbilityRules.SHIELD :
			amount, rolls = Rules.roll_dice(dice, mod, rng=self.rng)
			amount = max(1, amount)
			C.add(target.conditions, C.SHIELDED, turns=AbilityRules.turns(tier) + 1, value=amount)
			self.say(f"→ {target.name} is shielded for {amount} ({dice} {rolls} {mod:+d}).")
			return
		if effect == AbilityRules.BOOST :
			name = ability.get("condition") or C.INSPIRED
			C.add(target.conditions, name, turns=AbilityRules.turns(tier))
			self.say(f"→ {target.name} is {C.label(name).lower()}.")

	# ============================================================
	def help(self, actor: Combatant, target_id) -> Outcome :
		self.require_turn(actor)
		if self.crippled(actor, "charisma") :
			raise CombatError(f"{actor.name}'s Charisma is too low to help.")
		target = self._target(actor, target_id, enemy=False)
		if target.id == actor.id :
			raise CombatError("Help someone else.")
		self._spend(actor, AP_HELP)
		C.add(target.conditions, C.HELPED, turns=None, value=HELP_BONUS)
		self.say(f"🤝 **{actor.name}** helps **{target.name}** (+{HELP_BONUS} on their next roll).")
		return self.finish_action(actor)

	# ============================================================
	def revive(self, actor: Combatant, target_id) -> Outcome :
		self.require_turn(actor)
		if self.crippled(actor, "intelligence") :
			raise CombatError(f"{actor.name}'s Intelligence is too low to revive anyone without a healing item "
			                  f"(use one with Use item).")
		target = self._target(actor, target_id, enemy=False, standing=False)
		self.revive_now(actor, target)
		return self.finish_action(actor)

	# ============================================================
	def revive_now(self, actor: Combatant, target: Combatant) -> None :
		"""Tries to revive a downed ally, without the turn checks (automatic moves use it too)."""
		if not target.down :
			raise CombatError(f"{target.name} isn't downed.")
		if target.state == DEAD :
			raise CombatError(f"{target.name} is dead.")
		self._spend(actor, AP_REVIVE)
		bonuses = [Rules.Bonus("INT", self.mod(actor, "intelligence"))] + self.situational(actor, None)
		roll = Rules.roll_attack(bonuses, REVIVE_DC, rng=self.rng, fumble_to=0)
		if roll.total >= REVIVE_DC or roll.natural == 20 :
			target.hp = max(1, target.hp)
			target.state = STANDING
			target.death_successes = target.death_failures = 0
			target.acted = True
			self.say(f"🩹 **{actor.name}** revives **{target.name}** ({roll.text('DC')}). They're back with 1 HP.")
		else :
			self.say(f"🩹 **{actor.name}** tries to revive **{target.name}** but fails ({roll.text('DC')}).")

	# ============================================================
	def use_item(self, actor: Combatant, item_key: str | None, target_id) -> Outcome :
		"""Uses a consumable on the actor or an ally (2 AP). A healing item on a downed ally revives them."""
		self.require_turn(actor)
		item = actor.item(item_key)
		if item is None :
			raise CombatError(f"{actor.name} doesn't carry that item (or already used it).")
		target = self._target(actor, target_id if target_id is not None else actor.id, enemy=False, standing=False)
		if target.state == DEAD :
			raise CombatError(f"{target.name} is dead.")
		if target.down and item["use"] != Items.HEAL :
			raise CombatError(f"Only a healing item helps {target.name} while they're down.")
		self._spend(actor, Items.AP_ITEM)
		self.apply_item(actor, item, target)
		return self.finish_action(actor)

	# ============================================================
	def apply_item(self, actor: Combatant, item: dict, target: Combatant) -> None :
		"""Uses up the item and applies it, without the turn checks (automatic moves use it too)."""
		actor.stats.setdefault("used_items", []).append(item["entry_id"])
		self.outcome.used_items.append(item["entry_id"])
		on = "" if target.id == actor.id else f" on **{target.name}**"
		use, condition = item["use"], item.get("condition")
		if use == Items.HEAL :
			was_down = target.down
			amount, rolls = Rules.roll_dice(item["dice"], 0, rng=self.rng)
			healed = self.heal(target, max(1, amount))
			note = " (an automatic revive)" if was_down else ""
			self.say(f"🧪 **{actor.name}** uses {item['name']}{on}: +{healed} HP ({item['dice']} {rolls}){note}.")
		elif use == Items.CURE :
			present = [entry["name"] for entry in target.conditions if entry.get("name") in C.HARMFUL]
			name = condition if condition in present else (present[0] if present and condition is None else None)
			if name :
				C.remove(target.conditions, name)
				self.say(f"🧪 **{actor.name}** uses {item['name']}{on}: no longer {C.label(name).lower()}.")
			else :
				self.say(f"🧪 **{actor.name}** uses {item['name']}{on}, but there's nothing for it to cure.")
		elif use == Items.BOOST :
			value = None
			if condition == C.SHIELDED :
				value, _ = Rules.roll_dice(item["dice"], 0, rng=self.rng)
				value = max(1, value)
			C.add(target.conditions, condition, turns=int(item.get("turns") or 2), value=value)
			extra = f" for {value}" if value else ""
			self.say(f"🧪 **{actor.name}** uses {item['name']}{on}: {C.label(condition).lower()}{extra}.")
		else :
			self.say(f"🧪 **{actor.name}** uses {item['name']}{on}.\n-# The GM settles what it does.")
			self.outcome.gm_pings.append(f"{actor.name} used {item['name']}; settle what it does.")

	# ============================================================
	def flee(self, actor: Combatant) -> Outcome :
		self.require_turn(actor)
		helped = C.has(actor.conditions, C.HELPED)
		dc = FLEE_DC + len(self.fight.enemies(actor))
		actor.ap = 0
		if self.crippled(actor, "agility") and not helped :
			self.say(f"🏃 **{actor.name}** tries to flee, but can't get away without help.")
			self.end_turn(actor, quiet=True)
			return self.finish_action(actor)
		bonuses = [Rules.Bonus("AGI", self.mod(actor, "agility"))] + self.situational(actor, None)
		roll = Rules.roll_attack(bonuses, dc, rng=self.rng, fumble_to=0)
		if roll.total >= dc :
			actor.state = FLED
			actor.acted = True
			self.say(f"🏃 **{actor.name}** flees the fight ({roll.text('DC')}).")
		else :
			self.say(f"🏃 **{actor.name}** tries to flee but is cut off ({roll.text('DC')}).")
			self.end_turn(actor, quiet=True)
		return self.finish_action(actor)

	# ============================================================
	def other(self, actor: Combatant, text: str) -> Outcome :
		"""A free-text action the GM settles. It uses the rest of the turn; until settled, the AP counts as defending."""
		self.require_turn(actor)
		number = max([int(entry.get("number", 0)) for entry in self.fight.pending] + [0]) + 1
		self.fight.pending.append({"number" : number, "combatant_id" : actor.id, "round" : self.fight.round,
		                           "text" : text[:500]})
		self.say(f"📝 **{actor.name}**: {text[:500]}\n-# Waiting for the GM to settle this (#{number}).")
		self.outcome.gm_pings.append(f"{actor.name} did something the GM needs to settle (#{number}).")
		self.end_turn(actor)
		return self.finish_action(actor)

	# ============================================================
	def end_turn_action(self, actor: Combatant) -> Outcome :
		self.require_turn(actor)
		actor.idle_turns = 0
		self.end_turn(actor)
		return self.finish_action(actor)

	# == joining ==

	# ============================================================
	def join_problem(self, side_id: int, uid: int | None, character_id: int | None) -> str | None :
		"""Why a character can't join this side, or None."""
		fight = self.fight
		if fight.side(side_id) is None :
			return "That side is not in this fight."
		if fight.state == ENDED :
			return "This fight is over."
		if fight.state not in (SETUP, "pending") and not fight.late_join :
			return "This fight has started; the GM can allow late joins."
		if character_id is not None and any(combatant.character_id == character_id and combatant.in_fight
		                                    for combatant in fight.combatants) :
			return "That character is already in this fight."
		if fight.kind == "pvp" and uid is not None :
			invited = [int(value) for value in (fight.invites or {}).get(str(side_id), [])]
			on_side = any(combatant.uid == uid for combatant in fight.members(side_id))
			if uid not in invited and not on_side :
				return "Joining a side in a PvP fight needs an invite from someone on that side (/combat invite)."
		return None

	# ============================================================
	def joined(self, combatant: Combatant) -> None :
		"""A combatant that joins a running fight waits for its next turn."""
		fight = self.fight
		if fight.state in (ACTIVE, PAUSED) :
			combatant.acted = True
			if fight.pacing == LIVE :
				fight.order.append(combatant.id)
			elif combatant.side_id not in fight.order :
				fight.order.append(combatant.side_id)
		self.say(f"➕ **{combatant.name}** joins {fight.side(combatant.side_id).name}.")

	# == GM tools ==

	# ============================================================
	def pause(self) -> Outcome :
		fight = self.fight
		if fight.state != ACTIVE :
			raise CombatError("Only a running fight can be paused.")
		fight.state = PAUSED
		if fight.deadline is not None :
			fight.paused_seconds = max(0, int((fight.deadline - self.now).total_seconds()))
		fight.deadline = None
		self.say("⏸️ The fight is paused.")
		return self.outcome

	# ============================================================
	def resume(self) -> Outcome :
		fight = self.fight
		if fight.state != PAUSED :
			raise CombatError("The fight is not paused.")
		fight.state = ACTIVE
		fight.deadline = self.now + timedelta(seconds=fight.paused_seconds or self.timer())
		fight.paused_seconds = None
		self.say("▶️ The fight continues.")
		self.settle()
		return self.outcome

	# ============================================================
	def end_phase(self) -> Outcome :
		"""Ends the current phase or turn early: everyone who has not acted keeps their AP as AC."""
		if self.fight.state != ACTIVE :
			raise CombatError("The fight is not running.")
		for combatant in list(self.actors()) :
			self.end_turn(combatant, quiet=True)
		self.say("⏭️ The GM ends this turn.")
		self.settle()
		return self.outcome

	# ============================================================
	def skip(self, combatant: Combatant) -> Outcome :
		if combatant not in self.actors() :
			raise CombatError(f"It is not {combatant.name}'s turn.")
		self.end_turn(combatant, quiet=True)
		self.say(f"⏭️ The GM skips {combatant.name}'s turn.")
		self.settle()
		return self.outcome

	# ============================================================
	def adjust_hp(self, combatant: Combatant, change: int) -> Outcome :
		if change < 0 :
			self.say(f"🛠️ The GM deals {-change} damage to {combatant.name}.")
			self.damage(combatant, -change)
		elif change > 0 :
			healed = self.heal(combatant, change)
			self.say(f"🛠️ The GM heals {combatant.name} for {healed}.")
		self.check_victory()
		self.settle()
		return self.outcome

	# ============================================================
	def set_condition(self, combatant: Combatant, name: str, turns: int | None) -> Outcome :
		"""Adds a condition for some turns, or removes it with turns None."""
		if turns is None :
			if C.remove(combatant.conditions, name) :
				self.say(f"🛠️ {combatant.name} is no longer {C.label(name).lower()}.")
			return self.outcome
		value = turns if name == C.SHIELDED else None
		C.add(combatant.conditions, name, turns=turns if name != C.SHIELDED else 3, value=value)
		self.say(f"🛠️ {combatant.name} is {C.label(name).lower()}.")
		return self.outcome

	# ============================================================
	def remove(self, combatant: Combatant) -> Outcome :
		combatant.state = REMOVED
		combatant.acted = True
		self.say(f"➖ {combatant.name} is removed from the fight.")
		self.check_victory()
		self.settle()
		return self.outcome

	# ============================================================
	def move(self, combatant: Combatant, side_id: int) -> Outcome :
		side = self.fight.side(side_id)
		if side is None :
			raise CombatError("That side is not in this fight.")
		combatant.side_id = side_id
		self.say(f"↔️ {combatant.name} moves to {side.name}.")
		self.check_victory()
		self.settle()
		return self.outcome

	# ============================================================
	def control(self, combatant: Combatant, controller: str | None = None, behavior: str | None = None) -> Outcome :
		if controller is not None :
			if controller not in (GM, AUTO, PLAYER) or (controller == PLAYER and combatant.uid is None) :
				raise CombatError("That control mode doesn't fit this combatant.")
			combatant.controller = controller
		if behavior is not None :
			combatant.behavior = behavior
		self.settle()
		return self.outcome

	# ============================================================
	def settle_other(self, number: int, text: str, target: Combatant | None = None, change: int = 0) -> Outcome :
		entry = next((entry for entry in self.fight.pending if int(entry.get("number", 0)) == int(number)), None)
		if entry is None :
			raise CombatError(f"There is no unsettled action #{number}.")
		self.fight.pending.remove(entry)
		actor = self.fight.combatant(entry.get("combatant_id"))
		self.say(f"📜 #{number} ({actor.name if actor else 'someone'}): {text[:500]}")
		if target is not None and change :
			if change < 0 :
				self.damage(target, -change, actor)
				self.say(f"-# {target.name} takes {-change}.")
			else :
				self.say(f"-# {target.name} heals {self.heal(target, change)}.")
			self.check_victory()
			self.settle()
		return self.outcome

	# ============================================================
	def confirm_death(self, combatant: Combatant) -> Outcome :
		if combatant.state != DYING :
			raise CombatError(f"{combatant.name} is not dying.")
		combatant.state = DEAD
		self.say(f"⚰️ **{combatant.name}** has died.")
		if combatant.character_id :
			self.outcome.deaths[combatant.id] = combatant.character_id
		return self.outcome

	# ============================================================
	def spare(self, combatant: Combatant) -> Outcome :
		if combatant.state not in (DYING, DOWNED) :
			raise CombatError(f"{combatant.name} is not downed.")
		combatant.state = STABLE
		self.say(f"🕊️ {combatant.name} is spared and stable.")
		return self.outcome

	# ============================================================
	def finish(self) -> Outcome :
		"""The GM ends the fight: the side still standing wins, or nobody does."""
		if self.fight.state == ENDED :
			raise CombatError("The fight is already over.")
		standing = {combatant.side_id for combatant in self.fight.combatants if combatant.standing}
		self.end(next(iter(standing)) if len(standing) == 1 else None)
		return self.outcome
