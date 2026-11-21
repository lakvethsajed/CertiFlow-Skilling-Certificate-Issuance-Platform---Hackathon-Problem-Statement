import argparse
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import engine, legacy_now
from app.models import Approval, AuditLog, Batch, Decision
from app.models import BatchStatus as Status
from app.services.batches import (
    REQUIRED_APPROVALS,
    approval_count,
    candidate_count,
    current_revision,
)


def reconcile(db: Session, threshold: int) -> dict[str, int]:
    totals = {"queued": 0, "bypassed": 0, "requires_manual_review": 0}
    batches = db.scalars(
        select(Batch)
        .where(Batch.status == Status.PENDING_QUALITY_REVIEW)
        .order_by(Batch.id)
        .with_for_update(of=Batch)
    )
    for batch in batches:
        revision = current_revision(db, batch)
        if revision.quality_queued_at or revision.quality_review:
            continue
        count = candidate_count(db, revision.id)
        if not count or approval_count(db, revision.id) < REQUIRED_APPROVALS:
            totals["requires_manual_review"] += 1
            continue
        if count > threshold:
            latest = db.scalar(
                select(Approval.created_at)
                .where(
                    Approval.revision_id == revision.id,
                    Approval.decision == Decision.APPROVE,
                )
                .order_by(Approval.created_at.desc())
                .limit(1)
            )
            revision.quality_queued_at = latest.replace(tzinfo=UTC)
            batch.quality_required = True
            totals["queued"] += 1
        else:
            batch.status = Status.PENDING_STATE_APPROVAL
            batch.quality_required = False
            totals["bypassed"] += 1
        batch.version += 1
        db.add(
            AuditLog(
                revision_id=revision.id,
                action="QUALITY_ROUTING_RECONCILED",
                comment=f"Cutover routed {count} persisted candidates using threshold {threshold}.",
                created_at=legacy_now(),
            )
        )
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check legacy batches awaiting quality review."
    )
    parser.add_argument(
        "--apply", action="store_true", help="Commit the routing changes."
    )
    args = parser.parse_args()
    with Session(engine()) as db:
        totals = reconcile(db, settings().quality_threshold)
        if args.apply:
            if totals["requires_manual_review"]:
                raise SystemExit(
                    "Cutover aborted: at least one legacy batch requires manual review."
                )
            db.commit()
        else:
            db.rollback()
        print(f"{'Applied' if args.apply else 'Dry run'}: {totals}")


if __name__ == "__main__":
    main()
