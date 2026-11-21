import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import engine, utc_now
from app.main import app
from app.models import (
    AuditLog,
    Batch,
    BatchRevision,
    BatchStatus,
    District,
    IssuanceRequest,
    Role,
    StateReview,
    TrainingCentre,
    User,
)
from app.reconcile_quality import reconcile

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Requires PostgreSQL"
)
FORM = {
    "name": "Quality test batch",
    "course": "Python",
    "trainer": "Test trainer",
    "startDate": "2026-10-01",
    "endDate": "2026-10-20",
    "assessmentDate": "2026-10-21",
    "description": "",
}


@pytest.fixture(scope="module")
def clients():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
        patch.setenv("JWT_SECRET", "test-secret-for-sqlalchemy-integration-only")
        patch.setenv("QUALITY_THRESHOLD", "50")
        patch.setenv("NODE_ENV", "development")
        settings.cache_clear()
        engine.cache_clear()
        key = uuid4().hex
        password = "test-password-only"
        password_hash = bcrypt.hashpw(
            password.encode(), bcrypt.gensalt(rounds=4)
        ).decode()
        roles = {
            "centre": Role.TRAINING_CENTRE,
            "one": Role.DISTRICT_OFFICER,
            "two": Role.DISTRICT_OFFICER,
            "other": Role.DISTRICT_OFFICER,
            "quality": Role.QUALITY_TEAM,
            "second_quality": Role.QUALITY_TEAM,
            "state": Role.STATE_OFFICE,
            "second_state": Role.STATE_OFFICE,
        }
        emails = {name: f"{name}-{key}@example.test" for name in roles}
        with Session(engine()) as db:
            district = District(id=key, name="Workflow district " + key)
            outside = District(id=key + "-other", name="Unrelated district")
            centre = TrainingCentre(id=key, name="Workflow centre", district=district)
            db.add_all(
                [
                    User(
                        email=emails[name],
                        name=name,
                        password_hash=password_hash,
                        role=role,
                        district=outside
                        if name == "other"
                        else district
                        if role == Role.DISTRICT_OFFICER
                        else None,
                        centre=centre if role == Role.TRAINING_CENTRE else None,
                    )
                    for name, role in roles.items()
                ]
            )
            db.commit()
        api = {name: TestClient(app) for name in (*roles, "anonymous")}
        for name, role in roles.items():
            response = api[name].post(
                "/api/auth/login", json={"email": emails[name], "password": password}
            )
            assert response.status_code == 200, response.text
            assert api[name].get("/api/auth/session").json()["user"]["role"] == role
        yield api
        for client in api.values():
            client.close()
        engine().dispose()
        engine.cache_clear()
        settings.cache_clear()


def batch_payload(count: int) -> dict:
    students = [
        {
            "rowNumber": index + 2,
            "student_name": "Test Candidate",
            "student_id": f"test-{index}",
            "email": f"candidate-{index}@example.test",
            "phone_number": "9990000001",
            "course_name": "Python",
            "marks": "90",
            "assessment_date": "2026-10-21",
        }
        for index in range(count)
    ]
    return {
        "form": FORM,
        "upload": {"name": "candidates.csv", "size": 100, "students": students},
        "submit": True,
        "confirmed": True,
    }


def submit(clients: dict, count: int) -> dict:
    result = clients["centre"].post("/api/centre/batches", json=batch_payload(count))
    assert result.status_code == 201, result.text
    return result.json()


def decide(
    client: TestClient,
    kind: str,
    batch: dict,
    action: str = "approve",
    comment: str = "",
):
    return client.post(
        f"/api/{kind}/batches/{batch['id']}/{action}",
        json={"revision": batch["revision"], "comment": comment},
    )


def district_approve(clients: dict, batch: dict) -> dict:
    first = decide(clients["one"], "district", batch)
    assert first.status_code == 200, first.text
    assert first.json()["workflowStatus"] == "UNDER_REVIEW"
    assert decide(clients["one"], "district", batch).status_code == 409
    second = decide(clients["two"], "district", batch)
    assert second.status_code == 200, second.text
    return second.json()


