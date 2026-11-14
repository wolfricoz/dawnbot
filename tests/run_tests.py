"""Runs the test suite against a throwaway database.

Usage (from anywhere): .venv/Scripts/python.exe tests/run_tests.py [pattern]
  pattern: optional file pattern to run part of the suite, e.g. "test_config*.py".

Settings come from tests/.env.test (copy tests/.env.test.example). TEST=true makes database/database.py create a
database named dawnbot_<8 hex>_test for this run, which is dropped again when the run ends.
"""
import os
import sys
import unittest

from dotenv import load_dotenv

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, ROOT_DIR)

load_dotenv(os.path.join(TESTS_DIR, '.env.test'), override=True)
os.environ['TEST'] = 'true'
# Modules call load_environment() on import, which reads ".env" relative to the working directory. Working from tests/
# keeps the real .env (and its TOKEN) out of the test process.
os.chdir(TESTS_DIR)
os.environ.pop('TOKEN', None)

from sqlalchemy_utils import drop_database

from database.database import engine

assert engine.url.database.endswith('_test'), f"Refusing to run tests against {engine.url.database}"

pattern = sys.argv[1] if len(sys.argv) > 1 else 'test*.py'
suite = unittest.TestLoader().discover(os.path.join(TESTS_DIR, 'test_modules'), pattern=pattern,
                                       top_level_dir=TESTS_DIR)
try :
	# durations lists the slowest tests, so a slow test shows up in every run.
	result = unittest.TextTestRunner(durations=10).run(suite)
finally :
	# The test engine uses a connection pool; Postgres refuses to drop a database that still has open connections.
	engine.dispose()
	drop_database(engine.url)
sys.exit(not result.wasSuccessful())
