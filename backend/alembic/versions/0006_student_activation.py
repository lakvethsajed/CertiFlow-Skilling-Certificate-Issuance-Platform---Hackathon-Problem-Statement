"""Link activated student users to immutable approved candidate records."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_student_activation"
down_revision = "0005_issuance_request"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("User", sa.Column("candidateId", sa.Text()))
    op.add_column(
        "User",
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_foreign_key(
        "User_candidateId_fkey",
        "User",
        "Candidate",
        ["candidateId"],
        ["id"],
        ondelete="RESTRICT",
        onupdate="CASCADE",
    )
    op.create_index("User_candidateId_key", "User", ["candidateId"], unique=True)
    op.create_check_constraint(
        "User_candidate_role_check",
        "User",
        """"candidateId" IS NULL OR "role" = 'CANDIDATE'""",
    )
    for field in ("student_id", "email"):
        op.create_index(
            f"Candidate_normalized_{field}_idx",
            "Candidate",
            [sa.text(f"""lower(btrim("data" ->> '{field}'))""")],
        )
    op.create_table(
        "StudentIdentity",
        sa.Column("studentId", sa.Text(), primary_key=True),
        sa.Column("candidateId", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidateId"],
            ["Candidate.id"],
            name="StudentIdentity_candidateId_fkey",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
    )
    op.create_index(
        "StudentIdentity_candidateId_key",
        "StudentIdentity",
        ["candidateId"],
        unique=True,
    )
    op.create_table(
        "StudentActivation",
        sa.Column("studentId", sa.Text(), primary_key=True),
        sa.Column("challengeDigest", sa.Text(), nullable=False),
        sa.Column("otpDigest", sa.Text()),
        sa.Column("expiresAt", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("requestedAt", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("windowAt", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("grantDigest", sa.Text()),
        sa.Column("grantExpiresAt", postgresql.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(
            ["studentId"],
            ["StudentIdentity.studentId"],
            name="StudentActivation_studentId_fkey",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
    )
    for column in ("challengeDigest", "grantDigest"):
        op.create_index(
            f"StudentActivation_{column}_key",
            "StudentActivation",
            [column],
            unique=True,
        )


def downgrade() -> None:
    raise RuntimeError(
        "Restore a verified backup to preserve activated student accounts."
    )
