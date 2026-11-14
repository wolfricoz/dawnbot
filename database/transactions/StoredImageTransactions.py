from datetime import datetime

from sqlalchemy import Select, delete

from database.database import StoredImages
from database.transactions.DatabaseTransactions import DatabaseTransactions


class StoredImageTransactions(DatabaseTransactions) :
	"""Images kept in the storage channel. The row points at the storage message and caches its last link."""

	# ============================================================
	def get(self, image_id: int) -> StoredImages | None :
		with self.createsession() as session :
			return session.scalar(Select(StoredImages).where(StoredImages.id == image_id))

	# ============================================================
	def add(self, channel_id: int, message_id: int, url: str, expires_at: datetime | None) -> StoredImages :
		with self.createsession() as session :
			image = StoredImages(storage_channel_id=channel_id, storage_message_id=message_id, url=url,
			                     expires_at=expires_at)
			session.add(image)
			self.commit(session)
			return image

	# ============================================================
	def update_url(self, image_id: int, url: str, expires_at: datetime | None) -> StoredImages | None :
		with self.createsession() as session :
			image = session.scalar(Select(StoredImages).where(StoredImages.id == image_id))
			if image is None :
				return None
			image.url = url
			image.expires_at = expires_at
			self.commit(session)
			return image

	# ============================================================
	def delete(self, image_id: int) -> bool :
		with self.createsession() as session :
			result = session.execute(delete(StoredImages).where(StoredImages.id == image_id))
			self.commit(session)
			return result.rowcount > 0
