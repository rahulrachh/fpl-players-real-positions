"""Alembic environment. Uses the read-write engine from app.db (the database
path comes from DATABASE_PATH, see app.config)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

import app.db.models  # noqa: F401  (registers the tables on Base.metadata)
from app.db.base import Base
from app.db.engine import get_read_write_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(get_read_write_engine().url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_read_write_engine().connect() as connection:
        # Batch mode rebuilds tables (copy, drop, rename); with foreign keys on,
        # the drop would fail or cascade. Must be set outside a transaction.
        connection.execute(text("PRAGMA foreign_keys = OFF"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite cannot ALTER most things in place; batch mode recreates tables.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
