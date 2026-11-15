import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from classes.kernel.ConfigData import ConfigData
from classes.language import Languages
from classes.language.LanguageFlow import LanguageFlow, START
from classes.language.LetterFlow import LetterFlow
from classes.language.Languages import FLUENT, PARTIAL, Segment
from database.transactions.CharacterTransactions import CharacterTransactions
from database.transactions.LanguageTransactions import LanguageTransactions
from database.transactions.SpeciesTransactions import SpeciesTransactions
from resources.configs.ConfigMapping import ConfigMapping
from test_modules.base import DatabaseTestCase, GUILD_ID, USER_ID

ELVISH = 7


class TestScrambling(unittest.TestCase) :

	def test_words_keep_their_shape(self) :
		for word in ("Hello", "WORLD", "traveller", "don't", "A") :
			scrambled = Languages.scramble_word(word, ELVISH, "flowing")
			self.assertEqual(len(scrambled), len(word))
			self.assertEqual(scrambled[0].isupper(), word[0].isupper())
			self.assertEqual(scrambled.count("'"), word.count("'"))
		self.assertTrue(Languages.scramble_word("WORLD", ELVISH, "harsh").isupper())
		self.assertEqual(len(Languages.scramble_word("runes", ELVISH, "runes")), 5)

	def test_scrambling_is_the_same_every_time(self) :
		self.assertEqual(Languages.scramble_word("bread", ELVISH, "flowing"),
		                 Languages.scramble_word("Bread", ELVISH, "flowing").lower())
		self.assertNotEqual(Languages.scramble_word("bread", ELVISH, "flowing"),
		                    Languages.scramble_word("bread", ELVISH + 1, "flowing"))

	def test_speech_mode_keeps_the_narration(self) :
		text = 'She leaned in. "Meet me at dawn," she said.'
		scrambled = Languages.scramble(text, ELVISH, "harsh")
		self.assertTrue(scrambled.startswith("She leaned in. \""))
		self.assertTrue(scrambled.endswith('," she said.'))
		self.assertNotIn("Meet me", scrambled)
		self.assertNotIn("She leaned", Languages.scramble(text, ELVISH, "harsh", mode=Languages.ALL))

	def test_mentions_links_and_emoji_survive(self) :
		text = '"Hi <@123> see https://example.com/page and <:wave:999> `code`"'
		scrambled = Languages.scramble(text, ELVISH, "flowing")
		for kept in ("<@123>", "https://example.com/page", "<:wave:999>", "`code`") :
			self.assertIn(kept, scrambled)

	def test_partial_understanding(self) :
		text = '"' + " ".join(f"word{index}" for index in range(0)) + 'the quick brown fox jumps over the lazy dog"'
		partly = Languages.partial(text, ELVISH, "flowing")
		kept = [word for word in text.strip('"').split() if word in partly]
		self.assertTrue(0 < len(kept) < 9)
		self.assertEqual(partly, Languages.partial(text, ELVISH, "flowing"))

	def test_markers(self) :
		names = {"elvish" : ELVISH, "common" : 0}

		def lookup(name) :
			return names.get(name.lower())

		segments, unknown = Languages.split("Hi {Elvish}\"mae govannen\"{} bye {Dwarvish}x", lookup)
		self.assertEqual(unknown, ["Dwarvish"])
		self.assertEqual(segments, [Segment(None, "Hi "), Segment(ELVISH, "\"mae govannen\""),
		                            Segment(None, " bye x")])
		segments, _ = Languages.split("\"all elvish\" {common}\"now common\"", lookup, default=ELVISH)
		self.assertEqual([segment.language for segment in segments], [ELVISH, None])
		table = {ELVISH : ("Elvish", "flowing", None)}
		self.assertEqual(Languages.marked(segments, table), "‹Elvish› \"all elvish\" \"now common\"")
		again, _ = Languages.split(Languages.marked(segments, table, guillemets=False), lookup)
		self.assertEqual(again, segments)

	def test_render_for_readers(self) :
		segments = [Segment(None, "Hi "), Segment(ELVISH, "\"friend\"")]
		table = {ELVISH : ("Elvish", "flowing", None)}
		self.assertEqual(Languages.render(segments, table, {ELVISH : FLUENT}), "Hi \"friend\"")
		self.assertNotIn("friend", Languages.render(segments, table, {}))
		self.assertEqual(Languages.render(segments, table, {}, everything=True), "Hi \"friend\"")
		self.assertEqual(Languages.starting_slots(1, 9), 3)
		self.assertEqual(Languages.starting_slots(1, 4), 1)


