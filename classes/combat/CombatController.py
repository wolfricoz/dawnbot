import random
from math import ceil


class CombatController :

	# ============================================================
	@staticmethod
	def calculate_hit(chosen_character: dict, weapon: str, chosen_weapon: dict, hitchance_modifier: int,
	                  advantage: str, enemy_ac: int) :
		"""
		Rolls to hit. chosen_character is a combatant from CombatCache.combatant: its stats and the armor it fights in.
		:return: on a miss (False, final_hit, hit_result, hitmod); on a hit (final_hit, crit, hit_result, hitmod)
		"""
		crit = False
		hit_dice_count = 2 if advantage.lower() == "yes" else 1
		hit_results = []
		armor_mod = chosen_character['armor']
		hitmod = 0
		hitmod += chosen_weapon['hitmodifier'] or 0
		hitmod += hitchance_modifier
		hitmod += armor_mod['hitchance'] or 0
		if weapon.endswith('spell') :
			hitmod += ceil(chosen_character['charisma'] / 2)
		else :
			hitmod += ceil(chosen_character['perception'] / 2)
		while hit_dice_count > 0 :
			hit_dice_count -= 1
			temp_result = random.randint(1, 20)
			if temp_result == 20 :
				crit = True
			hit_results.append(temp_result)
		hit_result = max(hit_results)
		final_hit = hit_result + hitmod
		if final_hit < enemy_ac :
			return False, final_hit, hit_result, hitmod
		return final_hit, crit, hit_result, hitmod
