"""Scenes: a tracked roleplay in one channel or thread, with a pinned card, a post order and reminders.

`/scene start` opens a scene (one per channel or thread); players press **Join** with one character each. In `order`
mode a proxied post by the character whose turn it is passes the turn on, and a post out of turn moves its poster into
the current spot. `free` mode has no turns and reminds whoever everyone else has posted after. Reminders come after
SCENE_NUDGE_HOURS, skips after SCENE_SKIP_HOURS; `/scene away` pauses both for you. A fight started from the scene's
channel pauses it until the fight ends. `/scene end` writes the chronicle (CHRONICLE) and the timeline entry
(TIMELINE). See design/roleplay-tools.md, sections 2 and 3.
"""
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.scenes import Scenes
from classes.scenes.SceneFlow import SceneFlow
from database.transactions.CharacterTransactions import APPROVED, CharacterTransactions
from database.transactions.SceneTransactions import SceneTransactions
from views.combat.Pickers import reply

MODE_CHOICES = [Choice(name="Post order: players take turns", value=Scenes.ORDER),
                Choice(name="Free: no turns, reminders for whoever fell behind", value=Scenes.FREE)]
NO_SCENE = "There is no open scene here."


# ============================================================
async def member_characters(interaction: discord.Interaction, current: str) -> list[Choice[str]] :
	member = interaction.namespace.member
	if member is None :
		return []
	return [Choice(name=character.name[:100], value=character.name[:100])
	        for character in CharacterTransactions().get_all(member.id, interaction.guild_id, states=[APPROVED])
	        if current.lower() in character.name.lower()][:25]


