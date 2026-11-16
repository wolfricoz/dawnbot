"""Merchants: NPC shops at the server's locations. Each has its own stock, which restocks daily, weekly or by hand,
its own prices (a markup on the catalog, Charisma and faction standing) and services such as repairs and rooms. Some
haggle. Players trade with a merchant in a channel of one of its locations; GMs set merchants up.
"""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Access import Access
from classes.combat.AutoComplete import AutoComplete
from classes.economy import Merchants as Rules
from classes.gear import Condition, Rarity
from classes.gear.Gear import Gear, KINDS
from classes.kernel.GMRole import gm_only, is_gm
from classes.world.WorldFlow import WorldFlow
from database.database import Merchants
from database.transactions.CharacterGearTransactions import CharacterGearTransactions
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.MerchantTransactions import MerchantTransactions
from modules.Currency import balance_text
from modules.Gear import entry_choices, find_entry, refresh_post
from views.combat.Pickers import reply

RESTOCK_CHOICES = [Choice(name="Daily", value=Rules.DAILY), Choice(name="Weekly", value=Rules.WEEKLY),
                   Choice(name="Only when a GM restocks", value=Rules.MANUAL)]
CLEAR = "-"


# ============================================================
def parse_list(text: str | None, allowed: list[str], what: str) -> list[str] | None :
	"""`weapon, armor` into a list of allowed words; `none` or `-` is empty; None when text is None. Raises ValueError."""
	if text is None :
		return None
	words = [word.strip().lower() for word in text.replace(";", ",").split(",") if word.strip()]
	if words in (["none"], [CLEAR]) :
		return []
	unknown = [word for word in words if word not in allowed]
	if unknown :
		raise ValueError(f"Unknown {what}: {', '.join(unknown)}. Use {', '.join(allowed)}.")
	return list(dict.fromkeys(words))


