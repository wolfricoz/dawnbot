"""Locations: places in the world, each bound to a channel or thread, grouped into regions and joined by routes.

A location card has a description, an image, a climate (or its region's), whether it is indoors, a danger level,
hazards and an encounter table. A character is at the location of its last post (PRESENCE_DAYS). Routes give travel
time and danger for /travel. Staff (Manage Messages) set them up. See design/roleplay-tools.md, section 5.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.kernel.GMRole import gm_only
from classes.characters.ImageStorage import ImageStorage
from classes.world import Weather
from classes.world.WorldFlow import WorldFlow
from database.database import Locations
from database.transactions.RollTableTransactions import RollTableTransactions
from database.transactions.WorldTransactions import WorldTransactions
from views.buttons.Confirm import ask
from views.combat.Pickers import reply

CLIMATE_CHOICES = [Choice(name=climate.capitalize(), value=climate) for climate in Weather.CLIMATES
                   if climate != Weather.NONE]
DANGER_HELP = "0 safe to 5 deadly: travel here can bring an encounter"


# ============================================================
async def region_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=region.name[:100], value=region.name[:100])
	        for region in WorldTransactions().regions(interaction.guild_id)
	        if current.lower() in region.name.lower()][:25]


# ============================================================
async def faction_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	from database.transactions.EconomyTransactions import EconomyTransactions

	return [Choice(name=faction.name[:100], value=faction.name[:100])
	        for faction in EconomyTransactions().factions(interaction.guild_id)
	        if current.lower() in faction.name.lower()][:25]


# ============================================================
async def table_autocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	return [Choice(name=table.name[:100], value=table.name[:100])
	        for table in RollTableTransactions().get_all(interaction.guild_id)
	        if current.lower() in table.name.lower()][:25]


class LocationForm(discord.ui.Modal) :
	"""A location's description and hazards."""

	def __init__(self, title: str, on_submit, description: str | None, hazards: str | None) :
		super().__init__(title=title[:45])
		self.handler = on_submit
		self.description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph,
		                                        required=False, max_length=2000, default=description)
		self.hazards = discord.ui.TextInput(label="Hazards (optional)", style=discord.TextStyle.paragraph,
		                                    required=False, max_length=500, default=hazards)
		self.add_item(self.description)
		self.add_item(self.hazards)

	# ============================================================
	async def on_submit(self, interaction: discord.Interaction) :
		await self.handler(interaction, self.description.value, self.hazards.value)


# ============================================================
async def card(bot: discord.Client, guild: discord.Guild, location: Locations) -> discord.Embed :
	region = WorldTransactions().region(location.region_id)
	embed = discord.Embed(title=f"📍 {location.name}"[:256], description=(location.description or "")[:4096],
	                      colour=discord.Colour.dark_green())
	climate, key = WorldFlow.weather(guild.id, location)
	embed.add_field(name="Weather", value=Weather.text(climate, key), inline=True)
	where = [f"Region: {region.name}" if region else None, "Indoors" if location.indoor else None,
	         f"Climate: {(location.climate or (region.climate if region else Weather.TEMPERATE)).capitalize()}"]
	embed.add_field(name="Place", value="\n".join(part for part in where if part), inline=True)
	embed.add_field(name="Danger", value="☠️" * location.danger if location.danger else "Safe", inline=True)
	if location.hazards :
		embed.add_field(name="Hazards", value=location.hazards[:1024], inline=False)
	present = WorldFlow.who_is_at(guild, location)
	if present :
		embed.add_field(name="Here now", value=", ".join(character.name for character in present)[:1024],
		                inline=False)
	date = WorldFlow.date_line(guild.id)
	if date :
		embed.set_footer(text=date[:2048])
	url = await ImageStorage.url(bot, location.image_id)
	if url :
		embed.set_image(url=url)
	return embed


