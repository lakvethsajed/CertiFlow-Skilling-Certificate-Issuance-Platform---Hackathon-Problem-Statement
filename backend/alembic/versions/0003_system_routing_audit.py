"""Allow a cutover routing event to be attributed to the system."""

from alembic import op

revision = "0003_routing_audit"
down_revision = "0002_quality_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("AuditLog", "actorId", nullable=True)
    op.alter_column("AuditLog", "actorRole", nullable=True)
    op.create_check_constraint(
        "AuditLog_actor_scope",
        "AuditLog",
        """("actorId" IS NOT NULL AND "actorRole" IS NOT NULL) OR
           ("actorId" IS NULL AND "actorRole" IS NULL AND
            "action" = 'QUALITY_ROUTING_RECONCILED')""",
    )


def downgrade() -> None:
    raise RuntimeError(
        "Restore a verified backup to roll back recorded routing audit events."
    )
