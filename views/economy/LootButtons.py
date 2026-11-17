"""The buttons under a fight's loot: Claim (winning players) and Settle (the GM). They carry the loot's id, so they keep
working after a restart (registered with bot.add_dynamic_items in setup_hook). The rules are in
classes/economy/Loot.py."""
import logging

import discord

from views.combat.Pickers import Option, pick, reply

ACTIONS = {"claim" : ("Claim", "🙋", discord.ButtonStyle.success),
           "settle" : ("Settle (GM)", "🎁", discord.ButtonStyle.primary)}


class LootButton(discord.ui.DynamicItem[discord.ui.Button],
                 template=r"loot:(?P<loot>\d+):(?P<action>claim|settle)") :

	def __init__(self, loot_id: int, action: str) :
		label, emoji, style = ACTIONS[action]
		super().__init__(discord.ui.Button(label=label, emoji=emoji, style=style, custom_id=f"loot:{loot_id}:{action}"))
		self.loot_id = loot_id
		self.action = action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(int(match["loot"]), match["action"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		if self.action == "claim" :
			await start_claim(interaction, self.loot_id)
		else :
			await start_settle(interaction, self.loot_id)


# ============================================================
def loot_view(loot) -> discord.ui.View | None :
	if loot.state != "open" :
		return None
	view = discord.ui.View(timeout=None)
	for action in ACTIONS :
		view.add_item(LootButton(loot.id, action))
	return view


# ============================================================
def embed(loot) -> discord.Embed :
	from database.transactions.CharacterTransactions import CharacterTransactions

	lines = []
	for number, entry in enumerate(loot.items, start=1) :
		names = [CharacterTransactions().get_by_id(character_id) for character_id in entry.get("claims") or []]
		claimed = ", ".join(character.name for character in names if character) or "nobody yet"
		amount = f" ×{entry['amount']}" if entry.get("amount", 1) > 1 else ""
		winner = CharacterTransactions().get_by_id(entry["winner"]) if entry.get("winner") else None
		lines.append(f"**{number}. {entry['name']}**{amount}: " + (f"→ {winner.name}" if winner else f"claimed by "
		                                                                                               f"{claimed}"))
	if loot.currency :
		lines.append(f"💰 **{loot.currency} currency**, split evenly among the winners.")
	result = discord.Embed(title="🎁 Loot" if loot.state == "open" else "🎁 Loot (shared)",
	                       description="\n".join(lines) or "Nothing worth taking.", colour=discord.Colour.gold())
	if loot.state == "open" :
		result.set_footer(text="Winners: press Claim for what you want. Then the GM presses Settle: "
		                       + ("the GM picks between claimants." if loot.mode == "gm" else
		                          "claimants roll for contested items."))
	return result


# ============================================================
async def refresh(interaction: discord.Interaction, loot) -> None :
	try :
		channel = interaction.client.get_channel(loot.channel_id) or await interaction.client.fetch_channel(
			loot.channel_id)
		await channel.get_partial_message(loot.message_id).edit(embed=embed(loot), view=loot_view(loot))
	except (discord.HTTPException, AttributeError) as e :
		logging.warning(f"Could not update loot {loot.id}: {e}")


# ============================================================
async def post(interaction: discord.Interaction, fight) -> None :
	"""Rolls the loot of a finished fight and posts it in its thread (once per fight)."""
	from classes.combat.CombatFlow import CombatFlow
	from classes.economy import Loot

	if Loot.LootTransactions().of_fight(fight.id) is not None :
		return await reply(interaction, "This fight's loot was already rolled.")
	currency, items = Loot.roll(fight)
	if not currency and not items :
		return await reply(interaction, "The defeated enemies dropped nothing (bestiary entries get loot with "
		                                "/bestiary loot).")
	loot = Loot.LootTransactions().add(guild_id=fight.guild_id, fight_id=fight.id, currency=currency, items=items,
	                                   mode=Loot.mode(fight.guild_id))
	thread = await CombatFlow.thread(interaction.client, fight)
	if thread is None :
		return await reply(interaction, "I couldn't find the fight's thread.")
	message = await thread.send(embed=embed(loot), view=loot_view(loot))
	Loot.LootTransactions().update(loot.id, channel_id=thread.id, message_id=message.id)
	await reply(interaction, "Loot rolled.")


# ============================================================
async def start_claim(interaction: discord.Interaction, loot_id: int) -> None :
	from classes.economy import Loot
	from database.transactions.CombatTransactions import CombatTransactions

	loot = Loot.LootTransactions().get(loot_id)
	if loot is None or loot.state != "open" :
		return await reply(interaction, "This loot was already shared.")
	fight = CombatTransactions().load(loot.fight_id)
	mine = [combatant.character_id for combatant in fight.combatants if combatant.uid == interaction.user.id
	        and combatant.character_id in Loot.winners(fight)] if fight else []
	if not mine or not loot.items :
		return await reply(interaction, "Only the winners' players can claim loot." if not mine else
		                                "There are no items to claim.")
	character_id = mine[0]
	options = [Option(f"{number}. {entry['name']}"[:100], str(number - 1),
	                  default=character_id in (entry.get("claims") or []))
	           for number, entry in enumerate(loot.items[:25], start=1)]

	async def chosen(pick_interaction: discord.Interaction, values: list[str]) :
		current = Loot.LootTransactions().get(loot_id)
		if current is None or current.state != "open" :
			return await reply(pick_interaction, "This loot was already shared.")
		wanted = {int(value) for value in values}
		for index, entry in enumerate(current.items) :
			if (character_id in (entry.get("claims") or [])) != (index in wanted) :
				current = Loot.claim(current, index, character_id)
		await refresh(pick_interaction, current)
		await reply(pick_interaction, "Claims saved.")

	await pick(interaction, "What do you claim? (Pick everything you want; leaving one out takes the claim back.)",
	           options, "Items", chosen, max_values=len(options))


# ============================================================
async def start_settle(interaction: discord.Interaction, loot_id: int) -> None :
	from classes.combat.CombatFlow import CombatFlow
	from classes.economy import Loot
	from database.transactions.CharacterTransactions import CharacterTransactions
	from database.transactions.CombatTransactions import CombatTransactions

	loot = Loot.LootTransactions().get(loot_id)
	if loot is None or loot.state != "open" :
		return await reply(interaction, "This loot was already shared.")
	fight = CombatTransactions().load(loot.fight_id)
	if fight is None or not CombatFlow.is_gm(fight, interaction.user) :
		return await reply(interaction, "Only the fight's GM can settle the loot.")
	contested = [index for index, entry in enumerate(loot.items) if len(entry.get("claims") or []) > 1]
	picks: dict[int, int] = {}

	async def finish(last: discord.Interaction) :
		current = Loot.LootTransactions().get(loot_id)
		if current is None or current.state != "open" :
			return await reply(last, "This loot was already shared.")
		lines = Loot.settle(current, fight, picks, last.user.id)
		await refresh(last, Loot.LootTransactions().get(loot_id))
		await thread_say(last, current, "🎁 The loot is shared:\n" + "\n".join(lines))
		await reply(last, "Loot shared.")

	async def ask(next_interaction: discord.Interaction, remaining: list[int]) :
		if not remaining or loot.mode != Loot.GM :
			return await finish(next_interaction)
		index = remaining[0]
		entry = loot.items[index]
		options = [Option(character.name, str(character.id)) for character in
		           (CharacterTransactions().get_by_id(character_id) for character_id in entry["claims"]) if character]

		async def picked(pick_interaction: discord.Interaction, values: list[str]) :
			picks[index] = int(values[0])
			await ask(pick_interaction, remaining[1:])

		await pick(next_interaction, f"Who gets **{entry['name']}**?", options, "Character", picked)

	await ask(interaction, contested)


# ============================================================
async def thread_say(interaction: discord.Interaction, loot, text: str) -> None :
	try :
		channel = interaction.client.get_channel(loot.channel_id) or await interaction.client.fetch_channel(
			loot.channel_id)
		await channel.send(text[:2000], allowed_mentions=discord.AllowedMentions.none())
	except (discord.HTTPException, AttributeError) as e :
		logging.warning(f"Could not post loot {loot.id}: {e}")
