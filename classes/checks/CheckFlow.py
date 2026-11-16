"""The Discord side of checks: posting a check's card, rolling on it, helping, closing, passive checks and the timer
that closes checks when they run out. The rules live in classes/checks/Checks.py."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord

from classes.characters.Special import Special
from classes.checks import CheckCard, Checks, RollLog
from classes.checks.Checks import CLOSED, OPEN, OPPOSED, PASSIVE, PUBLIC, SECRET
from classes.combat import Fortune
from classes.combat.Rules import Bonus
from database.database import Characters, Checks as CheckRecord
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.CheckTransactions import CheckTransactions
from database.transactions.ProxyTransactions import ProxyTransactions
from views.combat.Pickers import Field, Form, Option, pick, reply

MENTION_LIMIT = 2000


class CheckFlow :
	_locks: dict[int, asyncio.Lock] = {}

	# ============================================================
	@staticmethod
	def lock(check_id: int) -> asyncio.Lock :
		return CheckFlow._locks.setdefault(check_id, asyncio.Lock())

	# ============================================================
	@staticmethod
	def runs(check: CheckRecord, member: discord.Member) -> bool :
		"""Whether a member runs the check: its caller, or staff."""
		from classes.kernel.GMRole import is_gm

		return member.id == check.caller_uid or is_gm(member)

	# ============================================================
	@staticmethod
	def base(guild_id: int) -> int :
		return Special.rules(guild_id).base

	# == posting ==

	# ============================================================
	@staticmethod
	async def post(interaction: discord.Interaction, check: CheckRecord, content: str | None = None,
	               mentions: discord.AllowedMentions | None = None) -> None :
		"""Posts a new check's card as the answer to the command."""
		from views.checks.CheckButtons import card_view

		await interaction.response.send_message(content=content, embed=CheckCard.embed(check, []),
		                                        view=card_view(check),
		                                        allowed_mentions=mentions or discord.AllowedMentions.none())
		message = await interaction.original_response()
		CheckTransactions().update(check.id, message_id=message.id)

	# ============================================================
	@staticmethod
	async def refresh(bot: discord.Client, check_id: int) -> None :
		"""Redraws a check's card."""
		from views.checks.CheckButtons import card_view

		check = CheckTransactions().get(check_id)
		if check is None or check.message_id is None :
			return
		channel = bot.get_channel(check.channel_id)
		try :
			if channel is None :
				channel = await bot.fetch_channel(check.channel_id)
			await channel.get_partial_message(check.message_id).edit(
				embed=CheckCard.embed(check, CheckTransactions().rolls(check.id)), view=card_view(check))
		except discord.HTTPException as e :
			logging.warning(f"Could not update the card of check {check.id}: {e}")

	# ============================================================
	@staticmethod
	def expiry(hours: int | None) -> datetime :
		hours = max(1, min(Checks.MAX_HOURS, hours or Checks.DEFAULT_HOURS))
		return datetime.now(timezone.utc) + timedelta(hours=hours)

	# ============================================================
	@staticmethod
	async def call(interaction: discord.Interaction, stat: str, dc_text: str | None, title: str | None, kind: str,
	               visibility: str, modifier: int, npc_bonus: int | None, npc_name: str | None,
	               role: discord.Role | None, member: discord.Member | None, hours: int | None) -> None :
		dc = Checks.parse_dc(dc_text)
		opposed = None
		if kind == OPPOSED :
			if npc_bonus is None :
				return await reply(interaction, "An opposed check from /check call is against an NPC: give its "
				                                "`npc_bonus` (and a `npc_name`). For one character against another, use "
				                                "/check oppose.")
			natural, total = Checks.npc_roll(npc_bonus)
			opposed = {"npc" : (npc_name or "the NPC")[:80], "bonus" : npc_bonus, "natural" : natural,
			           "total" : total}
			# Players have to beat the NPC; a tie goes to the NPC.
			dc = total + 1
		elif dc is None :
			names = ", ".join(name for name in Checks.DCS)
			return await reply(interaction, f"Give a DC: a number from {Checks.DC_MIN} to {Checks.DC_MAX}, or one of "
			                                f"{names}.")
		allowed = {key : value for key, value in (("role", role.id if role else None),
		                                          ("member", member.id if member else None)) if value}
		check = CheckTransactions().create(interaction.guild_id, interaction.channel_id, interaction.user.id, stat,
		                                   title=(title or None) and title[:200], dc=dc, kind=kind,
		                                   visibility=visibility, modifier=modifier, allowed=allowed,
		                                   opposed=opposed, expires_at=CheckFlow.expiry(hours))
		if check is None :
			return await reply(interaction, "Something went wrong saving the check; please try again.")
		logging.info(f"{interaction.user.name} called check {check.id} ({stat}, DC {dc}) in {interaction.guild.name}")
		await CheckFlow.post(interaction, check)
		if opposed and visibility != PUBLIC :
			await interaction.followup.send(f"🔒 {opposed['npc']} rolled **{opposed['total']}** ({opposed['natural']} "
			                                f"{npc_bonus:+d}).", ephemeral=True)

	# ============================================================
	@staticmethod
	async def oppose(interaction: discord.Interaction, member: discord.Member, their_name: str, my_name: str,
	                 my_stat: str, their_stat: str, title: str | None, hours: int | None) -> None :
		if member.id == interaction.user.id or member.bot :
			return await reply(interaction, "Pick another member's character to oppose.")
		mine = CharacterTransactions().get(interaction.user.id, interaction.guild_id, my_name)
		theirs = CharacterTransactions().get(member.id, interaction.guild_id, their_name)
		if mine is None or mine.state != APPROVED :
			return await reply(interaction, f"You have no approved character called {my_name}.")
		if theirs is None or theirs.state != APPROVED :
			return await reply(interaction, f"{member.display_name} has no approved character called {their_name}.")
		opposed = {"1" : {"uid" : mine.uid, "character_id" : mine.id, "name" : mine.name, "stat" : my_stat},
		           "2" : {"uid" : theirs.uid, "character_id" : theirs.id, "name" : theirs.name, "stat" : their_stat}}
		check = CheckTransactions().create(interaction.guild_id, interaction.channel_id, interaction.user.id, my_stat,
		                                   title=(title or None) and title[:200], kind=OPPOSED, visibility=PUBLIC,
		                                   opposed=opposed, expires_at=CheckFlow.expiry(hours))
		if check is None :
			return await reply(interaction, "Something went wrong saving the check; please try again.")
		await CheckFlow.post(interaction, check,
		                     content=f"{member.mention}: {mine.name} opposes {theirs.name}. Press **Roll** to answer.",
		                     mentions=discord.AllowedMentions(users=[member]))

	# == rolling ==

	# ============================================================
	@staticmethod
	async def start_roll(interaction: discord.Interaction, check_id: int) -> None :
		"""The Roll button: works out which character rolls, asking when there are several."""
		check = CheckTransactions().get(check_id)
		if check is None :
			return await reply(interaction, "That check no longer exists.")
		if check.state != OPEN :
			return await reply(interaction, "This check is closed.")
		rolled = {roll.character_id for roll in CheckTransactions().rolls(check.id)}
		if CheckCard.is_character_duel(check) :
			sides = [side for side in ("1", "2") if int(check.opposed[side]["uid"]) == interaction.user.id]
			if not sides :
				return await reply(interaction, "Only the two players in this opposed check can roll.")
			side = sides[0]
			if check.opposed[side]["character_id"] in rolled :
				return await reply(interaction, f"{check.opposed[side]['name']} already rolled.")
			return await CheckFlow.roll(interaction, check.id, int(check.opposed[side]["character_id"]))
		role_ids = [role.id for role in getattr(interaction.user, "roles", [])]
		if not Checks.may_roll(check.allowed, interaction.user.id, role_ids) :
			return await reply(interaction, "This check isn't for you.")
		characters = [character for character in
		              CharacterTransactions().get_all(interaction.user.id, interaction.guild_id, states=[APPROVED])
		              if character.id not in rolled]
		if not characters :
			return await reply(interaction, "You have no approved character left to roll on this check.")
		if len(characters) == 1 :
			return await CheckFlow.roll(interaction, check.id, characters[0].id)
		await pick(interaction, "Roll as which character?",
		           [Option(character.name, character.id, f"{CheckCard.stat_name(check.stat)} "
		                                                 f"{getattr(character, check.stat, 0)}")
		            for character in characters],
		           "Pick a character", lambda next_interaction, values : CheckFlow.roll(next_interaction, check.id,
		                                                                               int(values[0])))

	# ============================================================
	@staticmethod
	async def roll(interaction: discord.Interaction, check_id: int, character_id: int) -> None :
		if not interaction.response.is_done() :
			await interaction.response.defer(ephemeral=True, thinking=True)
		async with CheckFlow.lock(check_id) :
			check = CheckTransactions().get(check_id)
			character = CharacterTransactions().get_by_id(character_id)
			if check is None or check.state != OPEN :
				return await reply(interaction, "This check is closed.")
			if character is None or character.uid != interaction.user.id or character.state != APPROVED :
				return await reply(interaction, "That character can't roll.")
			duel = CheckCard.is_character_duel(check)
			side = 0
			stat = check.stat
			if duel :
				side = 1 if int(check.opposed["1"]["character_id"]) == character.id else 2
				stat = check.opposed[str(side)]["stat"]
			helps, help_ = Checks.take_help(check.helps, interaction.user.id)
			extras = [Bonus(f"Help ({help_.get('helper_name')})", Checks.HELP_BONUS)] if help_ else []
			result, first = CheckFlow.make_roll(check, character, stat, extras,
			                                    getattr(interaction.channel, "parent_id", None))
			details = {"bonuses" : [[bonus.label, bonus.value] for bonus in result.bonuses], "notes" : result.notes}
			if first is not None :
				details["rerolled"] = first.total
			saved = CheckTransactions().add_roll(check.id, character.id, interaction.user.id, character.name, stat,
			                                     side=side, natural=result.natural, total=result.total,
			                                     outcome=result.outcome,
			                                     helped_by=help_.get("helper_name") if help_ else None,
			                                     details=details)
			if saved is None :
				return await reply(interaction, f"{character.name} already rolled on this check.")
			changes = {"helps" : helps} if help_ else {}
			if duel :
				changes |= CheckFlow.settle_duel(check)
			if changes :
				CheckTransactions().update(check.id, **changes)
		await CheckFlow.refresh(interaction.client, check.id)
		text = CheckCard.own_result(check, character.name, result)
		if first is not None and check.visibility != SECRET :
			text += f"\n-# {Fortune.note(str(first.total))}"
		await reply(interaction, text)
		if check.visibility == SECRET :
			await RollLog.post(interaction.guild, f"🔒 Secret {CheckCard.stat_name(stat)} check "
			                                      f"({Checks.dc_text(check.dc)}) called by <@{check.caller_uid}> in "
			                                      f"<#{check.channel_id}>: {character.name} rolled {result.total} "
			                                      f"({Checks.OUTCOME_LABELS[result.outcome]}).")

	# ============================================================
	@staticmethod
	def make_roll(check: CheckRecord, character: Characters, stat: str, extras: list[Bonus],
	              parent_id: int | None = None) :
		"""Rolls for a character, with bad-roll protection when the roll can fail on its own (it has a DC). The
		weather at an outdoor location adds its modifier.

		@return: the result that counts, and the first roll when it was made again (else None).
		"""
		stats = Checks.stats_of(character)
		base = CheckFlow.base(check.guild_id)
		extras = list(extras) + CheckFlow.situational(check.guild_id, check.channel_id, parent_id, stat)
		from classes.flavor import OmenFlow

		bane = OmenFlow.bane(character)
		if bane :
			# An omen's bane: -1 on this check, then it is spent.
			extras.append(Bonus("Omen", OmenFlow.BANE_PENALTY))
			OmenFlow.use_bane(character.id)

		def make() :
			return Checks.roll(stats, stat, check.dc, base, check.modifier or 0, extras)

		if check.dc is None :
			return make(), None
		return Fortune.for_character(character.id, make, lambda result : result.success, lambda result : result.total)

	# ============================================================
	@staticmethod
	def situational(guild_id: int, channel_id: int | None, parent_id: int | None, stat: str) -> list[Bonus] :
		"""Modifiers from the world: the weather where the check is rolled."""
		from classes.world.WorldFlow import WorldFlow

		weather = WorldFlow.check_bonus(guild_id, channel_id, parent_id, stat)
		return [weather] if weather else []

	# ============================================================
	@staticmethod
	def settle_duel(check: CheckRecord) -> dict :
		"""When both sides of a duel rolled: the winner, and the check closes."""
		by_side = {roll.side : roll for roll in CheckTransactions().rolls(check.id)}
		if 1 not in by_side or 2 not in by_side :
			return {}

		def result(roll) :
			return Checks.CheckResult(natural=roll.natural, rolls=[roll.natural], bonuses=[], total=roll.total,
			                          dc=None, outcome=roll.outcome)

		opposed = dict(check.opposed)
		opposed["winner"] = Checks.opposed_winner(result(by_side[1]), result(by_side[2]))
		return {"opposed" : opposed, "state" : CLOSED, "closed_at" : datetime.now(timezone.utc)}

	# == helping ==

	# ============================================================
	@staticmethod
	async def start_help(interaction: discord.Interaction, check_id: int) -> None :
		check = CheckTransactions().get(check_id)
		if check is None or check.state != OPEN :
			return await reply(interaction, "This check is closed.")
		helped = {int(help_.get("helper_character_id", 0)) for help_ in check.helps or []}
		characters = [character for character in
		              CharacterTransactions().get_all(interaction.user.id, interaction.guild_id, states=[APPROVED])
		              if character.id not in helped]
		if not characters :
			return await reply(interaction, "You have no approved character that can still help on this check.")

		async def helper_chosen(next_interaction: discord.Interaction, character_id: int) :
			from views.checks.CheckButtons import HelpTargetView

			view = HelpTargetView(next_interaction.user.id,
			                      lambda last, target : CheckFlow.help(last, check_id, character_id, target))
			text = "Who do you help? They get +2 on their next roll on this check."
			if next_interaction.response.is_done() :
				await next_interaction.followup.send(text, view=view, ephemeral=True)
			else :
				await next_interaction.response.send_message(text, view=view, ephemeral=True)

		if len(characters) == 1 :
			return await helper_chosen(interaction, characters[0].id)
		await pick(interaction, "Help as which character?",
		           [Option(character.name, character.id) for character in characters], "Pick a character",
		           lambda next_interaction, values : helper_chosen(next_interaction, int(values[0])))

	# ============================================================
	@staticmethod
	async def help(interaction: discord.Interaction, check_id: int, character_id: int, target: discord.abc.User) -> None :
		async with CheckFlow.lock(check_id) :
			check = CheckTransactions().get(check_id)
			character = CharacterTransactions().get_by_id(character_id)
			if check is None or check.state != OPEN :
				return await reply(interaction, "This check is closed.")
			if character is None or character.uid != interaction.user.id :
				return await reply(interaction, "That character can't help.")
			if target.bot :
				return await reply(interaction, "Pick a member, not a bot.")
			problem = Checks.help_problem(check.helps, interaction.user.id, character.id, target.id)
			if problem :
				return await reply(interaction, problem)
			helps = list(check.helps or []) + [{"helper_uid" : interaction.user.id, "helper_character_id" : character.id,
			                                    "helper_name" : character.name, "target_uid" : target.id,
			                                    "used" : False}]
			CheckTransactions().update(check.id, helps=helps)
		await CheckFlow.refresh(interaction.client, check_id)
		await reply(interaction, f"🤝 {character.name} helps {target.display_name}: +{Checks.HELP_BONUS} on their next "
		                         f"roll on this check.")

	# == closing ==

	# ============================================================
	@staticmethod
	async def close(interaction: discord.Interaction, check_id: int) -> None :
		check = CheckTransactions().get(check_id)
		if check is None :
			return await reply(interaction, "That check no longer exists.")
		if not CheckFlow.runs(check, interaction.user) :
			return await reply(interaction, "Only whoever called the check (or staff) can close it.")
		if check.state == CLOSED :
			return await reply(interaction, "This check is already closed.")
		await CheckFlow.finish(interaction.client, check.id)
		await reply(interaction, "Check closed.")

	# ============================================================
	@staticmethod
	async def finish(bot: discord.Client, check_id: int) -> None :
		async with CheckFlow.lock(check_id) :
			check = CheckTransactions().get(check_id)
			if check is None or check.state == CLOSED :
				return
			CheckTransactions().update(check_id, state=CLOSED, closed_at=datetime.now(timezone.utc))
		await CheckFlow.refresh(bot, check_id)
		CheckFlow._locks.pop(check_id, None)

	# ============================================================
	@staticmethod
	async def results(interaction: discord.Interaction, check_id: int) -> None :
		check = CheckTransactions().get(check_id)
		if check is None :
			return await reply(interaction, "That check no longer exists.")
		if not CheckFlow.runs(check, interaction.user) :
			return await reply(interaction, "Only whoever called the check (or staff) can see its results.")
		await reply(interaction, CheckCard.results_text(check, CheckTransactions().rolls(check.id)))

	# ============================================================
	@staticmethod
	async def tick(bot: discord.Client) -> None :
		"""Closes checks whose time ran out."""
		for check in CheckTransactions().expired(datetime.now(timezone.utc)) :
			await CheckFlow.finish(bot, check.id)

	# == passive checks ==

	# ============================================================
	@staticmethod
	def present(guild: discord.Guild, channel_id: int, role: discord.Role | None,
	            member: discord.Member | None) -> list[Characters] :
		"""The approved characters that posted in this channel in the last few days, limited to a role or member."""
		from classes.kernel import RoleplaySettings
		from resources.configs.ConfigMapping import ConfigMapping

		days = RoleplaySettings.number(guild.id, ConfigMapping.PRESENCE_DAYS)
		since = datetime.now(timezone.utc) - timedelta(days=days)
		characters = []
		for character_id in ProxyTransactions().recent_characters(channel_id, since) :
			character = CharacterTransactions().get_by_id(character_id)
			if character is None or character.state != APPROVED or character.guild_id != guild.id :
				continue
			if role is not None or member is not None :
				player = guild.get_member(character.uid)
				in_role = role is not None and player is not None and role in player.roles
				if not in_role and not (member is not None and member.id == character.uid) :
					continue
			characters.append(character)
		return characters

	# ============================================================
	@staticmethod
	async def passive(interaction: discord.Interaction, stat: str, dc_text: str, modifier: int, title: str | None,
	                  role: discord.Role | None, member: discord.Member | None) -> None :
		dc = Checks.parse_dc(dc_text)
		if dc is None :
			return await reply(interaction, f"Give a DC: a number from {Checks.DC_MIN} to {Checks.DC_MAX}, or one of "
			                                f"{', '.join(Checks.DCS)}.")
		characters = CheckFlow.present(interaction.guild, interaction.channel_id, role, member)
		if not characters :
			from classes.kernel import RoleplaySettings
			from resources.configs.ConfigMapping import ConfigMapping

			days = RoleplaySettings.number(interaction.guild_id, ConfigMapping.PRESENCE_DAYS)
			return await reply(interaction, f"No characters posted here in the last {days} days"
			                                f"{' (in that role or for that member)' if role or member else ''}.")
		check = CheckTransactions().create(interaction.guild_id, interaction.channel_id, interaction.user.id, stat,
		                                   title=(title or None) and title[:200], dc=dc, kind=PASSIVE,
		                                   visibility=SECRET, modifier=modifier, state=CLOSED,
		                                   closed_at=datetime.now(timezone.utc))
		if check is None :
			return await reply(interaction, "Something went wrong saving the check; please try again.")
		base = CheckFlow.base(interaction.guild_id)
		extras = CheckFlow.situational(interaction.guild_id, interaction.channel_id,
		                               getattr(interaction.channel, "parent_id", None), stat)
		lines, passed = [], []
		for character in characters :
			# Passive rolls happen without the player knowing, so they don't count toward bad-roll protection.
			result = Checks.roll(Checks.stats_of(character), stat, dc, base, modifier, extras)
			CheckTransactions().add_roll(check.id, character.id, character.uid, character.name, stat,
			                             natural=result.natural, total=result.total, outcome=result.outcome)
			lines.append(f"**{character.name}** (<@{character.uid}>) · {result.breakdown()} · "
			             f"{Checks.OUTCOME_LABELS[result.outcome]}")
			if result.success :
				passed.append(character)
		head = f"👁️ Passive {CheckCard.stat_name(stat)} check · {Checks.dc_text(dc)}" + \
		       (f" · {title}" if title else "")
		text = "\n".join([head] + lines + [f"{len(passed)} of {len(characters)} passed. Only you see this."])
		from views.checks.CheckButtons import RevealView

		view = RevealView(interaction.user.id, lambda last : CheckFlow.ask_reveal(last, check.id, stat, passed)) \
			if passed else None
		if view is not None :
			await interaction.response.send_message(text[:2000], view=view, ephemeral=True)
		else :
			await interaction.response.send_message(text[:2000], ephemeral=True)
		await RollLog.post(interaction.guild, f"🔒 Passive {CheckCard.stat_name(stat)} check ({Checks.dc_text(dc)}) by "
		                                      f"<@{interaction.user.id}> in <#{interaction.channel_id}>:\n" +
		                   "\n".join(lines))

	# ============================================================
	@staticmethod
	async def ask_reveal(interaction: discord.Interaction, check_id: int, stat: str,
	                     passed: list[Characters]) -> None :
		async def written(form_interaction: discord.Interaction, fields: list[str]) :
			await form_interaction.response.defer(ephemeral=True)
			sent, failed = await CheckFlow.reveal(form_interaction, stat, passed, fields[0])
			text = f"Sent to {', '.join(sent)}." if sent else "Nothing was sent."
			if failed :
				text += f" These players have DMs closed: {', '.join(failed)}."
			await reply(form_interaction, text)

		await interaction.response.send_modal(Form("Reveal to those who passed", [
			Field("What do they notice?", "You notice the guard's hand drifting to his knife.", long=True,
			      max_length=1500)], written))

	# ============================================================
	@staticmethod
	async def reveal(interaction: discord.Interaction, stat: str, passed: list[Characters],
	                 text: str) -> tuple[list[str], list[str]] :
		"""DMs the players of the characters that passed. Returns who got it and who has DMs closed."""
		sent, failed = [], []
		where = getattr(interaction.channel, "mention", "the roleplay")
		for character in passed :
			embed = discord.Embed(title=f"👁️ {character.name} notices something", description=text[:4096],
			                      colour=discord.Colour.teal())
			embed.set_footer(text=f"Passive {CheckCard.stat_name(stat)} check in {interaction.guild.name}")
			embed.add_field(name="Where", value=where, inline=False)
			player = interaction.guild.get_member(character.uid)
			try :
				if player is None :
					player = await interaction.guild.fetch_member(character.uid)
				await player.send(embed=embed)
				sent.append(character.name)
			except discord.HTTPException :
				failed.append(character.name)
		return sent, failed
