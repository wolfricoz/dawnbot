"""The Discord side of roll tables: rolling one (publicly or secretly), the roll card, and the Grant and Start fight
buttons that apply a roll's actions. The rules live in classes/tables/Tables.py."""
import logging

import discord

from classes.characters.Special import Special
from classes.checks import RollLog
from classes.kernel.ConfigData import ConfigData
from classes.tables import Tables
from database.database import Characters, RollTables, TableRolls
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.RollTableTransactions import RollTableTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import Option, pick, reply

EVERYONE = "everyone"
STAFF = "staff"
VISIBILITIES = [EVERYONE, STAFF]
CARD_COLOUR = discord.Colour.gold()


class TableFlow :

	# ============================================================
	@staticmethod
	def is_staff(member) -> bool :
		permissions = getattr(member, "guild_permissions", None)
		return bool(permissions and permissions.manage_messages)

	# ============================================================
	@staticmethod
	def visible(table: RollTables, member) -> bool :
		return table.visibility != STAFF or TableFlow.is_staff(member)

	# ============================================================
	@staticmethod
	def lookup(guild_id: int, member=None) :
		"""Finds tables by name for [[nested]] rolls. Staff-only tables can be nested in any table: the roll happens
		on the server's side and only its result shows."""

		def find(name: str) :
			table = RollTableTransactions().find(guild_id, name)
			if table is None :
				return None
			return table.dice, RollTableTransactions().entries(table.id)

		return find

	# == rolling ==

	# ============================================================
	@staticmethod
	async def roll(interaction: discord.Interaction, table_name: str, character_name: str | None,
	               secret: bool) -> None :
		guild_id = interaction.guild_id
		table = RollTableTransactions().find(guild_id, table_name)
		if table is None or not TableFlow.visible(table, interaction.user) :
			return await reply(interaction, f"There is no table called {table_name}.")
		character = None
		if character_name :
			character = CharacterTransactions().get(interaction.user.id, guild_id, character_name)
			if character is None or character.state != APPROVED :
				return await reply(interaction, f"You have no approved character called {character_name}.")
		record, rolled, shift = TableFlow.make_roll(guild_id, table, interaction.user.id, character,
		                                            interaction.channel_id, secret)
		if rolled is None :
			return await reply(interaction, f"{table.name} has no entries to roll.")
		if record is None :
			return await reply(interaction, "Something went wrong saving the roll; please try again.")
		logging.info(f"{interaction.user.name} rolled {rolled.rolled} on table {table.id} in {interaction.guild.name}")
		embed = TableFlow.embed(record, table, character, shift, rolled.notes)
		from views.tables.TableButtons import roll_view, secret_view

		if secret :
			await interaction.response.send_message("🔒 Only you see this roll.", embed=embed,
			                                        view=secret_view(record, embed), ephemeral=True)
			await RollLog.post(interaction.guild, f"🔒 Secret roll on **{table.name}** by <@{interaction.user.id}> in "
			                                      f"<#{interaction.channel_id}>: {rolled.rolled} → {rolled.text}")
			return
		view = roll_view(record)
		if view is None :
			await interaction.response.send_message(embed=embed)
		else :
			await interaction.response.send_message(embed=embed, view=view)

	# ============================================================
	@staticmethod
	def make_roll(guild_id: int, table: RollTables, uid: int, character: Characters | None, channel_id: int | None,
	              secret: bool = False) :
		"""Rolls a table and keeps the roll. Returns (record, rolled, Luck shift); rolled is None when the table has no
		entries, record None when it couldn't be saved."""
		entries = RollTableTransactions().entries(table.id)
		shift = 0
		if table.luck and character is not None :
			shift = Tables.luck_shift(character.luck, Special.rules(guild_id).base)
		rolled = Tables.roll(entries, table.dice, TableFlow.lookup(guild_id), shift=shift)
		if rolled is None :
			return None, None, shift
		record = RollTableTransactions().add_roll(guild_id, table, uid,
		                                          character_id=character.id if character else None,
		                                          channel_id=channel_id, natural=rolled.natural,
		                                          rolled=rolled.rolled, text=rolled.text, actions=rolled.actions,
		                                          secret=secret)
		return record, rolled, shift

	# ============================================================
	@staticmethod
	async def post_roll(channel, table: RollTables, uid: int, character: Characters | None,
	                    heading: str | None = None) -> TableRolls | None :
		"""Rolls a table and posts its card in a channel (travel encounters). Returns the roll."""
		from views.tables.TableButtons import roll_view

		record, rolled, shift = TableFlow.make_roll(channel.guild.id, table, uid, character, channel.id)
		if record is None :
			return None
		embed = TableFlow.embed(record, table, character, shift, rolled.notes)
		view = roll_view(record)
		try :
			await channel.send(content=heading, embed=embed, view=view or discord.utils.MISSING,
			                   allowed_mentions=discord.AllowedMentions.none())
		except discord.HTTPException as e :
			logging.warning(f"Could not post a roll on table {table.id}: {e}")
		return record

	# ============================================================
	@staticmethod
	def embed(record: TableRolls, table: RollTables | None, character: Characters | None, shift: int = 0,
	          notes: list[str] | None = None) -> discord.Embed :
		embed = discord.Embed(title=f"🎲 {record.table_name}"[:256], description=record.text[:4096], colour=CARD_COLOUR)
		if character is not None :
			embed.set_author(name=f"{character.name} rolls on {record.table_name}"[:256])
		currency = ConfigData().get_key(record.guild_id, ConfigMapping.CURRENCY_NAME)
		rewards, encounter = Tables.actions_summary(record.actions or [], currency)
		if rewards :
			embed.add_field(name="Rewards", value=", ".join(rewards)[:1024], inline=False)
		if encounter :
			embed.add_field(name="Encounter", value=", ".join(encounter)[:1024], inline=False)
		if record.granted_to :
			names = [character.name for character in
			         (CharacterTransactions().get_by_id(character_id) for character_id in record.granted_to)
			         if character is not None]
			embed.add_field(name="Granted", value=f"✅ to {', '.join(names) or 'a character'}", inline=False)
		if notes :
			embed.add_field(name="Notes", value="\n".join(notes)[:1024], inline=False)
		dice = "weighted" if table is not None and table.dice == Tables.WEIGHTS else (table.dice if table else "")
		footer = f"Rolled {record.natural}" + (f" {shift:+d} Luck = {record.rolled}" if shift else "") + \
		         (f" on {dice}" if dice else "")
		embed.set_footer(text=footer)
		return embed

	# == granting ==

	# ============================================================
	@staticmethod
	def rewards_of(record: TableRolls) -> list[dict] :
		return [action for action in record.actions or [] if action.get("kind") in (Tables.ITEM, Tables.CURRENCY,
		                                                                              Tables.XP)]

	# ============================================================
	@staticmethod
	async def start_grant(interaction: discord.Interaction, roll_id: int) -> None :
		record = RollTableTransactions().get_roll(roll_id)
		if record is None :
			return await reply(interaction, "That roll no longer exists.")
		if not TableFlow.is_staff(interaction.user) :
			return await reply(interaction, "Only staff (Manage Messages) can grant a roll's rewards.")
		if not TableFlow.rewards_of(record) :
			return await reply(interaction, "This roll has no rewards to grant.")
		if record.granted_to :
			return await reply(interaction, "This roll's rewards were already granted.")
		card = interaction.message
		if record.character_id :
			character = CharacterTransactions().get_by_id(record.character_id)
			if character is not None and character.state == APPROVED :
				return await TableFlow.grant(interaction, roll_id, character.id, card)
		from views.tables.TableButtons import MemberPickView

		async def member_chosen(next_interaction: discord.Interaction, member: discord.abc.User) :
			characters = CharacterTransactions().get_all(member.id, next_interaction.guild_id, states=[APPROVED])
			if not characters :
				return await reply(next_interaction, f"{member.display_name} has no approved characters.")
			if len(characters) == 1 :
				return await TableFlow.grant(next_interaction, roll_id, characters[0].id, card)
			await pick(next_interaction, "Which character gets the rewards?",
			           [Option(character.name, character.id, f"Level {character.level}") for character in characters],
			           "Pick a character",
			           lambda last, values : TableFlow.grant(last, roll_id, int(values[0]), card))

		await interaction.response.send_message("Who gets the rewards?",
		                                        view=MemberPickView(interaction.user.id, member_chosen),
		                                        ephemeral=True)

	# ============================================================
	@staticmethod
	async def grant(interaction: discord.Interaction, roll_id: int, character_id: int,
	                card: discord.Message | None = None) -> None :
		from classes.characters.ForumPost import ForumPost
		from classes.gear.Gear import Gear
		from database.transactions.GearItemTransactions import GearItemTransactions

		if not interaction.response.is_done() :
			await interaction.response.defer(ephemeral=True, thinking=True)
		record = RollTableTransactions().get_roll(roll_id)
		character = CharacterTransactions().get_by_id(character_id)
		if record is None or character is None :
			return await reply(interaction, "That roll or character no longer exists.")
		if record.granted_to :
			return await reply(interaction, "This roll's rewards were already granted.")
		# Marked first, so a second press can't grant twice.
		RollTableTransactions().update_roll(roll_id, granted_to=[character.id])
		given, missing = [], []
		currency_name = ConfigData().get_key(record.guild_id, ConfigMapping.CURRENCY_NAME)
		for action in TableFlow.rewards_of(record) :
			kind = action.get("kind")
			if kind == Tables.ITEM :
				item = GearItemTransactions().find(record.guild_id, action.get("name") or "")
				if item is None :
					missing.append(str(action.get("name")))
					continue
				Gear.grant(character, item, interaction.user.id)
				given.append(item.name)
			elif kind == Tables.CURRENCY and action.get("amount") :
				Gear.give_currency(character, int(action["amount"]), interaction.user.id,
				                   note=f"Table: {record.table_name}")
				given.append(f"{action['amount']} {currency_name}")
			elif kind == Tables.XP and action.get("amount") :
				Special.add_xp(character, int(action["amount"]))
				given.append(f"{action['amount']} XP")
		updated = CharacterTransactions().get_by_id(character.id)
		if updated is not None and updated.state == APPROVED :
			await ForumPost.sync(interaction.client, updated)
		text = f"🎁 {interaction.user.mention} gives {character.name}: {', '.join(given) or 'nothing'}"
		if missing :
			text += f". Not in the catalog, so not given: {', '.join(missing)}"
		await reply(interaction, text + ".")
		if card is not None and not record.secret :
			record = RollTableTransactions().get_roll(roll_id)
			try :
				from views.tables.TableButtons import roll_view

				await card.edit(embed=TableFlow.embed(record, RollTableTransactions().get(record.table_id), None),
				                view=roll_view(record))
			except discord.HTTPException :
				pass
			try :
				await card.channel.send(text[:2000] + ".", allowed_mentions=discord.AllowedMentions.none())
			except discord.HTTPException :
				pass

	# == fights ==

	# ============================================================
	@staticmethod
	async def start_fight(interaction: discord.Interaction, roll_id: int) -> None :
		from classes.combat.CombatFlow import CombatFlow
		from classes.combat.Loadout import Loadout
		from database.transactions.BestiaryTransactions import BestiaryTransactions
		from database.transactions.CombatTransactions import CombatTransactions

		record = RollTableTransactions().get_roll(roll_id)
		if record is None :
			return await reply(interaction, "That roll no longer exists.")
		if record.uid != interaction.user.id and not TableFlow.is_staff(interaction.user) :
			return await reply(interaction, "Only whoever rolled this (or staff) can start the fight.")
		if record.fight_id :
			fight = CombatTransactions().load(record.fight_id)
			if fight is not None :
				return await reply(interaction, f"A fight was already started for this roll: <#{fight.thread_id}>.")
		npcs = [action for action in record.actions or [] if action.get("kind") == Tables.NPC]
		found, missing = [], []
		for action in npcs :
			entry = BestiaryTransactions().find(record.guild_id, action.get("name") or "")
			if entry is None :
				missing.append(str(action.get("name")))
			else :
				found.append((entry, int(action.get("count") or 1)))
		if not found :
			return await reply(interaction, f"The bestiary has none of these NPCs: {', '.join(missing)}. Add them with "
			                                f"/bestiary add or /bestiary import." if missing else
			                   "This roll has no NPCs to fight.")
		fight = await CombatFlow.start(interaction, record.table_name, None, False)
		if fight is None :
			return
		RollTableTransactions().update_roll(roll_id, fight_id=fight.id)
		enemies = fight.sides[-1].id
		for entry, count in found :
			await CombatFlow.add_npcs(interaction.client, fight.id,
			                          lambda name, side, position, entry=entry : Loadout.for_bestiary(entry, side, name,
			                                                                                          position),
			                          count, enemies, entry.name)
		if missing :
			await reply(interaction, f"Not in the bestiary, so not added: {', '.join(missing)}.")
