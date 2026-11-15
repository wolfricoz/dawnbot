"""The active effect catalog: every effect a spell or an active ability can be built from.

Ideas come from the Superpower Wiki's categories, lists of spells, D&D and other fantasy games. Many entries share a
mechanic and differ in damage type, condition and cost, so players can find the power they have in mind by its name.
Everything is pitched at a party of about 5th level in D&D terms (spells up to roughly 3rd level), so nothing stops
time, banishes, disintegrates or takes over a mind. The entries below are written by hand; GeneratedEffects.py adds
about 1,700 more by crossing themes (crystal, blood, dreams, cards...) and weapons with technique templates.
Magic effects are for spells, physical ones for abilities. See classes/combat/Effects.py for what each mechanic does.

Costs, roughly: an attack, blast or heal 2; with a light rider (burning, slowed, marked...) 3; with a heavy one
(stunned, silenced, disarmed...) 4. Conditions without damage 2 to 4, boosts 2 to 4 (1 less when they only work on
the user). Modifiers add 1 to 4, drawbacks take 1 off.
"""
from classes.combat import Conditions as C, GeneratedEffects
from classes.combat.Effects import AFFLICT, AREA, ATTACK, BACKLASH, BLAST, BLOOD, BOOST, CANTRIP, CLEANSE, COMPANION, \
	DISPEL, DOOM, DRAWBACK, ESCAPE, EXHAUST, Effect, HEAL, LINGERING, MAGIC, MASS, MODIFIER, NORMAL, ONCE, OVERCHARGE, \
	PHYSICAL, PRECISE, RECKLESS, REVIVE, SELF, SHIELD, STRONG, WEAK, WEAKEN, index, make

M = MAGIC
P = PHYSICAL

FIRE = "Fire"
FROST = "Frost"
LIGHTNING = "Lightning"
ARCANE = "Arcane"
POISON = "Poison"
RADIANT = "Radiant"
MENTAL = "Mental"
SLASHING = "Slashing"
PIERCING = "Piercing"
BLUNT = "Blunt"
ACID = "Acid"
NECROTIC = "Necrotic"
SONIC = "Sonic"

# Category names, in the order /ability effects lists them.
GENERAL = "General"
FIRE_CAT = "Fire & heat"
WATER_CAT = "Water & ice"
STORM_CAT = "Lightning & storm"
EARTH_CAT = "Earth, stone & metal"
AIR_CAT = "Air & sound"
LIGHT_CAT = "Light & holy"
SHADOW_CAT = "Shadow & void"
DEATH_CAT = "Death, blood & decay"
NATURE_CAT = "Nature, beasts & poison"
MIND_CAT = "Mind & psychic"
FORCE_CAT = "Force & telekinesis"
SPACE_CAT = "Space, time & gravity"
LIFE_CAT = "Life & healing"
WARD_CAT = "Protection & wards"
CURSE_CAT = "Curses & hexes"
SUMMON_CAT = "Summoning & creation"
BODY_CAT = "Body & transformation"
MARTIAL_CAT = "Martial arts & weapons"
ARCHERY_CAT = "Ranged & thrown"
TACTICS_CAT = "Tactics & leadership"
STEALTH_CAT = "Stealth & trickery"
GRIT_CAT = "Grit & endurance"
GADGET_CAT = "Alchemy & gadgets"
MODIFIER_CAT = "Modifiers"
DRAWBACK_CAT = "Drawbacks"
CATEGORIES = [GENERAL, FIRE_CAT, WATER_CAT, STORM_CAT, EARTH_CAT, AIR_CAT, LIGHT_CAT, SHADOW_CAT, DEATH_CAT,
              NATURE_CAT, MIND_CAT, FORCE_CAT, SPACE_CAT, LIFE_CAT, WARD_CAT, CURSE_CAT, SUMMON_CAT, BODY_CAT,
              MARTIAL_CAT, ARCHERY_CAT, TACTICS_CAT, STEALTH_CAT, GRIT_CAT, GADGET_CAT] \
             + GeneratedEffects.NEW_CATEGORIES + [MODIFIER_CAT, DRAWBACK_CAT]


# ============================================================
def attack(key: str, name: str, realm: str, category: str, cost: int, text: str, type: str | None = None,
           tier: str = CANTRIP, **params) -> Effect :
	if type :
		params["type"] = type
	return make(key, name, realm, category, ATTACK, cost, text, tier, **params)


# ============================================================
def blast(key: str, name: str, realm: str, category: str, cost: int, text: str, type: str | None = None,
          save: str = "agility", tier: str = CANTRIP, **params) -> Effect :
	if type :
		params["type"] = type
	return make(key, name, realm, category, BLAST, cost, text, tier, save=save, **params)


# ============================================================
def afflict(key: str, name: str, realm: str, category: str, cost: int, text: str, condition: str,
            tier: str = CANTRIP, **params) -> Effect :
	return make(key, name, realm, category, AFFLICT, cost, text, tier, condition=condition, **params)


# ============================================================
def boost(key: str, name: str, realm: str, category: str, cost: int, text: str, condition: str,
          tier: str = CANTRIP, aim: str = "", **params) -> Effect :
	return make(key, name, realm, category, BOOST, cost, text, tier, aim, condition=condition, **params)


