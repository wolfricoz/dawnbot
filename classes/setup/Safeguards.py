"""Checks that guard the destructive server-setup commands."""
import discord
from discord_py_utilities.permissions import check_missing_guild_permissions

# Templates rebuild a whole server, so they only run on (nearly) empty servers.
MAX_MEMBERS = 10
# What the bot needs to archive channels and build a template.
SETUP_PERMISSIONS = ["manage_channels", "manage_roles", "view_channel"]


# ============================================================
def human_member_count(guild: discord.Guild) -> int :
	"""Members that are not bots. When the member cache is incomplete this errs high, never low."""
	cached_humans = sum(1 for member in guild.members if not member.bot)
	cached_bots = len(guild.members) - cached_humans
	if guild.member_count is not None :
		return max(cached_humans, guild.member_count - cached_bots)
	return cached_humans


# ============================================================
def owner_error(interaction: discord.Interaction) -> str | None :
	if interaction.user.id != interaction.guild.owner_id :
		return "Only the owner of the server can run this command."
	return None


# ============================================================
def template_error(interaction: discord.Interaction) -> str | None :
	"""Why a template may not be applied here, or None when it may."""
	if error := owner_error(interaction) :
		return error
	humans = human_member_count(interaction.guild)
	if humans > MAX_MEMBERS :
		return (f"Templates can only be applied to servers with at most {MAX_MEMBERS} members (bots not counted); "
		        f"this server has {humans}.")
	return None


# ============================================================
def missing_permissions(guild: discord.Guild) -> list[str] :
	return check_missing_guild_permissions(guild, SETUP_PERMISSIONS) or []
