"""The bulk of the effect catalog: themes crossed with technique templates.

The hand-written entries in EffectCatalog.py and PassiveCatalog.py cover the famous powers and spells by name. This
module adds the long tail players ask for ("crystal lance", "blood golem", "crippling spear thrust") by crossing:

- magic themes (taken from the Superpower Wiki's manipulation categories and the usual spell schools: fire, crystal,
  blood, dreams, cards, gravity...) with magic templates (bolt, lance, nova, hex, ward, summon...), and
- physical themes (weapons, natural weapons and fighting styles) with physical templates (flurry, crippling,
  disarming, parry...).

Everything is pitched at a party of about 5th level in D&D terms: spells up to roughly 3rd level, martial tricks a
seasoned fighter or ranger has. Nothing reshapes reality, stops time or wipes out a target in one go; summons are small
helpers (sprites, hounds, wisps), not golems or demons.

A theme says which template groups fit it, its damage type, the light and heavy conditions it inflicts, the boost it
gives and what it summons, so every result is a real catalog effect the engine resolves. Keys are `<theme>_<template>`
and stay stable, because abilities store them; renaming a theme or template key breaks abilities that use it.
Hand-written entries win when a key or name clashes.
"""
from dataclasses import dataclass

from classes.combat import Conditions as C
from classes.combat.Effects import AFFLICT, ATTACK, BLAST, BOOST, CANTRIP, COMPANION, DISPEL, DOOM, Effect, HEAL, \
	MAGIC, NORMAL, PHYSICAL, SELF, SHIELD, WEAK, make

# Conditions a theme may use as its light rider (cheap) and its heavy rider (costly, Weak tier or higher).
LIGHT = {C.BURNING, C.BLEEDING, C.POISONED, C.SLOWED, C.MARKED, C.PRONE, C.BLINDED, C.WEAKENED, C.CORRODED,
         C.WITHERED, C.FRIGHTENED, C.DRAINED, C.VULNERABLE}
HEAVY = {C.STUNNED, C.SILENCED, C.ASLEEP, C.RESTRAINED, C.DISARMED, C.CHARMED, C.CURSED, C.CONFUSED}
# Boosts a theme's veil may give: minor ones cost 2, medium ones 3.
MINOR_BOOSTS = {C.INSPIRED, C.REGENERATING, C.EMPOWERED, C.FORTIFIED, C.BLESSED, C.FOCUSED}
MEDIUM_BOOSTS = {C.HASTED, C.EVASIVE, C.HIDDEN, C.WARDED, C.VAMPIRIC}

# Fighting styles that need no weapon (fists, kicks, elbows); every other weapon theme needs a weapon of its kind.
UNARMED = {"fist", "martial", "elbow"}

# Category names added by this module (the hand-written ones live in EffectCatalog.py).
OBJECTS_CAT = "Objects & craft"
COSMIC_CAT = "Sun, moon & stars"
CHAOS_CAT = "Chaos & wild magic"
BLADES_CAT = "Blades"
BLUNT_CAT = "Blunt weapons"
POLEARMS_CAT = "Spears & polearms"
RANGED_WEAPONS_CAT = "Bows, throwing & firearms"
NATURAL_CAT = "Unarmed & natural weapons"
NEW_CATEGORIES = [OBJECTS_CAT, COSMIC_CAT, CHAOS_CAT, BLADES_CAT, BLUNT_CAT, POLEARMS_CAT, RANGED_WEAPONS_CAT,
                  NATURAL_CAT]


@dataclass(frozen=True)
class Theme :
	"""A magic theme: what its effects deal, inflict, give and summon, and which template groups fit it."""
	key: str
	name: str
	noun: str
	category: str
	type: str | None
	light: str | None
	heavy: str | None
	boost: str | None
	summon: str | None
	groups: str


@dataclass(frozen=True)
class Weapon :
	"""A physical theme: a weapon, natural weapon or fighting style."""
	key: str
	name: str
	verb: str
	noun: str
	category: str
	type: str
	ranged: bool = False


