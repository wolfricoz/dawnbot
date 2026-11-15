"""The buttons under a table roll's card: Grant (staff give the rewards to a character) and Start fight (opens a fight
with the rolled NPCs). They carry the roll's id, so they keep working after a restart (registered with
bot.add_dynamic_items in setup_hook). Also the Show button of a secret roll and a member picker."""
from typing import Awaitable, Callable

import discord

from classes.tables import Tables
from database.database import TableRolls
from database.transactions.RollTableTransactions import RollTableTransactions

GRANT = "grant"
FIGHT = "fight"


class TableRollButton(discord.ui.DynamicItem[discord.ui.Button],
                      template=r"tableroll:(?P<roll>\d+):(?P<action>grant|fight)") :

	def __init__(self, roll_id: int, action: str, label: str | None = None,
	             style: discord.ButtonStyle = discord.ButtonStyle.secondary, emoji: str | None = None) :
		super().__init__(discord.ui.Button(label=label or action.capitalize(), style=style, emoji=emoji,
		                                   custom_id=f"tableroll:{roll_id}:{action}"))
		self.roll_id = roll_id
		self.action = action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(int(match["roll"]), match["action"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		from classes.tables.TableFlow import TableFlow

		if self.action == GRANT :
			await TableFlow.start_grant(interaction, self.roll_id)
		else :
			await TableFlow.start_fight(interaction, self.roll_id)


# ============================================================
def add_buttons(view: discord.ui.View, record: TableRolls) -> bool :
	"""Adds the Grant and Start fight buttons a roll still needs. Returns whether it added any."""
	added = False
	kinds = {action.get("kind") for action in record.actions or []}
	if kinds & {Tables.ITEM, Tables.CURRENCY, Tables.XP} and not record.granted_to :
		view.add_item(TableRollButton(record.id, GRANT, "Grant", discord.ButtonStyle.success, "🎁"))
		added = True
	if Tables.NPC in kinds and not record.fight_id :
		view.add_item(TableRollButton(record.id, FIGHT, "Start fight", discord.ButtonStyle.danger, "⚔️"))
		added = True
	return added


# ============================================================
def roll_view(record: TableRolls) -> discord.ui.View | None :
	view = discord.ui.View(timeout=None)
	return view if add_buttons(view, record) else None


# ============================================================
def secret_view(record: TableRolls, embed: discord.Embed) -> discord.ui.View :
	view = ShowView(record.id, embed)
	add_buttons(view, record)
	return view


class ShowView(discord.ui.View) :
	"""Under a secret roll: Show posts it in the channel for everyone."""

	def __init__(self, roll_id: int, embed: discord.Embed) :
		# Private messages can only be answered for 15 minutes.
		super().__init__(timeout=840)
		self.roll_id = roll_id
		self.embed = embed

	# ============================================================
	@discord.ui.button(label="Show", style=discord.ButtonStyle.primary, emoji="📢", row=1)
	async def show(self, interaction: discord.Interaction, button: discord.ui.Button) :
		record = RollTableTransactions().update_roll(self.roll_id, secret=False)
		view = roll_view(record) if record is not None else None
		await interaction.response.edit_message(content="📢 Shown in the channel.", view=None)
		if view is None :
			await interaction.channel.send(embed=self.embed)
		else :
			await interaction.channel.send(embed=self.embed, view=view)


class MemberPickView(discord.ui.View) :
	"""Picks a member."""

	def __init__(self, user_id: int, on_pick: Callable[[discord.Interaction, discord.abc.User], Awaitable[None]],
	             placeholder: str = "Pick a member") :
		super().__init__(timeout=300)
		self.user_id = user_id
		self.on_pick = on_pick
		select = discord.ui.UserSelect(placeholder=placeholder)
		select.callback = self.picked
		self.select = select
		self.add_item(select)

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		return interaction.user.id == self.user_id

	# ============================================================
	async def picked(self, interaction: discord.Interaction) :
		self.stop()
		await self.on_pick(interaction, self.select.values[0])
