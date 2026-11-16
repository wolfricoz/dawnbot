"""The market: characters sell items to other players' characters at a fixed price, one post per item in the market
forum. Buyers press Buy on the post; the market keeps a small fee, and unsold items go back after a while.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.economy import Trading
from classes.economy.MarketFlow import MarketFlow, PRICE_LIMIT
from classes.kernel import RoleplaySettings
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.TradeTransactions import TradeTransactions
from modules.Gear import entry_choices
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import reply

LIST_LIMIT = 4000


@app_commands.guild_only()
class Market(commands.GroupCog, name="Market", group_name="market") :
	"""Sell items to other players' characters at a fixed price."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _sellable(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		name = interaction.namespace.character
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name) if name else None
		if character is None :
			return []
		entries = [entry for entry in CharacterGearTransactions().get_all(character.id)
		           if Trading.tradable(entry) is None]
		return entry_choices(entries, current)

	# ============================================================
	async def _listings(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		staff = interaction.user.guild_permissions.manage_messages
		return [Choice(name=f"{listing.name} · {listing.price}"[:100], value=str(listing.id))
		        for listing in TradeTransactions().listings(interaction.guild_id)
		        if (staff or listing.seller_uid == interaction.user.id) and current.lower() in listing.name.lower()][:25]

	# ============================================================
	@app_commands.command(name="sell", description="Lists an item on the market")
	@app_commands.autocomplete(character=AutoComplete().approved_character, item=_sellable)
	@app_commands.describe(character="Your character", item="What it sells (equipped items have to be put away)",
	                       price="The asking price")
	async def sell(self, interaction: discord.Interaction, character: str, item: str,
	               price: app_commands.Range[int, 1, PRICE_LIMIT]) :
		"""
		Puts an item up for sale in the market forum at a fixed price. While it is listed it is out of your
		character's inventory and fights. When another player's character buys it, your character gets the price
		minus the market's fee (MARKET_FEE, 5% by default). Unsold items come back after MARKET_DAYS (14 by
		default); withdraw a listing sooner with its Withdraw button or /market withdraw.
		"""
		await MarketFlow.sell(interaction, character, item, price)

	# ============================================================
	@app_commands.command(name="browse", description="Lists what is for sale on the market")
	async def browse(self, interaction: discord.Interaction) :
		"""
		Lists everything for sale on the market, cheapest first, with a link to each post. Buy with the Buy button
		on the post.
		"""
		guild_id = interaction.guild_id
		listings = sorted(TradeTransactions().listings(guild_id), key=lambda listing : listing.price)
		if not listings :
			return await reply(interaction, "Nothing is for sale on the market.")
		currency = ConfigData().get_key(guild_id, ConfigMapping.CURRENCY_NAME)
		lines = [f"**{listing.name}** · {listing.price} {currency}" + (f" · <#{listing.thread_id}>"
		                                                              if listing.thread_id else "")
		         for listing in listings]
		embed = discord.Embed(title="Market", description="\n".join(lines)[:LIST_LIMIT],
		                      colour=discord.Colour.dark_gold())
		embed.set_footer(text=f"The market keeps {RoleplaySettings.number(guild_id, ConfigMapping.MARKET_FEE)}% of "
		                      f"each sale.")
		await interaction.response.send_message(embed=embed, ephemeral=True)

	# ============================================================
	@app_commands.command(name="withdraw", description="Takes a listing off the market")
	@app_commands.autocomplete(listing=_listings)
	async def withdraw(self, interaction: discord.Interaction, listing: str) :
		"""
		Takes one of your listings off the market; the item goes back to your character. Staff can withdraw any
		listing.
		"""
		if not listing.isdigit() :
			return await reply(interaction, "Pick a listing from the list.")
		await MarketFlow.withdraw(interaction, int(listing))


async def setup(bot) :
	await bot.add_cog(Market(bot))
