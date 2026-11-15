"""The embed /dice posts: the result, the dice, the modifiers, a meter and a line of story text."""
import random

import discord

from classes.dice.Dice import DiceRoll
from classes.dice.Flavor import Flavor, TIER_COLOURS, TIER_LABELS

D6_FACES = "⚀⚁⚂⚃⚄⚅"
METER_LENGTH = 12


class DiceCard :

	# ============================================================
	@staticmethod
	def face(roll: int, sides: int) -> str :
		"""One die: d6 faces as pips, the rest as numbers; the highest and lowest sides stand out."""
		if sides == 6 :
			text = f"{D6_FACES[roll - 1]} {roll}"
		else :
			text = str(roll)
		if roll == sides :
			return f"**`{text}`**🔥"
		if roll == 1 :
			return f"`{text}`💀"
		return f"`{text}`"

	# ============================================================
	@staticmethod
	def dice_text(roll: DiceRoll) -> str :
		"""Even 50 dice of 1000 sides stay well inside an embed field's 1024 characters."""
		return " ".join(DiceCard.face(value, roll.sides) for value in roll.rolls)

	# ============================================================
	@staticmethod
	def modifiers_text(roll: DiceRoll) -> str :
		lines = [f"{modifier.label} **{modifier.value:+d}**" for modifier in roll.modifiers]
		if roll.multiplier != 1 and roll.modifiers :
			lines.append(f"×{roll.multiplier} for a d{roll.sides} → **{roll.modifier:+d}**")
		return "\n".join(lines) or "none"

	# ============================================================
	@staticmethod
	def meter(roll: DiceRoll) -> str :
		"""▰▰▰▰▰▱▱▱: how close the total came to the most the dice can roll."""
		filled = round(roll.quality * METER_LENGTH)
		return "▰" * filled + "▱" * (METER_LENGTH - filled)

	# ============================================================
	@staticmethod
	def breakdown(roll: DiceRoll) -> str :
		"""`14 + 3 = 17`"""
		if not roll.modifier :
			return f"`{roll.natural}`" if roll.amount > 1 else ""
		sign = "+" if roll.modifier > 0 else "-"
		return f"`{roll.natural} {sign} {abs(roll.modifier)} = {roll.total}`"

	# ============================================================
	@staticmethod
	def embed(roll: DiceRoll, roller: str, goal: str | None = None, character_name: str | None = None,
	          stat: str | None = None, icon_url: str | None = None, thumbnail_url: str | None = None,
	          rng: random.Random | None = None) -> discord.Embed :
		"""
		@param roller: the member's display name, shown in the footer.
		@param icon_url: the character's avatar, or the member's when no character rolled.
		@param thumbnail_url: the character's avatar, shown large.
		"""
		tier = roll.tier
		name = character_name or roller
		action = f"{stat.capitalize()} check" if stat else "Roll"
		title = goal or f"{action}: {roll.notation}"

		description = (f"*{Flavor.line(tier, name, stat, rng)}*\n"
		               f"# 🎲 {roll.total}\n"
		               f"{DiceCard.breakdown(roll)}\n"
		               f"{DiceCard.meter(roll)}").replace("\n\n", "\n")

		embed = discord.Embed(title=title[:256], description=description, colour=TIER_COLOURS[tier],
		                      timestamp=discord.utils.utcnow())
		embed.set_author(name=f"{name} · {action}" if character_name or stat else f"{name} rolls the dice",
		                 icon_url=icon_url)
		embed.add_field(name=TIER_LABELS[tier], value=DiceCard.dice_text(roll), inline=False)
		embed.add_field(name="Roll", value=f"`{roll.notation}`", inline=True)
		embed.add_field(name="Modifiers", value=DiceCard.modifiers_text(roll), inline=True)
		if thumbnail_url :
			embed.set_thumbnail(url=thumbnail_url)
		embed.set_footer(text=f"Rolled by {roller}" if character_name else f"d{roll.sides}")
		return embed
