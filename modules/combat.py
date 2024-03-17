import random

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from components.databaseEvents import CombatSystem


class Combat(commands.GroupCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str):
        data = []
        armors = CombatSystem().weapons
        for x in armors.keys():
            if current.lower() in x.lower():
                data.append(app_commands.Choice(name=x.lower(), value=x.lower()))
        return data

    async def character_autocomplete(self, interaction: discord.Interaction, current: str):
        data = []
        characters = CombatSystem().characters[interaction.user.id]
        for x in characters.keys():
            if current.lower() in x.lower():
                data.append(app_commands.Choice(name=x.lower(), value=x.lower()))
        return data

    @app_commands.command(name="attack", description="attacks a target")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.autocomplete(character=character_autocomplete,
                               weapon=weapon_autocomplete)
    @app_commands.choices(damage_modifier=[Choice(name=str(x), value=x) for x in range(-10, 11)],
                          advantage=[Choice(name="yes", value="yes"), Choice(name="no", value="no")])
    async def attack(self, interaction: discord.Interaction, title: str, character: str, weapon: str, enemy_ac: int, damage_modifier: Choice[int] = 0, advantage: Choice[str] = "no"):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(title=title)

        if isinstance(damage_modifier, Choice):
            damage_modifier = damage_modifier.value
        if isinstance(advantage, Choice):
            advantage = advantage.value
        chosen_character = CombatSystem().characters[interaction.user.id][character]
        chosen_weapon = CombatSystem().weapons[weapon]
        # hit dice
        crit = False
        hit_dice_count = 2 if advantage.lower() == "yes" else 1
        hit_results = []
        hit_mod = chosen_character['perception'] + chosen_weapon['hitmodifier']
        while hit_dice_count > 0:
            hit_dice_count -= 1
            temp_result = random.randint(1, 20)
            if temp_result == 20:
                crit = True
            hit_results.append(temp_result + hit_mod)
        hit_result = max(hit_results)
        if hit_result < enemy_ac:
            embed.description = f"**{character}** missed the attack"
            embed.set_footer(text=f"Hit roll: {hit_result} vs {enemy_ac}")
            await interaction.followup.send(embed=embed)
            return
        # damage dice
        extra_dice = 0
        damage_mod = 0
        dice_string: str = chosen_weapon['dice']
        dice_array = dice_string.split("d")
        dice_number = int(dice_array[0])
        dice_size = int(dice_array[1])
        results = []
        if chosen_weapon['modifier'] is not None:
            if chosen_weapon['modifier'].lower().startswith("dice"):
                extra_dice += round(chosen_character[chosen_weapon['modifier'].split(":")[1].lower()] / 2)
            if chosen_weapon['modifier'].lower().startswith("damage"):
                damage_mod += chosen_character[chosen_weapon['modifier'].split(":")[1].lower()]
        damage_mod += damage_modifier
        while dice_number > 0 and crit is False:
            dice_number -= 1
            result = random.randint(1, dice_size)
            results.append(result)
        total_damage = sum(results) + damage_mod
        if crit:
           total_damage = (dice_size * dice_number) + (damage_mod * 2)
        embed.description = f"**{character}** hit the attack for **{total_damage}** damage"
        embed.set_footer(text=f"Debug: Hit roll: {hit_result} + {hit_mod} vs {enemy_ac}, Damage roll: {results} + {damage_mod} = {total_damage} (crit: {crit}) (advantage: {advantage})")
        await interaction.followup.send(embed=embed)
async def setup(bot):
    await bot.add_cog(Combat(bot))
