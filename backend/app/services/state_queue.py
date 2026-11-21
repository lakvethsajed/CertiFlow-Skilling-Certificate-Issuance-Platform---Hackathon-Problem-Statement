from datetime import timedelta

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import utc_now
from app.models import (
    Approval,
    AuditLog,
    Batch,
    BatchRevision,
    Candidate,
    CandidateCertificate,
    Certificate,
    Decision,
    District,
    IssuanceRequest,
    QualityReview,
    StateReview,
    TrainingCentre,
    User,
)
from app.models import BatchStatus as Status
from app.services.batches import REQUIRED_APPROVALS
from app.services.state import STATE_DECISION_STATUSES
from app.state_schemas import (
    StateActivity,
    StateDashboard,
    StateQueueItem,
    StateQueuePage,
    StateQueueQuery,
)

CANDIDATES = (
    select(func.count())
    .select_from(Candidate)
    .where(Candidate.revision_id == BatchRevision.id)
    .correlate(BatchRevision)
    .scalar_subquery()
)
DISTRICT_APPROVALS = (
    select(func.count(func.distinct(Approval.officer_id)))
    .where(
        Approval.revision_id == BatchRevision.id, Approval.decision == Decision.APPROVE
    )
    .correlate(BatchRevision)
    .scalar_subquery()
)
DISTRICT_BLOCK = (
    select(Approval.id)
    .where(
        Approval.revision_id == BatchRevision.id, Approval.decision != Decision.APPROVE
    )
    .correlate(BatchRevision)
    .exists()
)
LEGACY_HANDOFF = (
    select(func.max(AuditLog.created_at))
    .where(
        AuditLog.revision_id == BatchRevision.id,
        AuditLog.action.in_(("ADVANCED", "QUALITY_ROUTING_RECONCILED")),
    )
    .correlate(BatchRevision)
    .scalar_subquery()
)
QUEUED_AT = func.coalesce(
    BatchRevision.state_queued_at,
    QualityReview.created_at,
    func.timezone("UTC", LEGACY_HANDOFF),
)
CURRENT_REVISION = Batch.revision == BatchRevision.number


def pending_conditions() -> tuple:
    return (
        CURRENT_REVISION,
        Batch.status == Status.PENDING_STATE_APPROVAL,
        StateReview.revision_id.is_(None),
        BatchRevision.submitted_at.is_not(None),
        CANDIDATES > 0,
        DISTRICT_APPROVALS >= REQUIRED_APPROVALS,
        ~DISTRICT_BLOCK,
        or_(
            QualityReview.decision == Decision.APPROVE,
            and_(
                QualityReview.revision_id.is_(None),
                CANDIDATES <= settings().quality_threshold,
            ),
        ),
    )


def queue_base() -> Select:
    return (
        select(
            Batch.id.label("batch_id"),
            BatchRevision.number.label("revision"),
            BatchRevision.form["name"].astext.label("name"),
            BatchRevision.form["course"].astext.label("course"),
            TrainingCentre.name.label("centre"),
            District.name.label("district"),
            CANDIDATES.label("candidate_count"),
            DISTRICT_APPROVALS.label("district_approval_count"),
            QualityReview.decision.label("quality_decision"),
            StateReview.decision.label("decision"),
            Batch.status.label("batch_status"),
            CURRENT_REVISION.label("is_current"),
            QUEUED_AT.label("state_queued_at"),
        )
        .select_from(Batch)
        .join(BatchRevision, BatchRevision.batch_id == Batch.id)
        .join(TrainingCentre, TrainingCentre.id == Batch.centre_id)
        .join(District, District.id == TrainingCentre.district_id)
        .outerjoin(QualityReview, QualityReview.revision_id == BatchRevision.id)
        .outerjoin(StateReview, StateReview.revision_id == BatchRevision.id)
    )


def awaiting_issuance() -> tuple:
    return (
        CURRENT_REVISION,
        Batch.status == Status.FINAL_APPROVED,
        StateReview.decision == Decision.APPROVE,
        IssuanceRequest.revision_id.is_not(None),
    )


def delayed_conditions() -> tuple:
    deadline = utc_now() - timedelta(hours=settings().state_delay_hours)
    return (
        or_(
            and_(*pending_conditions(), QUEUED_AT <= deadline),
            and_(*awaiting_issuance(), IssuanceRequest.created_at <= deadline),
        ),
    )