# Groups: S strikes, A areas, C control, D drain and doom, W wards, H support, Z summons.
THEMES = [
	Theme("fire", "Fire", "fire", "Fire & heat", "Fire", C.BURNING, None, C.EMPOWERED, "Flame Sprite", "SACWZ"),
	Theme("magma", "Magma", "molten rock", "Fire & heat", "Fire", C.BURNING, C.RESTRAINED, C.FORTIFIED, "Cinder Hound",
	      "SACWZ"),
	Theme("ash", "Ash", "choking ash", "Fire & heat", "Fire", C.BLINDED, None, C.HIDDEN, "Ash Wisp", "SACWZ"),
	Theme("hellfire", "Hellfire", "hellfire", "Fire & heat", "Fire", C.BURNING, C.CURSED, C.EMPOWERED, "Imp",
	      "SACDZ"),
	Theme("frost", "Frost", "frost", "Water & ice", "Frost", C.SLOWED, C.STUNNED, C.FORTIFIED, "Frost Sprite",
	      "SACWZ"),
	Theme("ice", "Ice", "ice", "Water & ice", "Frost", C.SLOWED, C.RESTRAINED, C.FORTIFIED, "Ice Hound", "SACWZ"),
	Theme("water", "Water", "water", "Water & ice", "Blunt", C.PRONE, C.SILENCED, C.REGENERATING, "Water Sprite",
	      "SACWHZ"),
	Theme("steam", "Steam", "scalding steam", "Water & ice", "Fire", C.BLINDED, None, C.HIDDEN, "Steam Wisp", "SAWZ"),
	Theme("lightning", "Lightning", "lightning", "Lightning & storm", "Lightning", C.DRAINED, C.STUNNED, C.HASTED,
	      "Spark Sprite", "SACWZ"),
	Theme("thunder", "Thunder", "thunder", "Lightning & storm", "Sonic", C.PRONE, C.STUNNED, C.HASTED, "Storm Hawk",
	      "SACZ"),
	Theme("earth", "Earth", "earth", "Earth, stone & metal", "Blunt", C.PRONE, C.RESTRAINED, C.FORTIFIED,
	      "Mud Hound", "SACWZ"),
	Theme("stone", "Stone", "stone", "Earth, stone & metal", "Blunt", C.SLOWED, C.STUNNED, C.FORTIFIED, "Stone Servant",
	      "SACWZ"),
	Theme("crystal", "Crystal", "crystal shards", "Earth, stone & metal", "Piercing", C.BLEEDING, C.RESTRAINED,
	      C.WARDED, "Crystal Familiar", "SACWZ"),
	Theme("metal", "Iron", "iron", "Earth, stone & metal", "Slashing", C.BLEEDING, C.DISARMED, C.FORTIFIED,
	      "Iron Hound", "SACWZ"),
	Theme("sand", "Sand", "sand", "Earth, stone & metal", "Blunt", C.BLINDED, C.RESTRAINED, C.HIDDEN, "Sand Wisp",
	      "SACWZ"),
	Theme("acid", "Acid", "acid", "Earth, stone & metal", "Acid", C.CORRODED, None, None, "Acid Ooze", "SACDZ"),
	Theme("wind", "Wind", "wind", "Air & sound", "Slashing", C.PRONE, None, C.EVASIVE, "Wind Sprite", "SACWZ"),
	Theme("sound", "Sonic", "sound", "Air & sound", "Sonic", C.DRAINED, C.STUNNED, C.INSPIRED, "Echo", "SACWZ"),
	Theme("song", "Song", "song", "Air & sound", None, C.DRAINED, C.CHARMED, C.INSPIRED, "Spectral Singer", "CWHZ"),
	Theme("light", "Light", "light", "Light & holy", "Radiant", C.BLINDED, None, C.BLESSED, "Light Wisp", "SACWHZ"),
	Theme("holy", "Holy", "holy power", "Light & holy", "Radiant", C.BLINDED, C.SILENCED, C.BLESSED,
	      "Spectral Guardian", "SACWHZ"),
	Theme("solar", "Solar", "sunlight", COSMIC_CAT, "Fire", C.BURNING, None, C.EMPOWERED, "Sun Mote", "SAWZ"),
	Theme("star", "Star", "starlight", COSMIC_CAT, "Radiant", C.MARKED, C.STUNNED, C.FOCUSED, "Star Mote", "SACWZ"),
	Theme("lunar", "Lunar", "moonlight", COSMIC_CAT, "Arcane", C.MARKED, C.ASLEEP, C.HIDDEN, "Moon Moth", "SACWZ"),
	Theme("shadow", "Shadow", "shadow", "Shadow & void", "Necrotic", C.BLINDED, C.RESTRAINED, C.HIDDEN,
	      "Shadow Hound", "SACDWZ"),
	Theme("dark", "Dark", "darkness", "Shadow & void", "Necrotic", C.FRIGHTENED, C.CURSED, C.HIDDEN, "Gloom Stalker",
	      "SACDWZ"),
	Theme("dream", "Dream", "dreams", "Mind & psychic", "Mental", C.DRAINED, C.ASLEEP, C.FOCUSED, "Dream Phantom",
	      "SACWZ"),
	Theme("psychic", "Psychic", "psychic force", "Mind & psychic", "Mental", C.WEAKENED, C.STUNNED, C.FOCUSED,
	      "Thought Wisp", "SACWZ"),
	Theme("dread", "Dread", "dread", "Mind & psychic", "Mental", C.FRIGHTENED, C.CURSED, None, "Dread Wisp",
	      "SCDZ"),
	Theme("phantasm", "Phantasmal", "illusion", "Mind & psychic", "Mental", C.MARKED, C.CONFUSED, C.HIDDEN,
	      "Phantasmal Double", "SCWZ"),
	Theme("force", "Force", "force", "Force & telekinesis", "Arcane", C.PRONE, C.RESTRAINED, C.FORTIFIED,
	      "Spectral Hand", "SACWZ"),
	Theme("arcane", "Arcane", "arcane power", "Force & telekinesis", "Arcane", C.MARKED, C.SILENCED, C.FOCUSED,
	      "Arcane Familiar", "SACWZ"),
	Theme("rune", "Rune", "runes", "Force & telekinesis", "Arcane", C.MARKED, C.SILENCED, C.WARDED, "Rune Sentinel",
	      "SACWZ"),
	Theme("chaos", "Chaos", "chaos", CHAOS_CAT, "Arcane", C.VULNERABLE, C.CONFUSED, C.EMPOWERED, "Chaos Imp",
	      "SACDZ"),
	Theme("blood", "Blood", "blood", "Death, blood & decay", "Necrotic", C.BLEEDING, C.STUNNED, C.VAMPIRIC,
	      "Blood Leech", "SACDWZ"),
	Theme("bone", "Bone", "bone", "Death, blood & decay", "Piercing", C.BLEEDING, C.RESTRAINED, C.FORTIFIED,
	      "Skeleton", "SACWZ"),
	Theme("death", "Death", "death", "Death, blood & decay", "Necrotic", C.WITHERED, C.CURSED, C.VAMPIRIC,
	      "Zombie", "SACDZ"),
	Theme("rot", "Rot", "rot", "Death, blood & decay", "Poison", C.POISONED, None, None, "Rot Ghoul", "SACDZ"),
	Theme("soul", "Soul", "soul energy", "Death, blood & decay", "Necrotic", C.DRAINED, C.SILENCED, C.BLESSED,
	      "Spirit Guide", "SACDWHZ"),
	Theme("thorn", "Thorn", "thorns", "Nature, beasts & poison", "Slashing", C.BLEEDING, C.RESTRAINED,
	      C.REGENERATING, "Thorn Creeper", "SACWHZ"),
	Theme("venom", "Venom", "venom", "Nature, beasts & poison", "Poison", C.POISONED, C.ASLEEP, None,
	      "Venom Serpent", "SACDZ"),
	Theme("primal", "Primal", "primal fury", "Nature, beasts & poison", "Slashing", C.BLEEDING, C.STUNNED,
	      C.EMPOWERED, "Spirit Wolf", "SACWZ"),
	Theme("spore", "Spore", "spores", "Nature, beasts & poison", "Poison", C.POISONED, C.ASLEEP, None,
	      "Fungal Creeper", "SACZ"),
	Theme("life", "Life", "life", "Life & healing", None, None, None, C.REGENERATING, "Life Wisp", "WHZ"),
	Theme("card", "Card", "razor-edged cards", OBJECTS_CAT, "Slashing", C.BLEEDING, C.CONFUSED, C.EVASIVE,
	      "Card Soldier", "SACWZ"),
	Theme("thread", "Thread", "threads", OBJECTS_CAT, "Slashing", C.BLEEDING, C.RESTRAINED, C.EVASIVE, "Puppet",
	      "SCWZ"),
	Theme("chain", "Chain", "chains", OBJECTS_CAT, "Blunt", C.PRONE, C.RESTRAINED, C.FORTIFIED, "Animated Chains",
	      "SACWZ"),
	Theme("mirror", "Mirror", "mirrors", OBJECTS_CAT, "Arcane", C.BLINDED, C.CONFUSED, C.EVASIVE, "Mirror Double",
	      "SCWZ"),
	Theme("ink", "Ink", "living ink", OBJECTS_CAT, "Arcane", C.BLINDED, C.RESTRAINED, C.HIDDEN, "Ink Beast", "SACWZ"),
]

