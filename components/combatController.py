import logging
import random
from abc import ABC, abstractmethod
from math import ceil

from components.databaseEvents import CombatSystem


class CombatController(ABC):

    @staticmethod
    @abstractmethod
    def calculate_hit(chosen_character, weapon, chosen_weapon, hitchance_modifier, advantage, enemy_ac):
        """
        Calculate the hit chance
        :param weapon:
        :param chosen_character:
        :param chosen_weapon:
        :param hitchance_modifier:
        :param advantage:
        :param enemy_ac:
        :return:
        """
        crit = False
        hit_dice_count = 2 if advantage.lower() == "yes" else 1
        hit_results = []
        # This needs to be fixed, sometimes it doesn't get the armor. I need to check if the armor is None and if it is, set it to 0
        print(chosen_character['armor'])
        armor_mod = CombatSystem().get_armor_by_id(chosen_character['armor'])
        print(armor_mod)
        hitmod = 0
        hitmod += chosen_weapon['hitmodifier']
        hitmod += hitchance_modifier
        hitmod += armor_mod['hitchance'] if armor_mod is not None else 0
        print("Armor Success" if armor_mod is not None else "Armor fail")
        print(hitmod)
        hitmod += ceil(chosen_character['perception'] / 2)
        if weapon.endswith('spell'):
            hitmod += ceil(chosen_character['charisma'] / 2)
        while hit_dice_count > 0:
            hit_dice_count -= 1
            temp_result = random.randint(1, 20)
            if temp_result == 20:
                crit = True
            hit_results.append(temp_result)
        hit_result = max(hit_results)
        print(hitmod)
        final_hit = hit_result + hitmod
        if final_hit < enemy_ac:
            return False, final_hit, hit_result,  hitmod
        return final_hit, crit, hit_result, hitmod
