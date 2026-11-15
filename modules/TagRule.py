"""Restrictions through forum tags. Link a tag in the species forum to a requirement, and every species whose
post has that tag follows it. Retag a post to change who may pick it.
"""
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from classes.characters.Access import EVENT, KINDS, LEVEL, ROLE, STAFF_ONLY
from database.transactions.TagRuleTransactions import TagRuleTransactions

KIND_HELP = {ROLE : "needs a role", LEVEL : "needs a server level", STAFF_ONLY : "only staff give it out",
             EVENT : "hidden; only staff give it out"}


@app_commands.guild_only()
class TagRule(commands.GroupCog, name="TagRule", group_name="tagrule") :


	def __init__(self, bot: commands.Bot) :
		self.bot = bot

	# ============================================================
	async def _tags(self, interaction: discord.Interaction, current: str) -> list[Choice[str]] :
		"""The tags of the forum chosen in the same command."""
		chosen = interaction.namespace.forum
		forum = interaction.guild.get_channel(chosen.id) if chosen is not None else None
		if not isinstance(forum, discord.ForumChannel) :
			return []
		return [Choice(name=tag.name, value=str(tag.id)) for tag in forum.available_tags
		        if current.lower() in tag.name.lower()][:25]

	# ============================================================
	@staticmethod
	def _tag(forum: discord.ForumChannel, tag: str) -> discord.ForumTag | None :
		return next((item for item in forum.available_tags if str(item.id) == tag or item.name.lower() == tag.lower()),
		            None)

	# ============================================================
	@app_commands.command(name="add")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(tag=_tags)
	@app_commands.choices(kind=[Choice(name=f"{kind}: {KIND_HELP[kind]}", value=kind) for kind in KINDS])
	async def add(self, interaction: discord.Interaction, forum: discord.ForumChannel, tag: str, kind: Choice[str],
	              role: discord.Role = None, level: app_commands.Range[int, 1, 1000] = None) :
		"""
		Links a forum tag to a requirement. Kinds: role (members need `role`), level (members need server `level`:
		the number of level roles they have reached), staff_only (only staff can give it out) and event (hidden from
		members; only staff can give it out). A tag can have one rule of each kind.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		forum_tag = self._tag(forum, tag)
		if forum_tag is None :
			return await interaction.followup.send(f"{forum.mention} has no tag called {tag}.")
		value = None
		if kind.value == ROLE :
			if role is None :
				return await interaction.followup.send("Pick the role members need in `role`.")
			value = role.id
		elif kind.value == LEVEL :
			if level is None :
				return await interaction.followup.send("Set the server level members need in `level`.")
			value = level
		TagRuleTransactions().set(interaction.guild_id, forum.id, forum_tag.id, kind.value, value)
		await interaction.followup.send(f"Posts in {forum.mention} tagged **{forum_tag.name}** now follow: "
		                                f"{self.describe(kind.value, value)}.")

	# ============================================================
	@app_commands.command(name="remove")
	@app_commands.checks.has_permissions(manage_guild=True)
	@app_commands.autocomplete(tag=_tags)
	@app_commands.choices(kind=[Choice(name=kind, value=kind) for kind in KINDS])
	async def remove(self, interaction: discord.Interaction, forum: discord.ForumChannel, tag: str,
	                 kind: Choice[str] = None) :
		"""
		Removes a tag's rule of one kind, or all its rules when you leave `kind` out.

		**Permissions:**
		- `Manage Server`
		"""
		await interaction.response.defer(ephemeral=True)
		forum_tag = self._tag(forum, tag)
		if forum_tag is None :
			return await interaction.followup.send(f"{forum.mention} has no tag called {tag}.")
		removed = TagRuleTransactions().remove(forum_tag.id, kind.value if kind else None)
		await interaction.followup.send(f"Removed {removed} rule{'s' if removed != 1 else ''} from {forum_tag.name}.")

	# ============================================================
	@app_commands.command(name="list")
	async def list_rules(self, interaction: discord.Interaction) :
		"""
		Lists every tag rule on the server.
		"""
		await interaction.response.defer(ephemeral=True)
		lines = []
		for rule in TagRuleTransactions().get_all(interaction.guild_id) :
			forum = interaction.guild.get_channel(rule.forum_channel_id)
			tag = forum.get_tag(rule.tag_id) if isinstance(forum, discord.ForumChannel) else None
			lines.append(f"<#{rule.forum_channel_id}> **{tag.name if tag else 'a deleted tag'}**: "
			             f"{self.describe(rule.kind, rule.value)}")
		await interaction.followup.send("\n".join(lines)[:2000] if lines else "There are no tag rules yet.",
		                                allowed_mentions=discord.AllowedMentions.none())

	# ============================================================
	@staticmethod
	def describe(kind: str, value: int | None) -> str :
		return {ROLE : f"needs the <@&{value}> role", LEVEL : f"needs server level {value}",
		        STAFF_ONLY : "only staff give it out", EVENT : "hidden; only staff give it out"}[kind]


async def setup(bot) :
	await bot.add_cog(TagRule(bot))