WEAPONS = [
	Weapon("sword", "Sword", "Cut", "sword", BLADES_CAT, "Slashing"),
	Weapon("greatsword", "Greatsword", "Cleave", "greatsword", BLADES_CAT, "Slashing"),
	Weapon("axe", "Axe", "Chop", "axe", BLADES_CAT, "Slashing"),
	Weapon("dagger", "Dagger", "Stab", "dagger", BLADES_CAT, "Piercing"),
	Weapon("rapier", "Rapier", "Lunge", "rapier", BLADES_CAT, "Piercing"),
	Weapon("scimitar", "Scimitar", "Slash", "scimitar", BLADES_CAT, "Slashing"),
	Weapon("scythe", "Scythe", "Reap", "scythe", BLADES_CAT, "Slashing"),
	Weapon("whip", "Whip", "Lash", "whip", BLADES_CAT, "Slashing"),
	Weapon("mace", "Mace", "Blow", "mace", BLUNT_CAT, "Blunt"),
	Weapon("hammer", "Hammer", "Smash", "hammer", BLUNT_CAT, "Blunt"),
	Weapon("flail", "Flail", "Swing", "flail", BLUNT_CAT, "Blunt"),
	Weapon("staff", "Staff", "Sweep", "staff", BLUNT_CAT, "Blunt"),
	Weapon("club", "Club", "Bash", "club", BLUNT_CAT, "Blunt"),
	Weapon("shield", "Shield", "Slam", "shield", BLUNT_CAT, "Blunt"),
	Weapon("chain", "Chain", "Whirl", "chain", BLUNT_CAT, "Blunt"),
	Weapon("spear", "Spear", "Thrust", "spear", POLEARMS_CAT, "Piercing"),
	Weapon("halberd", "Halberd", "Hack", "halberd", POLEARMS_CAT, "Slashing"),
	Weapon("lance", "Lance", "Charge", "lance", POLEARMS_CAT, "Piercing"),
	Weapon("trident", "Trident", "Jab", "trident", POLEARMS_CAT, "Piercing"),
	Weapon("glaive", "Glaive", "Arc", "glaive", POLEARMS_CAT, "Slashing"),
	Weapon("bow", "Bow", "Shot", "bow", RANGED_WEAPONS_CAT, "Piercing", True),
	Weapon("crossbow", "Crossbow", "Quarrel", "crossbow", RANGED_WEAPONS_CAT, "Piercing", True),
	Weapon("sling", "Sling", "Stone", "sling", RANGED_WEAPONS_CAT, "Blunt", True),
	Weapon("javelin", "Javelin", "Throw", "javelin", RANGED_WEAPONS_CAT, "Piercing", True),
	Weapon("hatchet", "Hatchet", "Toss", "throwing hatchet", RANGED_WEAPONS_CAT, "Slashing", True),
	Weapon("shuriken", "Shuriken", "Flick", "throwing stars", RANGED_WEAPONS_CAT, "Slashing", True),
	Weapon("pistol", "Pistol", "Shot", "pistol", RANGED_WEAPONS_CAT, "Piercing", True),
	Weapon("rifle", "Rifle", "Round", "rifle", RANGED_WEAPONS_CAT, "Piercing", True),
	Weapon("scattergun", "Scattergun", "Blast", "scattergun", RANGED_WEAPONS_CAT, "Piercing", True),
	Weapon("fist", "Fist", "Punch", "fists", NATURAL_CAT, "Blunt"),
	Weapon("martial", "Martial", "Kick", "feet", NATURAL_CAT, "Blunt"),
	Weapon("elbow", "Elbow", "Strike", "elbows and knees", NATURAL_CAT, "Blunt"),
	Weapon("claw", "Claw", "Swipe", "claws", NATURAL_CAT, "Slashing"),
	Weapon("fang", "Fang", "Bite", "fangs", NATURAL_CAT, "Piercing"),
	Weapon("horn", "Horn", "Gore", "horns", NATURAL_CAT, "Piercing"),
	Weapon("tail", "Tail", "Lash", "tail", NATURAL_CAT, "Blunt"),
	Weapon("wing", "Wing", "Buffet", "wings", NATURAL_CAT, "Blunt"),
	Weapon("tentacle", "Tentacle", "Crush", "tentacles", NATURAL_CAT, "Blunt"),
]


