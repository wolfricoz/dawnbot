import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Access import Access
from classes.characters.CharacterFlow import CharacterFlow
from classes.characters.Special import STATS
from classes.gear.Gear import ARMOR, Gear, WEAPON
from classes.gear.GearCard import GearCard
from classes.gear.GearPost import GearPost
from classes.gear.Packs import Packs
from database.database import GearItems
from database.transactions.GearItemTransactions import GearItemTransactions
from views.buttons.Confirm import ask

DESCRIPTION_LIMIT = 4000
EMBEDS_PER_MESSAGE = 10
# Discord refuses a message whose embeds hold more than 6000 characters together.
MESSAGE_EMBED_LIMIT = 6000
# Typed into a text option of /armory edit, this clears the text.
CLEAR = "-"
TEXT_LIMIT = 1000

KIND_CHOICES = [Choice(name="Weapon", value=WEAPON), Choice(name="Armor", value=ARMOR)]
MODIFIER_CHOICES = [Choice(name="None", value="none")] + \
                   [Choice(name=f"{stat.capitalize()} added to damage", value=f"damage:{stat}") for stat in STATS] + \
                   [Choice(name=f"Half of {stat.capitalize()} as extra dice", value=f"dice:{stat}") for stat in STATS]
OPTION_HELP = {
	"requirements" : "SPECIAL minimums, like: strength 8, agility 4",
	"dice"         : "Weapon damage dice, like 1d8 or 2d6",
	"modifier"     : "Weapon: a stat added to the damage, or turned into extra dice",
	"hitmodifier"  : "Weapon: added to attack rolls",
	"hp"           : "Armor: hit points (no armor: 75)",
	"ap"           : "Armor: armor points (no armor: 25)",
	"ac"           : "Armor: armor class, what attacks must reach (no armor: 12)",
	"hitchance"    : "Armor: added to the wearer's attack rolls, usually 0 or less",
}


