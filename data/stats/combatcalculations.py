from math import floor


class CombatCalculations():
	HP_PER_POINT: float = 2.5
	BASE_MODIFIER: float = 0
	BONUS_PER_POINT: float = 0.5

	def __init__(self, overrides=None):
		self.base_hp: float = 100
		if overrides is None :
			overrides = {}
		for key, value in overrides.items() :
			setattr(self, key, value)

	def calculate_hp(self, points) -> int:
		"""
		Calcutes HP and rounds down to the nearest integer
		:param points:
		:return:
		"""
		return floor(self.base_hp + (self.HP_PER_POINT * points))

	def calculate_stat_modifier(self, points):
		return floor(self.BASE_MODIFIER + (self.BONUS_PER_POINT * points))