@pytest.mark.parametrize(
    ("count", "status"),
    [
        (50, "PENDING_STATE_APPROVAL"),
        (51, "PENDING_QUALITY_REVIEW"),
        (60, "PENDING_QUALITY_REVIEW"),
    ],
)
def test_persisted_count_and_distinct_approvals(
    clients: dict, count: int, status: str
) -> None:
    batch = submit(clients, count)
    quality = clients["quality"]
    path = f"/api/quality/batches/{batch['id']}"
    assert quality.get(path).status_code == 404
    assert (
        clients["other"].get(f"/api/district/batches/{batch['id']}").status_code == 404
    )
    advanced = district_approve(clients, batch)
    assert advanced["workflowStatus"] == status
    assert quality.get(path).status_code == (404 if count == 50 else 200)
    if count == 50:
        assert decide(quality, "quality", batch).status_code == 404
    else:
        result = quality.get("/api/quality/batches", params={"search": batch["id"]})
        assert result.status_code == 200, result.text
        assert result.json()["records"][0]["candidate_count"] == count
        assert result.json()["records"][0]["district_approval_count"] == 2


def test_roles_and_fresh_approvals_after_quality_return(clients: dict) -> None:
    batch = district_approve(clients, submit(clients, 51))
    path = f"/api/quality/batches/{batch['id']}"
    assert clients["centre"].get("/api/quality/dashboard").status_code == 403
    assert decide(clients["one"], "quality", batch).status_code == 403
    assert decide(clients["anonymous"], "quality", batch).status_code == 401
    quality = clients["quality"]
    assert decide(quality, "quality", batch, "return", "  ").status_code == 400
    returned = decide(quality, "quality", batch, "return", "Correct photo details.")
    assert returned.status_code == 200, returned.text
    assert returned.json()["workflowStatus"] == "RETURNED_FOR_CORRECTION"
    centre = clients["centre"]
    stored = next(
        item
        for item in centre.get("/api/centre/batches").json()
        if item["id"] == batch["id"]
    )
    assert stored["comment"] == "Correct photo details."
    revision = centre.put(
        f"/api/centre/batches/{batch['id']}",
        json={**batch_payload(51), "version": stored["version"]},
    )
    assert revision.status_code == 200, revision.text
    revision_two = revision.json()
    assert revision_two["revision"] == 2
    assert revision_two["approvalsReceived"] == 0
    assert quality.get(path, params={"revision": 2}).status_code == 404
    assert (
        quality.get(path, params={"revision": 1}).json()["qualityDecision"] == "RETURN"
    )
    assert (
        district_approve(clients, revision_two)["workflowStatus"]
        == "PENDING_QUALITY_REVIEW"
    )
    assert decide(quality, "quality", batch).status_code == 409
    assert (
        decide(quality, "quality", revision_two).json()["workflowStatus"]
        == "PENDING_STATE_APPROVAL"
    )


def test_rejection_requires_reason_and_ends_workflow(clients: dict) -> None:
    batch = district_approve(clients, submit(clients, 51))
    quality = clients["quality"]
    assert decide(quality, "quality", batch, "reject").status_code == 400
    result = decide(
        quality, "quality", batch, "reject", "Assessment records incomplete."
    )
    assert result.status_code == 200, result.text
    assert result.json()["workflowStatus"] == "REJECTED"
    assert decide(quality, "quality", batch).status_code == 409
    assert decide(clients["one"], "district", batch).status_code == 409
    history = quality.get(f"/api/quality/batches/{batch['id']}/history").json()
    assert any(
        "Rejected by Quality Team" == item["label"] for item in history["history"]
    )


