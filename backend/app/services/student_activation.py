import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal

import bcrypt
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import utc_now
from app.models import (
    BatchRevision,
    BatchStatus,
    Candidate,
    Decision,
    Role,
    StateReview,
    StudentActivationCode,
    StudentIdentity,
    User,
)
from app.services.batches import audit, current_revision, scoped_batch
from app.student_schemas import ActivationPassword, ActivationVerification

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def code_digest(code: str) -> str:
    key = settings().jwt_secret.get_secret_value().encode()
    return hmac.new(key, f"certiflow-activation:{code}".encode(), "sha256").hexdigest()


def candidate_email(candidate: Candidate) -> str:
    return (candidate.data.get("email") or "").strip().lower()


def student_key(candidate: Candidate) -> str:
    return candidate.data["student_id"].strip().lower()


def has_account(db: Session, candidate: Candidate) -> bool:
    return (
        db.scalar(
            select(User.id)
            .outerjoin(
                StudentIdentity, StudentIdentity.candidate_id == User.candidate_id
            )
            .where(
                (User.email == candidate_email(candidate))
                | (StudentIdentity.student_id == student_key(candidate))
            )
            .limit(1)
        )
        is not None
    )


def activation_eligible(db: Session, candidate: Candidate) -> bool:
    revision = db.get(BatchRevision, candidate.revision_id)
    if (
        revision.batch.revision != revision.number
        or revision.batch.status
        not in {
            BatchStatus.FINAL_APPROVED,
            BatchStatus.CERTIFICATES_GENERATED,
        }
        or revision.state_review is None
        or revision.state_review.decision != Decision.APPROVE
    ):
        return False
    conflicting_email = db.scalar(
        select(Candidate.id)
        .join(StateReview, StateReview.revision_id == Candidate.revision_id)
        .where(
            StateReview.decision == Decision.APPROVE,
            func.lower(func.btrim(Candidate.data["student_id"].astext))
            == student_key(candidate),
            func.lower(func.btrim(Candidate.data["email"].astext)).is_distinct_from(
                candidate_email(candidate)
            ),
        )
        .limit(1)
    )
    return not conflicting_email


@dataclass(frozen=True)
class ExportedActivation:
    student_id: str
    student_name: str
    course: str
    code: str = field(repr=False)


def export_codes(
    db: Session,
    actor: User,
    batch_id: str,
    regenerate_student: str | None = None,
    *,
    candidate_id: str | None = None,
    export_format: Literal["CSV", "PDF"] = "CSV",
) -> list[ExportedActivation]:
    batch = scoped_batch(db, batch_id, actor, lock=True)
    revision = current_revision(db, batch)
    if revision.submitted_at is None or batch.status in {
        BatchStatus.RETURNED_FOR_CORRECTION,
        BatchStatus.REJECTED,
    }:
        raise HTTPException(409, "Submit the batch before issuing activation codes.")
    candidates = sorted(revision.candidates, key=lambda row: row.row_number)
    if candidate_id is not None:
        candidates = [row for row in candidates if row.id == candidate_id]
        if not candidates:
            raise HTTPException(404, "Candidate not found in this batch revision.")
    if regenerate_student is not None:
        candidates = [
            row for row in candidates if student_key(row) == regenerate_student
        ]
        if not candidates:
            raise HTTPException(404, "Student not found in this batch revision.")

    existing = {
        row.candidate_id: row
        for row in db.scalars(
            select(StudentActivationCode)
            .where(
                StudentActivationCode.candidate_id.in_([row.id for row in candidates])
            )
            .with_for_update()
        )
    }
    identities = {
        student_id
        for student_id in db.scalars(
            select(StudentIdentity.student_id)
            .join(User, User.candidate_id == StudentIdentity.candidate_id)
            .where(
                StudentIdentity.student_id.in_([student_key(row) for row in candidates])
            )
        )
    }
    emails = set(
        db.scalars(
            select(User.email).where(
                User.email.in_([candidate_email(row) for row in candidates])
            )
        )
    )
    rows = []
    now = utc_now()
    config = settings()
    for candidate in candidates:
        record = existing.get(candidate.id)
        if (
            not candidate_email(candidate)
            or candidate_email(candidate) in emails
            or student_key(candidate) in identities
            or (record and record.used_at)
        ):
            if regenerate_student is not None:
                raise HTTPException(
                    409, "This student is not eligible for a new activation code."
                )
            continue
        if record and regenerate_student is None:
            continue
        code = "CF-" + "-".join(
            "".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(4)
        )
        if record is None:
            record = StudentActivationCode(candidate_id=candidate.id)
            db.add(record)
        record.code_digest = code_digest(code)
        record.created_at = now
        record.expires_at = now + timedelta(days=config.student_activation_days)
        record.created_by = actor.id
        record.grant_digest = None
        record.grant_expires_at = None
        rows.append(
            ExportedActivation(
                student_id=candidate.data["student_id"],
                student_name=candidate.data["student_name"],
                course=candidate.data["course_name"],
                code=code,
            )
        )
    if not rows:
        raise HTTPException(
            409,
            "No new activation codes are available. Regenerate a lost or expired code individually.",
        )
    audit(
        db,
        revision,
        actor,
        "ACTIVATION_CODES_REGENERATED"
        if regenerate_student
        else "ACTIVATION_CODES_EXPORTED",
        f"{len(rows)} activation credential(s) exported as {export_format}.",
    )
    return rows


