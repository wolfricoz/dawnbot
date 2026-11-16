"""The market (design/economy.md, phase 3): characters sell items to other players' characters at a fixed price, one
post per item in the MARKET forum. While listed, an item is out of its owner's inventory and fights. Anyone else
presses Buy and picks a character; the buyer pays the price, the seller gets it minus MARKET_FEE percent (which
leaves the economy), and the item changes hands in one step. The seller (or staff) can withdraw a listing, and an
unsold one ends after MARKET_DAYS, the item going back to the seller. The market needs economy mode and trading on.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord

from classes.economy import Trading
from classes.gear import Carry
from classes.gear.Gear import Gear
from classes.gear.GearCard import GearCard
from classes.kernel import RoleplaySettings
from classes.kernel.ConfigData import ConfigData
from database.database import Characters, MarketListings
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.TradeTransactions import Move, Payment, TradeTransactions, Transfer
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import Option, pick, reply

OPEN = "open"
SOLD = "sold"
WITHDRAWN = "withdrawn"
EXPIRED = "expired"
MARKS = {OPEN : "🟢", SOLD : "✅", WITHDRAWN : "⚪", EXPIRED : "⌛"}
MARKET_REASON = "market"
FEE_REASON = "market_fee"
LISTED = "listed"
PRICE_LIMIT = 1000000000


# ============================================================
def fee_for(guild_id: int, price: int) -> int :
	return price * RoleplaySettings.number(guild_id, ConfigMapping.MARKET_FEE) // 100


# ============================================================
def problem_for(guild_id: int) -> str | None :
	if not Gear.economy(guild_id) :
		return "There is no market in free mode."
	if not Trading.trading_on(guild_id) :
		return "Trading is off on this server."
	return None


# ============================================================
def purchase(listing: MarketListings, buyer: Characters, actor_uid: int) -> tuple[Transfer, int] :
	"""The transfer for buying a listing, and the fee: the buyer pays the price, the seller gets it minus the fee."""
	seller = CharacterTransactions().get_by_id(listing.seller_character_id) if listing.seller_character_id else None
	seller_name = seller.name if seller else "a seller"
	fee = fee_for(listing.guild_id, listing.price)
	transfer = Transfer(moves=[Move(listing.entry_id, listing.seller_character_id, buyer.id, (LISTED,), "market")],
	                    payments=[Payment(buyer.id, -listing.price, MARKET_REASON,
	                                      f"Bought {listing.name} from {seller_name}", actor_uid)])
	if listing.seller_character_id :
		transfer.payments.append(Payment(listing.seller_character_id, listing.price, MARKET_REASON,
		                                 f"Sold {listing.name} to {buyer.name}", actor_uid))
		if fee :
			transfer.payments.append(Payment(listing.seller_character_id, -fee, FEE_REASON, listing.name, actor_uid))
	return transfer, fee


# ============================================================
def buy_problem(listing: MarketListings, buyer: Characters) -> str | None :
	"""Why this character can't buy the listing, or None (checked again inside the transfer)."""
	if listing.state != OPEN :
		return "This listing isn't open any more."
	if buyer.state != APPROVED or buyer.guild_id != listing.guild_id :
		return "Pick one of your approved characters."
	if buyer.uid == listing.seller_uid :
		return "You can't buy your own listing."
	if buyer.currency < listing.price :
		return f"{buyer.name} has {buyer.currency}, not enough."
	entry = CharacterGearTransactions().get(listing.entry_id) if listing.entry_id else None
	item = GearItemTransactions().get(entry.gear_item_id) if entry is not None else None
	if entry is None :
		return "The item is gone."
	if item is not None :
		return Carry.too_heavy(buyer, item, max(1, entry.quantity or 1))
	return None


