"""The Discord side of downtime: checking a character may spend the day, running the activity and the result card."""
from datetime import datetime, timezone

import discord

from classes.checks import Checks
from classes.economy import Crafting, Downtime
from classes.kernel import RoleplaySettings
from classes.kernel.ConfigData import ConfigData
from database.database import Characters
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.LanguageTransactions import LanguageTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from resources.configs.ConfigMapping import ConfigMapping
from views.combat.Pickers import reply

WORK_REASON = "work"
CAROUSE_REASON = "carouse"
DOWNTIME_COLOUR = discord.Colour.dark_teal()


class DowntimeFlow :

	# ============================================================
	@staticmethod
	def day(guild_id: int, now: datetime | None = None) -> str :
		return Downtime.day_key(now or datetime.now(timezone.utc),
		                        RoleplaySettings.number(guild_id, ConfigMapping.DOWNTIME_RESET))

	# ============================================================
	@staticmethod
	def problem(character: Characters | None, now: datetime | None = None) -> str | None :
		"""Why a character can't spend downtime today, or None."""
		if character is None or character.state != APPROVED :
			return "Pick one of your approved characters."
		now = now or datetime.now(timezone.utc)
		if EconomyTransactions().downtime_on(character.id, DowntimeFlow.day(character.guild_id, now)) is not None :
			reset = Downtime.next_reset(now, RoleplaySettings.number(character.guild_id, ConfigMapping.DOWNTIME_RESET))
			return f"{character.name} already spent today's downtime; the next day starts <t:{int(reset.timestamp())}:R>."
		if not Downtime.active(character, now) :
			days = RoleplaySettings.number(character.guild_id, ConfigMapping.DOWNTIME_ACTIVE_DAYS)
			return f"{character.name} needs a roleplay post in the last {days} days to spend downtime."
		return None

	# ============================================================
	@staticmethod
	def economy(guild_id: int) -> bool :
		return str(ConfigData().get_key(guild_id, ConfigMapping.ECONOMY)).lower() != "free"

	# == activities ==

	# ============================================================
	@staticmethod
	def work(character: Characters, stat: str | None) -> tuple[str, list[str], dict, object | None] :
		"""Returns the outcome, lines, details and the occupation's table for a great day (or None)."""
		from classes.gear.Gear import Gear

		occupation = OccupationTransactions().get(character.occupation_id) if character.occupation_id else None
		odd_jobs = occupation is None
		base = occupation.pay if occupation is not None and occupation.pay is not None else \
			RoleplaySettings.number(character.guild_id, ConfigMapping.WORK_PAY)
		stat = (occupation.work_stat if occupation is not None and occupation.work_stat else stat) or "strength"
		result, first = Downtime.roll(character, stat)
		earned = Downtime.pay(base, result.outcome, odd_jobs)
		currency = ConfigData().get_key(character.guild_id, ConfigMapping.CURRENCY_NAME)
		job = occupation.name if occupation else "odd jobs"
		lines = [f"⚒️ {character.name} works ({job}): {result.breakdown()} on {stat.capitalize()} · "
		         f"{Checks.OUTCOME_LABELS[result.outcome]}", f"*{Downtime.FLAVOR.get(result.outcome, '')}*"]
		if earned :
			Gear.change_currency(character, earned, WORK_REASON, character.uid, note=f"Downtime: {job}")
			lines.append(f"Earned **{earned} {currency}**.")
		if first is not None :
			from classes.combat import Fortune

			lines.append(f"-# {Fortune.note(str(first.total))}")
		table = None
		if result.outcome == Checks.CRIT and occupation is not None and occupation.table_id :
			from database.transactions.RollTableTransactions import RollTableTransactions

			table = RollTableTransactions().get(occupation.table_id)
		return result.outcome, lines, {"earned" : earned, "stat" : stat, "total" : result.total}, table

	# ============================================================
	@staticmethod
	def study(character: Characters, language) -> tuple[str, list[str], dict] :
		from classes.language.LanguageFlow import LanguageFlow, STUDY

		result, _ = Downtime.roll(character, "intelligence")
		gained = Downtime.STUDY_POINTS.get(result.outcome, 0)
		points = EconomyTransactions().study(character.id, language.id) + gained
		EconomyTransactions().set_study(character.id, language.id, points)
		study_days = RoleplaySettings.number(character.guild_id, ConfigMapping.STUDY_DAYS)
		lines = [f"📖 {character.name} studies {language.name}: {result.breakdown()} · "
		         f"{Checks.OUTCOME_LABELS[result.outcome]} · +{gained} ({points} of {2 * study_days})"]
		stage = Downtime.study_stage(points, study_days)
		known = LanguageFlow.known(character).get(language.id)
		if stage == "fluent" and known != "fluent" :
			LanguageTransactions().teach(character.id, language.id, "fluent", STUDY)
			lines.append(f"🎓 {character.name} now speaks {language.name} fluently!")
		elif stage == "partial" and known is None :
			LanguageTransactions().teach(character.id, language.id, "partial", STUDY)
			lines.append(f"🎓 {character.name} can now follow some {language.name}.")
		return result.outcome, lines, {"points" : points, "language_id" : language.id}

	# ============================================================
	@staticmethod
	def carouse(character: Characters) -> tuple[str | None, list[str], dict] :
		"""Spends CAROUSE_COST for a free rumor listen at +2. Returns None as the outcome when it can't be paid."""
		from classes.gear.Gear import Gear

		cost = RoleplaySettings.number(character.guild_id, ConfigMapping.CAROUSE_COST) \
			if DowntimeFlow.economy(character.guild_id) else 0
		if cost :
			updated, problem = Gear.change_currency(character, -cost, CAROUSE_REASON, character.uid,
			                                        note="Downtime: carousing")
			if problem :
				return None, [problem], {}
		try :
			from classes.flavor.RumorFlow import RumorFlow

			outcome, heard = RumorFlow.overhear(character, bonus=2)
		except ImportError :
			outcome, heard = Checks.SUCCESS, []
		lines = [f"🍻 {character.name} carouses{f' ({cost} spent)' if cost else ''}."]
		lines += [f"👂 *{text}*" for text in heard] or ["Lots of laughter, but no news worth repeating."]
		return outcome, lines, {"heard" : len(heard), "cost" : cost}

	# ============================================================
	@staticmethod
	async def run(interaction: discord.Interaction, character_name: str, activity: str, language_name: str | None,
	              project_id: int | None, stat: str | None) -> None :
		character = CharacterTransactions().get(interaction.user.id, interaction.guild_id, character_name)
		problem = DowntimeFlow.problem(character)
		if problem :
			return await reply(interaction, problem)
		table = None
		if activity == Downtime.WORK :
			if not DowntimeFlow.economy(interaction.guild_id) :
				return await reply(interaction, "There is no currency to earn in free mode; try another activity.")
			outcome, lines, details, table = DowntimeFlow.work(character, stat)
		elif activity == Downtime.STUDY :
			language = LanguageTransactions().find(interaction.guild_id, language_name or "")
			if language is None or language.common :
				return await reply(interaction, "Pick a language to study (`language`).")
			from classes.language.LanguageFlow import LanguageFlow

			if LanguageFlow.known(character).get(language.id) == "fluent" :
				return await reply(interaction, f"{character.name} already speaks {language.name} fluently.")
			outcome, lines, details = DowntimeFlow.study(character, language)
		elif activity == Downtime.CRAFT :
			projects = EconomyTransactions().projects(character.id)
			project = next((entry for entry in projects if entry.id == project_id), projects[0] if projects else None)
			if project is None :
				return await reply(interaction, f"{character.name} has no crafting project; start one with /craft make.")
			outcome, lines, finished = Crafting.work(character, project, interaction.user.id)
			details = {"project_id" : project.id, "finished" : finished}
		else :
			outcome, lines, details = DowntimeFlow.carouse(character)
			if outcome is None :
				return await reply(interaction, lines[0])
		EconomyTransactions().add_downtime(character.id, DowntimeFlow.day(interaction.guild_id), activity, outcome,
		                                   details)
		embed = discord.Embed(title=f"🌙 Downtime: {activity.capitalize()}", description="\n".join(lines)[:4096],
		                      colour=DOWNTIME_COLOUR)
		embed.set_author(name=character.name)
		private = RoleplaySettings.toggle(interaction.guild_id, ConfigMapping.DOWNTIME_PRIVATE)
		await interaction.response.send_message(embed=embed, ephemeral=private)
		if table is not None and interaction.channel is not None :
			from classes.tables.TableFlow import TableFlow

			await TableFlow.post_roll(interaction.channel, table, interaction.user.id, character,
			                          f"✨ A great day for **{character.name}**:")
