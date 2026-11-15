"""The buttons under a scene's card (Join, Pass, Leave) and under a chronicle (Add summary). They carry the record's
id, so they keep working after a restart (registered with bot.add_dynamic_items in setup_hook)."""
import discord

from database.database import Scenes

JOIN = "join"
PASS = "pass"
LEAVE = "leave"


class SceneButton(discord.ui.DynamicItem[discord.ui.Button], template=r"scene:(?P<scene>\d+):(?P<action>join|pass|leave)") :

	def __init__(self, scene_id: int, action: str, label: str | None = None,
	             style: discord.ButtonStyle = discord.ButtonStyle.secondary, emoji: str | None = None) :
		super().__init__(discord.ui.Button(label=label or action.capitalize(), style=style, emoji=emoji,
		                                   custom_id=f"scene:{scene_id}:{action}"))
		self.scene_id = scene_id
		self.action = action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(int(match["scene"]), match["action"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		from classes.scenes.SceneFlow import SceneFlow

		if self.action == JOIN :
			await SceneFlow.start_join(interaction, self.scene_id)
		elif self.action == PASS :
			await SceneFlow.pass_turn(interaction, self.scene_id)
		else :
			await SceneFlow.leave(interaction, self.scene_id, interaction.user.id)


# ============================================================
def scene_view(scene: Scenes) -> discord.ui.View | None :
	if scene.state == "ended" :
		return None
	view = discord.ui.View(timeout=None)
	view.add_item(SceneButton(scene.id, JOIN, "Join", discord.ButtonStyle.success, "🎭"))
	if scene.mode == "order" :
		view.add_item(SceneButton(scene.id, PASS, "Pass", emoji="⏭️"))
	view.add_item(SceneButton(scene.id, LEAVE, "Leave", discord.ButtonStyle.danger))
	return view


class ChronicleButton(discord.ui.DynamicItem[discord.ui.Button], template=r"chronicle:(?P<chronicle>\d+):summary") :

	def __init__(self, chronicle_id: int) :
		super().__init__(discord.ui.Button(label="Add summary", style=discord.ButtonStyle.secondary, emoji="✍️",
		                                   custom_id=f"chronicle:{chronicle_id}:summary"))
		self.chronicle_id = chronicle_id

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(int(match["chronicle"]))

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		from classes.scenes.ChronicleSummary import ask_summary

		await ask_summary(interaction, self.chronicle_id)


# ============================================================
def chronicle_view(chronicle_id: int) -> discord.ui.View :
	view = discord.ui.View(timeout=None)
	view.add_item(ChronicleButton(chronicle_id))
	return view
