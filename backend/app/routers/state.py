from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from app.dependencies import Db, StateActor
from app.models import Decision
from app.services.state import state_batch_details, state_decision
from app.services.state_queue import state_dashboard, state_queue
from app.state_schemas import (
    StateDashboard,
    StateDecisionCommand,
    StateDecisionRequest,
    StateDecisionResult,
    StateQueuePage,
    StateQueueQuery,
)

router = APIRouter(prefix="/state", tags=["State Office"])
Action = Literal["approve", "return", "reject"]


@router.get("/dashboard")
def dashboard(db: Db, _actor: StateActor) -> StateDashboard:
    return state_dashboard(db)


@router.get("/batches")
def batches(
    params: Annotated[StateQueueQuery, Query()], db: Db, _actor: StateActor
) -> StateQueuePage:
    return state_queue(db, params)


@router.get("/batches/{batch_id}")
def batch_details(
    batch_id: UUID,
    db: Db,
    actor: StateActor,
    revision: Annotated[int | None, Query(gt=0)] = None,
) -> dict:
    return state_batch_details(db, actor, str(batch_id), revision)


@router.get("/batches/{batch_id}/history")
def batch_history(
    batch_id: UUID,
    db: Db,
    actor: StateActor,
    revision: Annotated[int | None, Query(gt=0)] = None,
) -> dict:
    details = state_batch_details(db, actor, str(batch_id), revision)
    return {"decisions": details["decisions"], "history": details["history"]}


@router.post("/batches/{batch_id}/{action}")
def decide_state(
    batch_id: UUID,
    action: Action,
    data: StateDecisionRequest,
    db: Db,
    actor: StateActor,
) -> StateDecisionResult:
    try:
        command = StateDecisionCommand(
            **data.model_dump(), decision=Decision(action.upper())
        )
    except ValidationError as error:
        raise HTTPException(400, "Enter a reason for this decision.") from error
    result = state_decision(db, actor, str(batch_id), command)
    db.commit()
    return result
