"""The line of story text under a /dice result, picked by how the roll went and, with a character, the stat used.

{name} is the character, or the member when no character rolled. Lines stay genre-neutral, since servers run
anything from wastelands to fantasy.
"""
import random

from classes.dice.Dice import CRITICAL_FAILURE, CRITICAL_SUCCESS, GREAT, MIXED, POOR, SUCCESS

# The label and colour each tier gets on the result card.
TIER_LABELS = {
	CRITICAL_SUCCESS : "✨ Critical success!",
	GREAT            : "🌟 Great roll",
	SUCCESS          : "✅ Solid roll",
	MIXED            : "➖ Could be better",
	POOR             : "⚠️ Poor roll",
	CRITICAL_FAILURE : "💀 Critical failure!",
}
TIER_COLOURS = {
	CRITICAL_SUCCESS : 0xF1C40F,
	GREAT            : 0x2ECC71,
	SUCCESS          : 0x3498DB,
	MIXED            : 0x95A5A6,
	POOR             : 0xE67E22,
	CRITICAL_FAILURE : 0xC0392B,
}

GENERAL = {
	CRITICAL_SUCCESS : [
		"The dice stop, and for a moment even fate seems impressed by {name}.",
		"Everything lines up perfectly. {name} couldn't have done it better on purpose.",
		"A flawless result. People will be telling this story about {name} for a while.",
		"{name} makes it look effortless, which it absolutely was not.",
		"Luck, skill and timing all show up at once for {name}.",
	],
	GREAT            : [
		"{name} pulls it off with room to spare.",
		"Clean, confident and convincing. {name} has this handled.",
		"That went better than {name} dared to hope.",
		"{name} makes it count.",
		"A strong showing from {name}.",
	],
	SUCCESS          : [
		"{name} gets it done. Not pretty, but it works.",
		"Steady and reliable; {name} does what needed doing.",
		"It holds together. {name} lets out a breath.",
		"Good enough, and good enough is what counts for {name} right now.",
		"{name} manages it, with only a little sweat.",
	],
	MIXED            : [
		"It sort of works. {name} isn't sure whether to celebrate.",
		"{name} gets halfway there, which is a strange place to be.",
		"Something goes right and something goes wrong. {name} will take it.",
		"Not a disaster, but {name} wouldn't call it a win either.",
		"The outcome wobbles before settling somewhere uncomfortable for {name}.",
	],
	POOR             : [
		"That didn't go the way {name} planned.",
		"{name} gives it a real try. It isn't enough.",
		"The attempt falls flat, and {name} knows it.",
		"Things slip out of {name}'s grasp.",
		"{name} will be thinking about this one later, and not fondly.",
	],
	CRITICAL_FAILURE : [
		"Somewhere, the universe is laughing at {name}.",
		"It goes wrong in a way nobody, least of all {name}, saw coming.",
		"{name} achieves the exact opposite of what was intended.",
		"A spectacular failure. At least {name} committed to it.",
		"The dice have spoken, and they are not on {name}'s side.",
	],
}

