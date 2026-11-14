"""One-off import of rptools templates into dawnbot.

Run from the repository root with the rptools database URL in RPTOOLS_DB (it is never printed):
    RPTOOLS_DB=postgresql+psycopg2://user:password@host:5432/rpcrafter .venv/Scripts/python.exe -m classes.setup.RptoolsImport

Templates keep their owner and name and are converted to the current format; a template whose owner already has one
with that name in dawnbot is skipped, so running the import twice is safe. rptools characters are not imported: they
have no server, which dawnbot characters need.
"""
import json
import logging
import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from classes.setup.ServerSetup import ServerSetup
from database.transactions.TemplateTransactions import TemplateTransactions


# ============================================================
def import_templates(source: Engine) -> tuple[int, int] :
	"""Copies every rptools template into dawnbot.

	@return: (templates imported, templates skipped because they already existed)
	"""
	imported = 0
	skipped = 0
	with source.connect() as connection :
		rows = connection.execute(text("SELECT user_id, name, data FROM templates ORDER BY id")).all()
	for user_id, name, data in rows :
		if isinstance(data, str) :
			data = json.loads(data)
		if TemplateTransactions().add(int(user_id), name, ServerSetup.normalize(data)) is None :
			skipped += 1
			continue
		imported += 1
	return imported, skipped


# ============================================================
def count_characters(source: Engine) -> int :
	with source.connect() as connection :
		if "characters" not in inspect(connection).get_table_names() :
			return 0
		return connection.execute(text("SELECT count(*) FROM characters")).scalar()


if __name__ == "__main__" :
	logging.basicConfig(level=logging.WARNING)
	url = os.getenv("RPTOOLS_DB")
	if not url :
		raise SystemExit("Set RPTOOLS_DB to the rptools database URL.")
	engine = create_engine(url)
	done, existing = import_templates(engine)
	print(f"Imported {done} template(s); {existing} already existed and were skipped.")
	characters = count_characters(engine)
	if characters :
		print(f"{characters} rptools character(s) were not imported (they have no server).")
