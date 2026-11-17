"""How a catalog item is shown: one line in a list, or a full embed."""
import discord

from classes.gear import Carry, Magic, Rarity
from classes.gear.Gear import Gear, KIND_LABELS
from classes.kernel.ConfigData import ConfigData
from database.database import GearItems
from resources.configs.ConfigMapping import ConfigMapping

FIELD_LIMIT = 1024


class GearCard :

	# ============================================================
	@staticmethod
	def requirements_text(item: GearItems) -> str :
		"""`Strength 8, Agility 4`, or an empty string."""
		return ", ".join(f"{stat.capitalize()} {minimum}" for stat, minimum in (item.requirements or {}).items())

	# ============================================================
	@staticmethod
	def price_text(guild_id: int, price: int) -> str :
		if not Gear.economy(guild_id) :
			return "free"
		return f"{price} {ConfigData().get_key(guild_id, ConfigMapping.CURRENCY_NAME)}"

	# ============================================================
	@staticmethod
	def line(item: GearItems, locked: str | None = None) -> str :
		"""`**Plate** (armor, Rare) · 2000 caps · needs Strength 8`, with the reason when the member cannot buy it."""
		parts = [f"**{item.name}** ({item.kind}, {Rarity.label(Rarity.of(item))})",
		         GearCard.price_text(item.guild_id, Gear.price(item))]
		requirements = GearCard.requirements_text(item)
		if requirements :
			parts.append(f"needs {requirements}")
		text = " · ".join(parts)
		return f"{text} (unavailable: {locked})" if locked else text

	# ============================================================
	@staticmethod
	def embed(item: GearItems) -> discord.Embed :
		embed = discord.Embed(title=item.name[:256], description=(item.description or "")[:4000],
		                      color=discord.Color.dark_gold())
		embed.add_field(name="Kind", value=KIND_LABELS.get(item.kind, item.kind.capitalize()))
		embed.add_field(name="Rarity", value=Rarity.label(Rarity.of(item)))
		if getattr(item, "slot", None) :
			embed.add_field(name="Worn on", value=item.slot.capitalize())
		if getattr(item, "weight", None) :
			embed.add_field(name="Weight", value=Carry.show(item.guild_id, item.weight))
		embed.add_field(name="Price", value=GearCard.price_text(item.guild_id, Gear.price(item)))
		requirements = GearCard.requirements_text(item)
		if requirements :
			embed.add_field(name="Requirements", value=requirements)
		enchantment = Magic.describe(item)
		if enchantment :
			embed.add_field(name="Enchantment", value=enchantment[:FIELD_LIMIT], inline=False)
		if item.effect :
			embed.add_field(name="Effect", value=item.effect[:FIELD_LIMIT], inline=False)
		if item.effect_met :
			embed.add_field(name="When the requirements are met", value=item.effect_met[:FIELD_LIMIT], inline=False)
		if item.effect_unmet :
			embed.add_field(name="When they are not", value=item.effect_unmet[:FIELD_LIMIT], inline=False)
		return embed