def verify_code(db: Session, data: ActivationVerification) -> str:
    record = db.scalar(
        select(StudentActivationCode)
        .where(StudentActivationCode.code_digest == code_digest(data.activation_code))
        .with_for_update()
    )
    now = utc_now()
    if record is not None and record.used_at is None and record.expires_at > now:
        candidate = db.get(Candidate, record.candidate_id)
        if (
            student_key(candidate) == data.student_id
            and activation_eligible(db, candidate)
            and not has_account(db, candidate)
        ):
            grant = secrets.token_urlsafe(32)
            record.grant_digest = token_digest(grant)
            record.grant_expires_at = now + timedelta(minutes=5)
            db.commit()
            return grant
    raise HTTPException(
        400, "The student ID or activation code is invalid, expired, or unavailable."
    )


def create_student_account(db: Session, request: ActivationPassword) -> None:
    record = db.scalar(
        select(StudentActivationCode)
        .where(StudentActivationCode.grant_digest == token_digest(request.grant))
        .with_for_update()
    )
    error = HTTPException(
        400, "The activation session is no longer valid. Verify your code again."
    )
    now = utc_now()
    if (
        not record
        or record.used_at
        or record.expires_at <= now
        or not record.grant_expires_at
        or record.grant_expires_at <= now
    ):
        raise error
    candidate = db.get(Candidate, record.candidate_id)
    if not activation_eligible(db, candidate):
        raise error
    key, email = student_key(candidate), candidate_email(candidate)
    db.execute(
        insert(StudentIdentity)
        .values(student_id=key, candidate_id=candidate.id, email=email)
        .on_conflict_do_nothing()
    )
    identity = db.get(StudentIdentity, key, with_for_update=True)
    if not identity or identity.email != email or has_account(db, candidate):
        raise error
    account = User(
        candidate_id=identity.candidate_id,
        email=email,
        name=candidate.data["student_name"],
        role=Role.CANDIDATE,
        is_active=True,
        password_hash=bcrypt.hashpw(
            request.password.encode(), bcrypt.gensalt(rounds=12)
        ).decode(),
    )
    db.add(account)
    record.used_at = now
    record.grant_digest = None
    record.grant_expires_at = None
    try:
        db.flush()
        audit(
            db,
            db.get(BatchRevision, candidate.revision_id),
            account,
            "STUDENT_ACTIVATED",
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise error from None
