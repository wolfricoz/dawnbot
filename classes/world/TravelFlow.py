"""Travel between locations (design/roleplay-tools.md, section 5): departure and arrival lines, the encounter roll on
dangerous routes, and arrivals that wait for in-world travel time."""
import logging
from datetime import datetime, timezone

import discord

from classes.characters.Special import Special
from classes.kernel import RoleplaySettings
from classes.world.WorldFlow import WorldFlow
from database.database import Characters, Locations, Travels
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.RollTableTransactions import RollTableTransactions
from database.transactions.WorldTransactions import WorldTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import reply


class TravelFlow :

	# ============================================================
	@staticmethod
	async def travel(interaction: discord.Interaction, character_name: str, destination) -> None :
		guild = interaction.guild
		if not RoleplaySettings.toggle(guild.id, ConfigMapping.TRAVEL) :
			return await reply(interaction, "Travel is off on this server; staff turn it on with /config roleplay "
			                                "travel on.")
		character = CharacterTransactions().get(interaction.user.id, guild.id, character_name)
		if character is None or character.state != APPROVED :
			return await reply(interaction, f"You have no approved character called {character_name}.")
		target = WorldFlow.location_here(destination)
		if target is None :
			return await reply(interaction, f"{destination.mention} isn't a location; staff set it up with "
			                                f"/location set.")
		if WorldTransactions().travelling(character.id) is not None :
			return await reply(interaction, f"{character.name} is already on the road.")
		origin = WorldFlow.location_here(interaction.channel) or WorldFlow.where_is(guild, character.id)
		if origin is not None and origin.id == target.id :
			return await reply(interaction, f"{character.name} is already at {target.name}.")
		route = WorldTransactions().route(origin.id, target.id) if origin is not None else None
		hours = route.hours if route else 0
		danger = route.danger if route else target.danger
		table_id = (route.table_id if route else None) or target.table_id
		natural, total, encounter = WorldFlow.encounter_roll(character.luck, danger, Special.rules(guild.id).base)
		arrive_at = WorldFlow.arrival_time(guild.id, hours)
		roll = {"natural" : natural, "total" : total, "danger" : danger, "table_id" : table_id,
		        "encounter" : encounter} if danger > 0 else None

		road = f" by the road from {origin.name}" if route and origin else ""
		now = datetime.now(timezone.utc)
		later = arrive_at > now
		when = f", arriving <t:{int(arrive_at.timestamp())}:R>" if later else ""
		await interaction.response.send_message(f"🧳 **{character.name}** sets out for **{target.name}**{road}{when}.",
		                                        allowed_mentions=discord.AllowedMentions.none())
		roll_text = f" Road roll {total} ({natural}) against {8 + 2 * danger}: " \
		            f"{'trouble on the way!' if encounter else 'a safe journey.'}" if roll else ""
		await interaction.followup.send(f"{character.name} is on the way.{roll_text}", ephemeral=True)
		if later :
			WorldTransactions().add_travel(guild.id, character.id, origin.id if origin else None, target.id,
			                               arrive_at, roll)
			return
		await TravelFlow.arrive(interaction.client, guild, character, target, origin, roll)

	# ============================================================
	@staticmethod
	async def arrive(bot: discord.Client, guild: discord.Guild, character: Characters, target: Locations,
	                 origin: Locations | None, roll: dict | None) -> None :
		channel = guild.get_channel_or_thread(target.channel_id)
		if channel is None :
			try :
				channel = await guild.fetch_channel(target.channel_id)
			except discord.HTTPException :
				return
		came_from = f" from {origin.name}" if origin else ""
		try :
			await channel.send(f"📍 **{character.name}** arrives at **{target.name}**{came_from}.",
			                   allowed_mentions=discord.AllowedMentions.none())
		except discord.HTTPException as e :
			logging.warning(f"Could not post an arrival in {guild.name}: {e}")
			return
		if not roll or not roll.get("encounter") :
			return
		from classes.kernel import GMRole

		table = RollTableTransactions().get(roll.get("table_id"))
		# The GM role (when the server has one) is pinged: an encounter needs a GM.
		gm, allowed = GMRole.mention(guild.id)
		heading = f"⚠️ {gm}Trouble on the road for **{character.name}** (<@{character.uid}>)."
		if table is None :
			try :
				await channel.send(f"{heading} The GM decides what waits for them.", allowed_mentions=allowed)
			except discord.HTTPException :
				pass
			return
		from classes.tables.TableFlow import TableFlow

		await TableFlow.post_roll(channel, table, character.uid, character, heading, allowed)

	# ============================================================
	@staticmethod
	async def arrivals(bot: discord.Client, now: datetime | None = None) -> None :
		"""Posts the arrivals whose travel time is over."""
		for travel in WorldTransactions().arrivals(now or datetime.now(timezone.utc)) :
			WorldTransactions().arrive(travel.id)
			await TravelFlow._arrive_record(bot, travel)

	# ============================================================
	@staticmethod
	async def _arrive_record(bot: discord.Client, travel: Travels) -> None :
		guild = bot.get_guild(travel.guild_id)
		character = CharacterTransactions().get_by_id(travel.character_id)
		target = WorldTransactions().location(travel.to_id)
		if guild is None or character is None or target is None :
			return
		await TravelFlow.arrive(bot, guild, character, target, WorldTransactions().location(travel.from_id),
		                        travel.encounter)
