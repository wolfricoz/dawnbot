"""The buttons under a fight's board. They carry the fight's id in their custom id, so they keep working after a
restart (registered with bot.add_dynamic_items in setup_hook)."""
import discord

from classes.combat.Engine import AUTOPILOTS
from classes.combat.State import ACTIVE, ENDED, Fight, PAUSED, PENDING, SETUP
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.CombatTransactions import CombatTransactions
from views.combat.Pickers import Option, pick, reply

JOIN = "join"
ACT = "act"
AUTO = "auto"
GM = "gm"
ACCEPT = "accept"
DECLINE = "decline"
AUTOPILOT_LABELS = {"weakest" : "Attack the weakest enemy", "revenge" : "Attack whoever hit me last",
                    "defend" : "Defend (keep AP as AC)", "support" : "Revive and help allies first"}


class CombatButton(discord.ui.DynamicItem[discord.ui.Button],
                   template=r"combat:(?P<fight>\d+):(?P<action>join|act|auto|gm|accept|decline)") :

	def __init__(self, fight_id: int, action: str, label: str | None = None,
	             style: discord.ButtonStyle = discord.ButtonStyle.secondary, emoji: str | None = None) :
		super().__init__(discord.ui.Button(label=label or action.capitalize(), style=style, emoji=emoji,
		                                   custom_id=f"combat:{fight_id}:{action}"))
		self.fight_id = fight_id
		self.action = action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(int(match["fight"]), match["action"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		fight = CombatTransactions().load(self.fight_id)
		if fight is None :
			return await reply(interaction, "That fight no longer exists.")
		handlers = {JOIN : join, ACT : act, AUTO : autopilot, GM : gm, ACCEPT : accept, DECLINE : decline}
		await handlers[self.action](interaction, fight)


# ============================================================
def board_view(fight: Fight) -> discord.ui.View | None :
	view = discord.ui.View(timeout=None)
	if fight.state == PENDING :
		view.add_item(CombatButton(fight.id, ACCEPT, "Accept", discord.ButtonStyle.success))
		view.add_item(CombatButton(fight.id, DECLINE, "Decline", discord.ButtonStyle.danger))
		return view
	if fight.state == ENDED :
		view.add_item(CombatButton(fight.id, GM, "GM", discord.ButtonStyle.secondary, "🛠️"))
		return view
	if fight.state == SETUP or fight.late_join :
		view.add_item(CombatButton(fight.id, JOIN, "Join", discord.ButtonStyle.success))
	if fight.state in (ACTIVE, PAUSED) :
		view.add_item(CombatButton(fight.id, ACT, "Act", discord.ButtonStyle.primary, "⚔️"))
	view.add_item(CombatButton(fight.id, AUTO, "Autopilot", discord.ButtonStyle.secondary, "🤖"))
	view.add_item(CombatButton(fight.id, GM, "GM", discord.ButtonStyle.secondary, "🛠️"))
	return view


# ============================================================
async def join(interaction: discord.Interaction, fight: Fight) -> None :
	from classes.combat.CombatFlow import CombatFlow

	characters = CombatFlow.joinable_characters(fight, interaction.user.id)
	if not characters :
		return await reply(interaction, "You have no approved character free to join (each character can be in "
		                                "one fight at a time).")
	sides = CombatFlow.joinable_sides(fight, interaction.user.id)
	if not sides :
		return await reply(interaction, CombatFlow.engine(fight).join_problem(fight.sides[0].id, interaction.user.id,
		                                                                      None) or "You can't join this fight.")

	async def finish(next_interaction: discord.Interaction, character_id: int, side_id: int) :
		if fight.lethal and CombatFlow.lethal_mode(fight.guild_id) == "agreed" :
			from views.buttons.Confirm import ask

			if not await ask(next_interaction, "☠️ This fight is **lethal**: your character can die. Join anyway?",
			                 "Join") :
				return
		await CombatFlow.join(next_interaction.client, next_interaction, fight.id, character_id, side_id,
		                      lethal_ok=fight.lethal)

	async def choose_side(next_interaction: discord.Interaction, character_id: int) :
		if len(sides) == 1 :
			return await finish(next_interaction, character_id, sides[0].id)
		await pick(next_interaction, "Which side?", [Option(side.name, side.id) for side in sides], "Pick a side",
		           lambda last, values : finish(last, character_id, int(values[0])))

	if len(characters) == 1 :
		return await choose_side(interaction, characters[0].id)
	await pick(interaction, "Which character joins?",
	           [Option(character.name, character.id, f"Level {character.level}") for character in characters],
	           "Pick a character", lambda next_interaction, values : choose_side(next_interaction, int(values[0])))


# ============================================================
async def act(interaction: discord.Interaction, fight: Fight) -> None :
	from views.combat.ActionPanel import open_panel

	mine = [combatant for combatant in fight.of_user(interaction.user.id) if combatant.standing]
	if not mine :
		return await reply(interaction, "You have no character standing in this fight.")
	if len(mine) == 1 :
		return await open_panel(interaction, fight.id, mine[0].id)
	await pick(interaction, "Act as which character?", [Option(combatant.name, combatant.id) for combatant in mine],
	           "Pick a character", lambda next_interaction, values : open_panel(next_interaction, fight.id,
	                                                                            int(values[0])))


# ============================================================
async def autopilot(interaction: discord.Interaction, fight: Fight) -> None :
	from classes.combat.CombatFlow import CombatFlow

	mine = fight.of_user(interaction.user.id)
	if not mine :
		return await reply(interaction, "You have no character in this fight.")

	async def chosen(next_interaction: discord.Interaction, values: list[str]) :
		await next_interaction.response.defer(ephemeral=True)
		for combatant in mine :
			await CombatFlow.run(next_interaction.client, fight.id,
			                     lambda engine, combatant_id=combatant.id : engine.control(
				                     engine.fight.combatant(combatant_id), behavior=values[0]),
			                     next_interaction, label="autopilot", undoable=False)
		await reply(next_interaction, f"Autopilot: {AUTOPILOT_LABELS[values[0]].lower()}. It only acts when you miss "
		                              f"a turn.")

	current = mine[0].behavior
	await pick(interaction, "When you miss a turn, what should your character do?",
	           [Option(AUTOPILOT_LABELS[value], value, default=value == current) for value in AUTOPILOTS],
	           "Pick an autopilot", chosen)


# ============================================================
async def gm(interaction: discord.Interaction, fight: Fight) -> None :
	from classes.combat.CombatFlow import CombatFlow
	from views.combat.GMPanel import open_gm_panel

	if not CombatFlow.is_gm(fight, interaction.user) :
		return await reply(interaction, "Only the fight's GM (or staff) can use the GM tools.")
	await open_gm_panel(interaction, fight.id)


# ============================================================
async def accept(interaction: discord.Interaction, fight: Fight) -> None :
	from classes.combat.CombatFlow import CombatFlow

	challenge = fight.challenge or {}
	if interaction.user.id != challenge.get("target_uid") :
		return await reply(interaction, "Only the challenged member can accept.")
	characters = [character for character in
	              CharacterTransactions().get_all(interaction.user.id, fight.guild_id, states=[APPROVED])
	              if CombatTransactions().open_fight_of(character.id) is None]
	if not characters :
		return await reply(interaction, "You have no approved character free to fight.")

	async def chosen(next_interaction: discord.Interaction, values: list[str]) :
		await CombatFlow.accept(next_interaction.client, next_interaction, fight.id, int(values[0]))

	note = " ☠️ It is lethal: your character can die." if fight.lethal else ""
	await pick(interaction, f"Fight with which character?{note}",
	           [Option(character.name, character.id, f"Level {character.level}" +
	                   (" · legendary" if character.legendary else "")) for character in characters],
	           "Pick a character", chosen)


# ============================================================
async def decline(interaction: discord.Interaction, fight: Fight) -> None :
	from classes.combat.CombatFlow import CombatFlow

	await CombatFlow.decline(interaction.client, interaction, fight.id)
