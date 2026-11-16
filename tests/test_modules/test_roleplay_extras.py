import re
from types import SimpleNamespace

from classes.characters.Access import Access, REPUTATION, Requirement, reputation_parts, reputation_value
from classes.characters.Choices import Choices
from classes.characters.Interview import Interview
from classes.economy import Crafting
from classes.economy.DowntimeFlow import DowntimeFlow
from classes.economy.JobFlow import JobFlow, OPEN, TAKEN
from classes.gear.Gear import Gear
from classes.kernel import GMRole
from classes.kernel.ConfigData import ConfigData
from database.transactions.CharacterGearTransactions import CharacterGearTransactions, MATERIAL
from database.transactions.EconomyTransactions import EconomyTransactions
from database.transactions.GearItemTransactions import GearItemTransactions
from database.transactions.LanguageTransactions import LanguageTransactions
from database.transactions.OccupationTransactions import OccupationTransactions
from database.transactions.SpeciesTransactions import SpeciesTransactions
from database.transactions.TagRuleTransactions import TagRuleTransactions
from database.transactions.WorldTransactions import WorldTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID
from views.buttons.RoleplayChannelPrompt import RoleplayChannelButton

GM_ROLE = 4242


class FixedRng :
	def __init__(self, *values) :
		self.values = list(values)

	def randint(self, low, high) :
		return self.values.pop(0)


def member(roles=(), staff=False) :
	return SimpleNamespace(id=USER_ID, guild=SimpleNamespace(id=GUILD_ID),
	                       roles=[SimpleNamespace(id=role) for role in roles],
	                       guild_permissions=SimpleNamespace(manage_messages=staff))


