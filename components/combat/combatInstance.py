from typing import List

import discord

from database.transactions.CombatInstanceTransactions import CombatInstanceTransactions


class CombatInstance():

	def __init__(self, channel: discord.TextChannel, new=False):
		self.channel = channel
		self.instance_controller = CombatInstanceTransactions()
		if not new:
			self.instance_data = self.instance_controller.getchannelinstance()
		else:
			self.instance_data = self.instance_controller.create()

	def get_instance_guid(self):
		return self.instance_data.guid

	def add_entity(self, entity_type= List['character', 'npc', 'enemy']):
		pass