ACTIVE_EFFECTS = [
	# == General: plain building blocks that take the ability's own damage type ==
	attack("bolt", "Bolt", M, GENERAL, 2, "a bolt of raw magic in the ability's damage type"),
	blast("burst", "Burst", M, GENERAL, 2, "an explosion of magic the target can dodge for half"),
	make("mend", "Mend", M, GENERAL, HEAL, 2, "closes wounds with magic"),
	make("ward", "Ward", M, GENERAL, SHIELD, 2, "a magic barrier that soaks up damage"),
	attack("strike", "Strike", P, GENERAL, 2, "a hard, well-placed blow in the ability's damage type"),
	blast("sweep", "Sweep", P, GENERAL, 2, "a wide swing or volley the target can dodge for half"),
	make("first_aid", "First Aid", P, GENERAL, HEAL, 2, "bandages and quick field care"),
	make("guard", "Guard", P, GENERAL, SHIELD, 2, "puts yourself or a shield between an ally and harm"),

	# == Fire & heat ==
	attack("fire_bolt", "Fire Bolt", M, FIRE_CAT, 2, "a mote of flame hurled at the target", FIRE),
	attack("pyrokinesis", "Pyrokinesis", M, FIRE_CAT, 3, "sets the target alight with your mind", FIRE,
	       on_hit=C.BURNING),
	blast("fireball", "Fireball", M, FIRE_CAT, 2, "a ball of fire that bursts on impact", FIRE),
	blast("flame_wave", "Flame Wave", M, FIRE_CAT, 3, "a wall of fire rolls over the target", FIRE,
	      on_fail=C.BURNING),
	attack("scorching_ray", "Scorching Ray", M, FIRE_CAT, 3, "several thin rays of heat", FIRE, hits=2),
	afflict("immolate", "Immolate", M, FIRE_CAT, 2, "wraps the target in clinging flames", C.BURNING),
	attack("searing_smite", "Searing Smite", M, FIRE_CAT, 3, "white-hot heat that melts through armor", FIRE,
	       ignore_dt=True),
	blast("inferno", "Wall of Fire", M, FIRE_CAT, 4, "a sheet of roaring flame", FIRE, tier=NORMAL, steps=1,
	      on_fail=C.BURNING),
	attack("magma_fist", "Magma Fist", M, FIRE_CAT, 3, "a fist of molten rock", FIRE, steps=1),
	afflict("heat_metal", "Heat Metal", M, FIRE_CAT, 3, "makes the target's weapon too hot to hold", C.DISARMED,
	        tier=WEAK),
	boost("fire_shield", "Fire Shield", M, FIRE_CAT, 3, "flames that burn anyone who strikes the target",
	      C.THORNS),
	attack("fire_breath", "Fire Breath", P, FIRE_CAT, 3, "breathes fire like a dragon", FIRE, on_hit=C.BURNING),
	attack("flaming_strike", "Flaming Strike", P, FIRE_CAT, 2, "a strike with a burning weapon or fist", FIRE),

	# == Water & ice ==
	attack("ray_of_frost", "Ray of Frost", M, WATER_CAT, 3, "a freezing beam that numbs the target", FROST,
	       on_hit=C.SLOWED),
	attack("ice_lance", "Ice Lance", M, WATER_CAT, 3, "a spear of ice that pierces armor", FROST, ignore_dt=True),
	blast("cone_of_cold", "Cone of Cold", M, WATER_CAT, 3, "a blast of bitter cold", FROST, save="endurance",
	      on_fail=C.SLOWED),
	afflict("flash_freeze", "Flash Freeze", M, WATER_CAT, 4, "encases the target in ice", C.STUNNED, tier=WEAK),
	afflict("frostbite", "Frostbite", M, WATER_CAT, 2, "frost creeps into the target's limbs", C.SLOWED),
	blast("blizzard", "Blizzard", M, WATER_CAT, 4, "a howling storm of ice and snow", FROST, save="endurance",
	      tier=NORMAL, steps=1, on_fail=C.SLOWED),
	attack("hydrokinesis", "Hydrokinesis", M, WATER_CAT, 3, "a crushing jet of water that knocks the target down",
	       BLUNT, on_hit=C.PRONE),
	afflict("drown", "Drown", M, WATER_CAT, 3, "fills the target's lungs with water", C.SILENCED, tier=WEAK),
	boost("ice_armor", "Ice Armor", M, WATER_CAT, 2, "a coat of hard ice", C.FORTIFIED),
	attack("tidal_slam", "Tidal Slam", M, WATER_CAT, 3, "a wave slams into the target", BLUNT, steps=1),
	afflict("ice_shackles", "Ice Shackles", M, WATER_CAT, 3, "ice locks the target's feet in place", C.RESTRAINED),

	# == Lightning & storm ==
	attack("shocking_grasp", "Shocking Grasp", M, STORM_CAT, 2, "a jolt of electricity through a touch", LIGHTNING,
	       accuracy=2),
	attack("lightning_bolt", "Lightning Bolt", M, STORM_CAT, 3, "a bolt of lightning", LIGHTNING, steps=1),
	attack("electrokinesis", "Electrokinesis", M, STORM_CAT, 4, "a current that locks up the target's muscles",
	       LIGHTNING, tier=WEAK, on_hit=C.STUNNED),
	blast("chain_lightning", "Chain Lightning", M, STORM_CAT, 3, "lightning that leaps between targets", LIGHTNING,
	      tier=WEAK),
	blast("thunderclap", "Thunderclap", M, STORM_CAT, 3, "a deafening boom", SONIC, save="endurance",
	      on_fail=C.PRONE),
	blast("call_lightning", "Call Lightning", M, STORM_CAT, 4, "lightning from the sky", LIGHTNING, tier=NORMAL,
	      steps=1),
	afflict("static_field", "Static Field", M, STORM_CAT, 3, "static saps the target's strength", C.DRAINED),
	boost("storm_speed", "Storm Speed", M, STORM_CAT, 3, "lightning in the veins makes the target faster",
	      C.HASTED),
	attack("thunder_strike", "Thunder Strike", P, STORM_CAT, 3, "a blow with a crack of thunder", SONIC,
	       on_hit=C.PRONE),

	# == Earth, stone & metal ==
	attack("stone_spike", "Stone Spike", M, EARTH_CAT, 2, "a spike of rock bursts from the ground", PIERCING),
	attack("geokinesis", "Geokinesis", M, EARTH_CAT, 3, "hurls a boulder", BLUNT, steps=1),
	blast("earthquake", "Tremor", M, EARTH_CAT, 4, "the ground heaves under the target", BLUNT, tier=NORMAL,
	      on_fail=C.PRONE),
	afflict("entomb", "Entomb", M, EARTH_CAT, 3, "stone closes around the target's legs", C.RESTRAINED),
	boost("stoneskin", "Stoneskin", M, EARTH_CAT, 2, "skin as hard as rock", C.FORTIFIED),
	attack("metal_shards", "Metal Shards", M, EARTH_CAT, 3, "a storm of razor-sharp metal", SLASHING,
	       on_hit=C.BLEEDING),
	afflict("magnetize", "Magnetize", M, EARTH_CAT, 3, "rips the target's weapon from its hands", C.DISARMED,
	        tier=WEAK),
	attack("acid_splash", "Acid Splash", M, EARTH_CAT, 3, "a glob of acid that eats armor", ACID,
	       on_hit=C.CORRODED),
	attack("ground_slam", "Ground Slam", P, EARTH_CAT, 3, "smashes the ground to knock the target off its feet",
	       BLUNT, on_hit=C.PRONE),

	# == Air & sound ==
	attack("gust", "Gust", M, AIR_CAT, 3, "a blast of wind that knocks the target over", BLUNT, on_hit=C.PRONE),
	blast("tornado", "Dust Devil", M, AIR_CAT, 4, "a small whirlwind of grit and air", BLUNT, tier=NORMAL, steps=1),
	afflict("suffocate", "Suffocate", M, AIR_CAT, 3, "pulls the air from the target's lungs", C.SILENCED,
	        tier=WEAK),
	attack("wind_blade", "Wind Blade", M, AIR_CAT, 3, "an invisible blade of air", SLASHING, accuracy=2),
	blast("sonic_scream", "Sonic Scream", M, AIR_CAT, 3, "a scream that shatters stone", SONIC,
	      save="endurance", on_fail=C.DRAINED),
	afflict("deafening_silence", "Silence", M, AIR_CAT, 3, "no sound reaches the target", C.SILENCED),
	boost("tailwind", "Tailwind", M, AIR_CAT, 3, "the wind carries the target", C.HASTED),
	boost("wind_wall", "Wind Wall", M, AIR_CAT, 3, "howling wind turns arrows aside", C.EVASIVE),
	blast("war_cry_blast", "Thunderous Roar", P, AIR_CAT, 3, "a roar that rattles everyone nearby", SONIC,
	      save="charisma", on_fail=C.FRIGHTENED),

	# == Light & holy ==
	attack("sacred_flame", "Sacred Flame", M, LIGHT_CAT, 2, "radiant fire from above", RADIANT, accuracy=1),
	attack("guiding_bolt", "Guiding Bolt", M, LIGHT_CAT, 3, "a flash of light that marks the target", RADIANT,
	       on_hit=C.MARKED),
	afflict("blinding_light", "Blinding Light", M, LIGHT_CAT, 2, "a flash that blinds", C.BLINDED),
	attack("smite", "Smite", M, LIGHT_CAT, 3, "divine power through a strike, hardest on the wounded", RADIANT,
	       execute=True),
	blast("sunburst", "Radiant Flash", M, LIGHT_CAT, 4, "a flash of searing light", RADIANT, save="perception",
	      tier=NORMAL, on_fail=C.BLINDED),
	attack("photokinesis", "Photokinesis", M, LIGHT_CAT, 3, "a beam of concentrated light", RADIANT, steps=1),
	boost("bless", "Bless", M, LIGHT_CAT, 2, "a blessing that steadies the target", C.BLESSED),
	boost("divine_favor", "Divine Favor", M, LIGHT_CAT, 2, "the gods guide the target's hand", C.INSPIRED),
	make("turn_undead", "Turn", M, LIGHT_CAT, AFFLICT, 3, "holy power that sends the unholy fleeing", WEAK,
	     condition=C.FRIGHTENED, save="charisma"),
	make("holy_purge", "Holy Purge", M, LIGHT_CAT, DISPEL, 2, "burns away the target's protections", count=1),

	# == Shadow & void ==
	attack("shadow_bolt", "Shadow Bolt", M, SHADOW_CAT, 2, "a bolt of living darkness", NECROTIC),
	afflict("darkness", "Darkness", M, SHADOW_CAT, 2, "magical darkness swallows the target's sight", C.BLINDED),
	boost("shadow_cloak", "Shadow Cloak", M, SHADOW_CAT, 3, "the target melts into the shadows", C.HIDDEN),
	attack("umbrakinesis", "Umbrakinesis", M, SHADOW_CAT, 3, "shadows lash and hold the target", NECROTIC,
	       on_hit=C.RESTRAINED),
	afflict("void_touch", "Void Touch", M, SHADOW_CAT, 3, "the void gnaws at the target's will", C.DRAINED),
	afflict("nightmare", "Nightmare", M, SHADOW_CAT, 3, "visions of terror", C.FRIGHTENED),
	make("eclipse", "Snuff Magic", M, SHADOW_CAT, DISPEL, 3, "darkness snuffs out the target's magic", WEAK, count=2),

	# == Death, blood & decay ==
	attack("life_drain", "Life Drain", M, DEATH_CAT, 3, "steals the target's life force", NECROTIC, drain=True),
	attack("chill_touch", "Chill Touch", M, DEATH_CAT, 3, "a ghostly touch that stops wounds from closing",
	       NECROTIC, on_hit=C.WITHERED),
	attack("blood_boil", "Blood Boil", M, DEATH_CAT, 3, "heats the target's blood", FIRE, on_hit=C.BLEEDING),
	attack("hemokinesis", "Hemokinesis", M, DEATH_CAT, 3, "turns the target's blood against it", SLASHING,
	       ignore_dt=True),
	afflict("wither", "Wither", M, DEATH_CAT, 3, "rots the flesh so it can't heal", C.WITHERED),
	afflict("rapid_aging", "Rapid Aging", M, DEATH_CAT, 3, "ages the target years in a moment", C.WEAKENED,
	        turns=1),
	make("death_mark", "Death Mark", M, DEATH_CAT, DOOM, 3, "marks the target for death", NORMAL),
	attack("bone_spear", "Bone Spear", M, DEATH_CAT, 2, "a spear of bone torn from the earth", PIERCING),
	blast("plague", "Plague", M, DEATH_CAT, 3, "a cloud of sickness", POISON, save="endurance",
	      on_fail=C.POISONED),
	make("raise_dead", "Raise Dead", M, DEATH_CAT, COMPANION, 3, "raises a corpse to fight for you", WEAK,
	     type=SLASHING),
	attack("vampiric_bite", "Vampiric Bite", P, DEATH_CAT, 3, "a bite that drinks the target's blood", PIERCING,
	       drain=True, requires="fang"),

	# == Nature, beasts & poison ==
	attack("thorn_whip", "Thorn Whip", M, NATURE_CAT, 3, "a vine covered in thorns", SLASHING, on_hit=C.BLEEDING),
	afflict("entangle", "Entangle", M, NATURE_CAT, 3, "roots and vines grab the target", C.RESTRAINED),
	attack("poison_spray", "Poison Spray", M, NATURE_CAT, 3, "a puff of toxic gas", POISON, on_hit=C.POISONED),
	afflict("venom_curse", "Venom", M, NATURE_CAT, 2, "poison seeps into the target's blood", C.POISONED),
	blast("swarm", "Insect Swarm", M, NATURE_CAT, 3, "a biting, stinging swarm", PIERCING, save="endurance",
	      on_fail=C.BLINDED),
	make("call_beast", "Call Beast", M, NATURE_CAT, COMPANION, 3, "calls a wild animal to your side", WEAK,
	     type=SLASHING),
	boost("barkskin", "Barkskin", M, NATURE_CAT, 2, "skin like tree bark", C.FORTIFIED),
	make("goodberry", "Healing Bloom", M, NATURE_CAT, HEAL, 3, "a flower whose nectar heals and purifies",
	     cleanse=True),
	attack("chlorokinesis", "Chlorokinesis", M, NATURE_CAT, 3, "plants burst up and crush the target", BLUNT,
	       steps=1),
	attack("venom_sting", "Venom Sting", P, NATURE_CAT, 3, "a poisoned stinger, fang or blade", PIERCING,
	       on_hit=C.POISONED),
	attack("claws", "Claws", P, NATURE_CAT, 3, "tears with claws or talons", SLASHING, on_hit=C.BLEEDING, requires="claw"),
	attack("pounce", "Pounce", P, NATURE_CAT, 3, "leaps on the target and pins it down", BLUNT, on_hit=C.PRONE),
	make("animal_companion", "Animal Companion", P, NATURE_CAT, COMPANION, 3, "a trained beast fights alongside you",
	     WEAK, type=SLASHING),
	attack("acid_spit", "Acid Spit", P, NATURE_CAT, 3, "spits burning acid", ACID, on_hit=C.CORRODED),

	# == Mind & psychic ==
	attack("mind_spike", "Mind Spike", M, MIND_CAT, 2, "drives a spike of thought into the target", MENTAL,
	       accuracy=1),
	blast("psychic_scream", "Psychic Shriek", M, MIND_CAT, 3, "a mental shriek", MENTAL, save="intelligence",
	      on_fail=C.STUNNED, tier=NORMAL),
	afflict("telepathic_charm", "Charm", M, MIND_CAT, 3, "the target can't bring itself to hurt you", C.CHARMED),
	afflict("confusion", "Confusion", M, MIND_CAT, 3, "scrambles the target's thoughts", C.CONFUSED),
	afflict("sleep", "Sleep", M, MIND_CAT, 4, "the target falls into a magical sleep", C.ASLEEP, tier=WEAK),
	afflict("terror", "Terror", M, MIND_CAT, 3, "fills the target with dread", C.FRIGHTENED),
	afflict("hold_person", "Hold Person", M, MIND_CAT, 4, "paralyses the target", C.STUNNED, tier=WEAK),
	afflict("illusion", "Illusion", M, MIND_CAT, 3, "phantom attackers confuse the target", C.CONFUSED),
	afflict("mind_blank", "Mind Fog", M, MIND_CAT, 3, "clouds the target's mind so spells won't come",
	        C.SILENCED),
	boost("precognition", "Precognition", M, MIND_CAT, 3, "the target sees the next attack coming", C.EVASIVE),
	boost("clarity", "Clarity", M, MIND_CAT, 2, "a calm, focused mind", C.FOCUSED),
	attack("psychic_crush", "Psychic Crush", M, MIND_CAT, 4, "crushes the target's mind", MENTAL, tier=WEAK,
	       on_hit=C.SILENCED),
	afflict("compel", "Compel", M, MIND_CAT, 2, "forces the target to come at you", C.TAUNTED),

	# == Force & telekinesis ==
	attack("magic_missile", "Magic Missile", M, FORCE_CAT, 3, "darts of force that rarely miss", ARCANE, hits=3,
	       accuracy=1),
	attack("telekinesis", "Telekinesis", M, FORCE_CAT, 3, "slams the target with your mind", BLUNT, on_hit=C.PRONE),
	attack("force_lance", "Force Lance", M, FORCE_CAT, 3, "a lance of pure force", ARCANE, ignore_dt=True),
	blast("force_wave", "Force Wave", M, FORCE_CAT, 3, "a wave of force", ARCANE, save="strength",
	      on_fail=C.PRONE),
	afflict("disarming_force", "Disarm", M, FORCE_CAT, 3, "yanks the target's weapon away", C.DISARMED, tier=WEAK),
	afflict("telekinetic_hold", "Telekinetic Hold", M, FORCE_CAT, 3, "holds the target in the air", C.RESTRAINED),
	attack("crushing_grip", "Crushing Grip", M, FORCE_CAT, 4, "an invisible hand squeezes the target", BLUNT,
	       tier=WEAK, on_hit=C.STUNNED),
	attack("arcane_blast", "Arcane Blast", M, FORCE_CAT, 2, "a blast of arcane power", ARCANE),
	attack("arcane_mark", "Hunter's Sigil", M, FORCE_CAT, 3, "brands the target so others find their mark", ARCANE,
	       on_hit=C.MARKED),

	# == Space, time & gravity ==
	boost("haste", "Haste", M, SPACE_CAT, 3, "speeds the target up", C.HASTED),
	afflict("slow", "Slow", M, SPACE_CAT, 2, "slows the target down", C.SLOWED),
	boost("blink", "Blink", M, SPACE_CAT, 3, "the target flickers out of the way", C.EVASIVE),
	afflict("gravity_well", "Gravity Well", M, SPACE_CAT, 3, "crushing gravity pins the target", C.RESTRAINED),

	# == Life & healing ==
	make("healing_word", "Healing Word", M, LIFE_CAT, HEAL, 2, "a word of power that heals"),
	make("cure_wounds", "Cure Wounds", M, LIFE_CAT, HEAL, 3, "a touch that heals more", WEAK, steps=1),
	make("purify", "Purify", M, LIFE_CAT, CLEANSE, 2, "cleans away poisons, curses and ailments", count=2),
	make("revivify", "Revivify", M, LIFE_CAT, REVIVE, 3, "brings a fallen ally back", WEAK),
	boost("regeneration", "Regeneration", M, LIFE_CAT, 2, "the target's wounds keep closing", C.REGENERATING),
	make("life_transfer", "Life Transfer", M, LIFE_CAT, HEAL, 2, "gives your own life to heal another",
	     self_cost=True),
	make("lay_on_hands", "Lay on Hands", P, LIFE_CAT, HEAL, 3, "a healer's practised hands", WEAK, steps=1),
	make("smelling_salts", "Smelling Salts", P, LIFE_CAT, REVIVE, 3, "shocks a downed ally awake", WEAK),
	make("antidote", "Treat Ailment", P, LIFE_CAT, CLEANSE, 2, "cleans wounds and treats poison", count=1),

	# == Protection & wards ==
	make("shield_spell", "Shield", M, WARD_CAT, SHIELD, 2, "a shimmering barrier"),
	make("force_field", "Force Field", M, WARD_CAT, SHIELD, 3, "a dome of force", WEAK, steps=1),
	boost("spell_ward", "Spell Ward", M, WARD_CAT, 3, "a ward against magic", C.WARDED),
	boost("mirror_ward", "Rebound", M, WARD_CAT, 4, "bounces the next spell back at its caster", C.REFLECTING,
	      tier=WEAK),
	boost("sanctuary", "Sanctuary", M, WARD_CAT, 3, "enemies' blows slide off the target", C.EVASIVE),
	boost("protection", "Protection", M, WARD_CAT, 2, "a protective aura", C.FORTIFIED),
	make("counterspell", "Counterspell", M, WARD_CAT, DISPEL, 2, "unravels the target's magic", count=1),
	make("bulwark", "Bulwark", P, WARD_CAT, SHIELD, 3, "braces a wall of shields", WEAK, steps=1, requires="shield"),
	boost("shield_wall", "Shield Wall", P, WARD_CAT, 2, "locks shields with the target", C.FORTIFIED, requires="shield"),
	boost("cover", "Take Cover", P, WARD_CAT, 3, "drags the target behind cover", C.HIDDEN),

	# == Curses & hexes ==
	afflict("hex", "Hex", M, CURSE_CAT, 2, "a hex that leaves the target open to harm", C.VULNERABLE),
	afflict("curse", "Curse", M, CURSE_CAT, 4, "a curse of misfortune", C.CURSED, tier=WEAK),
	afflict("bane", "Bane", M, CURSE_CAT, 2, "saps the target's strength", C.WEAKENED),
	make("doom", "Doom", M, CURSE_CAT, DOOM, 3, "seals the target's fate", NORMAL),
	afflict("evil_eye", "Evil Eye", M, CURSE_CAT, 2, "a glare that marks the target for harm", C.MARKED),
	attack("pain", "Pain", M, CURSE_CAT, 3, "pure agony", MENTAL, on_hit=C.WEAKENED),
	afflict("voodoo", "Voodoo", M, CURSE_CAT, 3, "a doll that makes the target suffer", C.VULNERABLE,
	        turns=1),
	afflict("misfortune", "Misfortune", M, CURSE_CAT, 3, "everything goes wrong for the target", C.CURSED,
	        tier=NORMAL, turns=-1),
	afflict("corrode", "Corrode", M, CURSE_CAT, 2, "armor rusts and rots", C.CORRODED),
	make("unravel", "Unravel", M, CURSE_CAT, DISPEL, 3, "unpicks its protections", NORMAL, count=2),

	# == Summoning & creation ==
	make("summon_elemental", "Minor Elemental", M, SUMMON_CAT, COMPANION, 3, "calls a small fire, water, earth or "
	     "air spirit", WEAK),
	make("spiritual_weapon", "Spiritual Weapon", M, SUMMON_CAT, COMPANION, 3, "a floating weapon of force", WEAK,
	     type=ARCANE),
	make("summon_spirit", "Summon Spirit", M, SUMMON_CAT, COMPANION, 3, "calls a restless spirit", WEAK,
	     type=NECROTIC),
	boost("mirror_image", "Mirror Image", M, SUMMON_CAT, 3, "illusory copies take the next blow", C.EVASIVE),
	make("conjure_blades", "Conjure Blades", M, SUMMON_CAT, ATTACK, 3, "conjured blades fly at the target",
	     type=SLASHING, hits=2),
	make("decoy", "Decoy", P, SUMMON_CAT, BOOST, 2, "a dummy or double draws the next attack", aim=SELF,
	     condition=C.EVASIVE),
	make("war_hound", "War Hound", P, SUMMON_CAT, COMPANION, 3, "unleashes a trained war hound", WEAK,
	     type=PIERCING),

	# == Body & transformation ==
	boost("rage", "Rage", P, BODY_CAT, 1, "a furious rage", C.EMPOWERED, aim=SELF),
	boost("super_strength", "Super Strength", P, BODY_CAT, 1, "muscles swell with power", C.EMPOWERED, aim=SELF,
	      turns=1),
	attack("mighty_blow", "Mighty Blow", P, BODY_CAT, 3, "puts everything into one blow", BLUNT, steps=1),
	boost("super_speed", "Super Speed", P, BODY_CAT, 2, "moves faster than the eye", C.HASTED, aim=SELF),
	boost("iron_skin", "Iron Skin", P, BODY_CAT, 1, "skin hard as iron", C.FORTIFIED, aim=SELF, turns=2),
	boost("healing_factor", "Healing Factor", P, BODY_CAT, 1, "wounds close by themselves", C.REGENERATING,
	      aim=SELF, turns=1),
	attack("tail_sweep", "Tail Sweep", P, BODY_CAT, 3, "a sweep of a heavy tail", BLUNT, on_hit=C.PRONE, requires="tail"),
	attack("horns", "Gore", P, BODY_CAT, 3, "charges with horns or tusks", PIERCING, on_hit=C.BLEEDING, requires="horn"),
	attack("bite", "Bite", P, BODY_CAT, 2, "sinks teeth in", PIERCING, requires="fang"),
	boost("shapeshift", "Beast Form", M, BODY_CAT, 2, "takes on a beast's might", C.EMPOWERED, aim=SELF),
	boost("enlarge", "Enlarge", M, BODY_CAT, 2, "the target grows to giant size", C.EMPOWERED),
	afflict("reduce", "Shrink", M, BODY_CAT, 3, "shrinks the target to half its size", C.WEAKENED, turns=1),
	boost("vampire_form", "Vampire Form", M, BODY_CAT, 3, "every wound you deal feeds you", C.VAMPIRIC, aim=SELF),
	boost("spikes", "Spiked Hide", P, BODY_CAT, 2, "spines that hurt anyone who hits you", C.THORNS, aim=SELF),
	attack("drain_bite", "Leech", P, BODY_CAT, 3, "latches on and drinks", PIERCING, drain=True, requires="fang"),

	# == Martial arts & weapons ==
	attack("power_attack", "Power Attack", P, MARTIAL_CAT, 3, "a heavy, committed swing", steps=1),
	attack("flurry", "Flurry of Blows", P, MARTIAL_CAT, 3, "a rapid series of strikes", hits=2),
	attack("whirlwind", "Whirlwind", P, MARTIAL_CAT, 4, "a spinning series of cuts", SLASHING, hits=3),
	attack("precise_strike", "Precise Strike", P, MARTIAL_CAT, 3, "a careful, accurate strike", accuracy=2),
	attack("vital_strike", "Vital Strike", P, MARTIAL_CAT, 3, "aims for a weak point", crit=2),
	attack("armor_breaker", "Armor Breaker", P, MARTIAL_CAT, 3, "a blow through the gaps in armor", ignore_dt=True),
	attack("sunder", "Sunder", P, MARTIAL_CAT, 3, "smashes the target's armor apart", BLUNT, on_hit=C.CORRODED),
	attack("rend", "Rend", P, MARTIAL_CAT, 3, "a tearing cut that keeps bleeding", SLASHING, on_hit=C.BLEEDING),
	attack("stunning_strike", "Stunning Strike", P, MARTIAL_CAT, 4, "a blow to a nerve point", BLUNT, tier=WEAK,
	       on_hit=C.STUNNED),
	attack("pressure_point", "Pressure Point", P, MARTIAL_CAT, 3, "numbs the target's arm", BLUNT,
	       on_hit=C.WEAKENED),
	attack("disarming_strike", "Disarming Strike", P, MARTIAL_CAT, 4, "knocks the weapon from the target's hand",
	       tier=WEAK, on_hit=C.DISARMED),
	attack("trip", "Trip", P, MARTIAL_CAT, 3, "sweeps the target's legs", BLUNT, on_hit=C.PRONE),
	attack("grapple", "Grapple", P, MARTIAL_CAT, 3, "grabs and holds the target", BLUNT, on_hit=C.RESTRAINED),
	attack("throat_punch", "Throat Strike", P, MARTIAL_CAT, 4, "a strike that steals the target's voice", BLUNT,
	       tier=WEAK, on_hit=C.SILENCED),
	attack("execute", "Execute", P, MARTIAL_CAT, 3, "finishes off the wounded", execute=True),
	attack("cleave", "Cleave", P, MARTIAL_CAT, 2, "cuts through one foe into the next", SLASHING),
	attack("shield_bash", "Shield Bash", P, MARTIAL_CAT, 4, "slams a shield into the target", BLUNT, tier=WEAK,
	       on_hit=C.STUNNED, steps=-1, requires="shield"),
	attack("charge", "Charge", P, MARTIAL_CAT, 3, "runs the target down", BLUNT, steps=1),
	attack("headbutt", "Headbutt", P, MARTIAL_CAT, 3, "a brutal headbutt", BLUNT, on_hit=C.DRAINED),
	boost("riposte_stance", "Riposte", P, MARTIAL_CAT, 2, "parries and answers every missed blow", C.RIPOSTE,
	      aim=SELF),
	boost("parry", "Parry", P, MARTIAL_CAT, 2, "readies to turn the next blow", C.EVASIVE, aim=SELF),
	boost("battle_focus", "Battle Focus", P, MARTIAL_CAT, 1, "narrows the world to the fight", C.FOCUSED,
	      aim=SELF),
	boost("blood_frenzy", "Blood Frenzy", P, MARTIAL_CAT, 2, "every cut you land restores you", C.VAMPIRIC,
	      aim=SELF),

	# == Ranged & thrown ==
	attack("aimed_shot", "Aimed Shot", P, ARCHERY_CAT, 2, "takes careful aim", PIERCING, accuracy=2,
	       requires="ranged"),
	attack("double_shot", "Double Shot", P, ARCHERY_CAT, 3, "two arrows at once", PIERCING, hits=2, requires="ranged"),
	attack("piercing_shot", "Piercing Shot", P, ARCHERY_CAT, 3, "a shot that punches through armor", PIERCING,
	       ignore_dt=True, requires="ranged"),
	blast("volley", "Volley", P, ARCHERY_CAT, 3, "a rain of arrows", PIERCING, tier=WEAK, requires="ranged"),
	attack("crippling_shot", "Crippling Shot", P, ARCHERY_CAT, 3, "a shot to the leg", PIERCING,
	       on_hit=C.SLOWED, requires="ranged"),
	attack("pinning_shot", "Pinning Shot", P, ARCHERY_CAT, 3, "pins the target to the ground", PIERCING,
	       on_hit=C.RESTRAINED, requires="ranged"),
	attack("headshot", "Headshot", P, ARCHERY_CAT, 4, "goes for the head", PIERCING, tier=WEAK, crit=3, requires="ranged"),
	attack("knife_throw", "Knife Throw", P, ARCHERY_CAT, 2, "a thrown blade", PIERCING, accuracy=1, requires="thrown"),
	attack("hunters_mark", "Hunter's Mark", P, ARCHERY_CAT, 3, "marks the prey for the whole party", PIERCING,
	       on_hit=C.MARKED, requires="ranged"),
	attack("ricochet", "Ricochet", P, ARCHERY_CAT, 3, "a trick shot off the walls", BLUNT, accuracy=2, steps=-1,
	       hits=2, requires="ranged"),

	# == Tactics & leadership ==
	boost("rally", "Rally", P, TACTICS_CAT, 2, "a shout that steadies an ally", C.INSPIRED),
	boost("battle_cry", "Battle Cry", P, TACTICS_CAT, 2, "fires an ally up", C.EMPOWERED),
	boost("tactical_order", "Tactical Order", P, TACTICS_CAT, 3, "tells an ally exactly where to move", C.HASTED),
	boost("stand_firm", "Stand Firm", P, TACTICS_CAT, 2, "keeps an ally's head clear", C.BLESSED),
	boost("brace", "Brace", P, TACTICS_CAT, 2, "helps an ally brace for the blow", C.FORTIFIED),
	afflict("taunt", "Taunt", P, TACTICS_CAT, 2, "goads the target into attacking you", C.TAUNTED),
	afflict("intimidate", "Intimidate", P, TACTICS_CAT, 2, "a threat that shakes the target", C.FRIGHTENED),
	afflict("expose_weakness", "Expose Weakness", P, TACTICS_CAT, 2, "points out where to hit", C.MARKED),
	afflict("demoralize", "Demoralize", P, TACTICS_CAT, 3, "breaks the target's spirit", C.WEAKENED),
	make("second_wind", "Second Wind", P, TACTICS_CAT, HEAL, 2, "catches your breath", aim=SELF),
	make("retreat", "Tactical Retreat", P, TACTICS_CAT, ESCAPE, 3, "slips away from the fight", NORMAL),
	afflict("feint", "Feint", P, TACTICS_CAT, 2, "draws the target off balance", C.VULNERABLE),

	# == Stealth & trickery ==
	boost("vanish", "Vanish", P, STEALTH_CAT, 2, "disappears from sight", C.HIDDEN, aim=SELF),
	attack("sneak_attack", "Sneak Attack", P, STEALTH_CAT, 3, "strikes where the target isn't looking", PIERCING,
	       execute=True, crit=1),
	attack("backstab", "Backstab", P, STEALTH_CAT, 3, "a blade between the ribs", PIERCING, steps=1),
	attack("garrote", "Garrote", P, STEALTH_CAT, 4, "chokes the target from behind", BLUNT, tier=WEAK,
	       on_hit=C.SILENCED),
	afflict("sand_in_eyes", "Dirty Trick", P, STEALTH_CAT, 2, "sand in the eyes", C.BLINDED),
	afflict("smoke_bomb", "Smoke Bomb", P, STEALTH_CAT, 2, "a cloud of choking smoke", C.BLINDED, save="perception"),
	afflict("distract", "Distract", P, STEALTH_CAT, 2, "a noise in the wrong place", C.CONFUSED),
	afflict("pickpocket", "Pickpocket", P, STEALTH_CAT, 3, "steals the target's weapon", C.DISARMED, tier=WEAK),
	boost("evasion", "Evasion", P, STEALTH_CAT, 2, "dodges the next blow", C.EVASIVE, aim=SELF),
	attack("poisoned_blade", "Poisoned Blade", P, STEALTH_CAT, 3, "a blade coated in poison", PIERCING,
	       on_hit=C.POISONED),
	attack("sleeper_dart", "Sleeper Dart", P, STEALTH_CAT, 4, "a dart dipped in sleeping draught", PIERCING,
	       tier=WEAK, steps=-2, on_hit=C.ASLEEP),
	make("escape_artist", "Escape Artist", P, STEALTH_CAT, CLEANSE, 1, "wriggles free of anything holding you",
	     aim=SELF, count=1),

	# == Grit & endurance ==
	boost("last_stand", "Last Stand", P, GRIT_CAT, 3, "refuses to fall", C.UNDYING, aim=SELF, tier=WEAK),
	boost("thick_skin", "Grit Teeth", P, GRIT_CAT, 1, "ignores the pain", C.FORTIFIED, aim=SELF, turns=3),
	make("shake_it_off", "Shake It Off", P, GRIT_CAT, CLEANSE, 1, "shrugs off whatever ails you", aim=SELF, count=1),
	make("adrenaline", "Adrenaline Rush", P, GRIT_CAT, HEAL, 2, "a rush that numbs pain", aim=SELF),
	boost("iron_will", "Iron Will", P, GRIT_CAT, 1, "nothing breaks your will", C.BLESSED, aim=SELF),
	boost("unstoppable", "Unstoppable", P, GRIT_CAT, 2, "keeps going whatever happens", C.HASTED, aim=SELF,
	      tier=WEAK),
	boost("berserk", "Berserk", P, GRIT_CAT, 2, "fights through anything", C.UNDYING, aim=SELF, tier=NORMAL,
	      turns=-1),
	boost("bodyguard", "Bodyguard", P, GRIT_CAT, 3, "puts themself in harm's way for an ally", C.UNDYING, tier=WEAK),

	# == Alchemy & gadgets ==
	blast("firebomb", "Alchemist's Fire", P, GADGET_CAT, 3, "a flask of liquid fire", FIRE, on_fail=C.BURNING),
	blast("frost_grenade", "Frost Grenade", P, GADGET_CAT, 3, "a canister of freezing mist", FROST,
	      save="endurance", on_fail=C.SLOWED),
	blast("acid_flask", "Acid Flask", P, GADGET_CAT, 3, "a shattering flask of acid", ACID, on_fail=C.CORRODED),
	afflict("flashbang", "Flashbang", P, GADGET_CAT, 3, "a blinding flash and bang", C.BLINDED, save="perception",
	        turns=1),
	afflict("net", "Net", P, GADGET_CAT, 3, "a weighted net", C.RESTRAINED),
	afflict("caltrops", "Caltrops", P, GADGET_CAT, 2, "spikes on the ground", C.SLOWED),
	afflict("knockout_gas", "Knockout Gas", P, GADGET_CAT, 4, "a cloud of sleeping gas", C.ASLEEP, tier=WEAK),
	blast("bomb", "Bomb", P, GADGET_CAT, 3, "a powder bomb", FIRE, tier=WEAK, steps=1),
	make("stimulant", "Stimulant", P, GADGET_CAT, BOOST, 3, "an injection of speed", condition=C.HASTED),
	make("healing_draught", "Healing Draught", P, GADGET_CAT, HEAL, 2, "a quick swig of a healing brew"),
	attack("shock_baton", "Shock Baton", P, GADGET_CAT, 4, "a jolt from a charged baton", LIGHTNING, tier=WEAK,
	       on_hit=C.STUNNED, steps=-1),
	afflict("poison_gas", "Poison Gas", P, GADGET_CAT, 2, "a cloud of toxic gas", C.POISONED),

	# == Modifiers ==
	make("widened", "Widened", M, MODIFIER_CAT, MODIFIER, 2, "the spell spreads to up to 3 targets", kind=AREA),
	make("mass_cast", "Mass Casting", M, MODIFIER_CAT, MODIFIER, 4, "the spell reaches up to 5 targets", NORMAL,
	     kind=MASS),
	make("empowered_spell", "Empowered", M, MODIFIER_CAT, MODIFIER, 2, "more power behind every die",
	     kind=OVERCHARGE),
	make("focused_spell", "Focused", M, MODIFIER_CAT, MODIFIER, 1, "harder to dodge or resist", kind=PRECISE),
	make("lingering_spell", "Lingering", M, MODIFIER_CAT, MODIFIER, 1, "its effects last longer", kind=LINGERING),
	make("sweeping", "Sweeping", P, MODIFIER_CAT, MODIFIER, 2, "hits up to 3 targets", kind=AREA),
	make("onslaught", "Onslaught", P, MODIFIER_CAT, MODIFIER, 4, "hits up to 5 targets", NORMAL, kind=MASS),
	make("heavy", "Heavy-Handed", P, MODIFIER_CAT, MODIFIER, 2, "more force behind every die", kind=OVERCHARGE),
	make("practised", "Practised", P, MODIFIER_CAT, MODIFIER, 1, "harder to dodge or resist", kind=PRECISE),
	make("lasting", "Lasting", P, MODIFIER_CAT, MODIFIER, 1, "its effects last longer", kind=LINGERING),

	# == Drawbacks ==
	make("blood_price", "Blood Price", M, DRAWBACK_CAT, DRAWBACK, -1, "paid for in your own blood", kind=BLOOD),
	make("mana_burn", "Mana Burn", M, DRAWBACK_CAT, DRAWBACK, -1, "leaves you drained", kind=EXHAUST),
	make("wild_magic", "Wild Magic", M, DRAWBACK_CAT, DRAWBACK, -1, "hurts you when it fails", kind=BACKLASH),
	make("frail_casting", "Frail Casting", M, DRAWBACK_CAT, DRAWBACK, -1, "leaves you weak", kind=WEAKEN),
	make("ritual", "Ritual", M, DRAWBACK_CAT, DRAWBACK, -1, "can only be cast once per fight", kind=ONCE),
	make("unguarded_casting", "Unguarded Casting", M, DRAWBACK_CAT, DRAWBACK, -1, "all focus, no defense",
	     kind=RECKLESS),
	make("overexertion", "Overexertion", P, DRAWBACK_CAT, DRAWBACK, -1, "tears your own muscles", kind=BLOOD),
	make("exhausting", "Exhausting", P, DRAWBACK_CAT, DRAWBACK, -1, "leaves you winded", kind=EXHAUST),
	make("reckless", "Reckless", P, DRAWBACK_CAT, DRAWBACK, -1, "leaves you wide open", kind=RECKLESS),
	make("strain", "Strain", P, DRAWBACK_CAT, DRAWBACK, -1, "leaves you weak", kind=WEAKEN),
	make("one_shot", "One Shot", P, DRAWBACK_CAT, DRAWBACK, -1, "can only be done once per fight", kind=ONCE),
	make("backfire", "Backfire", P, DRAWBACK_CAT, DRAWBACK, -1, "hurts you when it fails", kind=BACKLASH),
]

