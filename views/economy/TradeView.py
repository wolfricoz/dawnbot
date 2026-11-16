"""The buttons under a trade window. Trades are short (they expire after 10 minutes without a press), so the view isn't
kept across restarts; classes/economy/TradeFlow.py does the work."""
import discord

from classes.economy import Trading


class TradeView(discord.ui.View) :

	def __init__(self, trade_id: int) :
		super().__init__(timeout=Trading.EXPIRE_MINUTES * 60)
		self.trade_id = trade_id
		self.client: discord.Client | None = None

	# ============================================================
	async def on_timeout(self) :
		if self.client is not None :
			from classes.economy.TradeFlow import TradeFlow

			await TradeFlow.expire(self.client, self.trade_id)

	# ============================================================
	@discord.ui.button(label="Offer items", emoji="🎒", style=discord.ButtonStyle.primary)
	async def items(self, interaction: discord.Interaction, button: discord.ui.Button) :
		from classes.economy.TradeFlow import TradeFlow

		await TradeFlow.add_items(interaction, self.trade_id, self)

	# ============================================================
	@discord.ui.button(label="Offer currency", emoji="💰", style=discord.ButtonStyle.primary)
	async def currency(self, interaction: discord.Interaction, button: discord.ui.Button) :
		from classes.economy.TradeFlow import TradeFlow

		await TradeFlow.add_currency(interaction, self.trade_id, self)

	# ============================================================
	@discord.ui.button(label="Clear my offer", emoji="🧹", style=discord.ButtonStyle.secondary)
	async def clear(self, interaction: discord.Interaction, button: discord.ui.Button) :
		from classes.economy.TradeFlow import TradeFlow

		trade, side = await TradeFlow._side(interaction, self.trade_id)
		if trade is not None :
			await TradeFlow.change(interaction, self.trade_id, side, self, items=[], currency=0)

	# ============================================================
	@discord.ui.button(label="Accept", emoji="✅", style=discord.ButtonStyle.success)
	async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) :
		from classes.economy.TradeFlow import TradeFlow

		await TradeFlow.accept(interaction, self.trade_id, self)

	# ============================================================
	@discord.ui.button(label="Cancel", emoji="✖️", style=discord.ButtonStyle.danger)
	async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) :
		from classes.economy.TradeFlow import TradeFlow

		await TradeFlow.cancel(interaction, self.trade_id, self)
