import logging
import discord
from discord.ui import Select, Button, View

# Setting up basic logging configuration
logging.basicConfig(level=logging.INFO)


class CharacterDropdownSelect(discord.ui.Select) :
	def __init__(self, characters) :
		options = []
		for char in characters :
			# Shortened stat representation to easily fit within Discord's 100 char limit
			stat_summary = (
				f"S: {char.strength} | P: {char.perception} | "
				f"E: {char.endurance} | C: {char.charisma} | I: {char.intelligence} | "
				f"A: {char.agility} | L: {char.luck}"
			)

			options.append(
				discord.SelectOption(
					label=char.name[:100],
					value=str(char.id),
					description=stat_summary[:100],
					emoji="👤"
				)
			)

		super().__init__(
			placeholder="Select a character...",
			options=options,
			min_values=1,
			max_values=1
		)

	async def callback(self, interaction: discord.Interaction) :
		# Store selected character ID back into the parent view
		self.view.selected_character_id = int(self.values[0])
		self.view.interaction = interaction
		self.view.stop()


class SelectCharacterView(discord.ui.View) :
	def __init__(self, characters: list, timeout: float = 180.0) :
		super().__init__(timeout=timeout)
		self.all_characters = characters
		self.selected_character_id = None
		self.interaction = None
		self.current_page = 0
		self.items_per_page = 25

		# Calculate total pages needed based on 25 items per select menu maximum
		self.total_pages = (len(self.all_characters) + self.items_per_page - 1) // self.items_per_page
		self._update_page()

	def _update_page(self) :
		self.clear_items()

		# Slice data for the active page
		start = self.current_page * self.items_per_page
		end = start + self.items_per_page
		page_characters = self.all_characters[start :end]

		# Inject dropdown menu at row 0
		if page_characters :
			self.add_item(CharacterDropdownSelect(page_characters))

		logging.info(f"Total pages: {self.total_pages}, Current page: {self.current_page}")

		# Inject navigation control row if records bridge across multiple pages
		if self.total_pages > 1 :
			prev_button = discord.ui.Button(
				label="◀ Previous",
				style=discord.ButtonStyle.primary,
				disabled=(self.current_page == 0),
				row=1
			)
			prev_button.callback = self._previous_page
			self.add_item(prev_button)

			page_button = discord.ui.Button(
				label=f"Page {self.current_page + 1}/{self.total_pages}",
				style=discord.ButtonStyle.secondary,
				disabled=True,
				row=1
			)
			self.add_item(page_button)

			next_button = discord.ui.Button(
				label="Next ▶",
				style=discord.ButtonStyle.primary,
				disabled=(self.current_page >= self.total_pages - 1),
				row=1
			)
			next_button.callback = self._next_page
			self.add_item(next_button)

	async def _previous_page(self, interaction: discord.Interaction) :
		self.current_page = max(0, self.current_page - 1)
		self._update_page()
		await interaction.response.edit_message(view=self)

	async def _next_page(self, interaction: discord.Interaction) :
		self.current_page = min(self.total_pages - 1, self.current_page + 1)
		self._update_page()
		await interaction.response.edit_message(view=self)