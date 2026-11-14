class KeyNotFound(Exception) :
	"""A required config key has not been set for the guild."""

	def __init__(self, key) :
		self.key = key
		super().__init__(f"Key {key} not found in Config")
