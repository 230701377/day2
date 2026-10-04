import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Make sure the app package is importable when running `alembic` from /backend.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.db.session import Base
from app.models import models  # noqa: F401 - ensure models are imported

# Replace the file_config with a RawConfigParser so the URL (which may contain
# '%' characters in the password) is not interpreted as config interpolation.
import configparser

config = context.config

if config.config_file_name is not None and os.path.exists(config.config_file_name):
    fileConfig(config.config_file_name)
    raw = configparser.RawConfigParser()
    raw.read(config.config_file_name)
    config.file_config = raw

# Pass the URL through to the engine config dict directly - never call
# set_main_option which would re-introduce interpolation.
target_metadata = Base.metadata


def _url_section() -> dict:
    section = config.get_section(config.config_ini_section, {}) if config.config_file_name else {}
    section["sqlalchemy.url"] = settings.sqlalchemy_database_uri
    return section


def run_migrations_offline() -> None:
    context.configure(
        url=settings.sqlalchemy_database_uri,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        _url_section(),
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
