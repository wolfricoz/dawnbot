"""The Add summary button under a chronicle: a participant (or staff) writes what happened, posted in the chronicle's
thread."""
import discord

from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.SceneTransactions import SceneTransactions
from views.combat.Pickers import Field, Form, reply


# ============================================================
def may_summarise(chronicle_id: int, member) -> bool :
	from classes.kernel.GMRole import is_gm

	if is_gm(member) :
		return True
	for entry in SceneTransactions().chronicle_characters(chronicle_id) :
		character = CharacterTransactions().get_by_id(entry.character_id)
		if character is not None and character.uid == member.id :
			return True
	return False


# ============================================================
async def ask_summary(interaction: discord.Interaction, chronicle_id: int) -> None :
	record = SceneTransactions().chronicle(chronicle_id)
	if record is None :
		return await reply(interaction, "That chronicle no longer exists.")
	if not may_summarise(chronicle_id, interaction.user) :
		return await reply(interaction, "Only the players in this chronicle (or staff) can add its summary.")

	async def written(form_interaction: discord.Interaction, fields: list[str]) :
		text = fields[0].strip()
		SceneTransactions().update_chronicle(chronicle_id, summary=text)
		if record.scene_id :
			SceneTransactions().update(record.scene_id, summary=text)
		target = form_interaction.client.get_channel(record.thread_id) if record.thread_id else form_interaction.channel
		try :
			target = target or await form_interaction.client.fetch_channel(record.thread_id)
			await target.send(f"✍️ **Summary** by {form_interaction.user.mention}:\n{text}"[:2000],
			                  allowed_mentions=discord.AllowedMentions.none())
		except discord.HTTPException :
			pass
		await reply(form_interaction, "Summary added.")

	await interaction.response.send_modal(Form(f"Summary: {record.title}"[:45], [
		Field("What happened?", "A short summary of the scene", record.summary, long=True, max_length=1500)], written))
