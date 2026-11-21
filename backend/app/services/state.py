from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import utc_now
from app.models import (
    Approval,
    Batch,
    BatchRevision,
    Candidate,
    CandidateCertificate,
    Decision,
    IssuanceRequest,
    Role,
    StateReview,
    User,
)
from app.models import BatchStatus as Status
from app.schemas import ReviewDecision
from app.services.batches import (
    LABELS,
    REQUIRED_APPROVALS,
    approval_count,
    audit,
    candidate_count,
    current_revision,
    describe_batch,
)
from app.services.validation import inspect_batch
from app.state_schemas import (
    CertificateReadiness,
    StateDecisionCommand,
    StateDecisionResult,
)

STATE_DECISION_STATUSES = {
    Decision.APPROVE: Status.FINAL_APPROVED,
    Decision.RETURN: Status.RETURNED_FOR_CORRECTION,
    Decision.REJECT: Status.REJECTED,
}


def verify_prior_reviews(db: Session, revision: BatchRevision) -> int:
    count = candidate_count(db, revision.id)
    district_block = db.scalar(
        select(Approval.id)
        .where(
            Approval.revision_id == revision.id,
            Approval.decision != Decision.APPROVE,
        )
        .limit(1)
    )
    if (
        revision.submitted_at is None
        or count == 0
        or district_block
        or approval_count(db, revision.id) < REQUIRED_APPROVALS
    ):
        raise HTTPException(409, "This revision has not completed district review.")
    quality = revision.quality_review
    if (count > settings().quality_threshold and quality is None) or (
        quality is not None and quality.decision != Decision.APPROVE
    ):
        raise HTTPException(
            409, "This revision has not passed required quality review."
        )
    return count


def state_decision(
    db: Session, actor: User, batch_id: str, command: StateDecisionCommand
) -> StateDecisionResult:
    if actor.role != Role.STATE_OFFICE:
        raise HTTPException(403, "This account does not have access.")
    batch = db.scalar(
        select(Batch).where(Batch.id == batch_id).with_for_update(of=Batch)
    )
    if batch is None:
        raise HTTPException(404, "Batch not found.")
    if (
        batch.revision != command.revision
        or batch.status != Status.PENDING_STATE_APPROVAL
    ):
        raise HTTPException(409, "This revision is no longer open for final approval.")
    revision = current_revision(db, batch)
    if revision.state_review is not None:
        raise HTTPException(409, "A final decision already exists for this revision.")
    count = verify_prior_reviews(db, revision)
    approve = command.decision == Decision.APPROVE
    if approve:
        students = list(
            db.scalars(
                select(Candidate.data).where(Candidate.revision_id == revision.id)
            )
        )
        validation = inspect_batch(revision.form, students)
        if validation["technical"] or validation["batchFindings"]:
            raise HTTPException(
                422,
                {
                    "message": "This revision has blocking validation errors.",
                    "details": validation,
                },
            )

    reviewed_at = utc_now()
    revision.state_review = StateReview(
        reviewer_id=actor.id,
        decision=command.decision,
        comment=command.comment,
        created_at=reviewed_at,
    )
    batch.status = STATE_DECISION_STATUSES[command.decision]
    batch.quality_required = count > settings().quality_threshold
    batch.version += 1
    audit(db, revision, actor, f"STATE_{command.decision}", command.comment or None)
    db.flush()
    if approve:
        db.add(IssuanceRequest(revision_id=revision.id, created_at=reviewed_at))
        db.flush()
    return StateDecisionResult(
        batch_id=batch.id,
        revision=revision.number,
        status=batch.status,
        issuance_requested=approve,
        review=ReviewDecision(
            reviewer=actor.name,
            decision=command.decision,
            comment=command.comment,
            created_at=reviewed_at,
            revision=revision.number,
        ),
    )


def state_batch_details(
    db: Session, actor: User, batch_id: str, number: int | None
) -> dict:
    if actor.role != Role.STATE_OFFICE:
        raise HTTPException(403, "This account does not have access.")
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "Batch not found.")
    number = batch.revision if number is None else number
    revision = db.scalar(
        select(BatchRevision).where(
            BatchRevision.batch_id == batch_id, BatchRevision.number == number
        )
    )
    if revision is None:
        raise HTTPException(404, "Batch revision not found.")
    review = revision.state_review
    if review is None:
        if batch.revision != number or batch.status != Status.PENDING_STATE_APPROVAL:
            raise HTTPException(404, "Batch revision not found.")
        try:
            verify_prior_reviews(db, revision)
        except HTTPException as error:
            raise HTTPException(
                404, "Batch revision is not eligible for final review."
            ) from error

    details = describe_batch(db, batch, revision, actor)
    if review is not None and number != batch.revision:
        historical_status = STATE_DECISION_STATUSES[review.decision]
        details.update(
            status=LABELS[historical_status], workflowStatus=historical_status
        )
    approved = review is not None and review.decision == Decision.APPROVE
    expected = details["count"] if approved else 0
    requested = approved and db.get(IssuanceRequest, revision.id) is not None
    generated = (
        db.scalar(
            select(func.count())
            .select_from(CandidateCertificate)
            .join(Candidate, Candidate.id == CandidateCertificate.candidate_id)
            .where(Candidate.revision_id == revision.id)
        )
        or 0
    )
    threshold = settings().quality_threshold
    details.update(
        canReview=review is None,
        qualityRequired=details["count"] > threshold
        if review is None
        else revision.quality_review is not None,
        certificateReadiness=CertificateReadiness(
            final_approved=approved,
            expected=expected,
            generated=generated,
            pending=max(0, expected - generated) if requested else 0,
            failed=0,
        ),
    )
    return details