def test_concurrent_quality_decisions_commit_once(clients: dict) -> None:
    batch = district_approve(clients, submit(clients, 60))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda name: decide(clients[name], "quality", batch),
                ("quality", "second_quality"),
            )
        )
    assert sorted(result.status_code for result in results) == [200, 409]
    assert (
        next(result for result in results if result.status_code == 200).json()[
            "workflowStatus"
        ]
        == "PENDING_STATE_APPROVAL"
    )
    with Session(engine()) as db:
        logs = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .join(BatchRevision)
            .where(
                BatchRevision.batch_id == batch["id"],
                AuditLog.action == "QUALITY_APPROVE",
            )
        )
        assert logs == 1
    dashboard = clients["quality"].get("/api/quality/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["approved"] >= 1
    reviewed = clients["quality"].get(
        "/api/quality/batches",
        params={
            "view": "approved",
            "search": batch["id"],
            "course": "python",
            "page_size": 1,
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["total"] == 1
    assert reviewed.json()["records"][0]["batch_id"] == batch["id"]


def test_reconcile_legacy_queue_uses_actual_count_and_is_idempotent(
    clients: dict,
) -> None:
    small = district_approve(clients, submit(clients, 50))
    large = district_approve(clients, submit(clients, 51))
    with Session(engine()) as db:
        batches = [db.get(Batch, item["id"]) for item in (small, large)]
        for batch in batches:
            batch.status = BatchStatus.PENDING_QUALITY_REVIEW
            batch.quality_required = True
            batch.revisions[0].quality_queued_at = None
        db.flush()
        result = reconcile(db, 50)
        assert result == {"queued": 1, "bypassed": 1, "requires_manual_review": 0}
        assert batches[0].status == BatchStatus.PENDING_STATE_APPROVAL
        assert batches[1].revisions[0].quality_queued_at is not None
        assert not any(reconcile(db, 50).values())
        db.rollback()


def test_invalid_upload_and_draft_visibility(clients: dict) -> None:
    invalid = batch_payload(1)
    invalid["upload"]["students"][0]["email"] = "invalid"
    result = clients["centre"].post("/api/centre/batches", json=invalid)
    assert result.status_code == 422
    assert result.json()["details"]["technical"][0]["rowNumber"] == 2
    draft = clients["centre"].post(
        "/api/centre/batches",
        json={
            **batch_payload(1),
            "upload": None,
            "submit": False,
            "confirmed": False,
        },
    )
    assert draft.status_code == 201, draft.text
    identifier = draft.json()["id"]
    assert clients["one"].get(f"/api/district/batches/{identifier}").status_code == 404
    submitted = clients["centre"].put(
        f"/api/centre/batches/{identifier}",
        json={
            **batch_payload(1),
            "version": draft.json()["version"],
        },
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["count"] == 1
    assert submitted.json()["workflowStatus"] == "SUBMITTED"


def test_state_rechecks_prior_reviews_even_if_status_is_pending(clients: dict) -> None:
    small = submit(clients, 50)
    assert decide(clients["one"], "district", small).status_code == 200
    large = submit(clients, 51)
    district_approve(clients, large)
    with Session(engine()) as db:
        for batch in (small, large):
            db.get(Batch, batch["id"]).status = BatchStatus.PENDING_STATE_APPROVAL
        db.commit()
    for batch, stage in ((small, "district"), (large, "quality")):
        result = decide(clients["state"], "state", batch)
        assert result.status_code == 409
        assert stage in result.json()["message"]
    allowed = district_approve(clients, submit(clients, 51))
    assert decide(clients["quality"], "quality", allowed).status_code == 200
    result = decide(clients["state"], "state", allowed)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "FINAL_APPROVED"


def test_state_approval_is_atomic_and_queues_once(clients: dict) -> None:
    batch = district_approve(clients, submit(clients, 50))
    assert batch["workflowStatus"] == "PENDING_STATE_APPROVAL"
    for role in ("centre", "one", "quality", "anonymous"):
        assert decide(clients[role], "state", batch).status_code == (
            401 if role == "anonymous" else 403
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda name: decide(clients[name], "state", batch),
                ("state", "second_state"),
            )
        )
    assert sorted(result.status_code for result in results) == [200, 409]
    winner = next(result.json() for result in results if result.status_code == 200)
    assert winner["status"] == "FINAL_APPROVED"
    assert winner["issuance_requested"] is True
    assert decide(clients["state"], "state", batch).status_code == 409
    with Session(engine()) as db:
        revision = db.scalar(
            select(BatchRevision).where(BatchRevision.batch_id == batch["id"])
        )
        assert revision.state_queued_at is not None
        assert db.get(IssuanceRequest, revision.id) is not None
        assert (
            db.get(StateReview, revision.id).reviewer.name
            == winner["review"]["reviewer"]
        )
        logs = [event for event in revision.audit if event.action == "STATE_APPROVE"]
        assert len(logs) == 1
        assert logs[0].actor_role == Role.STATE_OFFICE
        assert logs[0].actor_id == revision.state_review.reviewer_id


def test_state_returns_and_rejections_do_not_request_issuance(clients: dict) -> None:
    for action, status in (
        ("return", "RETURNED_FOR_CORRECTION"),
        ("reject", "REJECTED"),
    ):
        batch = district_approve(clients, submit(clients, 50))
        assert decide(clients["state"], "state", batch, action, "  ").status_code == 400
        changed = decide(
            clients["state"], "state", batch, action, "Correct the roster."
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["status"] == status
        assert changed.json()["issuance_requested"] is False
        assert decide(clients["state"], "state", batch).status_code == 409
        with Session(engine()) as db:
            revision = db.scalar(
                select(BatchRevision).where(BatchRevision.batch_id == batch["id"])
            )
            assert db.get(IssuanceRequest, revision.id) is None
            assert any(
                event.action == f"STATE_{action.upper()}" for event in revision.audit
            )
        stored = next(
            item
            for item in clients["centre"].get("/api/centre/batches").json()
            if item["id"] == batch["id"]
        )
        assert stored["comment"] == "Correct the roster."
        correction = clients["centre"].put(
            f"/api/centre/batches/{batch['id']}",
            json={
                **batch_payload(50),
                "version": stored["version"],
            },
        )
        if action == "reject":
            assert correction.status_code == 409
            continue
        assert correction.status_code == 200, correction.text
        resubmitted = correction.json()
        assert resubmitted["revision"] == 2
        assert resubmitted["approvalsReceived"] == 0
        assert resubmitted["decisions"][-1]["role"] == "State Office"
        assert decide(clients["state"], "state", resubmitted).status_code == 409
        district_approve(clients, resubmitted)
        assert decide(clients["state"], "state", batch).status_code == 409
        assert decide(clients["state"], "state", resubmitted).status_code == 200


def test_failed_issuance_insert_rolls_back_state_approval(clients: dict) -> None:
    batch = district_approve(clients, submit(clients, 50))

    def fail_issuance(db: Session, _context: object, _instances: object) -> None:
        if any(isinstance(row, IssuanceRequest) for row in db.new):
            raise IntegrityError(
                "test issuance insert", None, Exception("test failure")
            )

    event.listen(Session, "before_flush", fail_issuance)
    try:
        assert decide(clients["state"], "state", batch).status_code == 409
    finally:
        event.remove(Session, "before_flush", fail_issuance)

    with Session(engine()) as db:
        revision = db.scalar(
            select(BatchRevision).where(BatchRevision.batch_id == batch["id"])
        )
        assert revision.batch.status == BatchStatus.PENDING_STATE_APPROVAL
        assert db.get(StateReview, revision.id) is None
        assert db.get(IssuanceRequest, revision.id) is None
        assert not any(log.action == "STATE_APPROVE" for log in revision.audit)
    assert decide(clients["state"], "state", batch).status_code == 200


def test_state_dashboard_and_queue_use_persisted_workflow(clients: dict) -> None:
    state = clients["state"]
    for key in ("centre", "one", "quality", "anonymous"):
        for path in ("/api/state/dashboard", "/api/state/batches"):
            assert clients[key].get(path).status_code == (
                401 if key == "anonymous" else 403
            )

    path = "/api/state/batches"
    unauthorized = district_approve(clients, submit(clients, 51))
    with Session(engine()) as db:
        db.get(Batch, unauthorized["id"]).status = BatchStatus.PENDING_STATE_APPROVAL
        db.commit()
    hidden = state.get(path, params={"search": unauthorized["id"]})
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["total"] == 0

    before = state.get("/api/state/dashboard")
    assert before.status_code == 200, before.text
    before = before.json()
    pending = district_approve(clients, submit(clients, 50))
    quality_batch = district_approve(clients, submit(clients, 51))
    assert decide(clients["quality"], "quality", quality_batch).status_code == 200
    approved = decide(state, "state", quality_batch)
    assert approved.status_code == 200, approved.text
    returned = district_approve(clients, submit(clients, 50))
    assert (
        decide(
            state, "state", returned, "return", "Check candidate details."
        ).status_code
        == 200
    )
    with Session(engine()) as db:
        revision = db.scalar(
            select(BatchRevision).where(BatchRevision.batch_id == pending["id"])
        )
        revision.state_queued_at = utc_now() - timedelta(hours=49)
        centre_name = revision.batch.centre.name
        district_name = revision.batch.centre.district.name
        db.commit()

    result = state.get(
        path,
        params={
            "search": pending["id"],
            "course": "python",
            "district": district_name.lower(),
            "sort": "oldest",
            "page_size": 1,
        },
    )
    assert result.status_code == 200, result.text
    row = result.json()["records"][0]
    assert row["centre"] == centre_name
    assert row["candidate_count"] == 50 and row["district_approval_count"] == 2
    assert row["quality_status"] == "NOT_REQUIRED"
    assert "students" not in row
    assert (
        state.get(
            path, params={"search": pending["id"], "page": 2, "page_size": 1}
        ).json()["records"]
        == []
    )
    assert (
        state.get(path, params={"search": pending["id"], "view": "delayed"}).json()[
            "total"
        ]
        == 1
    )
    assert (
        state.get(
            path, params={"search": quality_batch["id"], "view": "approved"}
        ).json()["records"][0]["quality_status"]
        == "APPROVED"
    )
    assert (
        state.get(path, params={"search": returned["id"], "view": "returned"}).json()[
            "total"
        ]
        == 1
    )
    assert (
        state.get(path, params={"search": returned["id"], "view": "pending"}).json()[
            "total"
        ]
        == 0
    )

    after = state.get("/api/state/dashboard").json()
    for key, added in (
        ("pending", 1),
        ("approved", 1),
        ("returned", 1),
        ("certificates_pending", 51),
        ("delayed", 1),
    ):
        assert after[key] == before[key] + added
    assert any(item["batch_id"] == quality_batch["id"] for item in after["activity"])


def test_state_details_are_revision_scoped_and_reflect_decisions(clients: dict) -> None:
    batch = submit(clients, 50)
    path = f"/api/state/batches/{batch['id']}"
    state = clients["state"]
    assert state.get(path).status_code == 404
    assert clients["quality"].get(path).status_code == 403
    district_approve(clients, batch)
    pending = state.get(path)
    assert pending.status_code == 200, pending.text
    assert pending.json()["canReview"] is True
    assert len(pending.json()["students"]) == 50
    assert pending.json()["qualityRequired"] is False
    assert len(pending.json()["decisions"]) == 2
    assert decide(state, "state", batch).status_code == 200
    approved = state.get(path, params={"revision": 1}).json()
    assert approved["canReview"] is False
    assert approved["certificateReadiness"] == {
        "final_approved": True,
        "expected": 50,
        "generated": 0,
        "pending": 50,
        "failed": 0,
    }
    assert (
        state.get(path + "/history", params={"revision": 1}).json()["decisions"][-1][
            "role"
        ]
        == "State Office"
    )

    returned = district_approve(clients, submit(clients, 50))
    returned_path = f"/api/state/batches/{returned['id']}"
    assert (
        decide(state, "state", returned, "return", "Check the record.").status_code
        == 200
    )
    old = state.get(returned_path).json()
    corrected = clients["centre"].put(
        f"/api/centre/batches/{returned['id']}",
        json={
            **batch_payload(51),
            "version": old["version"],
        },
    )
    assert corrected.status_code == 200
    assert state.get(returned_path, params={"revision": 2}).status_code == 404
    assert (
        state.get(returned_path, params={"revision": 1}).json()["status"] == "Returned"
    )

    revised = corrected.json()
    assert revised["workflowStatus"] == "SUBMITTED"
    assert revised["approvalsReceived"] == 0
    assert (
        district_approve(clients, revised)["workflowStatus"] == "PENDING_QUALITY_REVIEW"
    )
    assert state.get(returned_path, params={"revision": 2}).status_code == 404
    assert decide(clients["quality"], "quality", revised).status_code == 200
    eligible = state.get(returned_path, params={"revision": 2}).json()
    assert eligible["canReview"] is True
    assert eligible["qualityRequired"] is True
