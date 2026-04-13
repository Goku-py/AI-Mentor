import logging
from logging.config import fileConfig

from flask import current_app
from alembic import context

# ---------------------------------------------------------------------------
# Alembic config
# ---------------------------------------------------------------------------
config = context.config
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

# ---------------------------------------------------------------------------
# Import ALL models so they register with db.metadata before autogenerate.
# ---------------------------------------------------------------------------
from models_pkg import db, User, AuditLog  # noqa: F401, E402

# Use the metadata from our db instance directly — this is the source of truth.
target_metadata = db.metadata


# ---------------------------------------------------------------------------
# Engine helpers
# ---------------------------------------------------------------------------
def get_engine():
    try:
        return current_app.extensions["migrate"].db.get_engine()
    except (TypeError, AttributeError):
        return current_app.extensions["migrate"].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace("%", "%%")
    except AttributeError:
        return str(get_engine().url).replace("%", "%%")


config.set_main_option("sqlalchemy.url", get_engine_url())


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection required)."""
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
    """Run migrations in 'online' mode (connected to live DB)."""
    conf_args = current_app.extensions["migrate"].configure_args
    # Only set compare_type/compare_server_default if not already supplied
    conf_args.setdefault("compare_type", True)
    conf_args.setdefault("compare_server_default", True)

    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            **conf_args,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
