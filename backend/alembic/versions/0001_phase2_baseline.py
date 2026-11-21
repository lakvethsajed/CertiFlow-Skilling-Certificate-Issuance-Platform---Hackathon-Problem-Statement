"""Baseline for the Phase 2 PostgreSQL schema."""

from pathlib import Path

from sqlalchemy import inspect

from alembic import op

revision = "0001_phase2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not op.get_context().as_sql:
        tables = set(inspect(op.get_bind()).get_table_names()) - {"alembic_version"}
        if tables:
            raise RuntimeError(
                "Database already contains tables. Verify the Phase 2 schema against "
                "a backup before stamping 0001_phase2."
            )
    baseline_sql = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8")
    for statement in baseline_sql.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("The Phase 2 baseline cannot be dropped through Alembic.")
