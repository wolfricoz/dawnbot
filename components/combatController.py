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
        armor_mod = CombatSystem().get_armor_by_id(chosen_character['armor'])['hitchance']
        hitmod = 0
        hitmod += chosen_weapon['hitmodifier']
        hitmod += hitchance_modifier
        hitmod += armor_mod if armor_mod is not None else 0
        hit_mod = ceil(chosen_character['perception'] / 2)
        if weapon.endswith('spell'):
            hit_mod = ceil(chosen_character['charisma'] / 2)
        while hit_dice_count > 0:
            hit_dice_count -= 1
            temp_result = random.randint(1, 20)
            if temp_result == 20:
                crit = True
            hit_results.append(temp_result)
        hit_result = max(hit_results)
        print(hit_mod)
        final_hit = hit_result + hit_mod
        if final_hit < enemy_ac:
            return False, None, final_hit, None
        return final_hit, crit, hit_result, hit_mod
