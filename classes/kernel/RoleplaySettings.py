"""Reading and checking the roleplay tools' settings (resources/configs/ConfigMapping.roleplay_settings), all set with
/config roleplay."""
from classes.kernel.ConfigData import ConfigData
from resources.configs.ConfigMapping import ConfigMapping, defaults, roleplay_settings

NUMBER = "number"
CHOICE = "choice"
TOGGLE = "toggle"
TEXT = "text"
ON_WORDS = {"on", "true", "yes", "enabled", "1"}
OFF_WORDS = {"off", "false", "no", "disabled", "0"}


# ============================================================
def number(guild_id: int, key: ConfigMapping) -> int :
	value = ConfigData().get_int(guild_id, key)
	return int(value if value is not None else defaults.get(key, 0))


# ============================================================
def toggle(guild_id: int, key: ConfigMapping) -> bool :
	return ConfigData().get_toggle(guild_id, key, default=str(defaults.get(key, "DISABLED")))


# ============================================================
def text(guild_id: int, key: ConfigMapping) -> str :
	value = ConfigData().get_guild(guild_id).get(key.upper())
	return str(value) if value not in (None, "") else str(defaults.get(key, ""))


# ============================================================
def parse(key: str, value: str) -> tuple[str | int | None, str | None] :
	"""Checks a value typed for a setting. Returns what to store, or None and why it was refused."""
	rule = roleplay_settings.get(key)
	if rule is None :
		return None, f"There is no roleplay setting called {key}."
	value = (value or "").strip()
	kind = rule[0]
	if kind == NUMBER :
		try :
			number_ = int(value)
		except ValueError :
			return None, f"{key.lower()} needs a whole number."
		if not rule[1] <= number_ <= rule[2] :
			return None, f"{key.lower()} has to be between {rule[1]} and {rule[2]}."
		return number_, None
	if kind == CHOICE :
		if value.lower() not in rule[1] :
			return None, f"{key.lower()} can be {', '.join(rule[1])}."
		return value.lower(), None
	if kind == TOGGLE :
		if value.lower() in ON_WORDS :
			return "ENABLED", None
		if value.lower() in OFF_WORDS :
			return "DISABLED", None
		return None, f"{key.lower()} is on or off."
	if not value or len(value) > rule[1] :
		return None, f"{key.lower()} needs text of at most {rule[1]} characters."
	return value, None


# ============================================================
def describe(key: str) -> str :
	"""What values a setting takes, for autocomplete."""
	rule = roleplay_settings[key]
	if rule[0] == NUMBER :
		return f"{rule[1]} to {rule[2]}"
	if rule[0] == CHOICE :
		return " / ".join(rule[1])
	if rule[0] == TOGGLE :
		return "on / off"
	return "text"


# ============================================================
def shown(guild_id: int, key: str) -> str :
	"""A setting's current value as text."""
	rule = roleplay_settings[key]
	if rule[0] == NUMBER :
		return str(number(guild_id, key))
	if rule[0] == TOGGLE :
		return "on" if toggle(guild_id, key) else "off"
	return text(guild_id, key)
