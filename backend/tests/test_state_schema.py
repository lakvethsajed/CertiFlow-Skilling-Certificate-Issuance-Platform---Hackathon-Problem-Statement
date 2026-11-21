import os
from collections.abc import Callable
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DatabaseSession

from app.database import create_database_engine
from app.dependencies import StateActor, require_session
from app.models import (
    Batch,
    BatchRevision,
    BatchStatus,
    Decision,
    District,
    Role,
    StateReview,
    TrainingCentre,
    User,
)
from app.models import Session as LoginSession
from app.state_schemas import (
    StateDecisionCommand,
    StateDecisionRequest,
    StateQueueQuery,
)


@pytest.mark.parametrize("decision", [Decision.RETURN, Decision.REJECT])
def test_state_decision_requires_nonblank_reason(decision: Decision) -> None:
    with pytest.raises(ValidationError, match="Enter a reason"):
        StateDecisionCommand(revision=1, decision=decision, comment=" \t ")
    command = StateDecisionCommand(
        revision=1, decision=decision, comment=" Check the records. "
    )
    assert command.comment == "Check the records."


def test_state_payload_disallows_client_actor_and_decision() -> None:
    for extra in [
        {"reviewer_id": "user"},
        {"decision": "APPROVE"},
        {"role": "STATE_OFFICE"},
    ]:
        with pytest.raises(ValidationError, match="Extra inputs"):
            StateDecisionRequest.model_validate({"revision": 1, **extra})
    with pytest.raises(ValidationError):
        StateDecisionRequest.model_validate({"revision": True})
    with pytest.raises(ValidationError):
        StateQueueQuery(page_size=101)
    assert StateDecisionCommand(revision=1, decision=Decision.APPROVE).comment == ""


def session_for(role: Role) -> Callable[[], LoginSession]:
    def authenticated_session() -> LoginSession:
        return LoginSession(user=User(role=role))

    return authenticated_session


def test_state_role_dependency_authorizes_only_state_office() -> None:
    app = FastAPI()

    @app.get("/state-test")
    def state_scope(actor: StateActor) -> dict[str, Role]:
        return {"role": actor.role}

    with TestClient(app) as client:
        assert client.get("/state-test").status_code == 401
        for role in Role:
            app.dependency_overrides[require_session] = session_for(role)
            response = client.get("/state-test")
            assert response.status_code == (200 if role == Role.STATE_OFFICE else 403)


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Provide a migrated test database"
)
def test_state_review_constraints_in_postgres() -> None:
    engine = create_database_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with DatabaseSession(engine) as db:
            centre = TrainingCentre(
                id=str(uuid4()),
                name="Test centre",
                district=District(id=str(uuid4()), name="Test district"),
            )
            batch = Batch(centre=centre, status=BatchStatus.FINAL_APPROVED)
            revision = BatchRevision(batch=batch, number=1, form={})
            reviewers = [
                User(
                    email=f"{uuid4()}@example.test",
                    name="Test reviewer",
                    password_hash="unused test value",
                    role=Role.STATE_OFFICE,
                )
                for _ in range(2)
            ]
            db.add_all([revision, *reviewers])
            db.flush()
            for decision in (Decision.RETURN, Decision.REJECT):
                with (
                    pytest.raises(
                        IntegrityError, match="StateReview_decision_comment_check"
                    ),
                    db.begin_nested(),
                ):
                    db.add(
                        StateReview(
                            revision_id=revision.id,
                            reviewer=reviewers[0],
                            decision=decision,
                            comment=" \t ",
                        )
                    )
                    db.flush()
            db.add(
                StateReview(
                    revision_id=revision.id,
                    reviewer=reviewers[0],
                    decision=Decision.APPROVE,
                )
            )
            db.flush()
            with (
                pytest.raises(IntegrityError, match="StateReview_pkey"),
                db.begin_nested(),
            ):
                db.add(
                    StateReview(
                        revision_id=revision.id,
                        reviewer=reviewers[1],
                        decision=Decision.APPROVE,
                    )
                )
                db.flush()
            assert batch.status == BatchStatus.FINAL_APPROVED
            db.rollback()
    finally:
        engine.dispose()
