"""Finds or creates the one webhook the bot posts characters through in each channel, and remembers it."""
import asyncio
import logging

import discord

from classes.kernel.Queue import Singleton
from project.data import BOT_NAME

WEBHOOK_NAME = f"{BOT_NAME} characters"


class WebhookManager(metaclass=Singleton) :
	# {channel id: webhook}
	webhooks: dict[int, discord.Webhook] = {}
	# One lock per channel, so two posts arriving together do not both create a webhook.
	locks: dict[int, asyncio.Lock] = {}

	# ============================================================
	@staticmethod
	def parent(channel) -> discord.TextChannel | discord.ForumChannel :
		"""Webhooks belong to channels; a thread posts through its parent's webhook."""
		return channel.parent if isinstance(channel, discord.Thread) else channel

	# ============================================================
	async def get(self, bot: discord.Client, channel) -> discord.Webhook :
		"""The bot's webhook in the channel (or the thread's parent), creating it the first time.

		@raise discord.HTTPException: when the webhook cannot be read or created.
		"""
		parent = self.parent(channel)
		if parent.id in self.webhooks :
			return self.webhooks[parent.id]
		lock = self.locks.setdefault(parent.id, asyncio.Lock())
		async with lock :
			if parent.id in self.webhooks :
				return self.webhooks[parent.id]
			webhook = next((hook for hook in await parent.webhooks()
			                if hook.user is not None and hook.user.id == bot.user.id and hook.token), None)
			if webhook is None :
				webhook = await parent.create_webhook(name=WEBHOOK_NAME, reason="Posting as characters")
				logging.info(f"Created a character webhook in #{parent.name} ({parent.guild.name})")
			self.webhooks[parent.id] = webhook
			return webhook

	# ============================================================
	async def find(self, bot: discord.Client, channel, webhook_id: int) -> discord.Webhook | None :
		"""The bot's webhook with this id in the channel, for editing a message it sent."""
		webhook = await self.get(bot, channel)
		if webhook.id == webhook_id :
			return webhook
		hooks = await self.parent(channel).webhooks()
		return next((hook for hook in hooks if hook.id == webhook_id and hook.token), None)

	# ============================================================
	def forget(self, channel) -> None :
		"""Drops a remembered webhook, for example after someone deleted it."""
		self.webhooks.pop(self.parent(channel).id, None)
