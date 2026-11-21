import csv
import io
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import bcrypt
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import engine, legacy_now, utc_now
from app.issue_candidate_certificates import issue
from app.main import app
from app.models import (
    Batch,
    BatchRevision,
    BatchStatus,
    Candidate,
    CandidateCertificate,
    Decision,
    District,
    IssuanceRequest,
    Role,
    StateReview,
    StudentActivationCode,
    TrainingCentre,
    User,
)
from app.services.authentication import attempts

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Requires PostgreSQL"
)
PREFIX = "/api/student/activation/"


@pytest.fixture
def activation_client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("JWT_SECRET", "student-activation-test-only-secret")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("CERTIFICATE_STORAGE", str(tmp_path / "certificates"))
    settings.cache_clear()
    engine.cache_clear()
    attempts.clear()
    with TestClient(app) as client:
        yield client
    engine().dispose()
    engine.cache_clear()
    settings.cache_clear()


def candidate(
    approved: bool = True, student_id: str | None = None
) -> tuple[str, str, str]:
    key = uuid4().hex
    student_id = student_id or key
    email = f"{key}@example.test"
    with Session(engine()) as db:
        centre = TrainingCentre(
            id=key, name="Test centre", district=District(id=key, name="Test district")
        )
        batch = Batch(centre=centre, status=BatchStatus.FINAL_APPROVED)
        revision = BatchRevision(
            batch=batch,
            number=1,
            submitted_at=legacy_now(),
            form={
                "name": "Student activation test",
                "course": "Test course",
                "trainer": "Trainer",
                "startDate": "2026-10-01",
                "endDate": "2026-10-20",
                "assessmentDate": "2026-10-21",
                "description": "",
            },
        )
        db.add(revision)
        db.flush()
        row = Candidate(
            revision_id=revision.id,
            row_number=2,
            data={
                "rowNumber": 2,
                "student_id": student_id,
                "student_name": "Test student",
                "email": email,
                "course_name": "Test course",
                "assessment_date": "2026-10-21",
                "phone_number": "9990000001",
                "marks": "90",
            },
        )
        db.add(row)
        if approved:
            reviewer = User(
                email=f"reviewer-{key}@example.test",
                name="Reviewer",
                role=Role.STATE_OFFICE,
                password_hash="Unused",
            )
            db.add(
                StateReview(
                    revision_id=revision.id,
                    reviewer=reviewer,
                    decision=Decision.APPROVE,
                )
            )
            db.flush()
            db.add(IssuanceRequest(revision_id=revision.id))
        db.commit()
        return student_id, email, row.id


def batch_path(candidate_id: str) -> str:
    with Session(engine()) as db:
        row = db.get(Candidate, candidate_id)
        revision = db.get(BatchRevision, row.revision_id)
        return f"/api/centre/batches/{revision.batch_id}/activation-codes/"


def centre_login(client: TestClient, candidate_id: str) -> None:
    email = f"centre-{uuid4().hex}@example.test"
    with Session(engine()) as db:
        row = db.get(Candidate, candidate_id)
        centre = db.get(BatchRevision, row.revision_id).batch.centre
        db.add(
            User(
                email=email,
                role=Role.TRAINING_CENTRE,
                name="Training Centre",
                centre=centre,
                password_hash=bcrypt.hashpw(
                    b"test-centre-password", bcrypt.gensalt(rounds=4)
                ).decode(),
            )
        )
        db.commit()
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "test-centre-password"}
    )
    assert response.status_code == 200, response.text


def code_for(candidate_id: str) -> str:
    with TestClient(app) as centre:
        centre_login(centre, candidate_id)
        response = centre.post(batch_path(candidate_id) + "export")
        assert response.status_code == 200, response.text
        return next(csv.DictReader(io.StringIO(response.text)))["activation_code"]


def verify(client, student_id: str, code: str):
    return client.post(
        PREFIX + "verify", json={"student_id": student_id, "activation_code": code}
    )


def activate(client, grant: str):
    return client.post(
        PREFIX + "complete",
        json={
            "grant": grant,
            "password": "a-long-test-password",
            "confirm_password": "a-long-test-password",
        },
    )


