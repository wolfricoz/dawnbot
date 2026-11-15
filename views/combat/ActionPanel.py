"""The private panel a player (or the GM, for an NPC) acts through: pick an action, a target and a weapon or ability,
then press Do it. It shows the AP left and refreshes after every action."""
import discord

from classes.combat import Abilities as AbilityRules, Items
from classes.combat.CombatFlow import CombatFlow
from classes.combat.Engine import AP_HELP, AP_REVIVE, Engine
from classes.combat.Loadout import Loadout
from classes.combat.State import Combatant, Fight
from database.transactions.CombatTransactions import CombatTransactions
from views.combat.Pickers import Field, Form, OPTION_LIMIT, reply

ATTACK = "attack"
AIMED = "aimed"
ABILITY = "ability"
HELP = "help"
REVIVE = "revive"
ITEM = "item"
FLEE = "flee"
OTHER = "other"
ACTION_LABELS = {ATTACK : "Attack", AIMED : "Aimed attack (-4 to hit, +1 die, ignores DT)", ABILITY : "Use an ability",
                 HELP : f"Help an ally (+2 on their next roll, {AP_HELP} AP)",
                 REVIVE : f"Revive a downed ally ({AP_REVIVE} AP)", ITEM : f"Use an item ({Items.AP_ITEM} AP)",
                 FLEE : "Flee (uses all AP)",
                 OTHER : "Something else (the GM settles it; uses all AP)"}


class PanelSelect(discord.ui.Select) :

	def __init__(self, key: str, options: list[discord.SelectOption], placeholder: str, max_values: int = 1,
	             row: int = 0) :
		options = options[:OPTION_LIMIT]
		super().__init__(placeholder=placeholder, options=options, min_values=1,
		                 max_values=max(1, min(max_values, len(options))), row=row)
		self.key = key

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		await self.view.chose(interaction, self.key, list(self.values))


class PanelButton(discord.ui.Button) :

	def __init__(self, key: str, label: str, style: discord.ButtonStyle, row: int = 3, disabled: bool = False) :
		super().__init__(label=label, style=style, row=row, disabled=disabled)
		self.key = key

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		await self.view.pressed(interaction, self.key)