STAT_LINES = {
	"strength"     : {
		CRITICAL_SUCCESS : ["{name} puts their back into it, and something gives way that never should have.",
		                    "Raw power. {name} makes the impossible look like a warm-up."],
		GREAT            : ["{name}'s muscles do the talking, and they're very convincing.",
		                    "With a grunt of effort, {name} forces it through."],
		SUCCESS          : ["{name} heaves, strains, and it moves.",
		                    "Brute force does the job for {name}."],
		MIXED            : ["{name} gets it partway before arms start shaking.",
		                    "It budges a little. {name} is going to feel that tomorrow."],
		POOR             : ["{name} pushes hard, but it pushes back harder.",
		                    "Not enough muscle behind it; {name} comes up short."],
		CRITICAL_FAILURE : ["{name} pulls something, and it wasn't the target.",
		                    "With a mighty heave, {name} ends up flat on the ground."],
	},
	"perception"   : {
		CRITICAL_SUCCESS : ["Nothing escapes {name}. Not the detail, not the motive, not the hidden door.",
		                    "{name} notices it all, down to the dust on the floor that shouldn't be there."],
		GREAT            : ["{name}'s eyes catch exactly what matters.",
		                    "A flicker of movement, and {name} has already spotted it."],
		SUCCESS          : ["{name} picks up on it, after a second look.",
		                    "Something seems off, and {name} is right about that."],
		MIXED            : ["{name} senses something, but can't quite place it.",
		                    "Half the picture is clear to {name}. The other half is not."],
		POOR             : ["It was right there, and {name} looked straight past it.",
		                    "{name} squints into the distance and sees nothing useful."],
		CRITICAL_FAILURE : ["{name} is completely sure about what they saw. They are completely wrong.",
		                    "{name} misses the obvious so thoroughly that it's almost a talent."],
	},
	"endurance"    : {
		CRITICAL_SUCCESS : ["{name} shrugs it off like it was nothing. Maybe it was, to them.",
		                    "Tireless and unshaken, {name} could keep this up all day."],
		GREAT            : ["{name} grits their teeth and outlasts it.",
		                    "Where others would fold, {name} holds on."],
		SUCCESS          : ["{name} endures. It hurts, but they're still standing.",
		                    "Deep breath, keep going. {name} makes it through."],
		MIXED            : ["{name} makes it, barely, and needs a moment afterwards.",
		                    "Still upright, though {name} is swaying a bit."],
		POOR             : ["{name}'s body has had enough before the job is done.",
		                    "Exhaustion catches up with {name}."],
		CRITICAL_FAILURE : ["{name}'s legs give out at the worst possible moment.",
		                    "{name} collapses in a heap, completely spent."],
	},
	"charisma"     : {
		CRITICAL_SUCCESS : ["Every word lands. By the end, the room is on {name}'s side.",
		                    "{name} smiles, and suddenly everyone wants to help."],
		GREAT            : ["{name}'s charm works wonders.",
		                    "A few well-chosen words, and {name} has them listening."],
		SUCCESS          : ["{name} makes a decent impression.",
		                    "Not the speech of a lifetime, but {name} gets the point across."],
		MIXED            : ["They hear {name} out, but they aren't sold yet.",
		                    "{name} gets polite nods, the kind that mean very little."],
		POOR             : ["{name}'s words come out wrong, and the mood sours.",
		                    "Awkward silence follows whatever {name} just said."],
		CRITICAL_FAILURE : ["{name} manages to insult everyone present, including themselves.",
		                    "Whatever {name} meant to say, what came out will be remembered."],
	},
	"intelligence" : {
		CRITICAL_SUCCESS : ["The answer clicks into place, and {name} sees the whole picture at once.",
		                    "{name} solves it, then solves the problem behind the problem."],
		GREAT            : ["{name} works it out quickly and neatly.",
		                    "A flash of insight lights {name}'s way forward."],
		SUCCESS          : ["{name} thinks it through and gets there.",
		                    "Logic carries {name} to the right conclusion."],
		MIXED            : ["{name} has a theory. It's about half right.",
		                    "Some of it makes sense to {name}. Some of it really doesn't."],
		POOR             : ["{name} stares at the problem; the problem stares back.",
		                    "The pieces refuse to fit together for {name}."],
		CRITICAL_FAILURE : ["{name} reaches a confident, detailed and entirely wrong conclusion.",
		                    "{name} overthinks it until it somehow becomes worse."],
	},
	"agility"      : {
		CRITICAL_SUCCESS : ["{name} moves like water: quick, silent and impossible to catch.",
		                    "A blur of motion, and {name} lands perfectly."],
		GREAT            : ["Quick on their feet, {name} makes it look easy.",
		                    "{name} slips through with grace to spare."],
		SUCCESS          : ["{name} pulls it off with decent footwork.",
		                    "A quick move, and {name} is through."],
		MIXED            : ["{name} stumbles a little, but recovers.",
		                    "Not the cleanest move, but {name} gets there."],
		POOR             : ["{name} is a half-second too slow.",
		                    "A misstep throws {name} off balance."],
		CRITICAL_FAILURE : ["{name} trips over absolutely nothing, in full view of everyone.",
		                    "Arms flailing, {name} goes down hard."],
	},
	"luck"         : {
		CRITICAL_SUCCESS : ["Against all odds, everything breaks {name}'s way.",
		                    "It shouldn't have worked. It worked anyway, because it's {name}."],
		GREAT            : ["Fortune smiles on {name}.",
		                    "The odds tip in {name}'s favour, as if on cue."],
		SUCCESS          : ["A little luck goes a long way for {name}.",
		                    "Things fall {name}'s way, more or less."],
		MIXED            : ["Fortune can't decide what to do with {name}.",
		                    "A lucky break for {name}, followed by an unlucky one."],
		POOR             : ["Of course this happens to {name}. Of course.",
		                    "The coin lands on the wrong side for {name}."],
		CRITICAL_FAILURE : ["If something can go wrong for {name}, it just did, all at once.",
		                    "{name} must have broken a mirror recently. Several, maybe."],
	},
}


class Flavor :

	# ============================================================
	@staticmethod
	def line(tier: str, name: str, stat: str | None = None, rng: random.Random | None = None) -> str :
		"""A line for the tier. With a stat, its own lines come first; the general lines keep it from repeating."""
		rng = rng or random
		choices = STAT_LINES.get(stat or "", {}).get(tier, []) * 2 + GENERAL[tier]
		return rng.choice(choices).format(name=name)