def test_activation_is_single_use_and_uses_registered_candidate(
    activation_client,
) -> None:
    client = activation_client
    student_id, email, candidate_id = candidate()
    code = code_for(candidate_id)
    verified = verify(client, student_id.upper(), code.lower())
    assert verified.status_code == 200, verified.text
    grant = verified.json()["grant"]
    assert activate(client, grant).status_code == 204
    assert activate(client, grant).status_code == 400
    assert verify(client, student_id, code).status_code == 400
    with Session(engine()) as db:
        account = db.scalar(select(User).where(User.email == email))
        row = db.get(StudentActivationCode, candidate_id)
        assert account.candidate_id == candidate_id and account.role == Role.CANDIDATE
        assert bcrypt.checkpw(b"a-long-test-password", account.password_hash.encode())
        assert row.used_at and row.code_digest != code
    with TestClient(app) as centre:
        centre_login(centre, candidate_id)
        assert (
            centre.post(
                batch_path(candidate_id) + "regenerate", json={"student_id": student_id}
            ).status_code
            == 409
        )


def test_invalid_unknown_ineligible_conflicting_and_expired_codes(
    activation_client,
) -> None:
    client = activation_client
    student_id, _, candidate_id = candidate()
    code = code_for(candidate_id)
    invalid_code = "CF-2222-3333-4444-5555"
    bad_id = verify(client, uuid4().hex, code)
    assert bad_id.status_code == 400
    assert verify(client, student_id, invalid_code).json() == bad_id.json()
    with Session(engine()) as db:
        db.get(StudentActivationCode, candidate_id).expires_at = utc_now() - timedelta(
            seconds=1
        )
        db.commit()
    assert verify(client, student_id, code).json() == bad_id.json()
    not_approved, _, pending = candidate(approved=False)
    assert verify(client, not_approved, code_for(pending)).status_code == 400
    conflicting_id, _, conflicting = candidate()
    candidate(student_id=conflicting_id)
    assert verify(client, conflicting_id, code_for(conflicting)).status_code == 400


def test_export_is_owner_scoped_one_time_and_audited(activation_client) -> None:
    client = activation_client
    student_id, _, candidate_id = candidate()
    path = batch_path(candidate_id)
    assert client.post(path + "export").status_code == 401
    _, _, outsider_id = candidate()
    centre_login(client, outsider_id)
    assert client.post(path + "export").status_code == 404
    assert (
        client.post(path + "regenerate", json={"student_id": student_id}).status_code
        == 404
    )
    centre_login(client, candidate_id)
    exported = client.post(path + "export")
    assert exported.status_code == 200, exported.text
    assert exported.headers["cache-control"] == "no-store"
    row = next(csv.DictReader(io.StringIO(exported.text)))
    assert set(row) == {"student_id", "student_name", "course_name", "activation_code"}
    assert row["student_id"] == student_id
    code = row["activation_code"]
    assert code not in client.get("/api/centre/batches").text
    assert client.post(path + "export").status_code == 409
    old_grant = verify(client, student_id, code).json()["grant"]
    rotated = client.post(path + "regenerate", json={"student_id": student_id})
    assert rotated.status_code == 200, rotated.text
    new_code = next(csv.DictReader(io.StringIO(rotated.text)))["activation_code"]
    assert new_code != code
    assert verify(client, student_id, code).status_code == 400
    assert activate(client, old_grant).status_code == 400
    assert verify(client, student_id, new_code).status_code == 200
    response = client.get("/api/centre/batches")
    assert all(value not in response.text for value in (code, new_code, old_grant))
    labels = {event["label"] for batch in response.json() for event in batch["history"]}
    assert "Training Centre exported activation codes" in labels
    assert "Training Centre regenerated an activation code" in labels


def test_concurrent_grant_redemption_creates_one_account(activation_client) -> None:
    client = activation_client
    student_id, email, candidate_id = candidate()
    code = code_for(candidate_id)
    grant = verify(client, student_id, code).json()["grant"]
    with TestClient(app) as one, TestClient(app) as two, ThreadPoolExecutor(2) as pool:
        attempts = [pool.submit(activate, item, grant) for item in (one, two)]
        assert sorted(item.result().status_code for item in attempts) == [204, 400]
    with Session(engine()) as db:
        accounts = list(db.scalars(select(User).where(User.email == email)))
        assert len(accounts) == 1
        assert accounts[0].candidate_id == candidate_id


def student_login(
    client: TestClient, email: str, password: str = "a-long-test-password"
):
    return client.post(
        "/api/student/auth/login", json={"email": email, "password": password}
    )


def activated_student(client: TestClient) -> str:
    student_id, email, candidate_id = candidate()
    verified = verify(client, student_id, code_for(candidate_id))
    assert verified.status_code == 200, verified.text
    assert activate(client, verified.json()["grant"]).status_code == 204
    return email