class ActionPanel(discord.ui.View) :

	def __init__(self, user_id: int, fight_id: int, combatant_id: int) :
		super().__init__(timeout=900)
		self.user_id = user_id
		self.fight_id = fight_id
		self.combatant_id = combatant_id
		self.action = ATTACK
		self.targets: list[int] = []
		self.weapon_key: str | None = None
		self.ability_id: str | None = None
		self.item_key: str | None = None

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		return interaction.user.id == self.user_id

	# == drawing ==

	# ============================================================
	def render(self) -> str :
		"""Rebuilds the components from the fight as it is now; returns the panel's text."""
		self.clear_items()
		fight = CombatTransactions().load(self.fight_id)
		combatant = fight.combatant(self.combatant_id) if fight else None
		if fight is None or combatant is None :
			return "This fight or character is gone."
		engine = CombatFlow.engine(fight)
		if not combatant.standing :
			return f"**{combatant.name}** is {combatant.state} and can't act."
		weapon = combatant.weapon(combatant.weapon_key)
		header = (f"**{combatant.name}** · ❤️ {combatant.hp}/{combatant.hp_max} · AP {combatant.ap}/{combatant.ap_max}"
		          f" · AC {engine.effective_ac(combatant)} · holding {weapon['name'] if weapon else 'nothing'}")
		if combatant.passives :
			header += f"\n-# Passives (always on): {', '.join(passive['name'] for passive in combatant.passives)}"
		my_turn = combatant in engine.actors()
		if not my_turn :
			header += "\n-# It isn't your turn right now; the panel works once it is (press Refresh)."
		actions = [ATTACK, AIMED]
		if combatant.abilities :
			actions.append(ABILITY)
		actions += [HELP]
		if any(ally.down for ally in fight.allies(combatant, include_self=False)) :
			actions.append(REVIVE)
		if combatant.items :
			actions.append(ITEM)
		actions += [FLEE, OTHER]
		if self.action not in actions :
			self.action = ATTACK
		self.add_item(PanelSelect("action", [discord.SelectOption(label=ACTION_LABELS[action][:100], value=action,
		                                                          default=action == self.action)
		                                     for action in actions], "What to do", row=0))
		detail = self._detail(fight, engine, combatant)
		self.add_item(PanelButton("go", "Do it", discord.ButtonStyle.primary, disabled=not my_turn))
		self.add_item(PanelButton("end", "End turn", discord.ButtonStyle.secondary, disabled=not my_turn))
		self.add_item(PanelButton("refresh", "Refresh", discord.ButtonStyle.secondary))
		return f"{header}\n{detail}".strip()

	# ============================================================
	def _target_options(self, targets: list[Combatant], engine: Engine) -> list[discord.SelectOption] :
		return [discord.SelectOption(label=f"{target.name} · HP {target.hp}/{target.hp_max} · AC "
		                                   f"{engine.effective_ac(target)}"[:100], value=str(target.id),
		                             default=target.id in self.targets) for target in targets]

	# ============================================================
	def _detail(self, fight: Fight, engine: Engine, combatant: Combatant) -> str :
		if self.action in (ATTACK, AIMED) :
			enemies = fight.enemies(combatant)
			if not enemies :
				return "There is nobody left to attack."
			self.targets = [target for target in self.targets if fight.combatant(target) in enemies][:1] or \
			               [min(enemies, key=lambda enemy : enemy.hp).id]
			self.add_item(PanelSelect("targets", self._target_options(enemies, engine), "Target", row=1))
			usable = combatant.weapons
			if self.weapon_key not in [weapon.get("key") for weapon in usable] :
				self.weapon_key = combatant.weapon_key or (usable[0].get("key") if usable else None)
			options = []
			for weapon in usable :
				cost = engine.attack_cost(combatant, weapon, self.action == AIMED)
				label = f"{weapon.get('name')} · {cost} AP · {Loadout.weapon_line(combatant.stats, weapon).split(': ', 1)[-1]}"
				options.append(discord.SelectOption(label=label[:100], value=str(weapon.get("key")),
				                                    default=weapon.get("key") == self.weapon_key))
			if options :
				self.add_item(PanelSelect("weapon", options, "Weapon", row=2))
			chosen = combatant.weapon(self.weapon_key)
			return f"Costs {engine.attack_cost(combatant, chosen, self.action == AIMED)} AP." if chosen else ""
		if self.action == ABILITY :
			abilities = combatant.abilities
			if self.ability_id not in [str(ability["id"]) for ability in abilities] :
				self.ability_id = str(abilities[0]["id"])
			options = []
			for ability in abilities :
				left = engine.ability_uses_left(combatant, ability)
				uses = "∞" if left is None else f"{left} left"
				options.append(discord.SelectOption(label=f"{ability['name']} · {AbilityRules.ap(ability['tier'])} AP "
				                                          f"· {uses}"[:100], value=str(ability["id"]),
				                                    default=str(ability["id"]) == self.ability_id))
			self.add_item(PanelSelect("ability", options, "Ability", row=2))
			ability = combatant.ability(self.ability_id)
			targets = engine.ability_targets(combatant, ability)
			limit = AbilityRules.AREA_TARGETS if ability.get("area") else 1
			valid = [target.id for target in targets]
			self.targets = [target for target in self.targets if target in valid][:limit] or valid[:1]
			if targets :
				self.add_item(PanelSelect("targets", self._target_options(targets, engine),
				                          f"Target{'s (up to 3)' if limit > 1 else ''}", max_values=limit, row=1))
			return Loadout.ability_line(ability)
		if self.action in (HELP, REVIVE) :
			allies = [ally for ally in fight.allies(combatant, include_self=False)
			          if (ally.standing if self.action == HELP else ally.down)]
			if not allies :
				return "There is nobody to " + ("help." if self.action == HELP else "revive.")
			valid = [ally.id for ally in allies]
			self.targets = [target for target in self.targets if target in valid][:1] or valid[:1]
			self.add_item(PanelSelect("targets", self._target_options(allies, engine), "Ally", row=1))
			return ""
		if self.action == ITEM :
			items = combatant.items
			if self.item_key not in [item["key"] for item in items] :
				self.item_key = items[0]["key"]
			self.add_item(PanelSelect("item", [discord.SelectOption(label=f"{item['name']} · {Items.describe(item)}"[:100],
			                                                        value=item["key"], default=item["key"] == self.item_key)
			                                   for item in items], "Item", row=2))
			item = combatant.item(self.item_key)
			heals = item is not None and item["use"] == Items.HEAL
			allies = [ally for ally in fight.allies(combatant) if ally.standing or (heals and ally.down)]
			valid = [ally.id for ally in allies]
			self.targets = [target for target in self.targets if target in valid][:1] or [combatant.id]
			self.add_item(PanelSelect("targets", self._target_options(allies, engine), "Use it on", row=1))
			return f"{item['name']}: {Items.describe(item)}. It's used up." if item else ""
		if self.action == FLEE :
			return f"Roll d20 + AGI against {10 + len(fight.enemies(combatant))} to get away."
		return "Press Do it to describe what you do; the GM settles it."

	# == input ==

	# ============================================================
	async def chose(self, interaction: discord.Interaction, key: str, values: list[str]) -> None :
		if key == "action" :
			self.action = values[0]
			self.targets = []
		elif key == "targets" :
			self.targets = [int(value) for value in values]
		elif key == "weapon" :
			self.weapon_key = values[0]
		elif key == "ability" :
			self.ability_id = values[0]
			self.targets = []
		elif key == "item" :
			self.item_key = values[0]
			self.targets = []
		await interaction.response.edit_message(content=self.render(), view=self)

	# ============================================================
	async def pressed(self, interaction: discord.Interaction, key: str) -> None :
		if key == "refresh" :
			return await interaction.response.edit_message(content=self.render(), view=self)
		if key == "go" and self.action == OTHER :
			return await interaction.response.send_modal(Form("Something else", [
				Field("What does your character do?", long=True, max_length=500)], self._other))
		await interaction.response.defer()
		combatant_id = self.combatant_id
		if key == "end" :
			action, label = (lambda engine : engine.end_turn_action(engine.fight.combatant(combatant_id))), "end_turn"
		else :
			action, label = self._action(combatant_id)
		await CombatFlow.run(interaction.client, self.fight_id, action, interaction, label=label,
		                     actor_id=combatant_id, target_id=self.targets[0] if self.targets else None)
		await interaction.edit_original_response(content=self.render(), view=self)

	# ============================================================
	def _action(self, combatant_id: int) :
		targets = list(self.targets)
		first = targets[0] if targets else None
		weapon_key, ability_id, item_key = self.weapon_key, self.ability_id, self.item_key
		if self.action in (ATTACK, AIMED) :
			aimed = self.action == AIMED
			return (lambda engine : engine.attack(engine.fight.combatant(combatant_id), first, weapon_key, aimed)), \
				self.action
		if self.action == ABILITY :
			return (lambda engine : engine.use_ability(engine.fight.combatant(combatant_id), ability_id, targets)), \
				ABILITY
		if self.action == HELP :
			return (lambda engine : engine.help(engine.fight.combatant(combatant_id), first)), HELP
		if self.action == REVIVE :
			return (lambda engine : engine.revive(engine.fight.combatant(combatant_id), first)), REVIVE
		if self.action == ITEM :
			return (lambda engine : engine.use_item(engine.fight.combatant(combatant_id), item_key, first)), ITEM
		return (lambda engine : engine.flee(engine.fight.combatant(combatant_id))), FLEE

	# ============================================================
	async def _other(self, interaction: discord.Interaction, values: list[str]) -> None :
		await interaction.response.defer(ephemeral=True)
		combatant_id = self.combatant_id
		text = values[0]
		await CombatFlow.run(interaction.client, self.fight_id,
		                     lambda engine : engine.other(engine.fight.combatant(combatant_id), text), interaction,
		                     label=OTHER, actor_id=combatant_id)
		await reply(interaction, "Sent to the GM.")


# ============================================================
async def open_panel(interaction: discord.Interaction, fight_id: int, combatant_id: int) -> None :
	panel = ActionPanel(interaction.user.id, fight_id, combatant_id)
	content = panel.render()
	if interaction.response.is_done() :
		await interaction.followup.send(content, view=panel, ephemeral=True)
	else :
		await interaction.response.send_message(content, view=panel, ephemeral=True)