# ============================================================
def _label(name: str | None) -> str :
	return C.label(name).lower() if name else ""


# ============================================================
def magic_effects(theme: Theme) -> list[Effect] :
	"""Every magic template that fits the theme."""
	n, t, found = theme.noun, theme.type, []
	key = theme.key

	def add(template: str, name: str, mechanic: str, cost: int, text: str, tier: str = CANTRIP, aim: str = "",
	        **params) :
		params = {name : value for name, value in params.items() if value is not None}
		found.append(make(f"{key}_{template}", name, MAGIC, theme.category, mechanic, cost, text, tier, aim, **params))

	A = theme.name
	if "S" in theme.groups and t :
		add("bolt", f"{A} Bolt", ATTACK, 2, f"a bolt of {n}", type=t)
		add("lance", f"{A} Lance", ATTACK, 3, f"a lance of {n} that pierces armor", type=t, ignore_dt=True)
		add("barrage", f"{A} Barrage", ATTACK, 3, f"a barrage of {n}", type=t, hits=2)
		add("dart", f"{A} Dart", ATTACK, 3, f"a quick, sure dart of {n}", type=t, accuracy=2)
		add("rend", f"{A} Rend", ATTACK, 3, f"a tearing blast of {n}", type=t, steps=1)
		add("judgement", f"{A} Judgement", ATTACK, 3, f"{n} that finishes the wounded", type=t, execute=True)
		if theme.light :
			add("brand", f"{A} Brand", ATTACK, 3, f"{n} that leaves the target {_label(theme.light)}", type=t,
			    on_hit=theme.light)
		if theme.heavy :
			add("smite", f"{A} Smite", ATTACK, 4, f"{n} that leaves the target {_label(theme.heavy)}", WEAK, type=t,
			    on_hit=theme.heavy)
	if "A" in theme.groups and t :
		add("burst", f"{A} Burst", BLAST, 2, f"a burst of {n}, dodged for half", type=t)
		add("nova", f"{A} Nova", BLAST, 3, f"a nova of {n}", WEAK, type=t, steps=1)
		add("storm", f"{A} Storm", BLAST, 4, f"a storm of {n}", NORMAL, type=t, steps=1, on_fail=theme.light)
		if theme.light :
			add("wave", f"{A} Wave", BLAST, 3, f"a wave of {n} that leaves targets {_label(theme.light)}", type=t,
			    on_fail=theme.light)
	if "C" in theme.groups :
		if theme.light :
			add("hex", f"{A} Hex", AFFLICT, 2, f"a hex of {n}: {_label(theme.light)}", condition=theme.light)
		if theme.heavy :
			add("torment", f"{A} Torment", AFFLICT, 4, f"{n} that leaves the target {_label(theme.heavy)}", WEAK,
			    condition=theme.heavy)
		if theme.heavy != C.RESTRAINED :
			add("grasp", f"{A} Grasp", AFFLICT, 3, f"{n} holds the target fast", condition=C.RESTRAINED)
		add("curse", f"{A} Curse", AFFLICT, 2, f"{n} that opens the target to harm", condition=C.VULNERABLE)
		add("purge", f"{A} Purge", DISPEL, 2, f"{n} that strips away protections", count=1)
	if "D" in theme.groups :
		if t :
			add("leech", f"{A} Leech", ATTACK, 3, f"{n} that drains the target's life", type=t, drain=True)
		add("doom", f"{A} Doom", DOOM, 3, f"{n} that dooms the target", NORMAL)
	if "W" in theme.groups :
		add("ward", f"{A} Ward", SHIELD, 2, f"a shield of {n}")
		add("aegis", f"{A} Aegis", SHIELD, 3, f"a great shield of {n}", WEAK, steps=1)
		add("armor", f"{A} Armor", BOOST, 1, f"armor of {n} on yourself", aim=SELF, condition=C.FORTIFIED,
		    turns=2)
		add("mantle", f"{A} Mantle", BOOST, 2, f"{n} that hurts anyone who strikes you", aim=SELF, condition=C.THORNS)
		if theme.boost in MINOR_BOOSTS | MEDIUM_BOOSTS :
			add("veil", f"{A} Veil", BOOST, 3 if theme.boost in MEDIUM_BOOSTS else 2,
			    f"a veil of {n}: {_label(theme.boost)}", condition=theme.boost)
	if "H" in theme.groups :
		add("blessing", f"{A} Blessing", BOOST, 2, f"{n} that strengthens an ally", condition=C.EMPOWERED)
		add("mending", f"{A} Mending", HEAL, 2, f"{n} that heals")
		add("renewal", f"{A} Renewal", HEAL, 3, f"{n} that heals and purifies", WEAK, cleanse=True)
	if "Z" in theme.groups and theme.summon :
		add("summon", theme.summon, COMPANION, 3, f"summons a {theme.summon.lower()}", WEAK, type=t)
	return found


