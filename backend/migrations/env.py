from alembic import context
from sqlalchemy import create_engine, pool

from app.config import Settings
from app.models import Base

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    """The app sets this programmatically; the CLI falls back to the same
    settings the app would use, so both agree on which file is being migrated."""
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured

    settings = Settings()
    settings.ensure_dirs()
    return f"sqlite:///{settings.db_path}"


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        # render_as_batch: SQLite cannot ALTER COLUMN, so alembic recreates the table instead
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