@app_commands.guild_only()
class Scene(commands.GroupCog, name="Scene", group_name="scene") :
	"""Scenes with a post order, reminders and a chronicle when they end."""

	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _scene(self, interaction: discord.Interaction, host_only: bool = False) :
		scene = SceneFlow.scene_here(interaction.channel)
		if scene is None :
			await reply(interaction, NO_SCENE)
			return None
		if host_only and not SceneFlow.runs(scene, interaction.user) :
			await reply(interaction, "Only the scene's host (or staff) can do that.")
			return None
		return scene

	# ============================================================
	@app_commands.command(name="start", description="Starts a scene in this channel or thread")
	@app_commands.choices(mode=MODE_CHOICES)
	@app_commands.describe(title="The scene's title (default: the channel's name)", mode="Post order (default) or free")
	async def start(self, interaction: discord.Interaction, title: app_commands.Range[str, 1, 200] = None,
	                mode: Choice[str] = None) :
		"""
		Posts and pins the scene card here. You host the scene; players press **Join** to take part with one of their
		characters. The card shows the location and its weather, the in-world date, the participants and whose turn it
		is.
		"""
		await SceneFlow.start(interaction, title, mode.value if mode else Scenes.ORDER)

	# ============================================================
	@app_commands.command(name="end", description="Ends the scene here, writing its chronicle")
	@app_commands.describe(summary="A short summary of what happened", date="The in-world date it ended (default: the "
	                                                                          "calendar's)")
	async def end(self, interaction: discord.Interaction, summary: app_commands.Range[str, 1, 1500] = None,
	              date: app_commands.Range[str, 1, 100] = None) :
		"""
		Ends the scene: the card freezes, the chronicle is written in the chronicle channel (when set) and the timeline
		gets an entry (when set). Only the host or staff can end it.
		"""
		scene = await self._scene(interaction, host_only=True)
		if scene is None :
			return
		await interaction.response.defer(ephemeral=True, thinking=True)
		scene, chronicle = await SceneFlow.finish(interaction.client, scene.id, interaction.user.id, summary, date)
		where = f" The chronicle is in <#{chronicle.thread_id}>." if chronicle and chronicle.thread_id else ""
		await reply(interaction, f"🏁 **{scene.title}** has ended.{where}")

	# ============================================================
	@app_commands.command(name="join", description="Joins the scene here with one of your characters")
	async def join(self, interaction: discord.Interaction) :
		"""
		Joins the scene in this channel; the same as the card's **Join** button.
		"""
		scene = await self._scene(interaction)
		if scene is not None :
			await SceneFlow.start_join(interaction, scene.id)

	# ============================================================
	@app_commands.command(name="leave", description="Leaves the scene here")
	async def leave(self, interaction: discord.Interaction) :
		"""
		Leaves the scene in this channel; the same as the card's **Leave** button.
		"""
		scene = await self._scene(interaction)
		if scene is not None :
			await SceneFlow.leave(interaction, scene.id, interaction.user.id)

	# ============================================================
	@app_commands.command(name="pass", description="Passes your turn in the scene here")
	async def pass_turn(self, interaction: discord.Interaction) :
		"""
		Passes your turn to the next participant. The host or staff can pass anyone's turn.
		"""
		scene = await self._scene(interaction)
		if scene is not None :
			await SceneFlow.pass_turn(interaction, scene.id)

	# ============================================================
	@app_commands.command(name="away", description="Pauses scene reminders and skips for you")
	@app_commands.describe(days="For how many days (default: until /scene back)")
	async def away(self, interaction: discord.Interaction, days: app_commands.Range[int, 1, 365] = None) :
		"""
		Marks you as away in every scene: no reminders, and your turns are passed over without counting as skips,
		until the date or until you use /scene back.
		"""
		until = datetime.now(timezone.utc) + timedelta(days=days or 3650)
		SceneTransactions().set_away(interaction.user.id, until)
		text = f"until <t:{int(until.timestamp())}:D>" if days else "until you use /scene back"
		await reply(interaction, f"💤 You're away {text}.")

	# ============================================================
	@app_commands.command(name="back", description="Ends your away time in scenes")
	async def back(self, interaction: discord.Interaction) :
		"""
		Ends your away time; reminders and turns work for you again.
		"""
		SceneTransactions().set_away(interaction.user.id, None)
		await reply(interaction, "Welcome back!")

	# ============================================================
	@app_commands.command(name="add", description="Adds a member's character to the scene here (host)")
	@app_commands.autocomplete(character=member_characters)
	async def add(self, interaction: discord.Interaction, member: discord.Member, character: str) :
		"""
		Adds another member's approved character to the scene. Host or staff.
		"""
		scene = await self._scene(interaction, host_only=True)
		if scene is None :
			return
		record = CharacterTransactions().get(member.id, interaction.guild_id, character)
		if record is None or record.state != APPROVED :
			return await reply(interaction, f"{member.display_name} has no approved character called {character}.")
		await SceneFlow.join(interaction, scene.id, record, added_by_host=True)

	# ============================================================
	@app_commands.command(name="remove", description="Removes a member from the scene here (host)")
	async def remove(self, interaction: discord.Interaction, member: discord.Member) :
		"""
		Removes a member's character from the scene. Host or staff.
		"""
		scene = await self._scene(interaction, host_only=True)
		if scene is not None :
			await SceneFlow.leave(interaction, scene.id, member.id, removed=True)

	# ============================================================
	@app_commands.command(name="move", description="Moves a member in the post order (host)")
	@app_commands.describe(member="Who to move", position="Their new place, 1 being first")
	async def move(self, interaction: discord.Interaction, member: discord.Member,
	               position: app_commands.Range[int, 1, 100]) :
		"""
		Moves a participant to another place in the post order. Host or staff.
		"""
		scene = await self._scene(interaction, host_only=True)
		if scene is not None :
			await SceneFlow.move(interaction, scene, member.id, position)

	# ============================================================
	@app_commands.command(name="host", description="Hands the scene's host role to another member")
	async def host(self, interaction: discord.Interaction, member: discord.Member) :
		"""
		Makes another member the scene's host. Host or staff.
		"""
		scene = await self._scene(interaction, host_only=True)
		if scene is None :
			return
		SceneTransactions().update(scene.id, host_uid=member.id)
		await SceneFlow.refresh(interaction.client, scene.id)
		await reply(interaction, f"{member.display_name} hosts the scene now.")

	# ============================================================
	@app_commands.command(name="pause", description="Pauses the scene here: no reminders or skips (host)")
	async def pause(self, interaction: discord.Interaction) :
		"""
		Pauses the scene. Host or staff.
		"""
		scene = await self._scene(interaction, host_only=True)
		if scene is None :
			return
		SceneTransactions().update(scene.id, state=Scenes.PAUSED)
		await SceneFlow.refresh(interaction.client, scene.id)
		await reply(interaction, "⏸️ Scene paused.")

	# ============================================================
	@app_commands.command(name="resume", description="Resumes the paused scene here (host)")
	async def resume(self, interaction: discord.Interaction) :
		"""
		Resumes a paused scene; the current turn starts over. Host or staff.
		"""
		scene = await self._scene(interaction, host_only=True)
		if scene is None :
			return
		SceneTransactions().update(scene.id, state=Scenes.OPEN, paused_by_fight=None,
		                           turn_started_at=datetime.now(timezone.utc))
		await SceneFlow.refresh(interaction.client, scene.id)
		await reply(interaction, "▶️ Scene resumed.")

	# ============================================================
	@app_commands.command(name="card", description="Posts the scene card again at the bottom")
	async def card(self, interaction: discord.Interaction) :
		"""
		Posts the scene's card again (and pins it), for when it scrolled far up.
		"""
		from views.scenes.SceneButtons import scene_view

		scene = await self._scene(interaction)
		if scene is None :
			return
		await interaction.response.send_message(embed=SceneFlow.embed(scene), view=scene_view(scene))
		message = await interaction.original_response()
		SceneTransactions().update(scene.id, card_message_id=message.id)
		try :
			await message.pin(reason=f"Scene card: {scene.title}")
		except discord.HTTPException :
			pass


async def setup(bot) :
	await bot.add_cog(Scene(bot))
