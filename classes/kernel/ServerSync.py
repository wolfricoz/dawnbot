import discord

from database.transactions.ServerTransactions import ServerTransactions


# ============================================================
def sync_server(guild: discord.Guild) :
	"""Adds or refreshes one guild in the servers table. Config rows reference it, so call this before writing config."""
	owner_name = guild.owner.name if guild.owner else "Unknown"
	owner_id = guild.owner_id
	if not ServerTransactions().exists(guild.id) :
		ServerTransactions().add(guild.id, owner_name, guild.name, guild.member_count or 0, "", active=True,
		                         owner_id=owner_id)
		return
	ServerTransactions().update(guild.id, owner_name, guild.name, guild.member_count or 0, "", delete=False,
	                            owner_id=owner_id, active=True)