# ============================================================
def physical_effects(weapon: Weapon) -> list[Effect] :
	"""Every physical template that fits the weapon."""
	W, V, n, t, found = weapon.name, weapon.verb, weapon.noun, weapon.type, []
	base = f"{W} {V}"

	def add(template: str, name: str, mechanic: str, cost: int, text: str, tier: str = CANTRIP, aim: str = "",
	        **params) :
		if weapon.key not in UNARMED :
			params["requires"] = weapon.key
		found.append(make(f"{weapon.key}_{template}", name, PHYSICAL, weapon.category, mechanic, cost, text, tier,
		                  aim, **params))

	add("strike", base, ATTACK, 2, f"a solid {V.lower()} with the {n}", type=t)
	add("piercing", f"Piercing {base}", ATTACK, 3, f"a {V.lower()} through the gaps in armor", type=t,
	    ignore_dt=True)
	add("crippling", f"Crippling {base}", ATTACK, 3, f"a {V.lower()} that slows the target", type=t,
	    on_hit=C.SLOWED)
	add("toppling", f"Toppling {base}", ATTACK, 3, f"a {V.lower()} that knocks the target down", type=t,
	    on_hit=C.PRONE)
	add("pinning", f"Pinning {base}", ATTACK, 3, f"a {V.lower()} that pins the target in place", type=t,
	    on_hit=C.RESTRAINED)
	add("disarming", f"Disarming {base}", ATTACK, 4, f"a {V.lower()} that knocks the weapon away", WEAK, type=t,
	    on_hit=C.DISARMED)
	add("stunning", f"Stunning {base}", ATTACK, 4, f"a {V.lower()} that leaves the target reeling", WEAK, type=t,
	    on_hit=C.STUNNED)
	add("precise", f"Precise {base}", ATTACK, 3, f"a careful {V.lower()} that rarely misses", type=t, accuracy=2)
	add("vital", f"Vital {base}", ATTACK, 3, f"a {V.lower()} at a vital point", type=t, crit=2)
	add("finishing", f"Finishing {base}", ATTACK, 3, f"a {V.lower()} that finishes off the wounded", type=t,
	    execute=True)
	add("mighty", f"Mighty {base}", ATTACK, 3, f"a {V.lower()} with everything behind it", type=t, steps=1)
	add("hunters", f"Hunter's {base}", ATTACK, 3, f"a {V.lower()} that marks the target for the party", type=t,
	    on_hit=C.MARKED)
	if t == "Blunt" :
		add("bruising", f"Bruising {base}", ATTACK, 3, f"a {V.lower()} that saps the target's strength", type=t,
		    on_hit=C.WEAKENED)
	else :
		add("bleeding", f"Bleeding {base}", ATTACK, 3, f"a {V.lower()} that leaves a bleeding wound", type=t,
		    on_hit=C.BLEEDING)
	if weapon.ranged :
		add("double", f"Double {base}", ATTACK, 3, f"two quick shots with the {n}", type=t, hits=2)
		add("volley", f"{W} Volley", BLAST, 3, f"a volley from the {n}, dodged for half", WEAK, type=t)
		add("suppressing", f"Suppressing {W} Fire", AFFLICT, 2, f"shots from the {n} keep the target pinned down",
		    condition=C.PRONE)
	else :
		add("flurry", f"{W} Flurry", ATTACK, 3, f"a rapid series of blows with the {n}", type=t, hits=2)
		add("whirlwind", f"{W} Whirlwind", BLAST, 3, f"a spinning sweep of the {n}, dodged for half", WEAK, type=t)
		add("parry", f"{W} Parry", BOOST, 2, f"turns the next blow aside with the {n}", aim=SELF,
		    condition=C.EVASIVE)
		add("guard", f"{W} Guard", BOOST, 1, f"a defensive stance with the {n}", aim=SELF, condition=C.FORTIFIED,
		    turns=2)
		add("riposte", f"{W} Riposte", BOOST, 2, f"answers every missed blow with the {n}", aim=SELF,
		    condition=C.RIPOSTE)
		add("feint", f"{W} Feint", AFFLICT, 2, f"a feint with the {n} that leaves the target open",
		    condition=C.VULNERABLE)
	return found


