import discord
from discord.app_commands import Choice
from discord.ext import commands
from discord import app_commands, Interaction
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from components.configmaker import guildconfiger
import components.database as db
session = Session(bind=db.engine)


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
                if session.scalar(select(db.Levels).where(db.Levels.role_id == role.id)):
                    await interaction.followup.send("Role already added")
                    return
                level = db.Levels(guildid=interaction.guild.id, role_id=role.id, xp_required=xp_required)
                session.add(level)
                session.commit()
                await interaction.followup.send(f"Added {role.mention} with required xp: {xp_required}")
            case 'remove':
                if session.scalar(select(db.Levels).where(db.Levels.role_id == role.id)) is None:
                    await interaction.followup.send("Role does not exist")
                    return
                level = session.scalar(select(db.Levels).where(db.Levels.role_id == role.id))
                session.delete(level)
                session.commit()
                await interaction.followup.send(f"removed {role.mention}")
            case 'update':
                if session.scalar(select(db.Levels).where(db.Levels.role_id == role.id)) is None:
                    await interaction.followup.send("Role does not exist")
                    return
                level = session.scalar(select(db.Levels).where(db.Levels.role_id == role.id))
                level.xp_required = xp_required
                session.commit()
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
                await guildconfiger.addchannel(interaction.guild.id, interaction, channel, key, session)
            case 'remove':
                await guildconfiger.remchannel(interaction.guild.id, channel.id, key)
                await interaction.followup.send(f"channel removed from {key}")

    @app_commands.command(name='category')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def category(self, interaction: Interaction, category: discord.CategoryChannel):
        await interaction.response.defer(ephemeral=True)
        key = "channels"
        channels = []
        for channel in category.channels:
            await guildconfiger.addchannel(interaction.guild.id, interaction, channel, key, session)
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
                await guildconfiger.addchannel(interaction.guild.id, interaction, channel, key, session)
            case 'remove':
                await guildconfiger.addchannel(interaction.guild.id, interaction, channel, key, session)
                await interaction.followup.send(f"channel removed from {key}")



async def setup(bot):
    await bot.add_cog(config(bot))