@app_commands.guild_only()
class Location(commands.GroupCog, name="Location", group_name="location") :
	"""Places in the world, bound to channels, grouped in regions and joined by routes."""

	region = app_commands.Group(name="region", description="Regions: groups of locations that share a climate")
	route = app_commands.Group(name="route", description="Routes between locations, used by /travel")

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@app_commands.command(name="set", description="Makes this channel a location, or changes it")
	@gm_only()
	@app_commands.autocomplete(region=region_autocomplete, encounters=table_autocomplete,
	                           faction=faction_autocomplete)
	@app_commands.choices(climate=CLIMATE_CHOICES)
	@app_commands.describe(name="The location's name", region="The region it is in",
	                       climate="Its own climate (default: its region's)", indoor="Indoors: no weather",
	                       danger=DANGER_HELP, encounters="The roll table for encounters on the way here",
	                       image="A picture of the place", faction="The faction that holds it (carousing here gains "
	                                                               "standing)")
	async def set_location(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100] = None,
	                       region: str = None, climate: Choice[str] = None, indoor: bool = None,
	                       danger: app_commands.Range[int, 0, 5] = None, encounters: str = None,
	                       image: discord.Attachment = None, faction: str = None) :
		"""
		Makes the channel (or thread) you use it in a location, or changes the one it is. A form asks for the
		description and hazards. Options you leave out keep their value.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		guild_id = interaction.guild_id
		current = WorldTransactions().location_of(interaction.channel_id)
		fields = {}
		if name :
			fields["name"] = name
		elif current is None :
			fields["name"] = getattr(interaction.channel, "name", "Somewhere").replace("-", " ").title()[:100]
		if region :
			record = WorldTransactions().find_region(guild_id, region)
			if record is None :
				return await reply(interaction, f"There is no region called {region}; add it with /location region "
				                                f"add.")
			fields["region_id"] = record.id
		if climate :
			fields["climate"] = climate.value
		if indoor is not None :
			fields["indoor"] = indoor
		if danger is not None :
			fields["danger"] = danger
		if faction :
			from database.transactions.EconomyTransactions import EconomyTransactions

			holder = EconomyTransactions().find_faction(guild_id, faction)
			if holder is None :
				return await reply(interaction, f"There is no faction called {faction}.")
			fields["faction_id"] = holder.id
		if encounters :
			table = RollTableTransactions().find(guild_id, encounters)
			if table is None :
				return await reply(interaction, f"There is no roll table called {encounters}.")
			fields["table_id"] = table.id
		image_problem = None
		if image is not None :
			image_problem = ImageStorage.check(image.content_type, image.size) if ImageStorage.configured() else \
				"Image storage isn't set up for this bot, so the image was left out."

		async def save(form_interaction: discord.Interaction, description: str, hazards: str) :
			await form_interaction.response.defer(ephemeral=True)
			values = dict(fields, description=description.strip() or None, hazards=hazards.strip() or None)
			if image is not None and image_problem is None :
				values["image_id"] = await ImageStorage.store(form_interaction.client, image)
			location = WorldTransactions().save_location(guild_id, interaction.channel_id, **values)
			embed = await card(form_interaction.client, form_interaction.guild, location)
			note = f"\n⚠️ {image_problem}" if image_problem else ""
			await form_interaction.followup.send(f"Saved.{note}", embed=embed, ephemeral=True)

		await interaction.response.send_modal(LocationForm(f"Location: {fields.get('name') or current.name}", save,
		                                                   current.description if current else None,
		                                                   current.hazards if current else None))

	# ============================================================
	@app_commands.command(name="view", description="Shows a location's card")
	@app_commands.describe(channel="The location's channel (default: this one)")
	async def view(self, interaction: discord.Interaction, channel: discord.TextChannel = None) :
		"""
		Shows a location: its description, weather, region, danger, hazards and who is there.
		"""
		location = WorldFlow.location_here(channel or interaction.channel)
		if location is None :
			return await reply(interaction, "That channel isn't a location.")
		await interaction.response.send_message(embed=await card(interaction.client, interaction.guild, location),
		                                        ephemeral=True)

	# ============================================================
	@app_commands.command(name="who", description="Lists the characters at a location")
	@app_commands.describe(channel="The location's channel (default: this one)")
	async def who(self, interaction: discord.Interaction, channel: discord.TextChannel = None) :
		"""
		Lists the characters whose last post was at this location, within the last PRESENCE_DAYS days.
		"""
		location = WorldFlow.location_here(channel or interaction.channel)
		if location is None :
			return await reply(interaction, "That channel isn't a location.")
		present = WorldFlow.who_is_at(interaction.guild, location)
		if not present :
			return await reply(interaction, f"Nobody has been at {location.name} lately.")
		await reply(interaction, f"**At {location.name}:** " + ", ".join(f"{character.name} (<@{character.uid}>)"
		                                                                for character in present))

	# ============================================================
	@app_commands.command(name="list", description="Lists the server's locations")
	async def list_locations(self, interaction: discord.Interaction) :
		"""
		Lists every location with its region and channel.
		"""
		locations = WorldTransactions().locations(interaction.guild_id)
		if not locations :
			return await reply(interaction, "There are no locations yet; staff add them with /location set.")
		regions = {region.id : region.name for region in WorldTransactions().regions(interaction.guild_id)}
		lines = [f"**{location.name}** · <#{location.channel_id}>"
		         f"{f' · {regions[location.region_id]}' if location.region_id in regions else ''}"
		         f"{' · ' + '☠️' * location.danger if location.danger else ''}" for location in locations]
		await reply(interaction, "\n".join(lines)[:2000])

	# ============================================================
	@app_commands.command(name="remove", description="Stops this channel being a location")
	@gm_only()
	async def remove(self, interaction: discord.Interaction) :
		"""
		Removes the location of this channel, with its routes.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		location = WorldTransactions().location_of(interaction.channel_id)
		if location is None :
			return await reply(interaction, "This channel isn't a location.")
		if not await ask(interaction, f"Remove the location **{location.name}** and its routes?", "Remove") :
			return await reply(interaction, "Nothing was removed.")
		WorldTransactions().delete_location(location.id)
		await reply(interaction, f"Removed **{location.name}**.")

	# == regions ==

	# ============================================================
	@region.command(name="add", description="Adds a region")
	@gm_only()
	@app_commands.choices(climate=CLIMATE_CHOICES)
	async def region_add(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100],
	                     climate: Choice[str], description: app_commands.Range[str, 1, 1000] = None) :
		"""
		Adds a region. Its locations share its climate (unless they set their own) and its weather.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		region = WorldTransactions().add_region(interaction.guild_id, name, climate=climate.value,
		                                        description=description)
		if region is None :
			return await reply(interaction, f"There already is a region called {name}.")
		await reply(interaction, f"Added the region **{region.name}** ({climate.value}).")

	# ============================================================
	@region.command(name="edit", description="Changes a region")
	@gm_only()
	@app_commands.autocomplete(region=region_autocomplete)
	@app_commands.choices(climate=CLIMATE_CHOICES)
	async def region_edit(self, interaction: discord.Interaction, region: str,
	                      name: app_commands.Range[str, 1, 100] = None, climate: Choice[str] = None,
	                      description: app_commands.Range[str, 1, 1000] = None) :
		"""
		Changes a region's name, climate or description.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = WorldTransactions().find_region(interaction.guild_id, region)
		if record is None :
			return await reply(interaction, f"There is no region called {region}.")
		if name and name.lower() != record.name.lower() and WorldTransactions().find_region(interaction.guild_id, name) :
			return await reply(interaction, f"There already is a region called {name}.")
		changes = {key : value for key, value in (("name", name), ("climate", climate.value if climate else None),
		                                          ("description", description)) if value}
		WorldTransactions().update_region(record.id, **changes)
		await reply(interaction, f"Saved **{name or record.name}**.")

	# ============================================================
	@region.command(name="remove", description="Removes a region")
	@gm_only()
	@app_commands.autocomplete(region=region_autocomplete)
	async def region_remove(self, interaction: discord.Interaction, region: str) :
		"""
		Removes a region; its locations keep existing without one.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = WorldTransactions().find_region(interaction.guild_id, region)
		if record is None :
			return await reply(interaction, f"There is no region called {region}.")
		WorldTransactions().delete_region(record.id)
		await reply(interaction, f"Removed **{record.name}**.")

	# ============================================================
	@region.command(name="list", description="Lists the regions")
	async def region_list(self, interaction: discord.Interaction) :
		"""
		Lists the regions with their climates.
		"""
		regions = WorldTransactions().regions(interaction.guild_id)
		if not regions :
			return await reply(interaction, "There are no regions yet.")
		await reply(interaction, "\n".join(f"**{region.name}** · {region.climate}"
		                                   f"{f' · {region.description[:80]}' if region.description else ''}"
		                                   for region in regions)[:2000])

	# == routes ==

	# ============================================================
	@route.command(name="add", description="Adds a route between two locations")
	@gm_only()
	@app_commands.autocomplete(encounters=table_autocomplete)
	@app_commands.describe(start="One location's channel", end="The other location's channel",
	                       hours="In-world hours the journey takes", danger=DANGER_HELP,
	                       encounters="The roll table for encounters on this route",
	                       one_way="Only from start to end")
	async def route_add(self, interaction: discord.Interaction, start: discord.TextChannel, end: discord.TextChannel,
	                    hours: app_commands.Range[int, 0, 10000] = 0, danger: app_commands.Range[int, 0, 5] = 0,
	                    encounters: str = None, one_way: bool = False) :
		"""
		Adds a route. /travel along it takes its time (when in-world time flows) and rolls for encounters by its
		danger.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		first, second = WorldTransactions().location_of(start.id), WorldTransactions().location_of(end.id)
		if first is None or second is None or first.id == second.id :
			return await reply(interaction, "Both channels need to be different locations (/location set).")
		if WorldTransactions().route(first.id, second.id) is not None :
			return await reply(interaction, f"There already is a route between {first.name} and {second.name}.")
		table = RollTableTransactions().find(interaction.guild_id, encounters) if encounters else None
		if encounters and table is None :
			return await reply(interaction, f"There is no roll table called {encounters}.")
		WorldTransactions().add_route(interaction.guild_id, first.id, second.id, hours=hours, danger=danger,
		                              table_id=table.id if table else None, two_way=not one_way)
		arrow = "→" if one_way else "↔"
		await reply(interaction, f"Added the route {first.name} {arrow} {second.name}: {hours} hours, danger "
		                         f"{danger}.")

	# ============================================================
	@route.command(name="remove", description="Removes the route between two locations")
	@gm_only()
	async def route_remove(self, interaction: discord.Interaction, start: discord.TextChannel,
	                       end: discord.TextChannel) :
		"""
		Removes a route.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		first, second = WorldTransactions().location_of(start.id), WorldTransactions().location_of(end.id)
		route = WorldTransactions().route(first.id, second.id) if first and second else None
		if route is None :
			return await reply(interaction, "There is no route between those channels.")
		WorldTransactions().delete_route(route.id)
		await reply(interaction, f"Removed the route between {first.name} and {second.name}.")

	# ============================================================
	@route.command(name="list", description="Lists the routes")
	async def route_list(self, interaction: discord.Interaction) :
		"""
		Lists every route with its travel time and danger.
		"""
		routes = WorldTransactions().routes(interaction.guild_id)
		if not routes :
			return await reply(interaction, "There are no routes yet.")
		names = {location.id : location.name for location in WorldTransactions().locations(interaction.guild_id)}
		lines = [f"{names.get(route.from_id, '?')} {'↔' if route.two_way else '→'} {names.get(route.to_id, '?')} · "
		         f"{route.hours} h · danger {route.danger}" for route in routes]
		await reply(interaction, "\n".join(lines)[:2000])


async def setup(bot) :
	await bot.add_cog(Location(bot))