def test_student_login_checks_role_password_and_active_account(
    activation_client,
) -> None:
    client = activation_client
    email = activated_student(client)
    for invalid_email, invalid_password in (
        (email, "wrong password"),
        (f"{uuid4().hex}@example.test", "a-long-test-password"),
    ):
        response = student_login(client, invalid_email, invalid_password)
        assert response.status_code == 401
        assert response.json() == {"message": "Email or password is incorrect."}

    logged_in = student_login(client, email.upper())
    assert logged_in.status_code == 200, logged_in.text
    assert set(logged_in.json()) == {"id", "name", "email", "role"}
    assert logged_in.json()["role"] == "CANDIDATE"
    assert "HttpOnly" in logged_in.headers["set-cookie"]
    assert client.get("/api/auth/session").json()["user"]["email"] == email
    assert client.get("/api/state/dashboard").status_code == 403
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": "a-long-test-password"}
        ).status_code
        == 401
    )

    staff_email = f"{uuid4().hex}@example.test"
    with Session(engine()) as db:
        account = db.scalar(select(User).where(User.email == email))
        account.is_active = False
        db.add(
            User(
                email=staff_email,
                name="Test officer",
                role=Role.STATE_OFFICE,
                password_hash=bcrypt.hashpw(
                    b"a-long-test-password", bcrypt.gensalt(rounds=4)
                ).decode(),
            )
        )
        db.commit()
    assert client.get("/api/auth/session").json() == {"user": None}
    assert student_login(client, email).status_code == 401
    assert student_login(client, staff_email).status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"email": staff_email, "password": "a-long-test-password"},
        ).status_code
        == 200
    )
    assert client.post("/api/student/auth/logout").status_code == 403


def test_password_change_revokes_all_sessions_and_requires_current_password(
    activation_client,
) -> None:
    client = activation_client
    email = activated_student(client)
    path = "/api/student/auth/change-password"
    body = {
        "current_password": "a-long-test-password",
        "password": "another-long-password",
        "confirm_password": "another-long-password",
    }
    assert client.post(path, json=body).status_code == 401
    with TestClient(app) as other:
        assert student_login(client, email).status_code == 200
        assert student_login(other, email).status_code == 200
        for invalid in (
            {**body, "current_password": "wrong password"},
            {**body, "confirm_password": "different-password"},
            {**body, "password": "short", "confirm_password": "short"},
            {**body, "role": "STATE_OFFICE"},
        ):
            assert client.post(path, json=invalid).status_code == 400
        assert other.get("/api/auth/me").status_code == 200
        response = client.post(path, json=body)
        assert response.status_code == 204
        assert client.get("/api/auth/me").status_code == 401
        assert other.get("/api/auth/me").status_code == 401
        assert student_login(client, email).status_code == 401
        assert student_login(client, email, body["password"]).status_code == 200
        saved_cookie = client.cookies.get("certiflow_session")
        assert client.post("/api/student/auth/logout").status_code == 204
        replay = other.get(
            "/api/auth/me", headers={"Cookie": f"certiflow_session={saved_cookie}"}
        )
        assert replay.status_code == 401


def issue_for(email: str) -> str:
    with Session(engine()) as db:
        user = db.scalar(select(User).where(User.email == email))
        row = db.get(Candidate, user.candidate_id)
        batch_id = db.get(BatchRevision, row.revision_id).batch_id
        assert issue(db, batch_id) == 1
        assert issue(db, batch_id) == 0
        return db.scalar(
            select(CandidateCertificate.id).where(
                CandidateCertificate.candidate_id == row.id
            )
        )


