"""Add revision-level State Office decisions and queue timestamps."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_state_review"
down_revision = "0003_routing_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TYPE "BatchStatus" ADD VALUE 'FINAL_APPROVED'""")
    op.add_column(
        "BatchRevision",
        sa.Column("stateQueuedAt", postgresql.TIMESTAMP(timezone=True, precision=3)),
    )
    op.create_index(
        "BatchRevision_stateQueuedAt_idx", "BatchRevision", ["stateQueuedAt"]
    )
    op.create_table(
        "StateReview",
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
        sa.PrimaryKeyConstraint("revisionId", name="StateReview_pkey"),
        sa.ForeignKeyConstraint(
            ["revisionId"],
            ["BatchRevision.id"],
            name="StateReview_revisionId_fkey",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewerId"],
            ["User.id"],
            name="StateReview_reviewerId_fkey",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.CheckConstraint(
            """char_length("comment") <= 2000 AND
               ("decision" = 'APPROVE' OR "comment" ~ '[^[:space:]]')""",
            name="StateReview_decision_comment_check",
        ),
    )
    op.create_index(
        "StateReview_reviewerId_createdAt_idx",
        "StateReview",
        ["reviewerId", "createdAt"],
    )


def downgrade() -> None:
    raise RuntimeError(
        "Restore a verified backup to roll back this migration without losing decisions."
    )
