"""The buttons under a job on the job board. They carry the job's id, so they keep working after a restart
(registered with bot.add_dynamic_items in setup_hook)."""
import discord

from database.database import Jobs

ACTIONS = {"claim" : ("Claim", "🙋", discord.ButtonStyle.success),
           "withdraw" : ("Withdraw", "↩️", discord.ButtonStyle.secondary),
           "complete" : ("Complete", "🏁", discord.ButtonStyle.primary),
           "scene" : ("Start scene", "🎭", discord.ButtonStyle.secondary)}


class JobButton(discord.ui.DynamicItem[discord.ui.Button],
                template=r"job:(?P<job>\d+):(?P<action>claim|withdraw|complete|scene)") :

	def __init__(self, job_id: int, action: str) :
		label, emoji, style = ACTIONS[action]
		super().__init__(discord.ui.Button(label=label, emoji=emoji, style=style, custom_id=f"job:{job_id}:{action}"))
		self.job_id = job_id
		self.action = action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(int(match["job"]), match["action"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		from classes.economy.JobFlow import JobFlow

		handlers = {"claim" : JobFlow.start_claim, "withdraw" : JobFlow.withdraw, "complete" : JobFlow.start_complete,
		            "scene" : JobFlow.start_scene}
		await handlers[self.action](interaction, self.job_id)


# ============================================================
def job_view(job: Jobs) -> discord.ui.View | None :
	if job.state not in ("open", "taken") :
		return None
	view = discord.ui.View(timeout=None)
	for action in ACTIONS :
		view.add_item(JobButton(job.id, action))
	return view
