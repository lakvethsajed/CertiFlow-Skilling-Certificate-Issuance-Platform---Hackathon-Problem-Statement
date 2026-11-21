import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values

from alembic import context
from app.database import create_database_engine
from app.models import Base


def database_url() -> str:
    path = Path(__file__).resolve().parents[1] / ".env"
    url = os.environ.get("DATABASE_URL") or dotenv_values(path).get("DATABASE_URL")
    if not url:
        raise RuntimeError("Set DATABASE_URL before running Alembic.")
    return url


def include_name(
    name: str | None, object_type: str, _parent_names: Mapping[str, str | None]
) -> bool:
    return object_type != "table" or name != "_prisma_migrations"


if context.is_offline_mode():
    context.configure(
        dialect_name="postgresql",
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_database_engine(database_url())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=Base.metadata,
                compare_server_default=True,
                include_name=include_name,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
