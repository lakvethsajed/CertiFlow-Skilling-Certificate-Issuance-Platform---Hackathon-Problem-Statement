from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import CentreActor, Db, DistrictActor, QualityActor
from app.models import Batch, Certificate, Decision
from app.models import BatchStatus as Status
from app.schemas import (
    QualityDashboard,
    QualityDecisionRequest,
    QualityQueuePage,
    QualityQueueQuery,
)
from app.services.batches import (
    DISTRICT_ADVANCED,
    DISTRICT_OPEN,
    approval_count,
    audit,
    candidate_count,
    current_revision,
    describe_batch,
    legacy_iso,
    save_batch,
    scope,
    scoped_batch,
    summary,
)
from app.services.district import district_decision
from app.services.quality import (
    quality_dashboard,
    quality_decision,
    quality_details,
    quality_queue,
)
from app.services.validation import BatchInput

router = APIRouter()
Action = Literal["approve", "return", "reject"]
DistrictView = Literal["pending", "approved", "returned", "rejected", "history"]
DISTRICT_VIEWS = {
    "pending": DISTRICT_OPEN,
    "approved": DISTRICT_ADVANCED,
    "returned": (Status.RETURNED_FOR_CORRECTION,),
    "rejected": (Status.REJECTED,),
}


@router.get("/centre/batches")
def centre_batches(db: Db, actor: CentreActor) -> list[dict]:
    batches = db.scalars(
        select(Batch).where(scope(actor)).order_by(Batch.created_at.desc())
    )
    return [
        describe_batch(db, batch, current_revision(db, batch), actor)
        for batch in batches
    ]


@router.post("/centre/batches", status_code=201)
def create_batch(data: BatchInput, db: Db, actor: CentreActor) -> dict:
    result = save_batch(db, actor, data)
    db.commit()
    return result


@router.put("/centre/batches/{batch_id}")
def update_batch(batch_id: UUID, data: BatchInput, db: Db, actor: CentreActor) -> dict:
    result = save_batch(db, actor, data, str(batch_id))
    db.commit()
    return result


@router.get("/district/dashboard")
def district_dashboard(db: Db, actor: DistrictActor) -> dict:
    batches = list(db.scalars(select(Batch).where(scope(actor))))
    return {
        **{
            key: sum(batch.status in statuses for batch in batches)
            for key, statuses in DISTRICT_VIEWS.items()
        },
        "reviewed": sum(
            any(revision.approvals for revision in batch.revisions) for batch in batches
        ),
    }


@router.get("/district/batches")
def district_batches(
    db: Db, actor: DistrictActor, view: DistrictView = "pending"
) -> list[dict]:
    query = select(Batch).where(scope(actor)).order_by(Batch.created_at.desc())
    if view != "history":
        query = query.where(Batch.status.in_(DISTRICT_VIEWS[view]))
    results = []
    for batch in db.scalars(query):
        if view == "history" and not any(
            revision.approvals for revision in batch.revisions
        ):
            continue
        revision = current_revision(db, batch)
        results.append(
            summary(
                batch,
                revision,
                candidate_count(db, revision.id),
                approval_count(db, revision.id),
            )
        )
    return results


@router.get("/district/batches/{batch_id}")
def district_details(batch_id: UUID, db: Db, actor: DistrictActor) -> dict:
    batch = scoped_batch(db, str(batch_id), actor)
    revision = current_revision(db, batch)
    audit(db, revision, actor, "OPENED")
    result = describe_batch(db, batch, revision, actor)
    db.commit()
    return result


@router.post("/district/batches/{batch_id}/{action}")
def decide_district(
    batch_id: UUID,
    action: Action,
    data: QualityDecisionRequest,
    db: Db,
    actor: DistrictActor,
) -> dict:
    result = district_decision(db, actor, str(batch_id), Decision(action.upper()), data)
    db.commit()
    return result


@router.get("/quality/dashboard")
def dashboard(db: Db, _actor: QualityActor) -> QualityDashboard:
    return quality_dashboard(db)


@router.get("/quality/batches")
def queue(
    params: Annotated[QualityQueueQuery, Query()], db: Db, _actor: QualityActor
) -> QualityQueuePage:
    return quality_queue(db, params)


@router.get("/quality/batches/{batch_id}")
def details(
    batch_id: UUID,
    db: Db,
    actor: QualityActor,
    revision: Annotated[int | None, Query(gt=0)] = None,
) -> dict:
    return quality_details(db, actor, str(batch_id), revision)


@router.get("/quality/batches/{batch_id}/history")
def history(
    batch_id: UUID,
    db: Db,
    actor: QualityActor,
    revision: Annotated[int | None, Query(gt=0)] = None,
) -> dict:
    result = quality_details(db, actor, str(batch_id), revision)
    return {"decisions": result["decisions"], "history": result["history"]}


@router.post("/quality/batches/{batch_id}/{action}")
def decide_quality(
    batch_id: UUID,
    action: Action,
    data: QualityDecisionRequest,
    db: Db,
    actor: QualityActor,
) -> dict:
    result = quality_decision(db, actor, str(batch_id), Decision(action.upper()), data)
    db.commit()
    return result


@router.get("/certificates/{code}")
def verify(code: str, db: Db) -> dict:
    if len(code) > 128:
        raise HTTPException(400, "Invalid certificate code.")
    certificate = db.scalar(
        select(Certificate)
        .join(Batch)
        .where(Certificate.code == code, Batch.status == Status.CERTIFICATES_GENERATED)
    )
    if certificate is None:
        raise HTTPException(404, "Certificate not found.")
    return {"code": certificate.code, "issuedAt": legacy_iso(certificate.issued_at)}