@app_commands.guild_only()
class Merchant(commands.GroupCog, name="Merchant", group_name="merchant") :
	"""Trade with the merchants at your location."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# == autocomplete ==

	# ============================================================
	async def _merchants(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""The merchants here; GMs see every merchant."""
		location = WorldFlow.location_here(interaction.channel)
		everyone = is_gm(interaction.user)
		merchants = MerchantTransactions().get_all(interaction.guild_id) if everyone else \
			Rules.merchants_at(interaction.guild_id, location.id if location else None)
		return [Choice(name=merchant.name, value=merchant.name) for merchant in merchants
		        if current.lower() in merchant.name.lower()][:25]

	# ============================================================
	async def _wares(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		merchant = MerchantTransactions().find(interaction.guild_id, interaction.namespace.merchant or "")
		if merchant is None :
			return []
		return [Choice(name=item.name[:100], value=item.name[:100]) for _, item in Rules.wares(merchant)
		        if current.lower() in item.name.lower()][:25]

	# ============================================================
	async def _catalog(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=item.name[:100], value=item.name[:100])
		        for item in GearItemTransactions().get_all(interaction.guild_id)
		        if current.lower() in item.name.lower()][:25]

	# ============================================================
	async def _owned(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		name = interaction.namespace.character
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name) if name else None
		if character is None :
			return []
		return entry_choices(CharacterGearTransactions().get_all(character.id), current)

	# == helpers ==

	# ============================================================
	async def _here(self, interaction: discord.Interaction, name: str) -> Merchants | None :
		"""The merchant, if it trades where the command is used; tells the member otherwise."""
		merchant = MerchantTransactions().find(interaction.guild_id, name or "")
		if merchant is None :
			await reply(interaction, f"There is no merchant called {name}.")
			return None
		location = WorldFlow.location_here(interaction.channel)
		if not Rules.trades_at(merchant, location.id if location else None) :
			await reply(interaction, f"{merchant.name} doesn't trade here; go to one of its locations.")
			return None
		return merchant

	# ============================================================
	async def _character(self, interaction: discord.Interaction, name: str) :
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name)
		if character is None or character.state != APPROVED :
			await reply(interaction, "Pick one of your approved characters.")
			return None
		return character

	# ============================================================
	def _embed(self, merchant: Merchants, title: str | None = None, description: str | None = None) -> discord.Embed :
		embed = discord.Embed(title=title or merchant.name, description=(description or merchant.description or "")[:4000],
		                      colour=discord.Colour.dark_gold())
		embed.set_author(name=merchant.name, icon_url=merchant.avatar_url or None)
		return embed

	# == players ==

	# ============================================================
	@app_commands.command(name="browse", description="Shows what a merchant here sells")
	@app_commands.autocomplete(merchant=_merchants, character=AutoComplete().approved_character)
	@app_commands.describe(merchant="Leave out to list the merchants here", character="Show this character's prices")
	async def browse(self, interaction: discord.Interaction, merchant: str = None, character: str = None) :
		"""
		Lists the merchants at this location, or what one of them sells: each item with its price (for `character`,
		after its Charisma, standing and haggling), what is left of it, the kinds of gear the merchant buys, and its
		services.
		"""
		guild_id = interaction.guild_id
		if merchant is None :
			location = WorldFlow.location_here(interaction.channel)
			here = Rules.merchants_at(guild_id, location.id if location else None)
			if not here :
				return await reply(interaction, "No merchants trade here.")
			lines = [f"**{record.name}**" + (f": {record.description[:150]}" if record.description else "")
			         for record in here]
			return await interaction.response.send_message(embed=discord.Embed(
				title="Merchants here", description="\n".join(lines)[:4000], colour=discord.Colour.dark_gold()),
				ephemeral=True)
		record = await self._here(interaction, merchant)
		if record is None :
			return
		buyer = CharacterTransactions().get(interaction.user.id, guild_id, character) if character else None
		lines = []
		for line, item in Rules.wares(record) :
			cost = Rules.price(record, line, item, buyer) if buyer else Rules.base_price(record, line, item)
			left = "" if line.in_stock is None else f" · {line.in_stock} left"
			lines.append(f"**{item.name}** ({item.kind}, {Rarity.label(Rarity.of(item))}) · "
			             f"{balance_text(guild_id, cost) if Gear.economy(guild_id) else 'free'}{left}")
		embed = self._embed(record, description="\n".join(lines) or "Sold out until the next restock.")
		extras = []
		if record.buys :
			extras.append(f"Buys: {', '.join(record.buys)}")
		if record.services :
			services = [f"rooms ({balance_text(guild_id, record.lodging_price)} a week)" if service == Rules.LODGING
			            else service for service in record.services]
			extras.append(f"Services: {', '.join(services)}")
		if record.haggle_dc is not None :
			extras.append(f"Haggles (DC {record.haggle_dc})")
		if extras :
			embed.set_footer(text=" · ".join(extras)[:2048])
		await interaction.response.send_message(embed=embed, ephemeral=True)

	# ============================================================
	@app_commands.command(name="buy", description="Buys an item from a merchant here")
	@app_commands.autocomplete(character=AutoComplete().approved_character, merchant=_merchants, item=_wares)
	async def buy(self, interaction: discord.Interaction, character: str, merchant: str, item: str) :
		"""
		Buys an item from a merchant at this location, paid with your character's currency. The price is the
		merchant's, changed by Charisma, faction standing and anything you haggled.
		"""
		record = await self._here(interaction, merchant)
		buyer = await self._character(interaction, character) if record else None
		if buyer is None :
			return
		match = next(((line, ware) for line, ware in Rules.wares(record) if ware.name.lower() == item.strip().lower()),
		             None)
		if match is None :
			return await reply(interaction, f"{record.name} has no {item} for sale right now.")
		entry, problem = Rules.buy(record, *match, buyer, Access.of(interaction.user), interaction.user.id)
		if problem :
			return await reply(interaction, problem)
		logging.info(f"{interaction.user.name} bought {entry.name} from merchant {record.id} for character {buyer.id}")
		paid = f" for {balance_text(interaction.guild_id, entry.price_paid)}" if entry.price_paid else ""
		await reply(interaction, f"{buyer.name} bought **{match[1].name}** from {record.name}{paid}.")
		await refresh_post(self.bot, buyer.id)

	# ============================================================
	@app_commands.command(name="sell", description="Sells an item to a merchant here")
	@app_commands.autocomplete(character=AutoComplete().approved_character, merchant=_merchants, item=_owned)
	async def sell(self, interaction: discord.Interaction, character: str, merchant: str, item: str) :
		"""
		Sells one of your character's items to a merchant at this location, if it buys that kind of gear. It pays
		your Charisma's share of the catalog price, times how generous the merchant is.
		"""
		record = await self._here(interaction, merchant)
		seller = await self._character(interaction, character) if record else None
		if seller is None :
			return
		entry = find_entry(CharacterGearTransactions().get_all(seller.id), item)
		if entry is None :
			return await reply(interaction, f"{seller.name} doesn't own {item}.")
		value, problem = Rules.sell(record, entry, interaction.user.id)
		if problem :
			return await reply(interaction, problem)
		got = f" for {balance_text(interaction.guild_id, value)}" if value else " (nothing paid)"
		await reply(interaction, f"{seller.name} sold **{entry.name}** to {record.name}{got}.")
		await refresh_post(self.bot, seller.id)

	# ============================================================
	@app_commands.command(name="haggle", description="Haggles with a merchant here over an item")
	@app_commands.autocomplete(character=AutoComplete().approved_character, merchant=_merchants, item=_wares)
	async def haggle(self, interaction: discord.Interaction, character: str, merchant: str, item: str) :
		"""
		Haggles over one item, once per item until the merchant restocks: Charisma against the merchant's DC. A
		success takes 10% off, a strong success 20%; a bad failure offends the merchant, who won't deal with your
		character until the next restock.
		"""
		record = await self._here(interaction, merchant)
		haggler = await self._character(interaction, character) if record else None
		if haggler is None :
			return
		ware = next((ware for _, ware in Rules.wares(record) if ware.name.lower() == item.strip().lower()), None)
		if ware is None :
			return await reply(interaction, f"{record.name} has no {item} for sale right now.")
		outcome, lines = Rules.haggle(record, haggler, ware)
		if outcome is None :
			return await reply(interaction, lines[0])
		await interaction.response.send_message(embed=self._embed(record, title="Haggling", description="\n".join(lines)))

	# ============================================================
	@app_commands.command(name="repair", description="Has a merchant here repair an item")
	@app_commands.autocomplete(character=AutoComplete().approved_character, merchant=_merchants, item=_owned)
	async def repair(self, interaction: discord.Interaction, character: str, merchant: str, item: str) :
		"""
		Has a merchant with a repair service fix one of your character's items: 5%, 15% or 40% of its catalog price
		(Worn, Damaged, Broken) times the merchant's markup, changed by Charisma.
		"""
		record = await self._here(interaction, merchant)
		owner = await self._character(interaction, character) if record else None
		if owner is None :
			return
		if Rules.REPAIR not in (record.services or []) :
			return await reply(interaction, f"{record.name} doesn't do repairs.")
		entry = find_entry(CharacterGearTransactions().get_all(owner.id), item)
		if entry is None :
			return await reply(interaction, f"{owner.name} doesn't own {item}.")
		problem = Condition.repair_problem(entry)
		if problem :
			return await reply(interaction, problem)
		cost = Rules.repair_price(record, entry, GearItemTransactions().get(entry.gear_item_id), owner)
		if cost :
			_, problem = Gear.change_currency(owner, -cost, "repair", interaction.user.id,
			                                  note=f"{entry.name} at {record.name}")
			if problem :
				return await reply(interaction, problem)
		Condition.restore(entry, interaction.user.id)
		paid = f" for {balance_text(interaction.guild_id, cost)}" if cost else ""
		await reply(interaction, f"{record.name} repaired {owner.name}'s **{entry.name}**{paid}.")

	# ============================================================
	@app_commands.command(name="lodge", description="Rents a room from a merchant here")
	@app_commands.autocomplete(character=AutoComplete().approved_character, merchant=_merchants)
	async def lodge(self, interaction: discord.Interaction, character: str, merchant: str,
	                weeks: app_commands.Range[int, 1, 12] = 1) :
		"""
		Rents a room at this location for some weeks (added to time already paid). A room opens the stash here:
		/stash put and /stash take keep items safe, weightless and out of fights.
		"""
		record = await self._here(interaction, merchant)
		lodger = await self._character(interaction, character) if record else None
		if lodger is None :
			return
		location = WorldFlow.location_here(interaction.channel)
		if location is None :
			return await reply(interaction, "Rooms are rented in a location's channel.")
		lodging, problem = Rules.rent(record, lodger, location.id, weeks, interaction.user.id)
		if problem :
			return await reply(interaction, problem)
		await reply(interaction, f"{lodger.name} has a room at {location.name} until "
		                         f"{discord.utils.format_dt(lodging.paid_until, 'f')}.")

	# == GMs ==

	# ============================================================
	@app_commands.command(name="add", description="Adds a merchant (GMs)")
	@gm_only()
	@app_commands.choices(restock=RESTOCK_CHOICES)
	@app_commands.describe(markup="Times the catalog price (1 is the catalog price)",
	                       buys="Gear kinds it buys: weapon, armor, consumable, accessory, material (or none)",
	                       pays="Times the usual sale value it pays (1 is usual)",
	                       services="repair, lodging (or none)", lodging_price="What a room costs per week",
	                       haggle_dc="Charisma DC to haggle (leave out: no haggling)",
	                       here="Trade at this channel's location", faction="Its faction (prices follow standing)")
	async def add(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 100],
	              description: app_commands.Range[str, 1, 1000] = None, avatar_url: str = None,
	              markup: app_commands.Range[float, 0.1, 10.0] = 1.0, buys: str = None,
	              pays: app_commands.Range[float, 0.0, 5.0] = 1.0, services: str = None,
	              lodging_price: app_commands.Range[int, 0, 1000000] = 0,
	              haggle_dc: app_commands.Range[int, 5, 30] = None, restock: Choice[str] = None,
	              here: bool = True, faction: str = None) :
		"""
		Adds a merchant. With `here` (the default) it trades at this channel's location; add more locations with
		/merchant place, or none to let it trade anywhere. Fill its stock with /merchant stock.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		try :
			fields = self._fields(interaction, buys=buys, services=services, faction=faction)
		except ValueError as e :
			return await reply(interaction, str(e))
		location = WorldFlow.location_here(interaction.channel) if here else None
		if here and location is None :
			return await reply(interaction, "This channel isn't a location; use `here: False` or set it up with "
			                                "/location set.")
		record = MerchantTransactions().add(interaction.guild_id, name.strip(), description=description,
		                                    avatar_url=avatar_url, markup=markup, pays=pays,
		                                    lodging_price=lodging_price, haggle_dc=haggle_dc,
		                                    restock=restock.value if restock else Rules.WEEKLY,
		                                    location_ids=[location.id] if location else [], **fields)
		if record is None :
			return await reply(interaction, f"There already is a merchant called {name}.")
		await reply(interaction, f"Added **{record.name}**" + (f" at {location.name}" if location else "") +
		            ". Stock it with /merchant stock.")

	# ============================================================
	def _fields(self, interaction: discord.Interaction, buys=None, services=None, faction=None) -> dict :
		fields = {}
		parsed = parse_list(buys, KINDS + ["material"], "gear kinds")
		if parsed is not None :
			fields["buys"] = parsed
		parsed = parse_list(services, Rules.SERVICES, "services")
		if parsed is not None :
			fields["services"] = parsed
		if faction is not None :
			if faction.strip() in ("", CLEAR, "none") :
				fields["faction_id"] = None
			else :
				found = EconomyTransactions().find_faction(interaction.guild_id, faction)
				if found is None :
					raise ValueError(f"There is no faction called {faction}.")
				fields["faction_id"] = found.id
		return fields

	# ============================================================
	@app_commands.command(name="edit", description="Changes a merchant (GMs)")
	@gm_only()
	@app_commands.autocomplete(merchant=_merchants)
	@app_commands.choices(restock=RESTOCK_CHOICES)
	@app_commands.describe(buys="Gear kinds it buys, or none", services="repair, lodging, or none",
	                       haggle_dc="Charisma DC to haggle (0: no haggling)", faction="Its faction, or - for none")
	async def edit(self, interaction: discord.Interaction, merchant: str, name: app_commands.Range[str, 1, 100] = None,
	               description: app_commands.Range[str, 1, 1000] = None, avatar_url: str = None,
	               markup: app_commands.Range[float, 0.1, 10.0] = None, buys: str = None,
	               pays: app_commands.Range[float, 0.0, 5.0] = None, services: str = None,
	               lodging_price: app_commands.Range[int, 0, 1000000] = None,
	               haggle_dc: app_commands.Range[int, 0, 30] = None, restock: Choice[str] = None,
	               faction: str = None) :
		"""
		Changes a merchant; options you leave out keep their value. Type `-` in description or avatar_url to clear
		it.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = MerchantTransactions().find(interaction.guild_id, merchant)
		if record is None :
			return await reply(interaction, f"There is no merchant called {merchant}.")
		try :
			changes = self._fields(interaction, buys=buys, services=services, faction=faction)
		except ValueError as e :
			return await reply(interaction, str(e))
		if name and name.strip().lower() != record.name.lower() :
			if MerchantTransactions().find(interaction.guild_id, name) is not None :
				return await reply(interaction, f"There already is a merchant called {name}.")
			changes["name"] = name.strip()
		for field, value in (("description", description), ("avatar_url", avatar_url)) :
			if value is not None :
				changes[field] = None if value.strip() == CLEAR else value.strip()
		for field, value in (("markup", markup), ("pays", pays), ("lodging_price", lodging_price)) :
			if value is not None :
				changes[field] = value
		if haggle_dc is not None :
			changes["haggle_dc"] = haggle_dc or None
		if restock is not None :
			changes["restock"] = restock.value
		if not changes :
			return await reply(interaction, "Nothing to change: fill in at least one option.")
		MerchantTransactions().update(record.id, **changes)
		await reply(interaction, f"Updated **{changes.get('name', record.name)}**.")

	# ============================================================
	@app_commands.command(name="remove", description="Removes a merchant (GMs)")
	@gm_only()
	@app_commands.autocomplete(merchant=_merchants)
	async def remove(self, interaction: discord.Interaction, merchant: str) :
		"""
		Removes a merchant and its stock. Rooms rented from it stay paid, and stashes stay where they are.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = MerchantTransactions().find(interaction.guild_id, merchant)
		if record is None :
			return await reply(interaction, f"There is no merchant called {merchant}.")
		MerchantTransactions().delete(record.id)
		await reply(interaction, f"Removed {record.name}.")

	# ============================================================
	@app_commands.command(name="place", description="Adds or removes this location for a merchant (GMs)")
	@gm_only()
	@app_commands.autocomplete(merchant=_merchants)
	@app_commands.describe(remove="Stop trading here instead")
	async def place(self, interaction: discord.Interaction, merchant: str, remove: bool = False) :
		"""
		Lets a merchant trade at this channel's location too, or with `remove` stops it trading here. A merchant
		without any location trades everywhere. Move a travelling merchant by placing it somewhere new and removing it
		from where it was.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = MerchantTransactions().find(interaction.guild_id, merchant)
		location = WorldFlow.location_here(interaction.channel)
		if record is None or location is None :
			return await reply(interaction, "Pick a merchant, in a location's channel.")
		locations = [location_id for location_id in (record.location_ids or []) if location_id != location.id]
		if not remove :
			locations.append(location.id)
		MerchantTransactions().update(record.id, location_ids=locations)
		await reply(interaction, f"{record.name} {'no longer trades' if remove else 'trades'} at {location.name}.")

	# ============================================================
	@app_commands.command(name="stock", description="Adds or changes an item a merchant sells (GMs)")
	@gm_only()
	@app_commands.autocomplete(merchant=_merchants, item=_catalog)
	@app_commands.describe(quantity="How many each restock brings (leave out: unlimited)",
	                       chance="Percent chance it is there after a restock (default 100)",
	                       price="Its own price before markup (leave out: the catalog price)",
	                       remove="Stop selling it")
	async def stock(self, interaction: discord.Interaction, merchant: str, item: str,
	                quantity: app_commands.Range[int, 1, 10000] = None, chance: app_commands.Range[int, 1, 100] = 100,
	                price: app_commands.Range[int, 0, 1000000000] = None, remove: bool = False) :
		"""
		Puts a catalog item in a merchant's stock, or changes it: how many a restock brings, the chance it is there
		at all (rotating stock) and its own price. It is in stock straight away. Legendary items are never sold.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = MerchantTransactions().find(interaction.guild_id, merchant)
		ware = GearItemTransactions().find(interaction.guild_id, item)
		if record is None or ware is None :
			return await reply(interaction, "Pick a merchant and a catalog item.")
		if remove :
			done = MerchantTransactions().remove_stock(record.id, ware.id)
			return await reply(interaction, f"{record.name} {'no longer sells' if done else 'never sold'} {ware.name}.")
		if Rarity.of(ware) == Rarity.LEGENDARY :
			return await reply(interaction, "Legendary items are never sold; grant them instead.")
		MerchantTransactions().set_stock(record.id, ware.id, quantity=quantity, chance=chance, price=price,
		                                 in_stock=quantity, available=True)
		amount = "unlimited" if quantity is None else f"{quantity} per restock"
		rotating = f", there {chance}% of the time" if chance < 100 else ""
		await reply(interaction, f"{record.name} sells **{ware.name}** ({amount}{rotating}).")

	# ============================================================
	@app_commands.command(name="restock", description="Restocks a merchant now (GMs)")
	@gm_only()
	@app_commands.autocomplete(merchant=_merchants)
	async def restock(self, interaction: discord.Interaction, merchant: str) :
		"""
		Restocks a merchant now: every line comes back to its quantity, rotating items roll their chance, and
		haggles and grudges are forgotten.

		**Permissions:**
		- `Manage Messages`, or the GM role
		"""
		record = MerchantTransactions().find(interaction.guild_id, merchant)
		if record is None :
			return await reply(interaction, f"There is no merchant called {merchant}.")
		Rules.restock(record)
		await reply(interaction, f"{record.name} restocked: {len(Rules.wares(MerchantTransactions().get(record.id)))} "
		                         f"items for sale.")


async def setup(bot) :
	await bot.add_cog(Merchant(bot))
