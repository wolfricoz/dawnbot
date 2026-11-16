"""The trade window (design/economy.md, phase 3): /trade opens a message with both characters' offers and buttons for
the two players. Each adds items and currency to their side and presses Accept; any change clears both accepts, and
once both have accepted the bot swaps everything at once. The window expires after 10 minutes without a press.

The rules live in classes/economy/Trading.py; the transfer itself in TradeTransactions.transfer.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord

from classes.economy import Trading
from classes.gear.Gear import Gear
from classes.kernel.ConfigData import ConfigData
from database.database import Trades
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.TradeTransactions import TradeTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import Field, Form, Option, number, pick, reply

OPEN = "open"
DONE = "done"
CANCELLED = "cancelled"
EXPIRED = "expired"
COLOURS = {OPEN : discord.Colour.dark_gold(), DONE : discord.Colour.green(), CANCELLED : discord.Colour.dark_grey(),
           EXPIRED : discord.Colour.dark_grey()}
TITLES = {DONE : "Trade done", CANCELLED : "Trade cancelled", EXPIRED : "Trade expired"}


class TradeFlow :
	locks: dict[int, asyncio.Lock] = {}

	# ============================================================
	@staticmethod
	def lock(trade_id: int) -> asyncio.Lock :
		return TradeFlow.locks.setdefault(trade_id, asyncio.Lock())

	# == showing ==

	# ============================================================
	@staticmethod
	def embed(trade: Trades) -> discord.Embed :
		currency = ConfigData().get_key(trade.guild_id, ConfigMapping.CURRENCY_NAME)
		names = {}
		embed = discord.Embed(title=TITLES.get(trade.state, "Trade"), colour=COLOURS.get(trade.state))
		for side in Trading.SIDES :
			character = CharacterTransactions().get_by_id(Trading.character_of(trade, side))
			names[side] = character.name if character else "?"
			current = Trading.offer(trade, side)
			lines = []
			for entry_id in current["items"] :
				entry = CharacterGearTransactions().get(entry_id)
				if entry is not None :
					lines.append(f"• {Trading.item_line(entry)}")
			if current["currency"] :
				lines.append(f"• {current['currency']} {currency}")
			accepted = " ✅" if side in (trade.accepted or []) else ""
			uid = trade.left_uid if side == Trading.LEFT else trade.right_uid
			embed.add_field(name=f"{names[side]}{accepted}", value=(f"<@{uid}> offers:\n" +
			                                                        ("\n".join(lines) or "nothing yet"))[:1024])
		if trade.state == OPEN :
			embed.set_footer(text="Add what you offer, then both press Accept. Any change clears both accepts. The "
			                      "window expires after 10 minutes without a press.")
		return embed

	# ============================================================
	@staticmethod
	async def refresh(interaction: discord.Interaction, trade: Trades, view: discord.ui.View | None) -> None :
		"""Updates the trade message (the interaction may come from a private picker)."""
		try :
			channel = interaction.client.get_channel(trade.channel_id) or await interaction.client.fetch_channel(
				trade.channel_id)
			await channel.get_partial_message(trade.message_id).edit(embed=TradeFlow.embed(trade), view=view)
		except (discord.HTTPException, AttributeError) as e :
			logging.warning(f"Could not update trade {trade.id}: {e}")

	# == starting ==

	# ============================================================
	@staticmethod
	async def start(interaction: discord.Interaction, mine_name: str, member: discord.Member, theirs_name: str) -> None :
		from views.economy.TradeView import TradeView

		guild_id = interaction.guild_id
		if not Trading.trading_on(guild_id) :
			return await reply(interaction, "Trading is off on this server.")
		mine = CharacterTransactions().get(interaction.user.id, guild_id, mine_name)
		theirs = CharacterTransactions().get(member.id, guild_id, theirs_name)
		problem = Trading.pair_problem(mine, theirs)
		if problem :
			return await reply(interaction, problem)
		for character in (mine, theirs) :
			TradeFlow.expire_stale(character.id)
			if TradeTransactions().open_trades(character.id) :
				return await reply(interaction, f"{character.name} is already in a trade; finish or cancel it first.")
		trade = TradeTransactions().add_trade(guild_id, mine, theirs)
		view = TradeView(trade.id)
		view.client = interaction.client
		await interaction.response.send_message(f"<@{member.id}>, {mine.name} wants to trade with {theirs.name}.",
		                                        embed=TradeFlow.embed(trade), view=view,
		                                        allowed_mentions=discord.AllowedMentions(users=[member]))
		message = await interaction.original_response()
		TradeTransactions().update_trade(trade.id, channel_id=message.channel.id, message_id=message.id)

	# ============================================================
	@staticmethod
	def expire_stale(character_id: int, now: datetime | None = None) -> None :
		"""Open trades older than the window (left over from a restart) expire."""
		now = now or datetime.now(timezone.utc)
		for trade in TradeTransactions().open_trades(character_id) :
			if trade.created_at is not None and trade.created_at < now - timedelta(minutes=Trading.EXPIRE_MINUTES * 6) :
				TradeTransactions().update_trade(trade.id, state=EXPIRED, finished_at=now)

	# == the buttons ==

	# ============================================================
	@staticmethod
	async def _side(interaction: discord.Interaction, trade_id: int) -> tuple[Trades | None, str | None] :
		trade = TradeTransactions().trade(trade_id)
		if trade is None or trade.state != OPEN :
			await reply(interaction, "This trade is over.")
			return None, None
		side = Trading.side_of(trade, interaction.user.id)
		if side is None :
			await reply(interaction, "Only the two traders can use this.")
			return None, None
		return trade, side

	# ============================================================
	@staticmethod
	async def add_items(interaction: discord.Interaction, trade_id: int, view) -> None :
		trade, side = await TradeFlow._side(interaction, trade_id)
		if trade is None :
			return
		current = set(Trading.offer(trade, side)["items"])
		entries = [entry for entry in CharacterGearTransactions().get_all(Trading.character_of(trade, side))
		           if Trading.tradable(entry) is None]
		if not entries :
			return await reply(interaction, "Your character has nothing to offer (equipped items have to be put "
			                                "away first).")
		options = [Option(Trading.item_line(entry)[:100], str(entry.id), default=entry.id in current)
		           for entry in entries[:25]]

		async def chosen(pick_interaction: discord.Interaction, values: list[str]) :
			await TradeFlow.change(pick_interaction, trade_id, side, view, items=[int(value) for value in values])

		await pick(interaction, "What does your character offer? (Pick all of it; leaving an item out takes it back.)",
		           options, "Items to offer", chosen, max_values=len(options))

	# ============================================================
	@staticmethod
	async def add_currency(interaction: discord.Interaction, trade_id: int, view) -> None :
		trade, side = await TradeFlow._side(interaction, trade_id)
		if trade is None :
			return
		if not Gear.economy(trade.guild_id) :
			return await reply(interaction, "There is no currency in free mode.")
		character = CharacterTransactions().get_by_id(Trading.character_of(trade, side))

		async def submitted(form_interaction: discord.Interaction, values: list[str]) :
			amount = number(values[0])
			if amount is None or amount < 0 :
				return await reply(form_interaction, "Type a whole number of 0 or more.")
			if amount > character.currency :
				return await reply(form_interaction, f"{character.name} has only {character.currency}.")
			await TradeFlow.change(form_interaction, trade_id, side, view, currency=amount)

		current = Trading.offer(trade, side)["currency"]
		await interaction.response.send_modal(Form("Offer currency", [
			Field(f"Amount ({character.name} has {character.currency})", default=str(current), max_length=12)],
			submitted))

	# ============================================================
	@staticmethod
	async def change(interaction: discord.Interaction, trade_id: int, side: str, view, items: list[int] | None = None,
	                 currency: int | None = None) -> None :
		async with TradeFlow.lock(trade_id) :
			trade = TradeTransactions().trade(trade_id)
			if trade is None or trade.state != OPEN :
				return await reply(interaction, "This trade is over.")
			trade = TradeTransactions().update_trade(trade.id, offers=Trading.with_offer(trade, side, items, currency),
			                                         accepted=[])
		await TradeFlow.refresh(interaction, trade, view)
		await reply(interaction, "Offer changed; both sides have to accept again.")

	# ============================================================
	@staticmethod
	async def accept(interaction: discord.Interaction, trade_id: int, view) -> None :
		trade, side = await TradeFlow._side(interaction, trade_id)
		if trade is None :
			return
		async with TradeFlow.lock(trade_id) :
			trade = TradeTransactions().trade(trade_id)
			if trade is None or trade.state != OPEN :
				return await reply(interaction, "This trade is over.")
			problem = Trading.check(trade)
			if problem :
				return await reply(interaction, problem)
			accepted = sorted(set(trade.accepted or []) | {side})
			trade = TradeTransactions().update_trade(trade.id, accepted=accepted)
			done = set(accepted) == set(Trading.SIDES)
			if done :
				problem = TradeTransactions().transfer(Trading.build_transfer(trade, interaction.user.id),
				                                       trade.guild_id)
				if problem :
					TradeTransactions().update_trade(trade.id, accepted=[])
					trade = TradeTransactions().trade(trade.id)
					await TradeFlow.refresh(interaction, trade, view)
					return await reply(interaction, f"The trade couldn't go through: {problem}")
				trade = TradeTransactions().update_trade(trade.id, state=DONE,
				                                         finished_at=datetime.now(timezone.utc))
				logging.info(f"Trade {trade.id} done between characters {trade.left_character_id} and "
				             f"{trade.right_character_id}")
		if done :
			view.stop()
			await TradeFlow.refresh(interaction, trade, None)
			await TradeFlow.refresh_posts(interaction.client, trade)
			return await reply(interaction, "Trade done.")
		await TradeFlow.refresh(interaction, trade, view)
		await reply(interaction, "You accepted; waiting for the other side.")

	# ============================================================
	@staticmethod
	async def cancel(interaction: discord.Interaction, trade_id: int, view) -> None :
		trade, side = await TradeFlow._side(interaction, trade_id)
		if trade is None :
			return
		trade = TradeTransactions().update_trade(trade.id, state=CANCELLED, finished_at=datetime.now(timezone.utc))
		view.stop()
		await TradeFlow.refresh(interaction, trade, None)
		await reply(interaction, "Trade cancelled.")

	# ============================================================
	@staticmethod
	async def expire(client: discord.Client, trade_id: int) -> None :
		trade = TradeTransactions().trade(trade_id)
		if trade is None or trade.state != OPEN :
			return
		trade = TradeTransactions().update_trade(trade.id, state=EXPIRED, finished_at=datetime.now(timezone.utc))
		try :
			channel = client.get_channel(trade.channel_id) or await client.fetch_channel(trade.channel_id)
			await channel.get_partial_message(trade.message_id).edit(embed=TradeFlow.embed(trade), view=None)
		except (discord.HTTPException, AttributeError) as e :
			logging.warning(f"Could not close trade {trade.id}: {e}")

	# ============================================================
	@staticmethod
	async def refresh_posts(client: discord.Client, trade: Trades) -> None :
		from modules.Gear import refresh_post

		for side in Trading.SIDES :
			await refresh_post(client, Trading.character_of(trade, side))
