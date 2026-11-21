from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import utc_now
from app.models import (
    Approval,
    Batch,
    BatchRevision,
    Candidate,
    Decision,
    District,
    QualityReview,
    Role,
    TrainingCentre,
    User,
)
from app.models import BatchStatus as Status
from app.schemas import (
    QualityActivity,
    QualityDashboard,
    QualityDecisionRequest,
    QualityQueueItem,
    QualityQueuePage,
    QualityQueueQuery,
)
from app.services.batches import (
    REQUIRED_APPROVALS,
    approval_count,
    audit,
    candidate_count,
    current_revision,
    describe_batch,
    legacy_iso,
)

CANDIDATES = (
    select(func.count())
    .select_from(Candidate)
    .where(Candidate.revision_id == BatchRevision.id)
    .correlate(BatchRevision)
    .scalar_subquery()
)
APPROVALS = (
    select(func.count(func.distinct(Approval.officer_id)))
    .where(
        Approval.revision_id == BatchRevision.id, Approval.decision == Decision.APPROVE
    )
    .correlate(BatchRevision)
    .scalar_subquery()
)


def pending_conditions() -> tuple:
    return (
        Batch.status == Status.PENDING_QUALITY_REVIEW,
        Batch.revision == BatchRevision.number,
        BatchRevision.quality_queued_at.is_not(None),
        CANDIDATES > settings().quality_threshold,
        APPROVALS >= REQUIRED_APPROVALS,
    )


def pending_query() -> Select:
    return (
        select(Batch, BatchRevision, CANDIDATES, APPROVALS)
        .select_from(Batch)
        .join(BatchRevision, BatchRevision.batch_id == Batch.id)
        .where(*pending_conditions())
    )


def quality_dashboard(db: Session) -> QualityDashboard:
    totals = dict(
        db.execute(
            select(QualityReview.decision, func.count()).group_by(
                QualityReview.decision
            )
        ).all()
    )
    recent = db.execute(
        select(QualityReview, BatchRevision)
        .join(BatchRevision)
        .order_by(QualityReview.created_at.desc(), QualityReview.revision_id)
        .limit(8)
    )
    return QualityDashboard(
        pending=db.scalar(select(func.count()).select_from(pending_query().subquery()))
        or 0,
        approved=totals.get(Decision.APPROVE, 0),
        returned=totals.get(Decision.RETURN, 0),
        rejected=totals.get(Decision.REJECT, 0),
        activity=[
            QualityActivity(
                batch_id=revision.batch_id,
                batch_name=revision.form["name"],
                revision=revision.number,
                reviewer=review.reviewer.name,
                decision=review.decision,
                comment=review.comment,
                created_at=review.created_at,
            )
            for review, revision in recent
        ],
    )


