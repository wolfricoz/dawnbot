"""The buttons under a market listing. They carry the listing's id, so they keep working after a restart (registered
with bot.add_dynamic_items in setup_hook)."""
import discord

from database.database import MarketListings

ACTIONS = {"buy" : ("Buy", "🛒", discord.ButtonStyle.success),
           "withdraw" : ("Withdraw", "↩️", discord.ButtonStyle.secondary)}


class MarketButton(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"market:(?P<listing>\d+):(?P<action>buy|withdraw)") :

	def __init__(self, listing_id: int, action: str) :
		label, emoji, style = ACTIONS[action]
		super().__init__(discord.ui.Button(label=label, emoji=emoji, style=style,
		                                   custom_id=f"market:{listing_id}:{action}"))
		self.listing_id = listing_id
		self.action = action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(int(match["listing"]), match["action"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		from classes.economy.MarketFlow import MarketFlow

		if self.action == "buy" :
			await MarketFlow.start_buy(interaction, self.listing_id)
		else :
			await MarketFlow.withdraw(interaction, self.listing_id)


# ============================================================
def market_view(listing: MarketListings) -> discord.ui.View | None :
	if listing.state != "open" :
		return None
	view = discord.ui.View(timeout=None)
	for action in ACTIONS :
		view.add_item(MarketButton(listing.id, action))
	return view
