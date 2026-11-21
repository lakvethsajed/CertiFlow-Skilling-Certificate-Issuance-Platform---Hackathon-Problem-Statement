"""Add revision-level quality reviews and queue timestamps."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_quality_review"
down_revision = "0001_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "BatchRevision",
        sa.Column("qualityQueuedAt", postgresql.TIMESTAMP(timezone=True, precision=3)),
    )
    op.create_index(
        "BatchRevision_qualityQueuedAt_idx", "BatchRevision", ["qualityQueuedAt"]
    )
    op.create_table(
        "QualityReview",
        sa.Column("revisionId", sa.Text(), nullable=False),
        sa.Column("reviewerId", sa.Text(), nullable=False),
        sa.Column(
            "decision",
            postgresql.ENUM(
                "APPROVE", "RETURN", "REJECT", name="Decision", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "createdAt",
            postgresql.TIMESTAMP(timezone=True, precision=3),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("revisionId", name="QualityReview_pkey"),
        sa.ForeignKeyConstraint(
            ["revisionId"],
            ["BatchRevision.id"],
            name="QualityReview_revisionId_fkey",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewerId"],
            ["User.id"],
            name="QualityReview_reviewerId_fkey",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.CheckConstraint(
            """char_length("comment") <= 2000 AND
               ("decision" = 'APPROVE' OR "comment" ~ '[^[:space:]]')""",
            name="QualityReview_decision_comment_check",
        ),
    )
    op.create_index(
        "QualityReview_reviewerId_createdAt_idx",
        "QualityReview",
        ["reviewerId", "createdAt"],
    )


def downgrade() -> None:
    raise RuntimeError(
        "Removing recorded quality decisions is destructive. Restore a verified backup "
        "if you need to roll the schema back."
    )