class MarketFlow :
	locks: dict[int, asyncio.Lock] = {}

	# ============================================================
	@staticmethod
	def lock(listing_id: int) -> asyncio.Lock :
		return MarketFlow.locks.setdefault(listing_id, asyncio.Lock())

	# ============================================================
	@staticmethod
	def embed(listing: MarketListings) -> discord.Embed :
		entry = CharacterGearTransactions().get(listing.entry_id) if listing.entry_id else None
		item = GearItemTransactions().get(entry.gear_item_id) if entry is not None else None
		embed = GearCard.embed(item) if item is not None else discord.Embed(title=listing.name[:256])
		embed.title = f"{MARKS.get(listing.state, '')} {Trading.item_line(entry) if entry else listing.name}"[:256]
		embed.colour = discord.Colour.dark_gold() if listing.state == OPEN else discord.Colour.dark_grey()
		currency = ConfigData().get_key(listing.guild_id, ConfigMapping.CURRENCY_NAME)
		seller = CharacterTransactions().get_by_id(listing.seller_character_id) if listing.seller_character_id else None
		embed.insert_field_at(0, name="Asking", value=f"**{listing.price} {currency}**", inline=True)
		embed.insert_field_at(1, name="Seller", value=f"{seller.name if seller else '?'} (<@{listing.seller_uid}>)",
		                      inline=True)
		if listing.state == OPEN and listing.expires_at :
			embed.add_field(name="Ends", value=discord.utils.format_dt(listing.expires_at, "R"))
		elif listing.state == SOLD and listing.buyer_character_id :
			buyer = CharacterTransactions().get_by_id(listing.buyer_character_id)
			embed.add_field(name="Sold to", value=buyer.name if buyer else "?")
		elif listing.state in (WITHDRAWN, EXPIRED) :
			embed.add_field(name="Ended", value="withdrawn by the seller" if listing.state == WITHDRAWN else
			                "nobody bought it in time")
		return embed

	# ============================================================
	@staticmethod
	def thread_name(listing: MarketListings) -> str :
		return f"{MARKS.get(listing.state, '')} {listing.name} · {listing.price}"[:100]

	# ============================================================
	@staticmethod
	async def refresh(client: discord.Client, listing_id: int) -> None :
		from views.economy.MarketButtons import market_view

		listing = TradeTransactions().listing(listing_id)
		if listing is None or listing.thread_id is None :
			return
		try :
			thread = client.get_channel(listing.thread_id) or await client.fetch_channel(listing.thread_id)
			await thread.get_partial_message(listing.message_id or listing.thread_id).edit(
				embed=MarketFlow.embed(listing), view=market_view(listing))
			if isinstance(thread, discord.Thread) :
				over = listing.state != OPEN
				await thread.edit(name=MarketFlow.thread_name(listing), locked=over, archived=over)
		except discord.HTTPException as e :
			logging.warning(f"Could not update market listing {listing_id}: {e}")

	# == selling ==

	# ============================================================
	@staticmethod
	async def sell(interaction: discord.Interaction, character_name: str, item: str, price: int) -> None :
		from modules.Gear import find_entry
		from views.economy.MarketButtons import market_view

		guild = interaction.guild
		problem = problem_for(guild.id)
		if problem :
			return await reply(interaction, problem)
		board = await ConfigData().get_channel(guild, ConfigMapping.MARKET, optional=True)
		if not isinstance(board, discord.ForumChannel) :
			return await reply(interaction, "This server has no market forum; staff set one with /config "
			                                "singlechannels.")
		seller = CharacterTransactions().get(interaction.user.id, guild.id, character_name)
		if seller is None or seller.state != APPROVED :
			return await reply(interaction, "Pick one of your approved characters.")
		entry = find_entry(CharacterGearTransactions().get_all(seller.id), item)
		if entry is None :
			return await reply(interaction, f"{seller.name} doesn't own {item}.")
		problem = Trading.tradable(entry)
		if problem :
			return await reply(interaction, problem)
		days = RoleplaySettings.number(guild.id, ConfigMapping.MARKET_DAYS)
		listing = TradeTransactions().add_listing(guild.id, entry, seller, price,
		                                          datetime.now(timezone.utc) + timedelta(days=days))
		if listing is None :
			return await reply(interaction, f"{entry.name} can't be listed right now.")
		await interaction.response.defer(ephemeral=True)
		try :
			created = await board.create_thread(name=MarketFlow.thread_name(listing), embed=MarketFlow.embed(listing),
			                                    view=market_view(listing))
		except discord.HTTPException as e :
			logging.warning(f"Could not post market listing {listing.id}: {e}")
			TradeTransactions().close_listing(listing.id, WITHDRAWN)
			return await reply(interaction, "I couldn't post in the market forum; check my permissions there (and "
			                                "that posts there don't need a tag).")
		TradeTransactions().update_listing(listing.id, thread_id=created.thread.id, message_id=created.message.id)
		logging.info(f"{interaction.user.name} listed gear {entry.id} for {price} (listing {listing.id})")
		fee = fee_for(guild.id, price)
		await reply(interaction, f"🏷️ Listed: {created.thread.mention}. When it sells, {seller.name} gets {price - fee} "
		                         f"(the market keeps {fee}). Unsold, it comes back in {days} days.")

	# == buying ==

	# ============================================================
	@staticmethod
	async def start_buy(interaction: discord.Interaction, listing_id: int) -> None :
		listing = TradeTransactions().listing(listing_id)
		if listing is None or listing.state != OPEN :
			return await reply(interaction, "This listing isn't open any more.")
		if interaction.user.id == listing.seller_uid :
			return await reply(interaction, "You can't buy your own listing; use Withdraw to take it back.")
		characters = CharacterTransactions().get_all(interaction.user.id, interaction.guild_id, states=[APPROVED])
		if not characters :
			return await reply(interaction, "You need an approved character to buy.")
		if len(characters) == 1 :
			return await MarketFlow.buy(interaction, listing_id, characters[0].id)
		await pick(interaction, f"Buy **{listing.name}** for {listing.price} with which character?",
		           [Option(character.name, str(character.id), f"Has {character.currency}") for character in characters],
		           "Pick a character",
		           lambda next_interaction, values : MarketFlow.buy(next_interaction, listing_id, int(values[0])))

	# ============================================================
	@staticmethod
	async def buy(interaction: discord.Interaction, listing_id: int, character_id: int) -> None :
		async with MarketFlow.lock(listing_id) :
			listing = TradeTransactions().listing(listing_id)
			buyer = CharacterTransactions().get_by_id(character_id)
			if listing is None or buyer is None or buyer.uid != interaction.user.id :
				return await reply(interaction, "This listing isn't open any more.")
			problem = problem_for(listing.guild_id) or buy_problem(listing, buyer)
			if problem :
				return await reply(interaction, problem)
			transfer, fee = purchase(listing, buyer, interaction.user.id)
			problem = TradeTransactions().buy_listing(listing.id, transfer, buyer, fee)
			if problem :
				return await reply(interaction, problem)
		logging.info(f"Character {buyer.id} bought market listing {listing.id} for {listing.price}")
		await MarketFlow.refresh(interaction.client, listing_id)
		await reply(interaction, f"{buyer.name} bought **{listing.name}** for {listing.price}.")
		await MarketFlow.tell_seller(interaction.client, listing, f"💰 Your {listing.name} sold on the market for "
		                                                        f"{listing.price} (you got {listing.price - fee}).")
		from modules.Gear import refresh_post

		await refresh_post(interaction.client, buyer.id)

	# ============================================================
	@staticmethod
	async def tell_seller(client: discord.Client, listing: MarketListings, text: str) -> None :
		try :
			user = client.get_user(listing.seller_uid) or await client.fetch_user(listing.seller_uid)
			await user.send(text)
		except (discord.HTTPException, AttributeError) :
			pass

	# == ending ==

	# ============================================================
	@staticmethod
	async def withdraw(interaction: discord.Interaction, listing_id: int) -> None :
		listing = TradeTransactions().listing(listing_id)
		if listing is None or listing.state != OPEN :
			return await reply(interaction, "This listing isn't open any more.")
		staff = getattr(interaction.user, "guild_permissions", None) and interaction.user.guild_permissions.manage_messages
		if interaction.user.id != listing.seller_uid and not staff :
			return await reply(interaction, "Only the seller (or staff) can withdraw a listing.")
		async with MarketFlow.lock(listing_id) :
			closed = TradeTransactions().close_listing(listing_id, WITHDRAWN)
		if closed is None :
			return await reply(interaction, "This listing isn't open any more.")
		await MarketFlow.refresh(interaction.client, listing_id)
		await reply(interaction, f"Withdrawn: {listing.name} is back with its owner.")

	# ============================================================
	@staticmethod
	async def tick(client: discord.Client, now: datetime | None = None) -> None :
		"""Ends listings whose time ran out; the items go back to their sellers."""
		for listing in TradeTransactions().expired_listings(now) :
			async with MarketFlow.lock(listing.id) :
				closed = TradeTransactions().close_listing(listing.id, EXPIRED)
			if closed is None :
				continue
			await MarketFlow.refresh(client, listing.id)
			await MarketFlow.tell_seller(client, listing, f"⌛ Your {listing.name} didn't sell on the market; it's back "
			                                              f"with your character.")
