"""The server's gear shop. Browse the weapons and armor your characters can buy, look at an item, and buy it
with a character's currency. Some items need a server level or a role and show as unavailable until you have it;
event and staff items aren't sold and are only given out by staff.
"""
# The rules live in classes/gear/Gear.py.
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Access import Access
from classes.characters.CharacterFlow import CharacterFlow
from classes.combat.AutoComplete import AutoComplete
from classes.gear.Gear import ARMOR, Gear, ShopItem, WEAPON
from classes.gear.GearCard import GearCard
from database.database import Characters
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from modules.Currency import balance_text, find_own_character
from modules.Gear import refresh_post, unmet_warning

# What fits in one embed description.
PAGE_LIMIT = 4000
KIND_CHOICES = [Choice(name="Weapons", value=WEAPON), Choice(name="Armor", value=ARMOR)]


# ============================================================
def pages(lines: list[str], limit: int = PAGE_LIMIT) -> list[str] :
	"""Joins lines into as few pages as possible, each at most limit characters; a line is never split."""
	result, current = [], ""
	for line in lines :
		line = line[:limit]
		if current and len(current) + 1 + len(line) > limit :
			result.append(current)
			current = ""
		current = f"{current}\n{line}" if current else line
	if current :
		result.append(current)
	return result


# ============================================================
def find_item(items: list[ShopItem], name: str) -> ShopItem | None :
	"""The shop item with that name, without case; None when the member can't see it."""
	name = (name or "").strip().lower()
	return next((shop_item for shop_item in items if shop_item.item.name.lower() == name), None)


# ============================================================
def balances_text(guild_id: int, characters: list[Characters]) -> str :
	"""`Ayla: 1400 caps · Bryn: 300 caps`, or an empty string in free mode or without characters."""
	if not characters or not Gear.economy(guild_id) :
		return ""
	return " · ".join(f"{character.name}: {balance_text(guild_id, character.currency)}" for character in characters)


@app_commands.guild_only()
class Shop(commands.GroupCog, name="Shop", group_name="shop") :


	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# == helpers ==

	# ============================================================
	async def _visible_items(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		items = Gear.shop_items(interaction.guild_id, Access.of(interaction.user))
		return [Choice(name=shop_item.item.name[:100], value=shop_item.item.name[:100]) for shop_item in items
		        if current.lower() in shop_item.item.name.lower()][:25]

	# ============================================================
	async def _buyable_items(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		items = Gear.shop_items(interaction.guild_id, Access.of(interaction.user))
		return [Choice(name=shop_item.item.name[:100], value=shop_item.item.name[:100]) for shop_item in items
		        if not shop_item.locked and current.lower() in shop_item.item.name.lower()][:25]

	# ============================================================
	def _approved(self, interaction: discord.Interaction) -> list[Characters] :
		return CharacterTransactions().get_all(interaction.user.id, interaction.guild_id, states=[APPROVED])

	# == commands ==

	# ============================================================
	@app_commands.command(name="browse")
	@app_commands.choices(kind=KIND_CHOICES)
	async def browse(self, interaction: discord.Interaction, kind: Choice[str] = None) :
		"""
		Lists the gear in the shop, optionally only weapons or only armor, with prices and SPECIAL requirements.
		Items you can't buy yet are marked with the reason. Use /shop view for an item's details and /shop buy to
		buy it.
		"""
		await interaction.response.defer(ephemeral=True)
		guild_id = interaction.guild_id
		items = Gear.shop_items(guild_id, Access.of(interaction.user), kind.value if kind else None)
		if not items :
			return await interaction.followup.send("The shop has nothing for sale yet.", ephemeral=True)
		lines = [GearCard.line(shop_item.item, shop_item.locked) for shop_item in items]
		footer = balances_text(guild_id, self._approved(interaction))
		descriptions = pages(lines)
		for index, description in enumerate(descriptions) :
			title = "Shop" if index == 0 else None
			embed = discord.Embed(title=title, description=description, color=discord.Color.dark_gold())
			if footer and index == len(descriptions) - 1 :
				embed.set_footer(text=footer[:2048])
			await interaction.followup.send(embed=embed, ephemeral=True)

	# ============================================================
	@app_commands.command(name="view")
	@app_commands.autocomplete(item=_visible_items)
	async def view(self, interaction: discord.Interaction, item: str) :
		"""
		Shows an item's details: its price, SPECIAL requirements and effects, and whether each of your approved
		characters meets the requirements. Gear can be used without meeting them, but with a penalty.
		"""
		await interaction.response.defer(ephemeral=True)
		guild_id = interaction.guild_id
		shop_item = find_item(Gear.shop_items(guild_id, Access.of(interaction.user)), item)
		if shop_item is None :
			return await interaction.followup.send(f"The shop has no item called {item}.", ephemeral=True)
		embed = GearCard.embed(shop_item.item)
		if shop_item.locked :
			embed.add_field(name="Unavailable", value=f"This item {shop_item.locked}.", inline=False)
		lines = []
		for character in self._approved(interaction) :
			unmet = Gear.unmet_requirements(Gear.stats_of(character), shop_item.item)
			lines.append(f"**{character.name}**: " + (f"misses {', '.join(unmet)}" if unmet else "meets them"))
		if lines and shop_item.item.requirements :
			embed.add_field(name="Your characters", value="\n".join(lines)[:1024], inline=False)
		await interaction.followup.send(embed=embed, ephemeral=True)

	# ============================================================
	@app_commands.command(name="buy")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_buyable_items)
	async def buy(self, interaction: discord.Interaction, character: str, item: str) :
		"""
		Buys an item for one of your approved characters, paid with that character's currency. You can buy gear
		your character doesn't have the SPECIAL for; it still works, but with a penalty. Selling it back later
		returns 30% of the price.
		"""
		await interaction.response.defer(ephemeral=True)
		if (record := await find_own_character(interaction, character, approved=True)) is None :
			return
		guild_id = interaction.guild_id
		access = Access.of(interaction.user)
		shop_item = find_item(Gear.shop_items(guild_id, access), item)
		if shop_item is None :
			return await interaction.followup.send(f"The shop has no item called {item}.", ephemeral=True)
		entry, problem = Gear.buy(record, shop_item.item, access, interaction.user.id)
		if problem or entry is None :
			return await interaction.followup.send(problem or "Something went wrong, please try again.", ephemeral=True)
		updated = CharacterTransactions().get_by_id(record.id)
		if entry.price_paid :
			text = (f"{record.name} bought **{entry.name}** for {balance_text(guild_id, entry.price_paid)} and now "
			        f"has {balance_text(guild_id, updated.currency)}.")
		else :
			text = f"{record.name} got **{entry.name}** for free."
		text += " Equip it with /gear equip." + unmet_warning(updated, shop_item.item)
		logging.info(f"{interaction.user.name} bought {entry.name} for character {record.id} for {entry.price_paid}")
		await interaction.followup.send(text, ephemeral=True)
		await refresh_post(self.bot, record.id)


async def setup(bot) :
	await bot.add_cog(Shop(bot))