@app_commands.guild_only()
class Armory(commands.GroupCog, name="Armory", group_name="armory") :
	"""The server's gear catalog: the weapons and armor characters can buy in /shop or be given by staff. Staff add
	items by hand or import a ready-made genre pack. When a gear forum is set (/config singlechannels), every item gets
	its own post there, and tags on that post can restrict who may buy it (see /tagrule)."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	@staticmethod
	def hidden(item: GearItems) -> bool :
		"""True for event items, which only staff see."""
		return Access.hidden(Access.for_gear(item))

	# ============================================================
	async def _names(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""Catalog items; event items only for staff."""
		staff = interaction.user.guild_permissions.manage_messages
		return [Choice(name=item.name, value=item.name)
		        for item in GearItemTransactions().get_all(interaction.guild_id)
		        if current.lower() in item.name.lower() and (staff or not self.hidden(item))][:25]

	# ============================================================
	async def _packs(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=title, value=name) for name, title in Packs.available()
		        if current.lower() in title.lower() or current.lower() in name][:25]

	# ============================================================
	@staticmethod
	def text_update(value: str | None) -> tuple[bool, str | None] :
		"""What a text option of /armory edit asks for: (False, None) to leave it, (True, None) to clear it with `-`,
		(True, text) to set it."""
		if value is None :
			return False, None
		value = value.strip()
		return True, None if value in ("", CLEAR) else value

	# ============================================================
	@staticmethod
	def combat_changes(dice=None, modifier=None, hitmodifier=None, hp=None, ap=None, ac=None, hitchance=None) -> dict :
		"""The combat options that were filled in."""
		values = {"dice" : dice, "modifier" : modifier.value if isinstance(modifier, Choice) else modifier,
		          "hitmodifier" : hitmodifier, "hp" : hp, "ap" : ap, "ac" : ac, "hitchance" : hitchance}
		return {key : value for key, value in values.items() if value is not None}

	# ============================================================
	@staticmethod
	def pages(title: str, lines: list[str], limit: int = DESCRIPTION_LIMIT) -> list[discord.Embed] :
		"""The lines as embeds, as many as it takes to keep each description under the limit."""
		embeds, current = [], ""
		for line in lines :
			line = line[:limit]
			if current and len(current) + 1 + len(line) > limit :
				embeds.append(current)
				current = line
			else :
				current = f"{current}\n{line}" if current else line
		if current :
			embeds.append(current)
		return [discord.Embed(title=title if number == 0 else f"{title} (continued)", description=text,
		                      color=discord.Color.dark_gold()) for number, text in enumerate(embeds)]

	# ============================================================
	@staticmethod
	def batches(embeds: list[discord.Embed]) -> list[list[discord.Embed]] :
		"""The embeds grouped into messages Discord accepts: at most 10 per message and 6000 characters together."""
		batches, current, size = [], [], 0
		for embed in embeds :
			if current and (len(current) >= EMBEDS_PER_MESSAGE or size + len(embed) > MESSAGE_EMBED_LIMIT) :
				batches.append(current)
				current, size = [], 0
			current.append(embed)
			size += len(embed)
		if current :
			batches.append(current)
		return batches

	# ============================================================
	async def _post(self, item: GearItems) -> str :
		"""Posts or updates the item in the gear forum when there is one; returns a note for staff when it failed."""
		if not GearPost.configured(item.guild_id) :
			return ""
		if await GearPost.sync(self.bot, GearItemTransactions().get(item.id)) :
			return ""
		return " I could not post it in the gear forum; check that I can create posts there, and that posts there " \
		       "do not need a tag."

	# ============================================================
	@app_commands.command(name="add")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.choices(kind=KIND_CHOICES, modifier=MODIFIER_CHOICES)
	@app_commands.describe(**OPTION_HELP)
	async def add(self, interaction: discord.Interaction, kind: Choice[str], name: app_commands.Range[str, 1, 100],
	              price: app_commands.Range[int, 0, 10000000], description: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	              requirements: app_commands.Range[str, 1, 200] = None,
	              effect: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	              effect_met: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	              effect_unmet: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	              dice: app_commands.Range[str, 3, 7] = None, modifier: Choice[str] = None,
	              hitmodifier: app_commands.Range[int, -10, 10] = None, hp: app_commands.Range[int, 1, 1000] = None,
	              ap: app_commands.Range[int, 0, 1000] = None, ac: app_commands.Range[int, 0, 40] = None,
	              hitchance: app_commands.Range[int, -10, 10] = None) :
		"""
		Adds a weapon or armor set to the catalog. `requirements` are SPECIAL minimums written like
		`strength 8, agility 4` (short names like `str 8` work too); they never stop a character from owning or using
		the item, they decide whether `effect_met` (a bonus) or `effect_unmet` (a penalty) applies. `effect` is
		something the item always does.

		Combat values are optional. Weapons use `dice` (like 1d8), `modifier` (a stat added to the damage, or half a
		stat as extra dice) and `hitmodifier`. Armor uses `hp`, `ap`, `ac` and `hitchance`; values you leave out are
		those of a character without armor (75 HP, 25 AP, 12 AC, 0 hit chance). When a gear forum is set, the item is
		posted there.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		try :
			needs = Packs.parse_requirements(requirements)
			combat = Packs.combat_for(kind.value, None, self.combat_changes(dice, modifier, hitmodifier, hp, ap, ac,
			                                                                hitchance))
		except ValueError as e :
			return await interaction.followup.send(str(e))
		item = GearItemTransactions().add(interaction.guild_id, kind.value, name.strip(), price=price,
		                                  description=description, requirements=needs, effect=effect,
		                                  effect_met=effect_met, effect_unmet=effect_unmet, combat=combat)
		if item is None :
			return await interaction.followup.send(f"The catalog already has an item called {name}.")
		logging.info(f"{interaction.user.name} added gear item {item.name} in {interaction.guild.name}")
		note = await self._post(item)
		await interaction.followup.send(f"Added the {kind.value} **{item.name}**.{note}")

	# ============================================================
	@app_commands.command(name="edit")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=_names)
	@app_commands.choices(modifier=MODIFIER_CHOICES)
	@app_commands.describe(**OPTION_HELP)
	async def edit(self, interaction: discord.Interaction, name: str, new_name: app_commands.Range[str, 1, 100] = None,
	               price: app_commands.Range[int, 0, 10000000] = None,
	               description: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	               requirements: app_commands.Range[str, 1, 200] = None, clear_requirements: bool = False,
	               effect: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	               effect_met: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	               effect_unmet: app_commands.Range[str, 1, TEXT_LIMIT] = None,
	               dice: app_commands.Range[str, 3, 7] = None, modifier: Choice[str] = None,
	               hitmodifier: app_commands.Range[int, -10, 10] = None, hp: app_commands.Range[int, 1, 1000] = None,
	               ap: app_commands.Range[int, 0, 1000] = None, ac: app_commands.Range[int, 0, 40] = None,
	               hitchance: app_commands.Range[int, -10, 10] = None) :
		"""
		Changes a catalog item; options you leave out keep their value. `requirements` replaces all of the item's
		requirements, and `clear_requirements` removes them. Type `-` in description or one of the effects to clear
		it. An item's kind cannot change: remove it and add it again instead.

		Characters who own the item keep it under the name it had when they got it. The item's post in the gear forum
		is updated.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		item = GearItemTransactions().find(interaction.guild_id, name)
		if item is None :
			return await interaction.followup.send(f"The catalog has no item called {name}.")
		updates = {}
		if new_name and new_name.strip() != item.name :
			other = GearItemTransactions().find(interaction.guild_id, new_name.strip())
			if other is not None and other.id != item.id :
				return await interaction.followup.send(f"The catalog already has an item called {new_name}.")
			updates["name"] = new_name.strip()
		if price is not None :
			updates["price"] = price
		for field, value in (("description", description), ("effect", effect), ("effect_met", effect_met),
		                     ("effect_unmet", effect_unmet)) :
			change, text = self.text_update(value)
			if change :
				updates[field] = text
		try :
			if clear_requirements :
				if requirements :
					return await interaction.followup.send("Use either `requirements` or `clear_requirements`, not "
					                                       "both.")
				updates["requirements"] = {}
			elif requirements is not None :
				updates["requirements"] = Packs.parse_requirements(requirements)
			changes = self.combat_changes(dice, modifier, hitmodifier, hp, ap, ac, hitchance)
			if changes :
				updates["combat"] = Packs.combat_for(item.kind, item.combat, changes)
		except ValueError as e :
			return await interaction.followup.send(str(e))
		if not updates :
			return await interaction.followup.send("Nothing to change: fill in at least one option.")
		GearItemTransactions().update(item.id, **updates)
		logging.info(f"{interaction.user.name} edited gear item {item.name} in {interaction.guild.name}: "
		             f"{', '.join(updates)}")
		note = await self._post(item)
		await interaction.followup.send(f"Updated **{updates.get('name', item.name)}**.{note}")

	# ============================================================
	@app_commands.command(name="remove")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(name=_names)
	async def remove(self, interaction: discord.Interaction, name: str) :
		"""
		Removes an item from the catalog, and its post from the gear forum. Characters who own it keep their copy, and
		it can no longer be bought or granted.

		**Permissions:**
		- `Manage Server`
		"""
		item = GearItemTransactions().find(interaction.guild_id, name)
		if item is None :
			return await CharacterFlow.respond(interaction, f"The catalog has no item called {name}.")
		if not await ask(interaction, f"Remove **{item.name}** from the catalog? Characters who own it keep their copy.",
		                 "Remove") :
			return
		await GearPost.remove(self.bot, item)
		GearItemTransactions().delete(item.id)
		logging.info(f"{interaction.user.name} removed gear item {item.name} in {interaction.guild.name}")
		await interaction.followup.send(f"Removed {item.name} from the catalog.", ephemeral=True)

	# ============================================================
	@app_commands.command(name="list")
	@app_commands.choices(kind=KIND_CHOICES)
	async def list_items(self, interaction: discord.Interaction, kind: Choice[str] = None) :
		"""
		Lists the catalog with prices and SPECIAL requirements, marking the items you cannot buy and why. Pick a
		`kind` to see only weapons or only armor. Staff also see event items, which are hidden from members.
		"""
		await interaction.response.defer(ephemeral=True)
		kind = kind.value if isinstance(kind, Choice) else kind
		entries = Gear.shop_items(interaction.guild_id, Access.of(interaction.user), kind)
		if not entries :
			return await interaction.followup.send("The catalog is empty." if kind is None else
			                                       f"The catalog has no {'weapons' if kind == WEAPON else 'armor'}.")
		embeds = []
		for section, title in ((WEAPON, "Weapons"), (ARMOR, "Armor")) :
			lines = []
			for entry in entries :
				if entry.item.kind != section :
					continue
				line = GearCard.line(entry.item, entry.locked)
				if entry.item.forum_thread_id :
					line += f" · <#{entry.item.forum_thread_id}>"
				lines.append(line)
			embeds += self.pages(title, lines)
		for batch in self.batches(embeds) :
			await interaction.followup.send(embeds=batch, ephemeral=True)

	# ============================================================
	@app_commands.command(name="view")
	@app_commands.autocomplete(name=_names)
	async def view(self, interaction: discord.Interaction, name: str) :
		"""
		Shows a catalog item: its description, price, SPECIAL requirements, effects and combat values, and whether you
		can buy it.
		"""
		await interaction.response.defer(ephemeral=True)
		item = GearItemTransactions().find(interaction.guild_id, name)
		access = Access.of(interaction.user)
		if item is None or (self.hidden(item) and not access.staff) :
			return await interaction.followup.send(f"The catalog has no item called {name}.")
		embed = GearPost.card(item)
		if item.forum_thread_id :
			embed.add_field(name="Post", value=f"<#{item.forum_thread_id}>")
		locked = Gear.lock_reason(item, access)
		if locked :
			embed.set_footer(text=f"Not for sale to you: it {locked}."[:2048])
		await interaction.followup.send(embed=embed)

	# ============================================================
	@app_commands.command(name="import")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(pack=_packs)
	async def import_pack(self, interaction: discord.Interaction, pack: str) :
		"""
		Copies a ready-made genre pack (like Fantasy) into the catalog. Items whose name the catalog already has are
		skipped, so importing again only adds what is missing and never overwrites your changes. When a gear forum is
		set, every new item is posted there. You can edit or remove imported items like any other.

		**Permissions:**
		- `Manage Server`
		"""
		try :
			data = Packs.load(pack)
		except ValueError as e :
			return await CharacterFlow.respond(interaction, str(e))
		catalog = {item.name.lower() for item in GearItemTransactions().get_all(interaction.guild_id)}
		new = [item for item in data["items"] if item["name"].lower() not in catalog]
		if not new :
			return await CharacterFlow.respond(interaction, f"The catalog already has every item of the "
			                                                f"{data['title']} pack.")
		posting = GearPost.configured(interaction.guild_id)
		question = f"Import the **{data['title']}** pack? This adds {len(new)} item{'s' if len(new) != 1 else ''}"
		if len(new) < len(data["items"]) :
			question += f" ({len(data['items']) - len(new)} already in the catalog are skipped)"
		question += " and posts each in the gear forum." if posting else "."
		if not await ask(interaction, question, "Import") :
			return
		added, skipped = Packs.import_into(interaction.guild_id, pack)
		logging.info(f"{interaction.user.name} imported gear pack {pack} in {interaction.guild.name}: "
		             f"{len(added)} added, {len(skipped)} skipped")
		text = f"Imported the {data['title']} pack: {len(added)} added, {len(skipped)} skipped."
		if posting and added :
			failed = 0
			for item in added :
				if not await GearPost.sync(self.bot, item) :
					failed += 1
			if failed :
				text += f" {failed} could not be posted in the gear forum; check that I can create posts there, then " \
				        f"use /armory post."
		await interaction.followup.send(text, ephemeral=True)

	# ============================================================
	@app_commands.command(name="post")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def post(self, interaction: discord.Interaction) :
		"""
		Posts every catalog item in the gear forum, or updates its post when it already has one. Use it after setting
		the gear forum, or when posts were deleted. Items keep the tags they had, so their restrictions stay.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		if not GearPost.configured(interaction.guild_id) :
			return await interaction.followup.send("This server has no gear forum. Set one with "
			                                       "`/config singlechannels` (option `gear_forum`).")
		items = GearItemTransactions().get_all(interaction.guild_id)
		if not items :
			return await interaction.followup.send("The catalog is empty.")
		posted = 0
		for item in items :
			if await GearPost.sync(self.bot, item) :
				posted += 1
		text = f"Posted or updated {posted} of {len(items)} item{'s' if len(items) != 1 else ''}."
		if posted < len(items) :
			text += " Check that I can create posts in the gear forum, and that posts there do not need a tag."
		await interaction.followup.send(text)


async def setup(bot) :
	await bot.add_cog(Armory(bot))
