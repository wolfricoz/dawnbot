from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from database.database import Base, db_url

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Take the database from the same place the bot's engine does (the DB_* variables in .env), rather than from
# alembic.ini, so the CLI and the bot can never disagree about which database is being migrated. Only fills in a url
# that nothing else supplied, so a caller that deliberately points at another database still wins.
# The '%' escape is for ConfigParser, which treats a bare '%' in a value as interpolation.
if not config.get_main_option("sqlalchemy.url", None) :
    config.set_main_option("sqlalchemy.url", db_url.render_as_string(hide_password=False).replace("%", "%%"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None :
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None :
    """Run migrations in 'offline' mode: emit the SQL instead of running it."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle" : "named"},
    )

    with context.begin_transaction() :
        context.run_migrations()


def run_migrations_online() -> None :
    """Run migrations in 'online' mode against the configured database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection :
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detect column type changes
            compare_server_default=True,  # detect changes in default values
        )

        with context.begin_transaction() :
            context.run_migrations()


if context.is_offline_mode() :
    run_migrations_offline()
else :
    run_migrations_online()
