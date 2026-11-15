import importlib
import os
from test_modules.base import DatabaseTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKAGES = ["classes", "modules", "views", "tasks", "listeners", "database"]


class TestImports(DatabaseTestCase) :
	"""Every module imports, so a typo in a command or view file shows up in the tests rather than at startup."""

	def test_every_module_imports(self) :
		failures = []
		for package in PACKAGES :
			for folder, _, files in os.walk(os.path.join(ROOT, package)) :
				if "__pycache__" in folder :
					continue
				for filename in files :
					if not filename.endswith(".py") or filename == "__init__.py" :
						continue
					relative = os.path.relpath(os.path.join(folder, filename[:-3]), ROOT)
					name = relative.replace(os.sep, ".")
					try :
						importlib.import_module(name)
					except Exception as e :
						failures.append(f"{name}: {type(e).__name__}: {e}")
		self.assertEqual(failures, [], "\n".join(failures))

	def test_cogs_build_their_commands(self) :
		"""Loading a cog's command tree catches bad option types and autocomplete names."""
		from discord.ext import commands
		import discord

		bot = commands.Bot(command_prefix="?", intents=discord.Intents.none())
		for name in ("Combat", "Bestiary", "Ability", "DamageType", "GM", "Gear", "Character", "Armory", "School", "Shop") :
			module = importlib.import_module(f"modules.{name}")
			cog_class = getattr(module, name)
			cog = cog_class(bot)
			self.assertTrue(list(cog.walk_app_commands()), name)
