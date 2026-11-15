"""The passive effect catalog: every effect a passive ability or spell can be built from. Magic effects are for spell
passives, physical ones for ability passives. Each costs AP every turn while the character knows the passive (one more
at Strong). See classes/combat/Passives.py for what each type does and the amounts by tier.

Effects with the scope `choose` take the passive's target option: a damage type, or melee, ranged, magic or physical.
"""
from classes.combat import Conditions as C
from classes.combat.Effects import Effect, MAGIC, NORMAL, PHYSICAL, index, make
from classes.combat.Passives import AC, AURA, BERSERK, BONUS, CHOOSE, COUNTER, CRIT, DAMAGE, DC, DT, HEAL_POWER, HP, \
	IMMUNE, LAST_STAND, LIFESTEAL, MELEE, ON_STRONG_HIT, RANGED, REGENERATE, RESIST, SAVE, SECOND_WIND, SEQUENCE, \
	STACKS, THORNS, TO_HIT, TRIGGER, ANY

M = MAGIC
P = PHYSICAL

OFFENSE = "Offense"
DEFENSE = "Defense"
RESISTANCE = "Resistances & immunities"
RECOVERY = "Recovery"
REACTIONS = "Reactions"
PRESENCE = "Auras & presence"
GROWTH = "Growth"
CATEGORIES = [OFFENSE, DEFENSE, RESISTANCE, RECOVERY, REACTIONS, PRESENCE, GROWTH]


# ============================================================
def bonus(key: str, name: str, realm: str, category: str, cost: int, text: str, field: str,
          scope: str | None = None) -> Effect :
	return make(key, name, realm, category, BONUS, cost, text, field=field, scope=scope)


# ============================================================
def immune(key: str, name: str, realm: str, condition: str, text: str) -> Effect :
	return make(key, name, realm, RESISTANCE, IMMUNE, 1, text, NORMAL, condition=condition)


# ============================================================
def trigger(key: str, name: str, realm: str, category: str, cost: int, text: str, kind: str, tier: str = "weak",
            condition: str | None = None) -> Effect :
	return make(key, name, realm, category, TRIGGER, cost, text, tier, trigger=kind, condition=condition)


