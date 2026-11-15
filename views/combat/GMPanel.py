"""The GM's private panel: starting, pausing and ending the fight, NPCs, HP and conditions, settling "Other" actions,
sides, time, GM roles, NPC voices, deaths and rewards."""
from datetime import timedelta

import discord

from classes.combat import Conditions as C
from classes.combat.CombatFlow import CombatFlow
from classes.combat.Engine import AUTOPILOTS, BEHAVIORS
from classes.combat.Loadout import Loadout, PRESETS, preset_text, rank_of
from classes.combat.State import ACTIVE, AUTO, DYING, ENDED, Fight, GM, LIVE, PAUSED, PLAYER, SETUP
from database.transactions.BestiaryTransactions import BestiaryTransactions
from database.transactions.CombatTransactions import CombatTransactions
from views.combat.Pickers import Field, Form, Option, number, pick, reply

MAX_NPCS = 20
# Each group fits one select menu (Discord holds 25 options).
CONDITION_GROUPS = {"harmful" : C.HARMFUL, "helpful" : C.HELPFUL}


class GMButton(discord.ui.Button) :

	def __init__(self, key: str, label: str, row: int, style: discord.ButtonStyle = discord.ButtonStyle.secondary,
	             disabled: bool = False) :
		super().__init__(label=label, style=style, row=row, disabled=disabled)
		self.key = key

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		fight = CombatTransactions().load(self.view.fight_id)
		if fight is None :
			return await reply(interaction, "That fight no longer exists.")
		if not CombatFlow.is_gm(fight, interaction.user) :
			return await reply(interaction, "Only the fight's GM can do that.")
		await getattr(self.view, f"do_{self.key}")(interaction, fight)


