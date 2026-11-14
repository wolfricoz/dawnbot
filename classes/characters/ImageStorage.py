"""Keeps images, such as character avatars, as messages in the bot's storage channel (STORAGE_CHANNEL in .env).

Discord's attachment links are signed and stop working after about a day. The storage message itself stays, so a
fresh link is read from it whenever the cached one is close to expiring.
"""
import io
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import discord

from data.env.loader import env
from database.transactions.StoredImageTransactions import StoredImageTransactions

ALLOWED_TYPES = {"image/png" : "png", "image/jpeg" : "jpg", "image/webp" : "webp", "image/gif" : "gif"}
MAX_BYTES = 8 * 1024 * 1024
# A link is refreshed when it expires within this time.
REFRESH_MARGIN = timedelta(minutes=30)


class ImageError(Exception) :
	"""An image was refused or could not be stored; the message can be shown to the user."""


class ImageStorage :

	# ============================================================
	@staticmethod
	def configured() -> bool :
		return str(env("STORAGE_CHANNEL", "")).isnumeric()

	# ============================================================
	@staticmethod
	def check(content_type: str | None, size: int) -> str | None :
		"""Why an upload is refused, or None when it is fine."""
		if (content_type or "").split(";")[0].strip().lower() not in ALLOWED_TYPES :
			return "That file is not an image I can use. Please send a PNG, JPG, WEBP or GIF."
		if size > MAX_BYTES :
			return f"That image is too large. The limit is {MAX_BYTES // (1024 * 1024)} MB."
		return None

	# ============================================================
	@staticmethod
	def expiry(url: str) -> datetime | None :
		"""When a Discord attachment link stops working, read from its ex parameter (hex seconds)."""
		try :
			value = parse_qs(urlparse(url).query).get("ex", [None])[0]
			return datetime.fromtimestamp(int(value, 16), tz=timezone.utc) if value else None
		except (ValueError, OverflowError, OSError) :
			return None

	# ============================================================
	@staticmethod
	def is_fresh(expires_at: datetime | None, now: datetime | None = None) -> bool :
		"""False when the link has expired, expires soon, or its expiry is unknown."""
		if expires_at is None :
			return False
		if expires_at.tzinfo is None :
			expires_at = expires_at.replace(tzinfo=timezone.utc)
		return expires_at - (now or datetime.now(timezone.utc)) > REFRESH_MARGIN

	# ============================================================
	@staticmethod
	async def _channel(bot: discord.Client) -> discord.abc.Messageable :
		if not ImageStorage.configured() :
			raise ImageError("Image storage is not set up for this bot yet.")
		channel_id = int(env("STORAGE_CHANNEL"))
		channel = bot.get_channel(channel_id)
		if channel is None :
			try :
				channel = await bot.fetch_channel(channel_id)
			except discord.HTTPException as e :
				logging.error(f"Storage channel {channel_id} could not be reached: {e}")
				raise ImageError("I could not reach my image storage. Please try again later.")
		return channel

	# ============================================================
	@staticmethod
	async def store(bot: discord.Client, attachment: discord.Attachment) -> int :
		"""Copies an uploaded image into the storage channel.

		@return: the id of the stored image.
		@raise ImageError: when the file is refused or the upload fails.
		"""
		problem = ImageStorage.check(attachment.content_type, attachment.size)
		if problem :
			raise ImageError(problem)
		channel = await ImageStorage._channel(bot)
		extension = ALLOWED_TYPES[attachment.content_type.split(";")[0].strip().lower()]
		try :
			data = await attachment.read()
			message = await channel.send(file=discord.File(io.BytesIO(data), filename=f"image.{extension}"))
		except discord.HTTPException as e :
			logging.error(f"Storing an image failed: {e}")
			raise ImageError("I could not save that image. Please try again later.")
		url = message.attachments[0].url
		return StoredImageTransactions().add(channel.id, message.id, url, ImageStorage.expiry(url)).id

	# ============================================================
	@staticmethod
	async def _message(bot: discord.Client, image) -> discord.Message | None :
		channel = bot.get_channel(image.storage_channel_id)
		try :
			if channel is None :
				channel = await bot.fetch_channel(image.storage_channel_id)
			return await channel.fetch_message(image.storage_message_id)
		except discord.HTTPException as e :
			logging.warning(f"Stored image {image.id} could not be fetched: {e}")
			return None

	# ============================================================
	@staticmethod
	async def url(bot: discord.Client, image_id: int | None) -> str | None :
		"""A link to the image that still works, or None when the image is gone."""
		if image_id is None :
			return None
		image = StoredImageTransactions().get(image_id)
		if image is None :
			return None
		if ImageStorage.is_fresh(image.expires_at) :
			return image.url
		message = await ImageStorage._message(bot, image)
		if message is None or not message.attachments :
			return None
		url = message.attachments[0].url
		StoredImageTransactions().update_url(image.id, url, ImageStorage.expiry(url))
		return url

	# ============================================================
	@staticmethod
	async def file(bot: discord.Client, image_id: int | None) -> discord.File | None :
		"""The image itself, ready to attach to a message, or None when it is gone."""
		if image_id is None :
			return None
		image = StoredImageTransactions().get(image_id)
		if image is None :
			return None
		message = await ImageStorage._message(bot, image)
		if message is None or not message.attachments :
			return None
		try :
			return await message.attachments[0].to_file()
		except discord.HTTPException as e :
			logging.warning(f"Stored image {image.id} could not be downloaded: {e}")
			return None

	# ============================================================
	@staticmethod
	async def copy(bot: discord.Client, image_id: int | None) -> int | None :
		"""Stores a second copy of an image, so two characters never share one (each can change or lose its own).
		Returns the new image's id, or None when there is nothing to copy or copying failed."""
		file = await ImageStorage.file(bot, image_id)
		if file is None :
			return None
		try :
			channel = await ImageStorage._channel(bot)
			message = await channel.send(file=file)
		except (ImageError, discord.HTTPException) as e :
			logging.warning(f"Copying stored image {image_id} failed: {e}")
			return None
		url = message.attachments[0].url
		return StoredImageTransactions().add(channel.id, message.id, url, ImageStorage.expiry(url)).id

	# ============================================================
	@staticmethod
	async def delete(bot: discord.Client, image_id: int | None) -> None :
		"""Removes the image's storage message and its row. Missing images are ignored."""
		if image_id is None :
			return
		image = StoredImageTransactions().get(image_id)
		if image is None :
			return
		message = await ImageStorage._message(bot, image)
		if message is not None :
			try :
				await message.delete()
			except discord.HTTPException as e :
				logging.warning(f"Stored image {image.id} could not be deleted from storage: {e}")
		StoredImageTransactions().delete(image.id)