class TestExtras(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()

	def test_gm_role(self) :
		self.assertFalse(GMRole.is_gm(member([GM_ROLE])))
		self.assertTrue(GMRole.is_gm(member(staff=True)))
		self.assertEqual(GMRole.mention(GUILD_ID)[0], "")
		ConfigData().add_key(GUILD_ID, ConfigMapping.GM_ROLE, GM_ROLE, overwrite=True)
		self.assertTrue(GMRole.is_gm(member([GM_ROLE])))
		self.assertFalse(GMRole.is_gm(member([1])))
		text, allowed = GMRole.mention(GUILD_ID)
		self.assertEqual(text, f"<@&{GM_ROLE}> ")
		self.assertEqual([role.id for role in allowed.roles], [GM_ROLE])

	def test_reputation_requirements(self) :
		guild = EconomyTransactions().add_faction(GUILD_ID, "Guild")
		value = reputation_value(guild.id, "liked")
		self.assertEqual(reputation_parts(value), (guild.id, "liked"))
		rule = [Requirement(REPUTATION, value)]
		self.assertIn("needs Liked standing with Guild", Access().check(rule))
		self.assertIsNone(Access(standings={guild.id : 20}).check(rule))
		self.assertIsNone(Access(staff=True).check(rule))
		character = self.add_character()
		self.assertIsNotNone(Access().for_character(character.id).check(rule))
		EconomyTransactions().set_standing(character.id, guild.id, 30, 30, "test", None)
		self.assertIsNone(Access().for_character(character.id).check(rule))

	def test_reputation_tags_on_gear(self) :
		guild = EconomyTransactions().add_faction(GUILD_ID, "Smiths")
		TagRuleTransactions().set(GUILD_ID, 1, 77, REPUTATION, reputation_value(guild.id, "liked"))
		item = GearItemTransactions().add(GUILD_ID, "weapon", "Guild Hammer", price=10, requirements={}, combat={},
		                                  tag_ids=[77])
		character = self.add_character(currency=100)
		entry, problem = Gear.buy(character, item, Access(), USER_ID)
		self.assertIsNone(entry)
		self.assertIn("Liked standing", problem)
		EconomyTransactions().set_standing(character.id, guild.id, 20, 20, "test", None)
		entry, problem = Gear.buy(character, item, Access(), USER_ID)
		self.assertIsNone(problem)

	def test_occupation_faction(self) :
		watch = EconomyTransactions().add_faction(GUILD_ID, "Watch")
		occupation = OccupationTransactions().add(GUILD_ID, "Sergeant")
		OccupationTransactions().update(occupation.id, faction_id=watch.id, faction_tier="liked")
		choice = Choices.occupations(GUILD_ID, Access())[0]
		self.assertIn("Liked standing", choice.locked)
		character = self.add_character()
		EconomyTransactions().set_standing(character.id, watch.id, 15, 15, "test", None)
		self.assertIsNone(Choices.occupations(GUILD_ID, Access(), character.id)[0].locked)

	def test_flavor_lines(self) :
		occupation = OccupationTransactions().add(GUILD_ID, "Baker")
		self.assertEqual(DowntimeFlow.flavor(None, "success"), "The work got done.")
		OccupationTransactions().update(occupation.id, flavor={"success" : ["The bread rose perfectly."]})
		record = OccupationTransactions().get(occupation.id)
		self.assertEqual(DowntimeFlow.flavor(record, "success"), "The bread rose perfectly.")
		self.assertEqual(DowntimeFlow.flavor(record, "failure"), "A slow day; only half the pay.")

	def test_carousing_gains_standing(self) :
		ConfigData().add_key(GUILD_ID, ConfigMapping.ECONOMY, "free", overwrite=True)
		thieves = EconomyTransactions().add_faction(GUILD_ID, "Thieves")
		tavern = WorldTransactions().save_location(GUILD_ID, 90, name="Tavern", faction_id=thieves.id)
		character = self.add_character()
		outcome, lines, _ = DowntimeFlow.carouse(character, tavern)
		self.assertEqual(EconomyTransactions().standing(character.id, thieves.id), 1)
		self.assertTrue(any("Thieves" in line for line in lines))

	def test_flawed_projects(self) :
		iron = GearItemTransactions().add(GUILD_ID, MATERIAL, "Iron", price=1, requirements={}, combat={})
		sword = GearItemTransactions().add(GUILD_ID, "weapon", "Sword", price=100, requirements={}, combat={})
		character = self.add_character(strength=8)
		recipe = EconomyTransactions().add_recipe(GUILD_ID, "Sword", result_item_id=sword.id,
		                                          ingredients=[{"item_id" : iron.id, "amount" : 1}], stat="strength",
		                                          dc=12, days=2)
		# A bad failure leaves a flaw (cursed); a crit and a flaw cancel out (plain).
		for rolls, expected in (((1, 15, 15), "Cursed Sword"), ((20, 1, 15, 15), "Sword")) :
			CharacterGearTransactions().add(character.id, iron.id, "Iron", MATERIAL, "granted", 1)
			project = Crafting.start_project(character, recipe)
			rng = FixedRng(*rolls)
			finished = False
			while not finished :
				_, _, finished = Crafting.work(character, EconomyTransactions().project(project.id), rng=rng)
			names = [entry.name for entry in CharacterGearTransactions().get_all(character.id) if entry.kind == "weapon"]
			self.assertEqual(names[-1], expected)

	def test_job_state_tags(self) :
		tags = [SimpleNamespace(id=1, name="open"), SimpleNamespace(id=2, name="Taken"),
		        SimpleNamespace(id=3, name="Lore")]
		found = JobFlow.state_tags(SimpleNamespace(available_tags=tags))
		self.assertEqual({state : tag.id for state, tag in found.items()}, {OPEN : 1, TAKEN : 2})

	def test_location_button(self) :
		self.assertIsNotNone(re.fullmatch(RoleplayChannelButton.__discord_ui_compiled_template__,
		                                  "rpchannel:location:123"))

	def test_interview_languages(self) :
		elvish = LanguageTransactions().add(GUILD_ID, "Elvish")
		dwarvish = LanguageTransactions().add(GUILD_ID, "Dwarvish")
		LanguageTransactions().add(GUILD_ID, "Common", common=True)
		elf = SpeciesTransactions().add(GUILD_ID, "Elf", state="approved", language_ids=[elvish.id])
		self.assertTrue(Interview._languages_available(GUILD_ID))
		draft = SimpleNamespace(guild_id=GUILD_ID, answers={"name" : "Ayla", "stats" : {"intelligence" : 5}})
		self.assertEqual(Interview._language_slots(draft), 1)
		self.assertEqual({language.name for language in Interview._language_options(draft)}, {"Elvish", "Dwarvish"})
		self.assertIn("can pick 1", Interview._answer_languages(draft, "Elvish, Dwarvish"))
		self.assertIn("isn't one", Interview._answer_languages(draft, "Orcish"))
		self.assertIsNone(Interview._answer_languages(draft, "dwarvish"))
		self.assertEqual([language.name for language in Interview._chosen_languages(draft)], ["Dwarvish"])
		draft.answers["species_id"] = elf.id
		self.assertEqual([language.name for language in Interview._language_options(draft)], ["Dwarvish"])
		draft.answers["stats"]["intelligence"] = 9
		self.assertEqual(Interview._language_slots(draft), 3)
		self.assertIn("Pick up to **3**", Interview._languages_prompt(draft))
