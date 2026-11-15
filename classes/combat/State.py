"""A fight as plain data: the instance, its sides and its combatants.

The engine changes these objects and CombatTransactions saves them, so the rules never deal with database sessions.
"""
import copy
from dataclasses import dataclass, field
from datetime import datetime

# Fight states.
PENDING = "pending"
SETUP = "setup"
ACTIVE = "active"
PAUSED = "paused"
ENDED = "ended"
OPEN_STATES = [PENDING, SETUP, ACTIVE, PAUSED]

PVE = "pve"
PVP = "pvp"
ASYNC = "async"
LIVE = "live"
PACINGS = [ASYNC, LIVE]

# Combatant kinds, controllers and states.
CHARACTER = "character"
NPC = "npc"
PLAYER = "player"
GM = "gm"
AUTO = "auto"
CONTROLLERS = [PLAYER, GM, AUTO]
STANDING = "active"
DOWNED = "downed"
STABLE = "stable"
DYING = "dying"
FLED = "fled"
DEAD = "dead"
REMOVED = "removed"
DOWN_STATES = [DOWNED, STABLE, DYING]
OUT_STATES = [FLED, DEAD, REMOVED]

# The parts of a combatant and of the instance that change during a fight (what undo restores).
COMBATANT_STATE = ["side_id", "controller", "behavior", "hp", "hp_max", "ap", "ap_max", "ac", "dt", "conditions",
                   "ability_uses", "acted", "idle_turns", "state", "death_successes", "death_failures",
                   "last_attacker_id", "weapon_key"]
FIGHT_STATE = ["state", "round", "order", "turn_index", "paused_seconds", "winner_side_id", "pending", "idle_pinged"]


@dataclass
class Side :
	id: int
	name: str
	position: int = 1


@dataclass
class Combatant :
	id: int
	side_id: int
	kind: str
	name: str
	stats: dict = field(default_factory=dict)
	character_id: int | None = None
	uid: int | None = None
	bestiary_id: int | None = None
	controller: str = PLAYER
	behavior: str = "weakest"
	hp: int = 0
	hp_max: int = 0
	ap: int = 0
	ap_max: int = 0
	ac: int = 10
	dt: int = 0
	sequence: int = 0
	conditions: list = field(default_factory=list)
	ability_uses: dict = field(default_factory=dict)
	acted: bool = False
	idle_turns: int = 0
	state: str = STANDING
	death_successes: int = 0
	death_failures: int = 0
	last_attacker_id: int | None = None
	weapon_key: str | None = None
	position: int = 0
	lethal_ok: bool = False

	# ============================================================
	@property
	def standing(self) -> bool :
		return self.state == STANDING

	# ============================================================
	@property
	def down(self) -> bool :
		return self.state in DOWN_STATES

	# ============================================================
	@property
	def out(self) -> bool :
		return self.state in OUT_STATES

	# ============================================================
	@property
	def in_fight(self) -> bool :
		"""Standing or downed: still part of the fight."""
		return not self.out

	# ============================================================
	@property
	def base(self) -> int :
		return int(self.stats.get("base", 5))

	# ============================================================
	@property
	def special(self) -> dict :
		return self.stats.get("special") or {}

	# ============================================================
	@property
	def weapons(self) -> list[dict] :
		return self.stats.get("weapons") or []

	# ============================================================
	@property
	def abilities(self) -> list[dict] :
		return self.stats.get("abilities") or []

	# ============================================================
	@property
	def passives(self) -> list[dict] :
		return self.stats.get("passives") or []

	# ============================================================
	@property
	def items(self) -> list[dict] :
		"""The consumables it carries and hasn't used in this fight."""
		used = set(self.stats.get("used_items") or [])
		return [item for item in self.stats.get("items") or [] if item.get("entry_id") not in used]

	# ============================================================
	def item(self, key: str | None) -> dict | None :
		return next((item for item in self.items if item.get("key") == key), None)

	# ============================================================
	def weapon(self, key: str | None) -> dict | None :
		return next((weapon for weapon in self.weapons if weapon.get("key") == key), None)

	# ============================================================
	def ability(self, ability_id) -> dict | None :
		return next((ability for ability in self.abilities if str(ability.get("id")) == str(ability_id)), None)