PASSIVE_EFFECTS = [
	# == Offense ==
	bonus("weapon_training", "Weapon Training", P, OFFENSE, 1, "drilled with every weapon", TO_HIT, "physical"),
	bonus("keen_eye", "Keen Eye", P, OFFENSE, 1, "never misses at range", TO_HIT, RANGED),
	bonus("brawler", "Brawler", P, OFFENSE, 1, "at home in close combat", TO_HIT, MELEE),
	bonus("brute", "Brute", P, OFFENSE, 1, "hits harder than anyone expects", DAMAGE, MELEE),
	bonus("deadeye", "Deadeye", P, OFFENSE, 1, "shots land where they hurt", DAMAGE, RANGED),
	bonus("specialist", "Specialist", P, OFFENSE, 1, "masters one kind of damage (pick it as the target)", DAMAGE,
	      CHOOSE),
	bonus("trained_aim", "Trained Aim", P, OFFENSE, 1, "accurate with one kind of attack (pick the target)", TO_HIT,
	      CHOOSE),
	make("lethal", "Lethal", P, OFFENSE, CRIT, 1, "finds the weak spot more often"),
	make("savagery", "Savagery", P, OFFENSE, BERSERK, 1, "most dangerous when hurt"),
	make("bloodthirst", "Bloodthirst", P, OFFENSE, LIFESTEAL, 2, "drinks strength from every wound"),
	trigger("crushing_blows", "Crushing Blows", P, OFFENSE, 1, "strong hits knock the target down", ON_STRONG_HIT,
	        condition=C.PRONE),
	trigger("bleeder", "Bleeder", P, OFFENSE, 1, "strong hits leave deep cuts", ON_STRONG_HIT, condition=C.BLEEDING),
	trigger("staggering", "Staggering Blows", P, OFFENSE, 2, "strong hits stun", ON_STRONG_HIT, NORMAL,
	        condition=C.STUNNED),
	bonus("spell_accuracy", "Arcane Precision", M, OFFENSE, 1, "spells find their mark", TO_HIT, "magic"),
	bonus("spell_power", "Spell Power", M, OFFENSE, 1, "spells hit harder", DAMAGE, "magic"),
	bonus("elemental_affinity", "Elemental Affinity", M, OFFENSE, 1, "one element answers best (pick it as the "
	      "target)", DAMAGE, CHOOSE),
	bonus("attunement", "Attunement", M, OFFENSE, 1, "spells of one kind rarely miss (pick the target)", TO_HIT,
	      CHOOSE),
	make("potent_magic", "Potent Magic", M, OFFENSE, DC, 1, "spells are harder to resist"),
	make("overwhelming_will", "Overwhelming Will", P, OFFENSE, DC, 1, "tricks and threats are harder to shrug off"),
	make("arcane_focus", "Arcane Focus", M, OFFENSE, CRIT, 1, "spells strike true more often"),
	make("soul_siphon", "Soul Siphon", M, OFFENSE, LIFESTEAL, 2, "spells feed on the life they take"),
	make("blood_magic", "Blood Magic", M, OFFENSE, BERSERK, 1, "magic surges as blood is spilled"),
	trigger("searing_magic", "Searing Magic", M, OFFENSE, 1, "strong hits set the target alight", ON_STRONG_HIT,
	        condition=C.BURNING),
	trigger("frost_touch", "Frost Touch", M, OFFENSE, 1, "strong hits chill the target", ON_STRONG_HIT,
	        condition=C.SLOWED),
	trigger("hexblade", "Hexblade", M, OFFENSE, 1, "strong hits curse the target with weakness", ON_STRONG_HIT,
	        condition=C.VULNERABLE),
	trigger("mind_shatter", "Mind Shatter", M, OFFENSE, 2, "strong hits silence the target", ON_STRONG_HIT, NORMAL,
	        condition=C.SILENCED),

	# == Defense ==
	bonus("thick_hide", "Thick Hide", P, DEFENSE, 1, "tough skin, scales or fur", DT),
	bonus("nimble", "Nimble", P, DEFENSE, 1, "hard to pin down", AC),
	bonus("toughness", "Toughness", P, DEFENSE, 1, "can take a beating", HP),
	bonus("quick_reflexes", "Quick Reflexes", P, DEFENSE, 1, "always moves first", SEQUENCE),
	make("iron_will_passive", "Unshakeable", P, DEFENSE, SAVE, 1, "shrugs off fear and tricks"),
	bonus("arcane_armor", "Arcane Armor", M, DEFENSE, 1, "a permanent shimmer of protection", AC),
	bonus("mage_skin", "Mage Skin", M, DEFENSE, 1, "magic hardens the body", DT),
	bonus("vital_essence", "Vital Essence", M, DEFENSE, 1, "more life than a body should hold", HP),
	bonus("foresight", "Foresight", M, DEFENSE, 1, "sees the fight before it starts", SEQUENCE),
	make("spell_resistance", "Strong Mind", M, DEFENSE, SAVE, 1, "a mind hard to bend"),

	# == Resistances & immunities ==
	make("resistance_physical", "Hardened", P, RESISTANCE, RESIST, 1, "blows and blades do less", scope="physical"),
	make("resistance_any", "Resilient", P, RESISTANCE, RESIST, 1, "one kind of harm does less (pick the target)",
	     scope=CHOOSE),
	make("magic_resistance", "Magic Resistance", P, RESISTANCE, RESIST, 1, "spells do less", scope="magic"),
	make("elemental_ward", "Elemental Ward", M, RESISTANCE, RESIST, 1, "one kind of harm does less (pick the "
	     "target)", scope=CHOOSE),
	make("spell_turning", "Spell Turning", M, RESISTANCE, RESIST, 1, "spells against you lose their bite",
	     scope="magic"),
	make("kinetic_barrier", "Kinetic Barrier", M, RESISTANCE, RESIST, 1, "a barrier that blunts blows",
	     scope="physical"),
	immune("steady", "Steady", P, C.STUNNED, "can't be stunned"),
	immune("sure_footed", "Sure-Footed", P, C.PRONE, "can't be knocked down"),
	immune("fearless", "Fearless", P, C.FRIGHTENED, "can't be frightened"),
	immune("poison_immunity", "Poison Immunity", P, C.POISONED, "poison does nothing"),
	immune("free_movement", "Free Movement", P, C.RESTRAINED, "can't be held"),
	immune("iron_grip", "Iron Grip", P, C.DISARMED, "never lets go of the weapon"),
	immune("sleepless", "Sleepless", P, C.ASLEEP, "never sleeps"),
	immune("bloodless", "Bloodless", P, C.BLEEDING, "doesn't bleed"),
	immune("clear_mind", "Clear Mind", M, C.CONFUSED, "can't be confused"),
	immune("will_of_iron", "Will of Iron", M, C.CHARMED, "can't be charmed"),
	immune("fireproof", "Fireproof", M, C.BURNING, "can't burn"),
	immune("warm_blood", "Warm Blood", M, C.SLOWED, "cold and time magic can't slow it"),
	immune("true_sight", "True Sight", M, C.BLINDED, "can't be blinded"),
	immune("unbound_voice", "Unbound Voice", M, C.SILENCED, "can't be silenced"),
	immune("blessed_soul", "Blessed Soul", M, C.CURSED, "curses slide off"),
	immune("anchored", "Anchored", M, C.BANISHED, "can't be banished"),

	# == Recovery ==
	trigger("regeneration_passive", "Regeneration", P, RECOVERY, 2, "wounds close by themselves", REGENERATE),
	trigger("second_wind_passive", "Second Wind", P, RECOVERY, 1, "gets a second wind once per fight",
	        SECOND_WIND),
	trigger("undying", "Undying", P, RECOVERY, 2, "refuses to go down", LAST_STAND, NORMAL),
	make("field_medic", "Field Medic", P, RECOVERY, HEAL_POWER, 1, "heals others better"),
	trigger("troll_blood", "Undying Flesh", M, RECOVERY, 2, "magic knits the body back together", REGENERATE),
	trigger("phoenix", "Phoenix Soul", M, RECOVERY, 2, "rises from the ashes once", LAST_STAND, NORMAL),
	trigger("life_spring", "Wellspring", M, RECOVERY, 1, "a burst of life when hurt badly", SECOND_WIND),
	make("healers_gift", "Healer's Gift", M, RECOVERY, HEAL_POWER, 1, "healing spells are stronger"),

	# == Reactions ==
	trigger("counterattack", "Counterattack", P, REACTIONS, 1, "punishes melee attackers that miss", COUNTER),
	make("spiked_armor", "Spiked Armor", P, REACTIONS, THORNS, 1, "melee attackers that hit get hurt"),
	trigger("arcane_retort", "Arcane Retort", M, REACTIONS, 1, "a jolt for melee attackers that miss", COUNTER),
	make("burning_aura", "Burning Body", M, REACTIONS, THORNS, 1, "touching it burns"),

	# == Auras & presence ==
	make("commander", "Commander", P, PRESENCE, AURA, 2, "allies fight better near you", field=TO_HIT),
	make("war_banner", "War Banner", P, PRESENCE, AURA, 2, "allies hit harder near you", field=DAMAGE),
	make("protector", "Protector", P, PRESENCE, AURA, 2, "allies are safer near you", field=AC),
	make("aura_of_courage", "Aura of Courage", M, PRESENCE, AURA, 2, "allies are guided by your magic",
	     field=TO_HIT),
	make("aura_of_power", "Aura of Power", M, PRESENCE, AURA, 2, "allies' blows carry your magic", field=DAMAGE),
	make("aura_of_protection", "Aura of Protection", M, PRESENCE, AURA, 2, "a ward around your allies", field=AC),

	# == Growth ==
	make("battle_hardened", "Battle-Hardened", P, GROWTH, STACKS, 1, "each hit taken makes you tougher",
	     field=AC, scope=ANY),
	make("adrenaline_stacks", "Adrenaline", P, GROWTH, STACKS, 1, "each hit taken makes you hit harder",
	     field=DAMAGE, scope=ANY),
	make("fury", "Mounting Fury", P, GROWTH, STACKS, 1, "each hit from a source you pick sharpens your aim",
	     field=TO_HIT, scope=CHOOSE),
	make("vengeance", "Vengeance", P, GROWTH, STACKS, 1, "each hit from a source you pick makes you hit harder",
	     field=DAMAGE, scope=CHOOSE),
	make("toughened", "Toughened", P, GROWTH, STACKS, 1, "each hit from a source you pick makes you harder to hit",
	     field=AC, scope=CHOOSE),
	make("spellfed", "Spellfed", M, GROWTH, STACKS, 1, "spells that hit you make you stronger", field=DAMAGE,
	     scope="magic"),
	make("absorption", "Absorption", M, GROWTH, STACKS, 1, "absorbs one kind of harm (pick it) and grows",
	     field=DAMAGE, scope=CHOOSE),
	make("arcane_feedback", "Arcane Feedback", M, GROWTH, STACKS, 1, "every hit taken hardens your wards", field=AC,
	     scope=ANY),
]

CATALOG = index(PASSIVE_EFFECTS)


# ============================================================
def get(key: str) -> Effect | None :
	return CATALOG.get(key)


# ============================================================
def find(text: str) -> Effect | None :
	text = (text or "").strip()
	effect = CATALOG.get(text) or CATALOG.get(text.lower().replace(" ", "_"))
	if effect is not None :
		return effect
	return next((effect for effect in PASSIVE_EFFECTS if effect.name.lower() == text.lower()), None)


# ============================================================
def search(text: str, realm: str | None = None, category: str | None = None) -> list[Effect] :
	text = (text or "").strip().lower()
	pool = [effect for effect in PASSIVE_EFFECTS if (realm is None or effect.realm == realm)
	        and (category is None or effect.category == category)]
	if not text :
		return pool
	named = [effect for effect in pool if text in effect.name.lower()]
	return named + [effect for effect in pool if effect not in named and (text in effect.category.lower()
	                                                                      or text in effect.text.lower())]
