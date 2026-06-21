from typing import List, Literal

import discord

from database.transactions.CombatInstanceTransactions import CombatInstanceTransactions


class CombatInstance():

	def __init__(self, channel_id: int, new=False):
		# I dont think I'll actually use channel.. woops.

		self.channel_id = channel_id
		self.instance_controller = CombatInstanceTransactions()
		if not new:
			self.instance_data = self.instance_controller.get_channel_instance(self.channel_id)
		else:
			self.instance_data = self.instance_controller.create(channel_id=self.channel_id)

	def get_instance_guid(self):
		return self.instance_data.guid

	def add_entity(self, entity_type: Literal['character', 'npc', 'enemy']):
		pass



