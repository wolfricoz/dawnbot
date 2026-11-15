"""Game masters for the roleplay tools: staff (Manage Messages) and members with the server's GM role (GM_ROLE, set
with /config gmrole). The GM role is pinged when something needs a GM, such as an encounter on the road."""
import discord
from discord import app_commands

from classes.kernel.ConfigData import ConfigData
from resources.configs.ConfigMapping import ConfigMapping


# ============================================================
def role_id(guild_id: int) -> int | None :
	return ConfigData().get_int(guild_id, ConfigMapping.GM_ROLE)


# ============================================================
def is_gm(member) -> bool :
	"""Staff, or a member with the GM role."""
	permissions = getattr(member, "guild_permissions", None)
	if permissions is not None and permissions.manage_messages :
		return True
	guild = getattr(member, "guild", None)
	gm_role = role_id(guild.id) if guild is not None else None
	return gm_role is not None and any(role.id == gm_role for role in getattr(member, "roles", []))


# ============================================================
def gm_only() :
	"""A command check: staff or the GM role."""
	return app_commands.check(lambda interaction : is_gm(interaction.user))


# ============================================================
def mention(guild_id: int) -> tuple[str, discord.AllowedMentions] :
	"""The GM role's mention (or an empty string) and the allowed mentions that let it ping."""
	gm_role = role_id(guild_id)
	if gm_role is None :
		return "", discord.AllowedMentions.none()
	return f"<@&{gm_role}> ", discord.AllowedMentions(roles=[discord.Object(id=gm_role)], users=False,
	                                                   everyone=False)