# ============================================================
def theme_passives(theme: Theme) -> list[Effect] :
	"""Magic passive effects for a theme: affinity, attunement, resistance, absorption, an immunity and an infusion."""
	from classes.combat.Passives import BONUS, DAMAGE, IMMUNE, ON_STRONG_HIT, RESIST, STACKS, TO_HIT, TRIGGER

	found, t, A, n = [], theme.type, theme.name, theme.noun
	if t :
		found.append(make(f"{theme.key}_affinity", f"{A} Affinity", MAGIC, "Offense", BONUS, 1,
		                  f"{t} hits deal more ({n})", field=DAMAGE, scope=t))
		found.append(make(f"{theme.key}_attunement", f"{A} Attunement", MAGIC, "Offense", BONUS, 1,
		                  f"{t} attacks hit more often ({n})", field=TO_HIT, scope=t))
		found.append(make(f"{theme.key}_resistance", f"{A} Resistance", MAGIC, "Resistances & immunities", RESIST, 1,
		                  f"{t} hits do less ({n})", scope=t))
		found.append(make(f"{theme.key}_absorption", f"{A} Absorption", MAGIC, "Growth", STACKS, 1,
		                  f"each {t} hit taken makes you hit harder ({n})", field=DAMAGE, scope=t))
	if theme.light :
		found.append(make(f"{theme.key}_heart", f"{A} Heart", MAGIC, "Resistances & immunities", IMMUNE, 1,
		                  f"can't be {_label(theme.light)}", NORMAL, condition=theme.light))
		found.append(make(f"{theme.key}_infusion", f"{A} Infusion", MAGIC, "Offense", TRIGGER, 1,
		                  f"strong hits leave the target {_label(theme.light)}", trigger=ON_STRONG_HIT,
		                  condition=theme.light))
	return found