# The hand-written entries above, then the themed ones from GeneratedEffects.py (hand-written ones win on a clash).
ACTIVE_EFFECTS = GeneratedEffects.merge(ACTIVE_EFFECTS, GeneratedEffects.active())
CATALOG = index(ACTIVE_EFFECTS)


# ============================================================
def get(key: str) -> Effect | None :
	return CATALOG.get(key)


# ============================================================
def find(text: str) -> Effect | None :
	"""An effect by key or by name, without case."""
	text = (text or "").strip()
	effect = CATALOG.get(text) or CATALOG.get(text.lower().replace(" ", "_"))
	if effect is not None :
		return effect
	return next((effect for effect in ACTIVE_EFFECTS if effect.name.lower() == text.lower()), None)


# ============================================================
def search(text: str, realm: str | None = None, category: str | None = None) -> list[Effect] :
	"""Effects whose name, category or description mentions the text, names first."""
	text = (text or "").strip().lower()
	pool = [effect for effect in ACTIVE_EFFECTS if (realm is None or effect.realm == realm)
	        and (category is None or effect.category == category)]
	if not text :
		return pool
	named = [effect for effect in pool if text in effect.name.lower()]
	rest = [effect for effect in pool if effect not in named and (text in effect.category.lower()
	                                                             or text in effect.text.lower())]
	return named + rest