def state_queue(db: Session, params: StateQueueQuery) -> StateQueuePage:
    query = queue_base()
    sort_date = QUEUED_AT
    if params.view == "pending":
        query = query.where(*pending_conditions())
    elif params.view == "delayed":
        query = query.outerjoin(
            IssuanceRequest, IssuanceRequest.revision_id == BatchRevision.id
        ).where(*delayed_conditions())
        sort_date = case(
            (Batch.status == Status.FINAL_APPROVED, IssuanceRequest.created_at),
            else_=QUEUED_AT,
        )
    else:
        query = query.where(StateReview.revision_id.is_not(None))
        sort_date = StateReview.created_at
        decision = {
            "approved": Decision.APPROVE,
            "returned": Decision.RETURN,
            "rejected": Decision.REJECT,
        }.get(params.view)
        if decision:
            query = query.where(StateReview.decision == decision)

    if search := params.search.strip().lower():
        query = query.where(
            or_(
                func.lower(Batch.id).contains(search, autoescape=True),
                func.lower(BatchRevision.form["name"].astext).contains(
                    search, autoescape=True
                ),
                func.lower(TrainingCentre.name).contains(search, autoescape=True),
            )
        )
    if params.course and params.course.strip():
        query = query.where(
            func.lower(BatchRevision.form["course"].astext)
            == params.course.strip().lower()
        )
    if params.district and params.district.strip():
        query = query.where(
            func.lower(District.name) == params.district.strip().lower()
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = sort_date.asc() if params.sort == "oldest" else sort_date.desc()
    rows = db.execute(
        query.order_by(order.nulls_last(), BatchRevision.id)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    records = []
    for row in rows:
        status = (
            row.batch_status
            if row.is_current
            else STATE_DECISION_STATUSES[row.decision]
        )
        records.append(
            StateQueueItem(
                batch_id=row.batch_id,
                revision=row.revision,
                name=row.name,
                centre=row.centre,
                district=row.district,
                course=row.course,
                candidate_count=row.candidate_count,
                district_approval_count=row.district_approval_count,
                quality_status="APPROVED"
                if row.quality_decision == Decision.APPROVE
                else "NOT_REQUIRED",
                state_queued_at=row.state_queued_at,
                status=status,
            )
        )
    return StateQueuePage(
        records=records, total=total, page=params.page, page_size=params.page_size
    )


def state_dashboard(db: Session) -> StateDashboard:
    totals = dict(
        db.execute(
            select(StateReview.decision, func.count()).group_by(StateReview.decision)
        ).all()
    )
    delayed = (
        queue_base()
        .outerjoin(IssuanceRequest, IssuanceRequest.revision_id == BatchRevision.id)
        .where(*delayed_conditions())
    )
    pending_certificates = (
        select(func.coalesce(func.sum(CANDIDATES), 0))
        .select_from(Batch)
        .join(BatchRevision, BatchRevision.batch_id == Batch.id)
        .join(StateReview, StateReview.revision_id == BatchRevision.id)
        .join(IssuanceRequest, IssuanceRequest.revision_id == BatchRevision.id)
        .where(*awaiting_issuance())
    )
    recent = db.execute(
        select(StateReview, BatchRevision, User.name)
        .join(BatchRevision, BatchRevision.id == StateReview.revision_id)
        .join(User, User.id == StateReview.reviewer_id)
        .order_by(StateReview.created_at.desc(), StateReview.revision_id)
        .limit(8)
    )
    return StateDashboard(
        pending=db.scalar(
            select(func.count()).select_from(
                queue_base().where(*pending_conditions()).subquery()
            )
        )
        or 0,
        approved=totals.get(Decision.APPROVE, 0),
        returned=totals.get(Decision.RETURN, 0),
        rejected=totals.get(Decision.REJECT, 0),
        certificates_generated=(
            db.scalar(select(func.count()).select_from(Certificate)) or 0
        )
        + (db.scalar(select(func.count()).select_from(CandidateCertificate)) or 0),
        certificates_pending=db.scalar(pending_certificates) or 0,
        delayed=db.scalar(select(func.count()).select_from(delayed.subquery())) or 0,
        activity=[
            StateActivity(
                batch_id=revision.batch_id,
                batch_name=revision.form["name"],
                revision=revision.number,
                reviewer=name,
                decision=review.decision,
                comment=review.comment,
                created_at=review.created_at,
            )
            for review, revision, name in recent
        ],
    )