def test_student_portal_reads_only_owned_certificates(activation_client) -> None:
    client = activation_client
    email = activated_student(client)
    list_path = "/api/student/certificates"
    with TestClient(app) as another:
        another_email = activated_student(another)
        assert student_login(client, email).status_code == 200
        assert student_login(another, another_email).status_code == 200
        assert client.get("/api/student/profile").json()["email"] == email
        assert client.get("/api/student/profile").json()["total_issued"] == 0
        assert client.get(list_path).json()["records"] == []
        assert (
            client.patch(
                "/api/student/profile", json={"student_id": "other", "marks": "100"}
            ).status_code
            == 405
        )

        owned = issue_for(email)
        unrelated = issue_for(another_email)
        assert client.get("/api/student/profile").json()["total_issued"] == 1
        listed = client.get(
            list_path, params={"candidate_id": unrelated, "page_size": 1}
        ).json()
        assert [item["id"] for item in listed["records"]] == [owned]
        assert (
            client.get(list_path, params={"page": 2, "page_size": 1}).json()["records"]
            == []
        )
        assert client.get(f"{list_path}/{unrelated}").status_code == 404
        assert client.get(f"{list_path}/{unrelated}/download").status_code == 404

        response = client.get(f"{list_path}/{owned}/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-")
        assert response.headers["cache-control"] == "no-store"
        with TestClient(app) as anonymous:
            assert anonymous.get(f"{list_path}/{owned}/download").status_code == 401

        with Session(engine()) as db:
            db.get(CandidateCertificate, owned).status = "CANCELLED"
            db.commit()
        assert client.get(f"{list_path}/{owned}").json()["status"] == "CANCELLED"
        assert client.get(f"{list_path}/{owned}/download").status_code == 409


@pytest.mark.parametrize(
    "role",
    [Role.TRAINING_CENTRE, Role.DISTRICT_OFFICER, Role.QUALITY_TEAM, Role.STATE_OFFICE],
)
def test_office_roles_cannot_access_student_portal(
    activation_client, role: Role
) -> None:
    client = activation_client
    key = uuid4().hex
    email = f"{key}@example.test"
    with Session(engine()) as db:
        district = District(id=key, name="Test district")
        db.add(
            User(
                email=email,
                name="Test office user",
                role=role,
                password_hash=bcrypt.hashpw(
                    b"a-long-test-password", bcrypt.gensalt(rounds=4)
                ).decode(),
                centre=TrainingCentre(id=key, name="Test centre", district=district)
                if role == Role.TRAINING_CENTRE
                else None,
                district=district if role == Role.DISTRICT_OFFICER else None,
            )
        )
        db.commit()
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": "a-long-test-password"}
        ).status_code
        == 200
    )
    assert client.get("/api/student/profile").status_code == 403
    assert client.get("/api/student/certificates").status_code == 403


def test_activation_pdf_uses_same_one_time_credential_and_owner_scope(
    activation_client,
) -> None:
    client = activation_client
    student_id, _, candidate_id = candidate()
    outsider_student, _, outsider = candidate()
    batch = batch_path(candidate_id).removesuffix("/activation-codes/")
    pdf_path = batch + "/activation-slips"
    assert client.post(pdf_path).status_code == 401
    centre_login(client, outsider)
    assert client.post(pdf_path).status_code == 404
    centre_login(client, candidate_id)
    assert (
        client.post(batch + f"/candidates/{outsider}/activation-slip").status_code
        == 404
    )
    response = client.post(pdf_path)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    document = PdfReader(io.BytesIO(response.content))
    assert len(document.pages) == 1
    page = document.pages[0].extract_text()
    assert all(
        s in page for s in (student_id, "Test student", "Test course", "Page 1 of 1")
    )
    assert outsider_student not in page
    code = re.search(r"CF-(?:[A-Z0-9]{4}-){3}[A-Z0-9]{4}", page).group()
    assert verify(client, student_id, code).status_code == 200
    assert client.post(batch_path(candidate_id) + "export").status_code == 409
    assert client.post(pdf_path).status_code == 409
    assert code not in client.get("/api/centre/batches").text


def test_individual_slip_only_issues_for_selected_candidate(activation_client) -> None:
    client = activation_client
    student_id, _, candidate_id = candidate()
    second_id = str(uuid4())
    with Session(engine()) as db:
        row = db.get(Candidate, candidate_id)
        data = {
            **row.data,
            "student_id": second_id,
            "student_name": "Second student",
            "email": f"{second_id}@example.test",
            "rowNumber": 3,
        }
        db.add(
            Candidate(
                id=second_id, revision_id=row.revision_id, row_number=3, data=data
            )
        )
        db.commit()
    centre_login(client, candidate_id)
    batch = batch_path(candidate_id).removesuffix("/activation-codes/")
    response = client.post(batch + f"/candidates/{candidate_id}/activation-slip")
    assert response.status_code == 200, response.text
    page = PdfReader(io.BytesIO(response.content)).pages[0].extract_text()
    assert student_id in page and second_id not in page
    remaining = client.post(batch_path(candidate_id) + "export")
    assert remaining.status_code == 200, remaining.text
    assert [
        row["student_id"] for row in csv.DictReader(io.StringIO(remaining.text))
    ] == [second_id]
