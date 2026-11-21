from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.dependencies import legacy_now
from app.models import (
    Approval,
    AuditLog,
    Batch,
    BatchRevision,
    Candidate,
    CandidateCertificate,
    Decision,
    Role,
    TrainingCentre,
    User,
)
from app.models import (
    BatchStatus as Status,
)
from app.services.validation import BatchInput, inspect_batch, validate_upload

REQUIRED_APPROVALS = 2
DISTRICT_OPEN = (Status.SUBMITTED, Status.UNDER_REVIEW)
DISTRICT_ADVANCED = (
    Status.PENDING_QUALITY_REVIEW,
    Status.PENDING_STATE_APPROVAL,
    Status.FINAL_APPROVED,
    Status.CERTIFICATES_GENERATED,
)
LABELS = {
    Status.DRAFT: "Draft",
    Status.SUBMITTED: "Submitted",
    Status.UNDER_REVIEW: "Under Review",
    Status.RETURNED_FOR_CORRECTION: "Returned",
    Status.REJECTED: "Rejected",
    Status.PENDING_QUALITY_REVIEW: "Pending Quality Review",
    Status.PENDING_STATE_APPROVAL: "Pending State Approval",
    Status.FINAL_APPROVED: "Final Approved",
    Status.CERTIFICATES_GENERATED: "Certificates Generated",
}
AUDIT_LABELS = {
    "ACTIVATION_CODES_EXPORTED": "Training Centre exported activation codes",
    "ACTIVATION_CODES_REGENERATED": "Training Centre regenerated an activation code",
    "STUDENT_ACTIVATED": "Student activated their account",
    "SUBMITTED": "Submitted by Training Centre",
    "RESUBMITTED": "Corrected batch resubmitted",
    "ADVANCED": "District review completed",
    "APPROVE": "District officer approved",
    "RETURN": "Returned by District Officer",
    "REJECT": "Rejected by District Officer",
    "QUALITY_APPROVE": "Quality Team approved",
    "QUALITY_RETURN": "Returned by Quality Team",
    "QUALITY_REJECT": "Rejected by Quality Team",
    "STATE_APPROVE": "State Office approved",
    "STATE_RETURN": "Returned by State Office",
    "STATE_REJECT": "Rejected by State Office",
    "QUALITY_ROUTING_RECONCILED": "Quality routing reconciled at cutover",
}


def legacy_iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=UTC).isoformat() if value else None


def scope(actor: User):
    if actor.role == Role.TRAINING_CENTRE:
        return Batch.centre_id == actor.centre_id
    if actor.role == Role.DISTRICT_OFFICER:
        return (Batch.status != Status.DRAFT) & Batch.centre.has(
            TrainingCentre.district_id == actor.district_id
        )
    raise HTTPException(403, "This account does not have access.")


def scoped_batch(
    db: Session, batch_id: str, actor: User, *, lock: bool = False
) -> Batch:
    query = select(Batch).where(Batch.id == batch_id, scope(actor))
    batch = db.scalar(query.with_for_update(of=Batch) if lock else query)
    if batch is None:
        raise HTTPException(404, "Batch not found.")
    return batch


def current_revision(db: Session, batch: Batch) -> BatchRevision:
    revision = db.scalar(
        select(BatchRevision).where(
            BatchRevision.batch_id == batch.id, BatchRevision.number == batch.revision
        )
    )
    if revision is None:
        raise HTTPException(409, "The current batch revision is unavailable.")
    return revision


def candidate_count(db: Session, revision_id: str) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Candidate)
            .where(Candidate.revision_id == revision_id)
        )
        or 0
    )


def approval_count(db: Session, revision_id: str) -> int:
    return (
        db.scalar(
            select(func.count(func.distinct(Approval.officer_id))).where(
                Approval.revision_id == revision_id,
                Approval.decision == Decision.APPROVE,
            )
        )
        or 0
    )


def audit(
    db: Session,
    revision: BatchRevision,
    actor: User,
    action: str,
    comment: str | None = None,
) -> None:
    db.add(
        AuditLog(
            revision_id=revision.id,
            actor_id=actor.id,
            actor_role=actor.role,
            action=action,
            comment=comment,
            created_at=legacy_now(),
        )
    )


def summary(batch: Batch, revision: BatchRevision, count: int, approved: int) -> dict:
    return {
        "id": batch.id,
        "name": revision.form["name"],
        "course": revision.form["course"],
        "centre": batch.centre.name,
        "district": batch.centre.district.name,
        "submittedAt": legacy_iso(revision.submitted_at),
        "count": count,
        "status": LABELS[batch.status],
        "approvalsReceived": approved,
        "approvalsRequired": REQUIRED_APPROVALS,
    }