class GMPanel(discord.ui.View) :

	def __init__(self, user_id: int, fight: Fight) :
		super().__init__(timeout=900)
		self.user_id = user_id
		self.fight_id = fight.id
		state = fight.state
		running = state in (ACTIVE, PAUSED)
		ended = state == ENDED
		self.add_item(GMButton("start", "Start", 0, discord.ButtonStyle.success, disabled=state != SETUP))
		self.add_item(GMButton("pause", "Resume" if state == PAUSED else "Pause", 0, disabled=not running))
		self.add_item(GMButton("end_phase", "End this turn", 0, disabled=state != ACTIVE))
		self.add_item(GMButton("finish", "End fight", 0, discord.ButtonStyle.danger, disabled=ended))
		self.add_item(GMButton("undo", "Undo last", 0, disabled=state == SETUP))
		self.add_item(GMButton("add_npc", "Add from bestiary", 1, disabled=ended))
		self.add_item(GMButton("quick_npc", "Quick NPC", 1, disabled=ended))
		self.add_item(GMButton("act_as", "Act as NPC", 1, disabled=state != ACTIVE))
		self.add_item(GMButton("control", "Control", 1, disabled=ended))
		self.add_item(GMButton("speak", "Speak as NPC", 1))
		self.add_item(GMButton("hp", "Change HP", 2, disabled=ended))
		self.add_item(GMButton("condition", "Conditions", 2, disabled=ended))
		self.add_item(GMButton("skip", "Skip a turn", 2, disabled=state != ACTIVE))
		self.add_item(GMButton("remove", "Remove", 2, disabled=ended))
		self.add_item(GMButton("move", "Move side", 2, disabled=ended))
		self.add_item(GMButton("settle", "Settle 'Other'", 3, disabled=not fight.pending))
		self.add_item(GMButton("sides", "Sides", 3, disabled=ended))
		self.add_item(GMButton("time", "Add time", 3, disabled=state != ACTIVE))
		self.add_item(GMButton("late", "Close late joins" if fight.late_join else "Allow late joins", 3,
		                       disabled=ended))
		self.add_item(GMButton("roles", "GM roles", 3))
		self.add_item(GMButton("death", "Death / spare", 4, disabled=not running or not fight.lethal))
		self.add_item(GMButton("rewards", "Rewards", 4, discord.ButtonStyle.success, disabled=not ended))
		self.add_item(GMButton("aftermath", "Injuries / broken gear", 4, disabled=state == SETUP))

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		return interaction.user.id == self.user_id

	# == helpers ==

	# ============================================================
	async def _run(self, interaction: discord.Interaction, action, label: str, undoable: bool = True) -> None :
		if not interaction.response.is_done() :
			await interaction.response.defer(ephemeral=True)
		outcome = await CombatFlow.run(interaction.client, self.fight_id, action, interaction, label=label,
		                               undoable=undoable)
		if outcome is not None :
			await reply(interaction, "Done.")

	# ============================================================
	@staticmethod
	def _combatant_options(fight: Fight, combatants: list) -> list[Option] :
		return [Option(f"{combatant.name} ({fight.side(combatant.side_id).name})", combatant.id,
		               f"HP {combatant.hp}/{combatant.hp_max} · {combatant.state} · {combatant.controller}")
		        for combatant in combatants]

	# ============================================================
	async def _pick_combatant(self, interaction: discord.Interaction, fight: Fight, combatants: list, text: str,
	                          then) -> None :
		await pick(interaction, text, self._combatant_options(fight, combatants), "Pick a combatant",
		           lambda next_interaction, values : then(next_interaction, int(values[0])))

	# ============================================================
	async def _pick_side(self, interaction: discord.Interaction, fight: Fight, text: str, then,
	                     default: int | None = None) -> None :
		await pick(interaction, text, [Option(side.name, side.id, default=side.id == default) for side in fight.sides],
		           "Pick a side", lambda next_interaction, values : then(next_interaction, int(values[0])))

	# == the fight ==

	# ============================================================
	async def do_start(self, interaction: discord.Interaction, fight: Fight) -> None :
		await self._run(interaction, lambda engine : engine.start(), "start", undoable=False)

	# ============================================================
	async def do_pause(self, interaction: discord.Interaction, fight: Fight) -> None :
		if fight.state == PAUSED :
			return await self._run(interaction, lambda engine : engine.resume(), "resume", undoable=False)
		await self._run(interaction, lambda engine : engine.pause(), "pause", undoable=False)

	# ============================================================
	async def do_end_phase(self, interaction: discord.Interaction, fight: Fight) -> None :
		await self._run(interaction, lambda engine : engine.end_phase(), "end_phase")

	# ============================================================
	async def do_finish(self, interaction: discord.Interaction, fight: Fight) -> None :
		from views.buttons.Confirm import ask

		if not await ask(interaction, "End the fight now? The side still standing wins; with more than one, nobody "
		                              "does.", "End fight") :
			return
		await self._run(interaction, lambda engine : engine.finish(), "finish")

	# ============================================================
	async def do_undo(self, interaction: discord.Interaction, fight: Fight) -> None :
		await interaction.response.defer(ephemeral=True)
		await CombatFlow.undo(interaction.client, self.fight_id, interaction)

	# == NPCs ==

	# ============================================================
	async def do_add_npc(self, interaction: discord.Interaction, fight: Fight) -> None :
		entries = BestiaryTransactions().get_all(fight.guild_id)
		if not entries :
			return await reply(interaction, "The bestiary is empty; add NPCs with /bestiary add, or use Quick NPC.")

		async def entry_chosen(next_interaction: discord.Interaction, values: list[str]) :
			entry = BestiaryTransactions().get(int(values[0]))
			enemies = fight.sides[-1].id if fight.sides else None

			async def side_chosen(side_interaction: discord.Interaction, side_id: int) :
				async def counted(form_interaction: discord.Interaction, fields: list[str]) :
					count = max(1, min(MAX_NPCS, number(fields[0]) or 1))
					rank = rank_of(fields[1])
					await form_interaction.response.defer(ephemeral=True)
					await CombatFlow.add_npcs(form_interaction.client, self.fight_id,
					                          lambda name, side, position : Loadout.for_bestiary(entry, side, name,
					                                                                             position, rank=rank),
					                          count, side_id, entry.name, form_interaction)

				await side_interaction.response.send_modal(Form(f"Add {entry.name}"[:45], [
					Field("How many?", "1", "1", max_length=2),
					Field("Miniboss or boss? (empty for neither)", "boss", required=False, max_length=10)], counted))

			await self._pick_side(next_interaction, fight, f"Which side does {entry.name} fight on?", side_chosen,
			                      enemies)

		await pick(interaction, "Which NPC?", [Option(entry.name, entry.id, f"{entry.preset} · HP {entry.hp} · AC "
		                                                                    f"{entry.ac}") for entry in entries],
		           "Pick from the bestiary", entry_chosen)

	# ============================================================
	async def do_quick_npc(self, interaction: discord.Interaction, fight: Fight) -> None :
		async def preset_chosen(next_interaction: discord.Interaction, values: list[str]) :
			preset = values[0]

			async def filled(form_interaction: discord.Interaction, fields: list[str]) :
				name = fields[0].strip() or preset.capitalize()
				count = max(1, min(MAX_NPCS, number(fields[1]) or 1))
				damage_type = fields[2].strip() or None

				async def side_chosen(side_interaction: discord.Interaction, side_id: int) :
					await side_interaction.response.defer(ephemeral=True)
					await CombatFlow.add_npcs(side_interaction.client, self.fight_id,
					                          lambda npc_name, side, position : Loadout.for_preset(
						                          preset, npc_name, side, damage_type, position),
					                          count, side_id, name, side_interaction)

				await self._pick_side(form_interaction, fight, "Which side?", side_chosen, fight.sides[-1].id)

			await next_interaction.response.send_modal(Form(f"Quick {preset} NPC", [
				Field("Name", "Bandit", max_length=80), Field("How many?", "1", "1", max_length=2),
				Field("Damage type (optional)", "Slashing", required=False, max_length=50)], filled))

		options = [Option(preset.capitalize(), preset, preset_text(preset)) for preset in PRESETS]
		await pick(interaction, "Which difficulty?", options, "Pick a preset", preset_chosen)

	# ============================================================
	async def do_act_as(self, interaction: discord.Interaction, fight: Fight) -> None :
		from views.combat.ActionPanel import open_panel

		engine = CombatFlow.engine(fight)
		npcs = [combatant for combatant in engine.actors() if combatant.controller == GM]
		if not npcs :
			return await reply(interaction, "No GM-controlled NPC can act right now. Set NPCs to GM control with "
			                                "Control.")
		await self._pick_combatant(interaction, fight, npcs, "Act as which NPC?",
		                           lambda next_interaction, combatant_id : open_panel(next_interaction, self.fight_id,
		                                                                              combatant_id))

	# ============================================================
	async def do_control(self, interaction: discord.Interaction, fight: Fight) -> None :
		async def chosen(next_interaction: discord.Interaction, combatant_id: int) :
			combatant = fight.combatant(combatant_id)
			modes = [Option("GM controls it", GM), Option("Automatic", AUTO)]
			if combatant.uid :
				modes.insert(0, Option("Its player controls it", PLAYER))
			behaviors = AUTOPILOTS if combatant.kind == "character" else BEHAVIORS

			async def mode_chosen(mode_interaction: discord.Interaction, values: list[str]) :
				controller = values[0]

				async def behavior_chosen(last: discord.Interaction, picked: list[str]) :
					await self._run(last, lambda engine : engine.control(engine.fight.combatant(combatant_id),
					                                                     controller, picked[0]), "control",
					                undoable=False)

				await pick(mode_interaction, "How should it act automatically?",
				           [Option(value.capitalize(), value, default=value == combatant.behavior) for value in behaviors],
				           "Pick a behavior", behavior_chosen)

			await pick(next_interaction, f"Who controls {combatant.name}?", modes, "Pick control", mode_chosen)

		await self._pick_combatant(interaction, fight, [combatant for combatant in fight.combatants
		                                                if combatant.in_fight], "Which combatant?", chosen)

	# ============================================================
	async def do_speak(self, interaction: discord.Interaction, fight: Fight) -> None :
		async def chosen(next_interaction: discord.Interaction, combatant_id: int) :
			async def written(form_interaction: discord.Interaction, fields: list[str]) :
				await form_interaction.response.defer(ephemeral=True)
				await CombatFlow.speak(form_interaction.client, form_interaction, self.fight_id, combatant_id, fields[0])

			await next_interaction.response.send_modal(Form("Speak as NPC", [
				Field("What do they say?", long=True, max_length=1800)], written))

		npcs = [combatant for combatant in fight.combatants if combatant.kind == "npc"]
		if not npcs :
			return await reply(interaction, "There are no NPCs in this fight.")
		await self._pick_combatant(interaction, fight, npcs, "Speak as which NPC?", chosen)

	# == combatants ==

	# ============================================================
	async def do_hp(self, interaction: discord.Interaction, fight: Fight) -> None :
		async def chosen(next_interaction: discord.Interaction, combatant_id: int) :
			async def typed(form_interaction: discord.Interaction, fields: list[str]) :
				change = number(fields[0])
				if not change :
					return await reply(form_interaction, "Type a number like -5 or +3.")
				await self._run(form_interaction, lambda engine : engine.adjust_hp(engine.fight.combatant(combatant_id),
				                                                                   change), "hp")

			await next_interaction.response.send_modal(Form("Change HP", [
				Field("Change (-5 deals 5, +3 heals 3)", "-5", max_length=5)], typed))

		await self._pick_combatant(interaction, fight, [combatant for combatant in fight.combatants
		                                                if combatant.in_fight], "Whose HP?", chosen)

	# ============================================================
	async def do_condition(self, interaction: discord.Interaction, fight: Fight) -> None :
		async def chosen(next_interaction: discord.Interaction, combatant_id: int) :
			combatant = fight.combatant(combatant_id)

			async def group_chosen(group_interaction: discord.Interaction, groups: list[str]) :
				options = [Option(f"{'Remove' if C.has(combatant.conditions, name) else 'Add'} {C.label(name)}", name,
				                  C.DEFINITIONS[name][2]) for name in CONDITION_GROUPS[groups[0]]]
				await pick(group_interaction, f"Conditions of {combatant.name}: "
				                              f"{C.text(combatant.conditions) or 'none'}", options, "Pick a condition",
				           condition_chosen)

			async def condition_chosen(condition_interaction: discord.Interaction, values: list[str]) :
				name = values[0]
				if C.has(combatant.conditions, name) :
					return await self._run(condition_interaction, lambda engine : engine.set_condition(
						engine.fight.combatant(combatant_id), name, None), "condition")

				async def typed(form_interaction: discord.Interaction, fields: list[str]) :
					amount = max(1, min(20, number(fields[0]) or 1)) if name != C.SHIELDED else max(1, number(fields[0]) or 1)
					await self._run(form_interaction, lambda engine : engine.set_condition(
						engine.fight.combatant(combatant_id), name, amount), "condition")

				label = "Shield amount" if name == C.SHIELDED else "For how many turns?"
				await condition_interaction.response.send_modal(Form(C.label(name), [Field(label, "2", "2",
				                                                                           max_length=3)], typed))

			await pick(next_interaction, f"Conditions of {combatant.name}: {C.text(combatant.conditions) or 'none'}",
			           [Option("Harmful conditions", "harmful"), Option("Helpful conditions", "helpful")],
			           "Which kind?", group_chosen)

		await self._pick_combatant(interaction, fight, [combatant for combatant in fight.combatants
		                                                if combatant.in_fight], "Whose conditions?", chosen)

	# ============================================================
	async def do_skip(self, interaction: discord.Interaction, fight: Fight) -> None :
		actors = CombatFlow.engine(fight).actors()
		if not actors :
			return await reply(interaction, "Nobody is waiting to act.")
		await self._pick_combatant(interaction, fight, actors, "Skip whose turn?",
		                           lambda next_interaction, combatant_id : self._run(
			                           next_interaction, lambda engine : engine.skip(engine.fight.combatant(combatant_id)),
			                           "skip"))

	# ============================================================
	async def do_remove(self, interaction: discord.Interaction, fight: Fight) -> None :
		await self._pick_combatant(interaction, fight, [combatant for combatant in fight.combatants
		                                                if combatant.in_fight], "Remove whom from the fight?",
		                           lambda next_interaction, combatant_id : self._run(
			                           next_interaction, lambda engine : engine.remove(
				                           engine.fight.combatant(combatant_id)), "remove"))

	# ============================================================
	async def do_move(self, interaction: discord.Interaction, fight: Fight) -> None :
		async def chosen(next_interaction: discord.Interaction, combatant_id: int) :
			await self._pick_side(next_interaction, fight, "Move to which side?",
			                      lambda side_interaction, side_id : self._run(
				                      side_interaction, lambda engine : engine.move(engine.fight.combatant(combatant_id),
				                                                                    side_id), "move"))

		await self._pick_combatant(interaction, fight, [combatant for combatant in fight.combatants
		                                                if combatant.in_fight], "Move whom?", chosen)

	# ============================================================
	async def do_settle(self, interaction: discord.Interaction, fight: Fight) -> None :
		async def chosen(next_interaction: discord.Interaction, values: list[str]) :
			entry_number = int(values[0])
			targets = [Option("Nobody (just describe it)", "0")] + self._combatant_options(
				fight, [combatant for combatant in fight.combatants if combatant.in_fight])

			async def target_chosen(target_interaction: discord.Interaction, picked: list[str]) :
				target_id = int(picked[0])

				async def typed(form_interaction: discord.Interaction, fields: list[str]) :
					change = number(fields[1]) or 0
					await self._run(form_interaction, lambda engine : engine.settle_other(
						entry_number, fields[0], engine.fight.combatant(target_id) if target_id else None, change),
					                "settle")

				await target_interaction.response.send_modal(Form(f"Settle #{entry_number}", [
					Field("What happens?", long=True, max_length=500),
					Field("HP change for the target (optional)", "-4", required=False, max_length=5)], typed))

			await pick(next_interaction, "Does it change anyone's HP?", targets, "Pick a target", target_chosen)

		await pick(interaction, "Which action?", [Option(f"#{entry['number']}", entry["number"], entry["text"][:100])
		                                          for entry in fight.pending], "Pick an action", chosen)

	# == settings ==

	# ============================================================
	async def do_sides(self, interaction: discord.Interaction, fight: Fight) -> None :
		async def chosen(next_interaction: discord.Interaction, values: list[str]) :
			choice = values[0]

			async def typed(form_interaction: discord.Interaction, fields: list[str]) :
				name = fields[0].strip()[:50]
				if not name :
					return await reply(form_interaction, "Type a name.")
				if choice == "new" :
					CombatTransactions().add_side(self.fight_id, name)
					text = f"➕ A new side joins the fight: **{name}**."
				else :
					side_id = int(choice)

					def rename(engine) :
						side = engine.fight.side(side_id)
						old = side.name
						side.name = name
						engine.say(f"The side {old} is now called **{name}**.")
						return engine.outcome

					return await self._run(form_interaction, rename, "sides", undoable=False)
				await form_interaction.response.defer(ephemeral=True)
				await CombatFlow.run(form_interaction.client, self.fight_id,
				                     lambda engine : engine.say(text) or engine.outcome, form_interaction,
				                     label="sides", undoable=False)
				await reply(form_interaction, "Done.")

			await next_interaction.response.send_modal(Form("New side" if choice == "new" else "Rename side",
			                                                [Field("Name", max_length=50)], typed))

		options = [Option("Add a side", "new")] + [Option(f"Rename {side.name}", side.id) for side in fight.sides]
		await pick(interaction, "Sides", options, "Pick", chosen)

	# ============================================================
	async def do_time(self, interaction: discord.Interaction, fight: Fight) -> None :
		unit = "minutes" if fight.pacing == LIVE else "hours"

		async def typed(form_interaction: discord.Interaction, fields: list[str]) :
			amount = number(fields[0])
			if not amount or amount < 1 :
				return await reply(form_interaction, "Type a whole number above 0.")

			def extend(engine) :
				fight_now = engine.fight
				if fight_now.deadline is None :
					return engine.outcome
				fight_now.deadline += timedelta(minutes=amount) if unit == "minutes" else timedelta(hours=amount)
				engine.say(f"⏳ The GM adds {amount} {unit}; this turn now ends <t:{int(fight_now.deadline.timestamp())}:R>.")
				return engine.outcome

			await self._run(form_interaction, extend, "time", undoable=False)

		await interaction.response.send_modal(Form("Add time", [Field(f"How many {unit}?", "2", max_length=3)], typed))

	# ============================================================
	async def do_late(self, interaction: discord.Interaction, fight: Fight) -> None :
		def toggle(engine) :
			engine.fight.late_join = not engine.fight.late_join
			engine.say("Late joins are now " + ("allowed." if engine.fight.late_join else "closed."))
			return engine.outcome

		await self._run(interaction, toggle, "late_join", undoable=False)

	# ============================================================
	async def do_roles(self, interaction: discord.Interaction, fight: Fight) -> None :
		view = RolesView(interaction.user.id, self.fight_id)
		await interaction.response.send_message("Pick a member to hand the GM role to, or to add or remove as co-GM.",
		                                        view=view, ephemeral=True)

	# ============================================================
	async def do_death(self, interaction: discord.Interaction, fight: Fight) -> None :
		downed = [combatant for combatant in fight.combatants if combatant.state in ("downed", DYING)]
		if not downed :
			return await reply(interaction, "Nobody is downed or dying.")

		async def chosen(next_interaction: discord.Interaction, combatant_id: int) :
			combatant = fight.combatant(combatant_id)
			options = [Option("Spare them (stable)", "spare")]
			if combatant.state == DYING :
				note = "The character dies: it stops posting and its post is locked" if combatant.character_id else None
				options.insert(0, Option("Confirm the death", "death", note))

			async def decided(last: discord.Interaction, values: list[str]) :
				if values[0] == "death" :
					return await self._run(last, lambda engine : engine.confirm_death(
						engine.fight.combatant(combatant_id)), "death", undoable=False)
				await self._run(last, lambda engine : engine.spare(engine.fight.combatant(combatant_id)), "spare")

			await pick(next_interaction, f"{combatant.name} is {combatant.state}.", options, "Decide", decided)

		await self._pick_combatant(interaction, fight, downed, "Whom?", chosen)

	# ============================================================
	async def do_rewards(self, interaction: discord.Interaction, fight: Fight) -> None :
		xp, currency = CombatFlow.suggested_rewards(fight)

		async def typed(form_interaction: discord.Interaction, fields: list[str]) :
			await form_interaction.response.defer(ephemeral=True)
			await CombatFlow.give_rewards(form_interaction.client, form_interaction, self.fight_id,
			                              max(0, number(fields[0]) or 0), max(0, number(fields[1]) or 0), fields[2])

		await interaction.response.send_modal(Form("Rewards for each winner", [
			Field("XP", str(xp), str(xp), max_length=7), Field("Currency", str(currency), str(currency), max_length=9),
			Field("Gear (catalog items, separated by commas)", "Healing Draught, Hedge Knife", required=False,
			      max_length=300)], typed))

	# ============================================================
	async def do_aftermath(self, interaction: discord.Interaction, fight: Fight) -> None :
		"""Picks a character in the fight, then adds an injury to its sheet or marks one of its items broken."""
		from classes.gear.Gear import Gear

		characters = [combatant for combatant in fight.combatants if combatant.character_id]
		if not characters :
			return await reply(interaction, "There are no characters in this fight.")

		async def chosen(next_interaction: discord.Interaction, combatant_id: int) :
			character_id = fight.combatant(combatant_id).character_id
			entries = [entry for entry, _ in Gear.inventory(character_id)]

			async def decided(choice_interaction: discord.Interaction, values: list[str]) :
				if values[0] == "injury" :
					async def written(form_interaction: discord.Interaction, fields: list[str]) :
						await form_interaction.response.defer(ephemeral=True)
						await CombatFlow.add_injury(form_interaction.client, form_interaction, self.fight_id,
						                            character_id, fields[0])

					return await choice_interaction.response.send_modal(Form("Injury", [
						Field("What happened to them?", "A deep cut across the left arm", long=True,
						      max_length=300)], written))

				async def broken(item_interaction: discord.Interaction, picked: list[str]) :
					await item_interaction.response.defer(ephemeral=True)
					await CombatFlow.break_gear(item_interaction.client, item_interaction, self.fight_id,
					                            int(picked[0]))

				await pick(choice_interaction, "Which item broke?",
				           [Option(entry.name, entry.id, entry.kind) for entry in entries], "Item", broken)

			options = [Option("Add an injury to the sheet", "injury")]
			if entries :
				options.append(Option("Mark an item broken", "broken"))
			await pick(next_interaction, "What happened?", options, "Choose", decided)

		await self._pick_combatant(interaction, fight, characters, "Whose?", chosen)


