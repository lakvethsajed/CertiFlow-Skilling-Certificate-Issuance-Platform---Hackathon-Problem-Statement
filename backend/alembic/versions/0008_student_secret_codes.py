"""Add one-time Training Centre-issued activation credentials."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008_student_secret_codes"
down_revision = "0007_candidate_certificate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "StudentActivationCode",
        sa.Column("candidateId", sa.Text(), primary_key=True),
        sa.Column("codeDigest", sa.Text(), nullable=False),
        sa.Column("expiresAt", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("usedAt", postgresql.TIMESTAMP(timezone=True)),
        sa.Column("createdAt", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("createdBy", sa.Text(), nullable=False),
        sa.Column("grantDigest", sa.Text()),
        sa.Column("grantExpiresAt", postgresql.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(
            ["candidateId"],
            ["Candidate.id"],
            name="StudentActivationCode_candidateId_fkey",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["createdBy"],
            ["User.id"],
            name="StudentActivationCode_createdBy_fkey",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
    )
    for column in ("codeDigest", "grantDigest"):
        op.create_index(
            f"StudentActivationCode_{column}_key",
            "StudentActivationCode",
            [column],
            unique=True,
        )


def downgrade() -> None:
    raise RuntimeError(
        "Restore a verified backup to preserve issued activation credentials."
    )
