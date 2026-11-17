"""Magic item designs: players design enchanted items from catalog items and catalog effects, staff review them, and an
approved design becomes a catalog item with an enchanting recipe that spellcasters (or the recipe's occupation) craft.
"""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat.AutoComplete import AutoComplete
from classes.economy import Enchanting
from classes.gear import Magic, Rarity
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import reply

RARITY_CHOICES = [Choice(name=Rarity.label(rarity), value=rarity) for rarity in Enchanting.DESIGN_RARITIES]


# ============================================================
async def decide(interaction: discord.Interaction, design_id: int, approve: bool, reason: str | None = None) -> None :
	"""A reviewer's Approve or Deny on a design card."""
	from views.economy.EnchantButtons import review_view

	design = Enchanting.DesignTransactions().get(design_id)
	if design is None or design.state != Enchanting.PENDING :
		return await reply(interaction, "This design was already decided.")
	if approve :
		item, problem = Enchanting.approve(design, interaction.user.id)
		if problem :
			return await reply(interaction, f"It can't be approved: {problem}")
		text = f"✨ Your magic item design **{design.name}** was approved. Spellcasters (or the recipe's occupation) " \
		       f"can make it with /craft make {design.name}."
	else :
		Enchanting.DesignTransactions().update(design.id, state=Enchanting.DENIED)
		text = f"Your magic item design **{design.name}** was denied: {reason}"
	design = Enchanting.DesignTransactions().get(design_id)
	try :
		await interaction.response.edit_message(embed=Enchanting.embed(design), view=None)
	except discord.HTTPException :
		await reply(interaction, "Decided.")
	try :
		user = interaction.client.get_user(design.creator_uid) or await interaction.client.fetch_user(design.creator_uid)
		await user.send(text)
	except discord.HTTPException :
		pass
	logging.info(f"{interaction.user.name} {'approved' if approve else 'denied'} enchant design {design.id}")


@app_commands.guild_only()
class Enchant(commands.GroupCog, name="Enchant", group_name="enchant") :
	"""Design magic items for staff to approve."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _bases(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		return [Choice(name=item.name[:100], value=item.name[:100])
		        for item in GearItemTransactions().get_all(interaction.guild_id)
		        if item.kind in ("weapon", "armor", "accessory") and not Magic.enchanted(item)
		        and current.lower() in item.name.lower()][:25]

	# ============================================================
	async def _effects(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		from classes.combat import EffectCatalog, PassiveCatalog
		from modules.Ability import effect_choice

		activation = getattr(interaction.namespace, "activation", None) or Magic.ACTIVE
		catalog = PassiveCatalog if activation == Magic.PASSIVE else EffectCatalog
		return [effect_choice(effect) for effect in catalog.search(current, None)[:25]]

	# ============================================================
	@app_commands.command(name="design", description="Designs a magic item for staff to review")
	@app_commands.autocomplete(character=AutoComplete().approved_character, base=_bases, effect=_effects,
	                           second_effect=_effects)
	@app_commands.choices(rarity=RARITY_CHOICES,
	                      activation=[Choice(name="Active (used as an action)", value=Magic.ACTIVE),
	                                  Choice(name="Passive (always on)", value=Magic.PASSIVE)],
	                      recharge=[Choice(name="After each fight", value=Magic.FIGHT),
	                                Choice(name="Each day", value=Magic.DAY)])
	@app_commands.describe(character="The character the design is for", base="The catalog item to enchant",
	                       name="The new item's name", bonus="+1 to hit (weapon) or +1 DT (armor)",
	                       charges="Active: uses (empty: the tier's usual)")
	async def design(self, interaction: discord.Interaction, character: str, base: str,
	                 name: app_commands.Range[str, 1, 100], rarity: Choice[str], activation: Choice[str],
	                 effect: str, second_effect: str = None, charges: app_commands.Range[int, 1, 10] = None,
	                 recharge: Choice[str] = None, bonus: bool = False,
	                 description: app_commands.Range[str, 1, 1000] = None) :
		"""
		Designs a magic item: a catalog weapon, armor or accessory with an enchantment built from catalog effects,
		within its rarity's budget (Uncommon: one effect up to Weak; Rare: one up to Normal or two up to Weak; Very
		rare: one up to Strong or two up to Normal). Staff review it in the review channel. Once approved it joins
		the catalog (it is never sold) with an enchanting recipe: spellcasters, or characters with the occupation
		staff set, make it with /craft make, using the base item.
		"""
		problem = Enchanting.creation_problem(interaction.user)
		if problem :
			return await reply(interaction, problem)
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None or record.state != APPROVED :
			return await reply(interaction, "Pick one of your approved characters.")
		base_item = GearItemTransactions().find(interaction.guild_id, base)
		data, problem = Magic.build(activation.value, [effect, second_effect], charges,
		                            recharge.value if recharge else None, bonus)
		problem = problem or Enchanting.design_problem(interaction.guild_id, name.strip(), base_item, rarity.value, data)
		if problem :
			return await reply(interaction, problem)
		review = await ConfigData().get_channel(interaction.guild, ConfigMapping.CHARACTER_REVIEW)
		if review is None :
			return await reply(interaction, "This server has no review channel yet; staff set it with /config "
			                                "singlechannels.")
		design = Enchanting.DesignTransactions().add(guild_id=interaction.guild_id, creator_uid=interaction.user.id,
		                                             character_id=record.id, base_item_id=base_item.id,
		                                             name=name.strip(), description=description, rarity=rarity.value,
		                                             enchantments=data)
		from views.economy.EnchantButtons import review_view

		try :
			message = await review.send(embed=Enchanting.embed(design), view=review_view(design.id))
			Enchanting.DesignTransactions().update(design.id, review_message_id=message.id)
		except discord.HTTPException :
			return await reply(interaction, "I couldn't post in the review channel; check my permissions there.")
		await reply(interaction, f"✨ **{design.name}** is waiting for staff review. You'll get a DM when it's "
		                         f"decided.")

	# ============================================================
	@app_commands.command(name="designs", description="Lists your magic item designs")
	async def designs(self, interaction: discord.Interaction) :
		"""
		Lists your magic item designs and whether they were approved. Staff see everyone's.
		"""
		staff = interaction.user.guild_permissions.manage_messages
		designs = Enchanting.DesignTransactions().of_user(interaction.guild_id, None if staff else interaction.user.id)
		if not designs :
			return await reply(interaction, "No designs yet; make one with /enchant design.")
		lines = [f"**{design.name}** ({Rarity.label(design.rarity)}) · {design.state} · <@{design.creator_uid}>"
		         for design in designs]
		await interaction.response.send_message(embed=discord.Embed(title="Magic item designs",
		                                                            description="\n".join(lines)[:4000],
		                                                            colour=discord.Colour.blurple()),
		                                        ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot) :
	await bot.add_cog(Enchant(bot))
