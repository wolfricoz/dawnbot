"""Fights: starting one, PvP challenges and invites, the board, and the quick attack roll outside fights. The fight
itself runs through the buttons on its board (see classes/combat/CombatFlow.py)."""
import logging

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.combat import Fortune, Rules
from classes.combat.AutoComplete import AutoComplete
from classes.combat.CombatFlow import CombatFlow
from classes.combat.DamageTypes import ALWAYS, DamageTypes, STRONG_HIT
from classes.combat.Loadout import Loadout
from classes.combat.State import PVP
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.CombatTransactions import CombatTransactions
from views.combat.Pickers import reply

PACING_CHOICES = [Choice(name="Async (long phases per side)", value="async"),
                  Choice(name="Live (short turns in order)", value="live")]


@app_commands.guild_only()
class Combat(commands.GroupCog, name="Combat", group_name="combat") :
	"""Fights in their own thread, PvP challenges, and quick attack rolls."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# == autocomplete ==

	# ============================================================
	async def _weapons(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		name = interaction.namespace.character
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, name) if name else None
		if character is None :
			return []
		weapons = Loadout.character_stats(character)["weapons"]
		return [Choice(name=weapon["name"][:100], value=weapon["key"]) for weapon in weapons
		        if current.lower() in weapon["name"].lower()][:25]

	# == fights ==

	# ============================================================
	@app_commands.command(name="start", description="Starts a fight in a new thread (or in this thread)")
	@app_commands.choices(pacing=PACING_CHOICES)
	async def start(self, interaction: discord.Interaction, title: app_commands.Range[str, 1, 100] = "Combat",
	                pacing: Choice[str] = None, lethal: bool = False) :
		"""
		Starts a fight. Used in a channel it opens a new thread; used in a thread, the fight runs there. You become
		the fight's GM: add NPCs, start it and run it from the **GM** button on the board. Players join with
		**Join** and act with **Act**.

		`pacing` only counts when the server lets the starter choose (`combat_pacing` set to `choose`); otherwise
		the server's pacing is used. `lethal` fights can kill characters; whether you can start one depends on the
		server's `combat_lethal` setting.
		"""
		await CombatFlow.start(interaction, title, pacing.value if pacing else None, lethal)

	# ============================================================
	@app_commands.command(name="challenge", description="Challenges another member to a PvP fight")
	@app_commands.autocomplete(character=AutoComplete().approved_character)
	async def challenge(self, interaction: discord.Interaction, member: discord.Member, character: str,
	                    lethal: bool = False) :
		"""
		Challenges another member's characters to a fight with one of yours. They accept (and pick their character)
		or decline with the buttons on the board. Others can join a side when someone on it invites them with
		`/combat invite`. You are the fight's GM and start it from the board.

		You'll both see a warning when a legendary character is involved. `lethal` needs the server's
		`combat_lethal` setting to allow it.
		"""
		await CombatFlow.challenge(interaction, member, character, lethal)

	# ============================================================
	@app_commands.command(name="invite", description="Invites a member to join your side in this PvP fight")
	async def invite(self, interaction: discord.Interaction, member: discord.Member) :
		"""
		Lets a member join your side in the PvP fight running in this thread. Run it in the fight's thread.
		"""
		fight = CombatTransactions().load_by_thread(interaction.channel_id)
		if fight is None :
			return await reply(interaction, "There is no fight running in this thread.")
		if fight.kind != PVP :
			return await reply(interaction, "Invites are only needed in PvP fights; anyone can join this one.")
		mine = fight.of_user(interaction.user.id)
		if not mine :
			return await reply(interaction, "Only someone fighting on a side can invite to it.")
		if member.bot :
			return await reply(interaction, "Invite a person, not a bot.")
		side_id = mine[0].side_id
		async with CombatFlow.lock(fight.id) :
			fight = CombatTransactions().load(fight.id)
			invites = dict(fight.invites or {})
			invited = list(invites.get(str(side_id), []))
			if member.id not in invited :
				invited.append(member.id)
			invites[str(side_id)] = invited
			CombatTransactions().set_fields(fight.id, invites=invites, late_join=fight.late_join)
		await interaction.response.send_message(f"{member.mention} can now join **{fight.side(side_id).name}** with "
		                                        f"the Join button on the board.",
		                                        allowed_mentions=discord.AllowedMentions(users=[member]))

	# ============================================================
	@app_commands.command(name="board", description="Posts this thread's fight board again")
	async def board(self, interaction: discord.Interaction) :
		"""
		Posts the board of the fight in this thread again, for when it scrolled far up or was deleted.
		"""
		fight = CombatTransactions().load_by_thread(interaction.channel_id)
		if fight is None :
			return await reply(interaction, "There is no fight running in this thread.")
		await interaction.response.defer(ephemeral=True)
		fight.board_message_id = None
		await CombatFlow.update_board(self.bot, fight)
		await reply(interaction, "Posted the board again.")

	# == quick roll ==

	# ============================================================
	@app_commands.command(name="attack", description="Rolls an attack with one of your weapons against an AC")
	@app_commands.autocomplete(character=AutoComplete().approved_character, weapon=_weapons)
	async def attack(self, interaction: discord.Interaction, character: str, weapon: str,
	                 target_ac: app_commands.Range[int, 1, 40], target_dt: app_commands.Range[int, 0, 20] = 0,
	                 aimed: bool = False, hit_modifier: app_commands.Range[int, -10, 10] = 0,
	                 damage_modifier: app_commands.Range[int, -20, 20] = 0, title: app_commands.Range[str, 1, 100] = None) :
		"""
		Rolls an attack outside a fight: one of your character's weapons against an AC you choose, with its stats,
		proficiency, armor and gear rules. `aimed` is -4 to hit, adds a damage die and ignores DT. Inside a fight's
		thread, use the board instead.
		"""
		if CombatTransactions().load_by_thread(interaction.channel_id) is not None :
			return await reply(interaction, "A fight is running in this thread; act through the **Act** button on its "
			                                "board.")
		record = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character)
		if record is None or record.state != APPROVED :
			return await reply(interaction, f"You have no approved character called {character}.")
		stats = Loadout.character_stats(record)
		chosen = next((item for item in stats["weapons"] if item["key"] == weapon or item["name"].lower() ==
		               weapon.lower()), None)
		if chosen is None :
			return await reply(interaction, f"{record.name} has no weapon called {weapon}.")
		base = stats["base"]
		bonuses = Rules.weapon_bonuses(stats, chosen, base)
		if aimed :
			bonuses.append(Rules.Bonus("aimed", Rules.AIMED_PENALTY))
		if hit_modifier :
			bonuses.append(Rules.Bonus("extra", hit_modifier))
		disadvantage = chosen.get("range") == Rules.RANGED and stats["special"]["perception"] <= 0
		roll, first = Fortune.for_character(record.id, lambda : Rules.roll_attack(
			bonuses, target_ac, stats["crit_min"] - Rules.weapon_crit_widen(chosen), stats["fumble_max"],
			disadvantage=disadvantage, confirm_crits=stats["confirm_crits"]), lambda attack : attack.hit,
		                                    lambda attack : attack.total)
		embed = discord.Embed(title=title or f"{record.name} attacks with {chosen['name']}",
		                      color=discord.Color.red())
		lines = [f"**To hit:** {roll.text()}", f"-# {Rules.bonus_text(bonuses)}"]
		if first is not None :
			lines.append(f"-# {Fortune.note(str(first.total))}")
		if roll.fumble :
			lines.append("**Fumble!** The attacker is left open (-2 AC until their next turn).")
		elif not roll.hit :
			lines.append("**Miss.**")
		else :
			table = DamageTypes.table(interaction.guild_id)
			kind = table.get((chosen.get("type") or "").lower())
			triggered = kind is not None and (kind["trigger"] == ALWAYS or (kind["trigger"] == STRONG_HIT and roll.strong))
			ignore_dt = aimed or (triggered and kind["effect"].get("kind") == "ignore_dt")
			damage = Rules.roll_damage(chosen["dice"], Rules.damage_bonus(stats, chosen, base) + damage_modifier,
			                           target_dt, crit=roll.crit, extra_dice=1 if aimed else 0, ignore_dt=ignore_dt)
			label = "Crit!" if roll.crit else ("Strong hit" if roll.strong else "Hit")
			lines.append(f"**{label}** for **{damage.total}** damage ({damage.text()}).")
			if triggered :
				lines.append(f"-# {kind['name']}: {DamageTypes.describe(kind['effect'])}.")
		embed.description = "\n".join(lines)
		logging.info(f"{interaction.user.name} rolled an attack with {chosen['name']} for character {record.id}")
		await interaction.response.send_message(embed=embed)


async def setup(bot) :
	await bot.add_cog(Combat(bot))
