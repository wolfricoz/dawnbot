import discord
from discord import app_commands, Interaction
from discord.app_commands import Choice
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import Session

import components.database as db
from components.configMaker import guildconfiger
from components.databaseEvents import TransactionController


class config(commands.GroupCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='roles')
    @app_commands.choices(option=[
        Choice(name="add", value="add"),
        Choice(name="remove", value="remove"),
        Choice(name="update", value="update"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def roles(self, interaction: Interaction, option: Choice['str'], role: discord.Role, xp_required: int = 0):
        await interaction.response.defer(ephemeral=True)
        match option.value:
            case 'add':
                if TransactionController.add_role(role, interaction.guild, xp_required) is None:
                    await interaction.followup.send("Role already added")
                    return
                await interaction.followup.send(f"Added {role.mention} with required xp: {xp_required}")
            case 'remove':
                if TransactionController.remove_role(role) is None:
                    await interaction.followup.send("Role does not exist")
                    return
                await interaction.followup.send(f"removed {role.mention}")
            case 'update':

                await interaction.followup.send(f"Updated {role.mention} with required xp: {xp_required}")

    @app_commands.command(name='announcement')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def announcement(self, interaction: Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        await guildconfiger.edit_value(interaction.guild.id, channel.id, "announcement")
        await interaction.followup.send(f"Announcement channel set to {channel.mention}")

    @app_commands.command(name='xp_gain')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def xp_per_character(self, interaction: Interaction, amount_of_characters: int):
        await interaction.response.defer(ephemeral=True)
        await guildconfiger.edit_value(interaction.guild.id, amount_of_characters, "xp_gain")
        await interaction.followup.send(f"xp_per_character set to {amount_of_characters}")

    @app_commands.command(name='currency_gain')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def currency_per_character(self, interaction: Interaction, amount_of_characters: int):
        await interaction.response.defer(ephemeral=True)
        await guildconfiger.edit_value(interaction.guild.id, amount_of_characters, "currency_gain")
        await interaction.followup.send(f"currency_per_character set to {amount_of_characters}")

    @app_commands.command(name='currency_name')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def currency_name(self, interaction: Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        await guildconfiger.edit_value(interaction.guild.id, name, "currency_name")
        await interaction.followup.send(f"currency name set to {name}")

    @app_commands.command(name='channel')
    @app_commands.choices(option=[
        Choice(name="add", value="add"),
        Choice(name="remove", value="remove"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def channel(self, interaction: Interaction, option: Choice['str'], channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        key = "channels"
        match option.value:
            case 'add':
                await guildconfiger.addchannel(interaction.guild.id, interaction, channel, key)
            case 'remove':
                await guildconfiger.remchannel(interaction.guild.id, channel.id, key)
                await interaction.followup.send(f"channel removed from {key}")

    @app_commands.command()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(option=[Choice(name=x, value=x) for x in ["character", "timeline", "modlog"]])
    async def singlechannels(self, interaction: Interaction, option: Choice[str], channel: discord.TextChannel|discord.ForumChannel):
        await interaction.response.defer(ephemeral=True)
        key = option.value
        await guildconfiger.edit_value(interaction.guild.id, channel.id, key)
        await interaction.followup.send(f"{key} channel set to {channel.mention}")

    @app_commands.command(name='category')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def category(self, interaction: Interaction, category: discord.CategoryChannel):
        await interaction.response.defer(ephemeral=True)
        key = "channels"
        channels = []
        for channel in category.channels:
            if isinstance(channel, discord.TextChannel):
                await guildconfiger.addchannel(interaction.guild.id, interaction, channel, key)
                channels.append(channel.name)
            if isinstance(channel, discord.ForumChannel):
                await guildconfiger.addforum(interaction.guild.id, interaction, channel, key)
                channels.append(channel.name)
        await interaction.followup.send(f"Channels added: {', '.join(channels)}")

    @app_commands.command(name='forum')
    @app_commands.choices(option=[
        Choice(name="add", value="add"),
        Choice(name="remove", value="remove"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def forum(self, interaction: Interaction, option: Choice['str'], channel: discord.ForumChannel):
        await interaction.response.defer(ephemeral=True)
        key = "channels"
        match option.value:
            case 'add':
                await guildconfiger.addforum(interaction.guild.id, interaction, channel, key)
            case 'remove':
                await guildconfiger.remchannel(interaction.guild.id, channel.id, key)
                await interaction.followup.send(f"channel removed from {key}")


async def setup(bot):
    await bot.add_cog(config(bot))
