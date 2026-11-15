"""The Reply and Report buttons under a delivered letter. They carry the letter's id, so they keep working after a
restart (registered with bot.add_dynamic_items in setup_hook)."""
import discord


class LetterButton(discord.ui.DynamicItem[discord.ui.Button], template=r"letter:(?P<letter>\d+):(?P<action>reply|report)") :

	def __init__(self, letter_id: int, action: str) :
		labels = {"reply" : ("Reply", "✍️", discord.ButtonStyle.primary),
		          "report" : ("Report", "🚩", discord.ButtonStyle.secondary)}
		label, emoji, style = labels[action]
		super().__init__(discord.ui.Button(label=label, emoji=emoji, style=style,
		                                   custom_id=f"letter:{letter_id}:{action}"))
		self.letter_id = letter_id
		self.action = action

	# ============================================================
	@classmethod
	async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match) :
		return cls(int(match["letter"]), match["action"])

	# ============================================================
	async def callback(self, interaction: discord.Interaction) :
		from classes.language.LetterFlow import LetterFlow

		if self.action == "reply" :
			await LetterFlow.start_reply(interaction, self.letter_id)
		else :
			await LetterFlow.report(interaction, self.letter_id)


# ============================================================
def letter_view(letter_id: int) -> discord.ui.View :
	view = discord.ui.View(timeout=None)
	view.add_item(LetterButton(letter_id, "reply"))
	view.add_item(LetterButton(letter_id, "report"))
	return view