class TestLanguageRecords(DatabaseTestCase) :

	def setUp(self) :
		super().setUp()
		self.add_server()
		self.elvish = LanguageTransactions().add(GUILD_ID, "Elvish", sound="flowing")

	def test_common_is_made_once(self) :
		common = LanguageFlow.common(GUILD_ID)
		self.assertTrue(common.common)
		self.assertEqual(common.name, "Common")
		self.assertEqual(LanguageFlow.common(GUILD_ID).id, common.id)

	def test_known_includes_species(self) :
		species = SpeciesTransactions().add(GUILD_ID, "Elf", state="approved", language_ids=[self.elvish.id]) \
			if hasattr(SpeciesTransactions(), "add") else None
		character = self.add_character(species_id=species.id if species else None)
		if species is not None :
			self.assertEqual(LanguageFlow.known(character), {self.elvish.id : FLUENT})
		dwarvish = LanguageTransactions().add(GUILD_ID, "Dwarvish")
		LanguageTransactions().teach(character.id, dwarvish.id, PARTIAL, START)
		self.assertEqual(LanguageFlow.known(character)[dwarvish.id], PARTIAL)

	def test_prepare_posts(self) :
		character = self.add_character()
		self.assertEqual(LanguageFlow.prepare(character, "plain text"), ("plain text", None, None))
		_, _, problem = LanguageFlow.prepare(character, '{Elvish}"hello there"')
		self.assertIn("doesn't speak Elvish", problem)
		self.assertIn("no language called", LanguageFlow.prepare(character, "{Klingon}hi")[2])
		LanguageTransactions().teach(character.id, self.elvish.id, FLUENT, START)
		posted, segments, problem = LanguageFlow.prepare(character, 'She smiles. {Elvish}"hello there"')
		self.assertIsNone(problem)
		self.assertTrue(posted.startswith("She smiles. \""))
		self.assertNotIn("hello there", posted)
		self.assertEqual(LanguageFlow.prepare(character, "a {common}b")[0], "a b")
		CharacterTransactions().update(character.id, speaking_language_id=self.elvish.id)
		character = CharacterTransactions().get_by_id(character.id)
		self.assertNotIn("hi friend", LanguageFlow.prepare(character, '"hi friend"')[0])

	def test_understand(self) :
		writer = self.add_character("Writer")
		LanguageTransactions().teach(writer.id, self.elvish.id, FLUENT, START)
		_, segments, _ = LanguageFlow.prepare(writer, '{Elvish}"a secret plan"')
		LanguageFlow.save(555, writer, segments)
		member = SimpleNamespace(id=USER_ID + 1, guild_permissions=SimpleNamespace(manage_messages=False))
		self.assertIn("None of your characters", LanguageFlow.understand_text(GUILD_ID, member, 555))
		reader = self.add_character("Reader", user_id=USER_ID + 1)
		LanguageTransactions().teach(reader.id, self.elvish.id, FLUENT, START)
		self.assertIn("a secret plan", LanguageFlow.understand_text(GUILD_ID, member, 555))
		staff = SimpleNamespace(id=USER_ID + 9, guild_permissions=SimpleNamespace(manage_messages=True))
		self.assertIn("a secret plan", LanguageFlow.understand_text(GUILD_ID, staff, 555))
		self.assertIn("‹Elvish›", LanguageFlow.chronicle_text(555))
		self.assertEqual(LanguageFlow.edit_text(555, GUILD_ID), '{Elvish}"a secret plan"')
		self.assertIn("isn't in another language", LanguageFlow.understand_text(GUILD_ID, staff, 556))

	def test_slots(self) :
		character = self.add_character(intelligence=9)
		self.assertEqual(LanguageFlow.slots(character), (0, 3))
		LanguageTransactions().teach(character.id, self.elvish.id, FLUENT, START)
		self.assertEqual(LanguageFlow.slots(character), (1, 3))
		ConfigData().add_key(GUILD_ID, ConfigMapping.LANGUAGE_SLOTS, 0, overwrite=True)
		self.assertEqual(LanguageFlow.slots(character)[1], 2)

	def test_letters(self) :
		sender = self.add_character("Sender")
		recipient = self.add_character("Recipient", user_id=USER_ID + 1)
		now = datetime.now(timezone.utc)
		letter = LanguageTransactions().add_letter(GUILD_ID, from_character_id=sender.id, to_character_id=recipient.id,
		                                           from_uid=USER_ID, from_name="Sender", to_name="Recipient",
		                                           subject="Hi", body="Meet me", deliver_at=now - timedelta(minutes=1),
		                                           state="in_transit", language_id=self.elvish.id)
		self.assertEqual([entry.id for entry in LanguageTransactions().due_letters(now)], [letter.id])
		self.assertNotIn("Meet me", LanguageFlow.letter_text(GUILD_ID, self.elvish.id, "Meet me", recipient))
		LanguageTransactions().teach(recipient.id, self.elvish.id, FLUENT, START)
		self.assertEqual(LanguageFlow.letter_text(GUILD_ID, self.elvish.id, "Meet me", recipient), "Meet me")
		self.assertTrue(LetterFlow.may_read(letter, USER_ID))
		self.assertTrue(LetterFlow.may_read(letter, USER_ID + 1))
		self.assertFalse(LetterFlow.may_read(letter, USER_ID + 2))
		guild = SimpleNamespace(id=GUILD_ID)
		self.assertEqual(LetterFlow.delay(guild, sender, recipient, True), timedelta(hours=1))
		self.assertEqual(LetterFlow.delay(guild, sender, recipient, False), timedelta(hours=6))
		LanguageTransactions().update_letter(letter.id, state="delivered")
		self.assertEqual(len(LanguageTransactions().inbox(recipient.id)), 1)
		self.assertEqual(LanguageTransactions().in_transit(GUILD_ID), [])
