import logging

import discord

from components.combat.combatInstance import CombatInstance
from components.helpers.singleton import Singleton
from database.transactions.CombatInstanceTransactions import CombatInstanceTransactions


class InstanceManager(metaclass=Singleton):
	"""

	"""
	def __init__(self):
		self.instances = {} # channel:instance
		self.load_active_instances()

	def load_active_instances(self):
		instances = CombatInstanceTransactions().get_all(active_only=True)
		logging.info(f"[Instance Manager] Found {len(instances)} active instances")
		for instance in instances:
			if not instance.channel_id:
				continue
			self.instances[instance.channel_id] = instance
		logging.info(f"[Instance Manager] Loaded {len(instances)} active instances")


	def create(self, channel: discord.TextChannel):
		self.instances[channel.id] = CombatInstance(channel, new=True)

	def load(self, channel: discord.TextChannel):
		return self.instances[channel.id]