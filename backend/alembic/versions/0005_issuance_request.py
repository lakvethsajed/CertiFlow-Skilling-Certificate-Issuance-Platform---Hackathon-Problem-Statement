"""Create the durable issuance request written by final approval."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_issuance_request"
down_revision = "0004_state_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "IssuanceRequest",
        sa.Column("revisionId", sa.Text(), nullable=False),
        sa.Column(
            "createdAt",
            postgresql.TIMESTAMP(timezone=True, precision=3),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("revisionId", name="IssuanceRequest_pkey"),
        sa.ForeignKeyConstraint(
            ["revisionId"],
            ["StateReview.revisionId"],
            name="IssuanceRequest_revisionId_fkey",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
    )


def downgrade() -> None:
    raise RuntimeError(
        "Restore a verified backup to preserve recorded issuance requests."
    )