@dataclass
class Fight :
	id: int
	guild_id: int
	gm_uid: int
	guid: str = ""
	channel_id: int | None = None
	thread_id: int | None = None
	board_message_id: int | None = None
	co_gms: list = field(default_factory=list)
	kind: str = PVE
	state: str = SETUP
	pacing: str = ASYNC
	lethal: bool = False
	round: int = 0
	order: list = field(default_factory=list)
	turn_index: int = 0
	deadline: datetime | None = None
	paused_seconds: int | None = None
	title: str = "Combat"
	winner_side_id: int | None = None
	late_join: bool = False
	invites: dict = field(default_factory=dict)
	pending: list = field(default_factory=list)
	challenge: dict | None = None
	idle_pinged: list = field(default_factory=list)
	sides: list[Side] = field(default_factory=list)
	combatants: list[Combatant] = field(default_factory=list)

	# ============================================================
	def side(self, side_id) -> Side | None :
		return next((side for side in self.sides if side.id == side_id), None)

	# ============================================================
	def combatant(self, combatant_id) -> Combatant | None :
		return next((combatant for combatant in self.combatants if combatant.id == combatant_id), None)

	# ============================================================
	def members(self, side_id: int, include_out: bool = False) -> list[Combatant] :
		return sorted([combatant for combatant in self.combatants
		               if combatant.side_id == side_id and (include_out or combatant.in_fight)],
		              key=lambda combatant : combatant.position)

	# ============================================================
	def standing(self, side_id: int | None = None) -> list[Combatant] :
		return [combatant for combatant in self.combatants
		        if combatant.standing and (side_id is None or combatant.side_id == side_id)]

	# ============================================================
	def enemies(self, combatant: Combatant, standing_only: bool = True) -> list[Combatant] :
		return [other for other in self.combatants if other.side_id != combatant.side_id
		        and (other.standing if standing_only else other.in_fight)]

	# ============================================================
	def allies(self, combatant: Combatant, include_self: bool = True) -> list[Combatant] :
		return [other for other in self.combatants if other.side_id == combatant.side_id and other.in_fight
		        and (include_self or other.id != combatant.id)]

	# ============================================================
	def of_user(self, uid: int) -> list[Combatant] :
		"""The user's characters in this fight that are still in it."""
		return [combatant for combatant in self.combatants if combatant.uid == uid and combatant.kind == "character"
		        and combatant.in_fight]

	# ============================================================
	def is_gm(self, uid: int, staff: bool = False) -> bool :
		return staff or uid == self.gm_uid or uid in (self.co_gms or [])

	# ============================================================
	@property
	def open(self) -> bool :
		return self.state in OPEN_STATES

	# ============================================================
	def snapshot(self) -> dict :
		"""The parts of the fight that actions change, for undo."""
		return {"fight" : {key : copy.deepcopy(getattr(self, key)) for key in FIGHT_STATE},
		        "combatants" : {str(combatant.id) : {key : copy.deepcopy(getattr(combatant, key))
		                                             for key in COMBATANT_STATE}
		                        for combatant in self.combatants}}

	# ============================================================
	def restore(self, snapshot: dict) -> None :
		for key, value in (snapshot.get("fight") or {}).items() :
			if key in FIGHT_STATE :
				setattr(self, key, copy.deepcopy(value))
		for combatant in self.combatants :
			saved = (snapshot.get("combatants") or {}).get(str(combatant.id))
			if saved is None :
				continue
			for key, value in saved.items() :
				if key in COMBATANT_STATE :
					setattr(combatant, key, copy.deepcopy(value))