# ============================================================
def weapon_passives(weapon: Weapon) -> list[Effect] :
	"""Physical passive effects for a weapon: mastery (damage) and training (to hit) with its damage type or range."""
	from classes.combat.Passives import BONUS, DAMAGE, RANGED, TO_HIT

	scope = RANGED if weapon.ranged else weapon.type
	what = "ranged attacks" if weapon.ranged else f"{weapon.type} attacks"
	return [make(f"{weapon.key}_mastery", f"{weapon.name} Mastery", PHYSICAL, "Offense", BONUS, 1,
	             f"a {weapon.noun} expert: more damage with {what}", field=DAMAGE, scope=scope),
	        make(f"{weapon.key}_training", f"{weapon.name} Training", PHYSICAL, "Offense", BONUS, 1,
	             f"drilled with the {weapon.noun}: {what} hit more often", field=TO_HIT, scope=scope)]


# ============================================================
def merge(handmade: list[Effect], generated: list[Effect]) -> list[Effect] :
	"""The hand-written entries followed by the generated ones whose key and name are still free."""
	keys = {effect.key for effect in handmade}
	names = {effect.name.lower() for effect in handmade}
	merged = list(handmade)
	for effect in generated :
		if effect.key in keys or effect.name.lower() in names :
			continue
		keys.add(effect.key)
		names.add(effect.name.lower())
		merged.append(effect)
	return merged


# ============================================================
def active() -> list[Effect] :
	found = []
	for theme in THEMES :
		found += magic_effects(theme)
	for weapon in WEAPONS :
		found += physical_effects(weapon)
	return found


# ============================================================
def passive() -> list[Effect] :
	found = []
	for theme in THEMES :
		found += theme_passives(theme)
	for weapon in WEAPONS :
		found += weapon_passives(weapon)
	return found