def describe_batch(
    db: Session, batch: Batch, revision: BatchRevision, actor: User
) -> dict:
    candidates = sorted(revision.candidates, key=lambda item: item.row_number)
    students = [item.data for item in candidates]
    validation = inspect_batch(revision.form, students)
    errors = {item["rowNumber"]: item["errors"] for item in validation["technical"]}
    approvals = sorted(revision.approvals, key=lambda item: (item.created_at, item.id))
    approved = sum(item.decision == Decision.APPROVE for item in approvals)
    review = revision.quality_review
    state = revision.state_review
    last = state or review or (approvals[-1] if approvals else None)
    stage = 0 if batch.status == Status.DRAFT else 1
    if approvals:
        stage = min(3, 2 + approved)
    if batch.status == Status.UNDER_REVIEW:
        stage = 3
    if batch.status in DISTRICT_ADVANCED:
        stage = 3
    if review:
        stage = 4
    if state:
        stage = 5
    if batch.status == Status.CERTIFICATES_GENERATED:
        stage = 6

    decisions = []
    history = [{"label": "Batch created", "date": legacy_iso(batch.created_at)}]
    revisions = db.scalars(
        select(BatchRevision)
        .where(
            BatchRevision.batch_id == batch.id, BatchRevision.number <= revision.number
        )
        .order_by(BatchRevision.number)
    ).all()
    for entry in revisions:
        for item in sorted(entry.approvals, key=lambda row: (row.created_at, row.id)):
            decisions.append(
                {
                    "id": item.id,
                    "officer": item.officer.name,
                    "role": "District Officer",
                    "decision": item.decision,
                    "date": legacy_iso(item.created_at),
                    "comment": item.comment,
                    "revision": entry.number,
                }
            )
        if item := entry.quality_review:
            decisions.append(
                {
                    "id": "quality-" + entry.id,
                    "officer": item.reviewer.name,
                    "role": "Quality Team",
                    "decision": item.decision,
                    "date": item.created_at.isoformat(),
                    "comment": item.comment,
                    "revision": entry.number,
                }
            )
        if item := entry.state_review:
            decisions.append(
                {
                    "id": "state-" + entry.id,
                    "officer": item.reviewer.name,
                    "role": "State Office",
                    "decision": item.decision,
                    "date": item.created_at.isoformat(),
                    "comment": item.comment,
                    "revision": entry.number,
                }
            )
        history.extend(
            {
                "label": AUDIT_LABELS[event.action],
                "date": legacy_iso(event.created_at),
                "note": event.comment,
                "revision": entry.number,
            }
            for event in sorted(entry.audit, key=lambda row: (row.created_at, row.id))
            if event.action in AUDIT_LABELS
        )
    reason = None
    if last and last.decision in (Decision.RETURN, Decision.REJECT):
        reason = AUDIT_LABELS.get(
            f"STATE_{last.decision}"
            if state
            else f"QUALITY_{last.decision}"
            if review
            else str(last.decision)
        )
    returned_at = None
    if last and last.decision == Decision.RETURN:
        returned_at = (
            last.created_at.isoformat()
            if (state or review)
            else legacy_iso(last.created_at)
        )
    return {
        **revision.form,
        **summary(batch, revision, len(students), approved),
        "workflowStatus": batch.status,
        "version": batch.version,
        "revision": revision.number,
        "stage": stage,
        "qualityRequired": batch.quality_required,
        "createdAt": legacy_iso(batch.created_at),
        "upload": revision.upload,
        "students": [
            {**item, "errors": errors.get(item["rowNumber"], [])} for item in students
        ],
        "certificatesIssued": int(batch.certificate is not None)
        + (
            db.scalar(
                select(func.count())
                .select_from(CandidateCertificate)
                .join(Candidate, Candidate.id == CandidateCertificate.candidate_id)
                .where(Candidate.revision_id == revision.id)
            )
            if batch.status == Status.CERTIFICATES_GENERATED
            else 0
        ),
        "correctionDraft": batch.correction_draft
        if actor.role == Role.TRAINING_CENTRE
        else None,
        "reason": reason,
        "comment": last.comment if reason else None,
        "returnedAt": returned_at,
        "canReview": (
            actor.role == Role.DISTRICT_OFFICER
            and batch.status in DISTRICT_OPEN
            and all(item.officer_id != actor.id for item in approvals)
        ),
        "decisions": decisions,
        "history": history,
        "validation": validation,
    }


def save_batch(
    db: Session, actor: User, data: BatchInput, batch_id: str | None = None
) -> dict:
    form, students = validate_upload(data)
    upload = data.upload.model_dump(exclude={"students"}) if data.upload else None
    batch = scoped_batch(db, batch_id, actor, lock=True) if batch_id else None
    returned = bool(batch and batch.status == Status.RETURNED_FOR_CORRECTION)
    if batch and (
        batch.version != data.version or not (returned or batch.status == Status.DRAFT)
    ):
        raise HTTPException(409, "This batch changed. Reload it before editing.")
    if batch and returned and not data.submit:
        batch.correction_draft = {
            **form,
            "centre": batch.centre.name,
            "district": batch.centre.district.name,
            "students": students,
            "upload": upload,
        }
        batch.version += 1
        db.flush()
        return describe_batch(db, batch, current_revision(db, batch), actor)
    if batch is None:
        batch = Batch(
            centre_id=actor.centre_id, quality_required=False, created_at=legacy_now()
        )
        db.add(batch)
        db.flush()
        revision = BatchRevision(batch_id=batch.id, number=1, form=form)
        db.add(revision)
    elif returned:
        batch.revision += 1
        batch.version += 1
        revision = BatchRevision(batch_id=batch.id, number=batch.revision, form=form)
        db.add(revision)
    else:
        batch.version += 1
        revision = current_revision(db, batch)
        db.execute(delete(Candidate).where(Candidate.revision_id == revision.id))
    batch.status = Status.SUBMITTED if data.submit else Status.DRAFT
    batch.correction_draft = None
    batch.quality_required = False
    revision.form = form
    revision.upload = upload
    revision.submitted_at = legacy_now() if data.submit else None
    db.flush()
    db.add_all(
        Candidate(revision_id=revision.id, row_number=item["rowNumber"], data=item)
        for item in students
    )
    if data.submit:
        audit(db, revision, actor, "RESUBMITTED" if returned else "SUBMITTED")
    db.flush()
    return describe_batch(db, batch, revision, actor)
