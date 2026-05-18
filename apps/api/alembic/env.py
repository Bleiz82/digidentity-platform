import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from env only when the ini still holds the placeholder.
# If test code called cfg.set_main_option("sqlalchemy.url", testcontainer_url) before
# invoking alembic.command.upgrade(), the raw value is a concrete URL (no "%") and
# we must NOT override it — DATABASE_URL_SYNC points to the CI service container,
# not the freshly-started testcontainer.
try:
    _raw_url = config.file_config.get(
        config.config_ini_section, "sqlalchemy.url", raw=True
    )
except Exception:
    _raw_url = None
if not _raw_url or "%" in str(_raw_url):
    if url := os.getenv("DATABASE_URL_SYNC"):
        config.set_main_option("sqlalchemy.url", url)

target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