class RolesView(discord.ui.View) :
	"""Picks a member, then what to do: hand over the GM role, or add or remove them as co-GM."""

	def __init__(self, user_id: int, fight_id: int) :
		super().__init__(timeout=300)
		self.user_id = user_id
		self.fight_id = fight_id

	# ============================================================
	async def interaction_check(self, interaction: discord.Interaction) -> bool :
		return interaction.user.id == self.user_id

	# ============================================================
	@discord.ui.select(cls=discord.ui.UserSelect, placeholder="Pick a member")
	async def member(self, interaction: discord.Interaction, select: discord.ui.UserSelect) :
		member = select.values[0]
		if member.bot :
			return await reply(interaction, "Pick a person, not a bot.")
		member_id = member.id

		async def chosen(next_interaction: discord.Interaction, values: list[str]) :
			def change(engine) :
				fight = engine.fight
				if values[0] == "hand" :
					old = fight.gm_uid
					fight.gm_uid = member_id
					fight.co_gms = [uid for uid in fight.co_gms if uid != member_id]
					engine.say(f"<@{member_id}> is now the GM (taking over from <@{old}>).")
				elif values[0] == "add" :
					if member_id not in fight.co_gms and member_id != fight.gm_uid :
						fight.co_gms.append(member_id)
					engine.say(f"<@{member_id}> is now a co-GM.")
				else :
					fight.co_gms = [uid for uid in fight.co_gms if uid != member_id]
					engine.say(f"<@{member_id}> is no longer a co-GM.")
				return engine.outcome

			await next_interaction.response.defer(ephemeral=True)
			await CombatFlow.run(next_interaction.client, self.fight_id, change, next_interaction, label="roles",
			                     undoable=False)
			await reply(next_interaction, "Done.")

		await pick(interaction, f"What about {member.display_name}?",
		           [Option("Hand them the GM role", "hand"), Option("Add as co-GM", "add"),
		            Option("Remove as co-GM", "remove")], "Pick", chosen)


# ============================================================
async def open_gm_panel(interaction: discord.Interaction, fight_id: int) -> None :
	fight = CombatTransactions().load(fight_id)
	if fight is None :
		return await reply(interaction, "That fight no longer exists.")
	panel = GMPanel(interaction.user.id, fight)
	text = f"GM tools for **{fight.title}** ({fight.state})."
	if fight.pending :
		text += f" {len(fight.pending)} action{'s' if len(fight.pending) != 1 else ''} waiting to be settled."
	await interaction.response.send_message(text, view=panel, ephemeral=True)
