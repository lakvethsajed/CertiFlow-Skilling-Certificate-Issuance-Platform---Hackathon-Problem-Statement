from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import legacy_now, utc_now
from app.models import Approval, Decision, User
from app.models import BatchStatus as Status
from app.schemas import QualityDecisionRequest
from app.services.batches import (
    DISTRICT_OPEN,
    REQUIRED_APPROVALS,
    audit,
    candidate_count,
    current_revision,
    describe_batch,
    scoped_batch,
)


def district_decision(
    db: Session,
    actor: User,
    batch_id: str,
    decision: Decision,
    request: QualityDecisionRequest,
) -> dict:
    if decision != Decision.APPROVE and not request.comment:
        raise HTTPException(400, "Enter a reason for this decision.")
    batch = scoped_batch(db, batch_id, actor, lock=True)
    if batch.revision != request.revision or batch.status not in DISTRICT_OPEN:
        raise HTTPException(409, "This revision is no longer open for review.")
    revision = current_revision(db, batch)
    details = describe_batch(db, batch, revision, actor)
    if not details["canReview"]:
        raise HTTPException(409, "You already recorded a decision for this revision.")
    validation = details["validation"]
    if decision == Decision.APPROVE and (
        validation["technical"] or validation["batchFindings"]
    ):
        raise HTTPException(
            422,
            {
                "message": "This batch has blocking validation errors.",
                "details": validation,
            },
        )
    db.add(
        Approval(
            revision_id=revision.id,
            officer_id=actor.id,
            decision=decision,
            comment=request.comment,
            created_at=legacy_now(),
        )
    )
    audit(db, revision, actor, str(decision), request.comment or None)
    if decision == Decision.RETURN:
        batch.status = Status.RETURNED_FOR_CORRECTION
    elif decision == Decision.REJECT:
        batch.status = Status.REJECTED
    elif details["approvalsReceived"] + 1 < REQUIRED_APPROVALS:
        batch.status = Status.UNDER_REVIEW
    else:
        batch.quality_required = (
            candidate_count(db, revision.id) > settings().quality_threshold
        )
        batch.status = (
            Status.PENDING_QUALITY_REVIEW
            if batch.quality_required
            else Status.PENDING_STATE_APPROVAL
        )
        if batch.quality_required:
            revision.quality_queued_at = utc_now()
        else:
            revision.state_queued_at = utc_now()
        audit(db, revision, actor, "ADVANCED")
    batch.version += 1
    db.flush()
    db.expire(revision, ["approvals", "audit"])
    return describe_batch(db, batch, revision, actor)