def quality_queue(db: Session, params: QualityQueueQuery) -> QualityQueuePage:
    status_by_decision = {
        Decision.APPROVE: Status.PENDING_STATE_APPROVAL,
        Decision.RETURN: Status.RETURNED_FOR_CORRECTION,
        Decision.REJECT: Status.REJECTED,
    }
    if params.view == "pending":
        query = (
            pending_query()
            .add_columns(QualityReview.decision)
            .outerjoin(QualityReview, QualityReview.revision_id == BatchRevision.id)
            .where(QualityReview.revision_id.is_(None))
        )
        sort_date = BatchRevision.quality_queued_at
    else:
        query = (
            select(Batch, BatchRevision, CANDIDATES, APPROVALS, QualityReview.decision)
            .select_from(Batch)
            .join(BatchRevision, BatchRevision.batch_id == Batch.id)
            .join(QualityReview, QualityReview.revision_id == BatchRevision.id)
        )
        if params.view != "history":
            decision = {
                "approved": Decision.APPROVE,
                "returned": Decision.RETURN,
                "rejected": Decision.REJECT,
            }[params.view]
            query = query.where(QualityReview.decision == decision)
        sort_date = QualityReview.created_at
    query = query.join(TrainingCentre, TrainingCentre.id == Batch.centre_id).join(
        District, District.id == TrainingCentre.district_id
    )
    if params.search:
        pattern = params.search.strip().lower()
        query = query.where(
            func.lower(Batch.id).contains(pattern, autoescape=True)
            | func.lower(BatchRevision.form["name"].astext).contains(
                pattern, autoescape=True
            )
            | func.lower(TrainingCentre.name).contains(pattern, autoescape=True)
        )
    if params.course:
        query = query.where(
            func.lower(BatchRevision.form["course"].astext) == params.course.lower()
        )
    if params.district:
        query = query.where(func.lower(District.name) == params.district.lower())
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(
            sort_date.asc() if params.sort == "oldest" else sort_date.desc(),
            BatchRevision.id,
        )
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    return QualityQueuePage(
        records=[
            QualityQueueItem(
                batch_id=batch.id,
                revision=revision.number,
                name=revision.form["name"],
                centre=batch.centre.name,
                district=batch.centre.district.name,
                course=revision.form["course"],
                candidate_count=count,
                district_approval_count=approvals,
                status=status_by_decision[decision] if decision else batch.status,
                submitted_at=legacy_iso(revision.submitted_at),
                quality_queued_at=revision.quality_queued_at,
            )
            for batch, revision, count, approvals, decision in rows
        ],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


def eligible(db: Session, batch: Batch, revision: BatchRevision) -> bool:
    return (
        batch.status == Status.PENDING_QUALITY_REVIEW
        and batch.revision == revision.number
        and revision.quality_queued_at is not None
        and revision.quality_review is None
        and candidate_count(db, revision.id) > settings().quality_threshold
        and approval_count(db, revision.id) >= REQUIRED_APPROVALS
    )


def describe_quality(
    db: Session, batch: Batch, revision: BatchRevision, actor: User
) -> dict:
    details = describe_batch(db, batch, revision, actor)
    review = revision.quality_review
    details["canReview"] = eligible(db, batch, revision)
    details["qualityQueuedAt"] = revision.quality_queued_at
    details["qualityDecision"] = review.decision if review else None
    if review and revision.number != batch.revision:
        details["status"] = {
            "APPROVE": "Pending State Approval",
            "RETURN": "Returned",
            "REJECT": "Rejected",
        }[review.decision]
        details["workflowStatus"] = {
            Decision.APPROVE: Status.PENDING_STATE_APPROVAL,
            Decision.RETURN: Status.RETURNED_FOR_CORRECTION,
            Decision.REJECT: Status.REJECTED,
        }[review.decision]
    return details


def quality_details(
    db: Session, actor: User, batch_id: str, number: int | None
) -> dict:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found.")
    query = select(BatchRevision).where(BatchRevision.batch_id == batch_id)
    if number is not None:
        query = query.where(BatchRevision.number == number)
    revisions = db.scalars(query.order_by(BatchRevision.number.desc())).all()
    for revision in revisions:
        if revision.quality_review or eligible(db, batch, revision):
            return describe_quality(db, batch, revision, actor)
    raise HTTPException(404, "Batch not found.")


def quality_decision(
    db: Session,
    actor: User,
    batch_id: str,
    decision: Decision,
    request: QualityDecisionRequest,
) -> dict:
    if actor.role != Role.QUALITY_TEAM:
        raise HTTPException(403, "This account does not have access.")
    if decision != Decision.APPROVE and not request.comment:
        raise HTTPException(400, "Enter a reason for this decision.")
    batch = db.scalar(
        select(Batch).where(Batch.id == batch_id).with_for_update(of=Batch)
    )
    if not batch:
        raise HTTPException(404, "Batch not found.")
    revision = current_revision(db, batch)
    if candidate_count(db, revision.id) <= settings().quality_threshold:
        raise HTTPException(404, "Batch not found.")
    if request.revision != revision.number or not eligible(db, batch, revision):
        raise HTTPException(409, "This revision is no longer open for quality review.")
    validation = describe_batch(db, batch, revision, actor)["validation"]
    if decision == Decision.APPROVE and (
        validation["technical"] or validation["batchFindings"]
    ):
        raise HTTPException(422, "This batch has blocking validation errors.")
    revision.quality_review = QualityReview(
        reviewer_id=actor.id,
        decision=decision,
        comment=request.comment,
        created_at=utc_now(),
    )
    batch.status = {
        Decision.APPROVE: Status.PENDING_STATE_APPROVAL,
        Decision.RETURN: Status.RETURNED_FOR_CORRECTION,
        Decision.REJECT: Status.REJECTED,
    }[decision]
    if decision == Decision.APPROVE:
        revision.state_queued_at = revision.quality_review.created_at
    batch.version += 1
    audit(db, revision, actor, f"QUALITY_{decision}", request.comment or None)
    db.flush()
    db.expire(revision, ["audit"])
    return describe_quality(db, batch, revision, actor)
