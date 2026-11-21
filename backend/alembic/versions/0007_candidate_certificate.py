"""Store issued candidate certificates separately from legacy batch certificates."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_candidate_certificate"
down_revision = "0006_student_activation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "CandidateCertificate",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("candidateId", sa.Text(), nullable=False),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("issuedAt", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), server_default="ACTIVE", nullable=False),
        sa.ForeignKeyConstraint(
            ["candidateId"],
            ["Candidate.id"],
            name="CandidateCertificate_candidateId_fkey",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'CANCELLED')",
            name="CandidateCertificate_status_check",
        ),
    )
    op.create_index(
        "CandidateCertificate_candidateId_key",
        "CandidateCertificate",
        ["candidateId"],
        unique=True,
    )
    op.create_index(
        "CandidateCertificate_number_key",
        "CandidateCertificate",
        ["number"],
        unique=True,
    )


def downgrade() -> None:
    raise RuntimeError("Restore a verified backup to preserve issued certificates.")
