import random

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from components.autocomplete import autocomplete
from components.combatController import CombatController
from components.databaseEvents import CombatSystem
from math import ceil


class Combat(commands.GroupCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="attack", description="attacks a target. Only fill in modifier if you have extra bonuses that aren't from stats.")
    @app_commands.autocomplete(character=autocomplete().character,
                               weapon=autocomplete().weapon)
    @app_commands.choices(hitchance_modifier=[Choice(name=str(x), value=x) for x in range(-10, 11)],
                          damage_modifier=[Choice(name=str(x), value=x) for x in range(-10, 11)],
                          advantage=[Choice(name="yes", value="yes"), Choice(name="no", value="no")])
    async def attack(self, interaction: discord.Interaction, title: str, character: str, weapon: str, enemy_ac: int, hitchance_modifier: Choice[int] = 0, damage_modifier: Choice[int] = 0, advantage: Choice[str] = "no"):
        print("attack")
        await interaction.response.defer()

        embed = discord.Embed(title=title)

        if isinstance(damage_modifier, Choice):
            damage_modifier = damage_modifier.value
        if isinstance(advantage, Choice):
            advantage = advantage.value
        if isinstance(hitchance_modifier, Choice):
            hitchance_modifier = hitchance_modifier.value
        chosen_character = CombatSystem().characters[interaction.user.id][character]
        chosen_weapon = CombatSystem().weapons[weapon]
        print(chosen_weapon)
        # hit dice
        final_hit, crit, hit_result, hit_mod = CombatController.calculate_hit(chosen_character, weapon, chosen_weapon, hitchance_modifier, advantage, enemy_ac)

        if final_hit is False:
            embed.description = f"**{character}** missed the attack"
            embed.set_footer(text=f"Hit roll: {crit} ({hit_result} + {hit_mod}) vs {enemy_ac}")
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
                extra_dice += ceil(chosen_character[chosen_weapon['modifier'].split(":")[1].lower()] / 2)
            if chosen_weapon['modifier'].lower().startswith("damage"):
                damage_mod += chosen_character[chosen_weapon['modifier'].split(":")[1].lower()]
        damage_mod += damage_modifier
        dice_number += extra_dice
        while dice_number > 0 and crit is False:
            dice_number -= 1
            result = random.randint(1, dice_size)
            results.append(result)
        total_damage = sum(results) + damage_mod
        if crit:
            total_damage = (dice_size * dice_number) + (damage_mod * 2)
        embed.description = f"**{character}** hit the attack for **{total_damage}** damage with **{weapon}**!"
        embed.set_footer(text=f"Debug: Hit roll: {final_hit} ({hit_result} + {hit_mod}) vs {enemy_ac}, Damage roll: {results} + {damage_mod} = {total_damage} (crit: {crit}) (advantage: {advantage})")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Combat(bot))
