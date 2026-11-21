from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(StrEnum):
    TRAINING_CENTRE = "TRAINING_CENTRE"
    DISTRICT_OFFICER = "DISTRICT_OFFICER"
    QUALITY_TEAM = "QUALITY_TEAM"
    STATE_OFFICE = "STATE_OFFICE"
    CANDIDATE = "CANDIDATE"


class BatchStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RETURNED_FOR_CORRECTION = "RETURNED_FOR_CORRECTION"
    REJECTED = "REJECTED"
    PENDING_QUALITY_REVIEW = "PENDING_QUALITY_REVIEW"
    PENDING_STATE_APPROVAL = "PENDING_STATE_APPROVAL"
    FINAL_APPROVED = "FINAL_APPROVED"
    CERTIFICATES_GENERATED = "CERTIFICATES_GENERATED"


class Decision(StrEnum):
    APPROVE = "APPROVE"
    RETURN = "RETURN"
    REJECT = "REJECT"


role_type = ENUM(Role, name="Role", create_type=False)
status_type = ENUM(BatchStatus, name="BatchStatus", create_type=False)
decision_type = ENUM(Decision, name="Decision", create_type=False)
legacy_timestamp = TIMESTAMP(precision=3)


def new_id() -> str:
    return str(uuid4())


def foreign_key(target: str, name: str, on_delete: str = "RESTRICT") -> ForeignKey:
    return ForeignKey(target, name=name, ondelete=on_delete, onupdate="CASCADE")


class District(Base):
    __tablename__ = "District"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)


class TrainingCentre(Base):
    __tablename__ = "TrainingCentre"
    __table_args__ = (Index("TrainingCentre_districtId_idx", "districtId"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    district_id: Mapped[str] = mapped_column(
        "districtId", foreign_key("District.id", "TrainingCentre_districtId_fkey")
    )
    district: Mapped[District] = relationship()


class User(Base):
    __tablename__ = "User"
    __table_args__ = (
        Index("User_email_key", "email", unique=True),
        Index("User_candidateId_key", "candidateId", unique=True),
        CheckConstraint(
            """"candidateId" IS NULL OR "role" = 'CANDIDATE'""",
            name="User_candidate_role_check",
        ),
        CheckConstraint(
            """("role" <> 'DISTRICT_OFFICER' OR "districtId" IS NOT NULL)
               AND ("role" <> 'TRAINING_CENTRE' OR "centreId" IS NOT NULL)""",
            name="User_required_scope",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column("passwordHash", Text)
    role: Mapped[Role] = mapped_column(role_type)
    district_id: Mapped[str | None] = mapped_column(
        "districtId", foreign_key("District.id", "User_districtId_fkey", "SET NULL")
    )
    centre_id: Mapped[str | None] = mapped_column(
        "centreId", foreign_key("TrainingCentre.id", "User_centreId_fkey", "SET NULL")
    )
    candidate_id: Mapped[str | None] = mapped_column(
        "candidateId", foreign_key("Candidate.id", "User_candidateId_fkey")
    )
    is_active: Mapped[bool] = mapped_column(
        "isActive", Boolean, server_default=text("true")
    )
    district: Mapped[District | None] = relationship()
    centre: Mapped[TrainingCentre | None] = relationship()


class Session(Base):
    __tablename__ = "Session"
    __table_args__ = (Index("Session_userId_idx", "userId"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        "userId", foreign_key("User.id", "Session_userId_fkey", "CASCADE")
    )
    expires_at: Mapped[datetime] = mapped_column("expiresAt", legacy_timestamp)
    user: Mapped[User] = relationship()


class Batch(Base):
    __tablename__ = "Batch"
    __table_args__ = (Index("Batch_centreId_status_idx", "centreId", "status"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_id)
    centre_id: Mapped[str] = mapped_column(
        "centreId", foreign_key("TrainingCentre.id", "Batch_centreId_fkey")
    )
    status: Mapped[BatchStatus] = mapped_column(status_type, server_default="DRAFT")
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", legacy_timestamp, server_default=text("CURRENT_TIMESTAMP")
    )
    quality_required: Mapped[bool] = mapped_column(
        "qualityRequired", Boolean, server_default=text("true")
    )
    correction_draft: Mapped[dict[str, Any] | None] = mapped_column(
        "correctionDraft", JSONB(none_as_null=True)
    )
    centre: Mapped[TrainingCentre] = relationship()
    revisions: Mapped[list["BatchRevision"]] = relationship(back_populates="batch")
    certificate: Mapped["Certificate | None"] = relationship()


class BatchRevision(Base):
    __tablename__ = "BatchRevision"
    __table_args__ = (
        Index("BatchRevision_batchId_number_key", "batchId", "number", unique=True),
        Index("BatchRevision_qualityQueuedAt_idx", "qualityQueuedAt"),
        Index("BatchRevision_stateQueuedAt_idx", "stateQueuedAt"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(
        "batchId", foreign_key("Batch.id", "BatchRevision_batchId_fkey")
    )
    number: Mapped[int] = mapped_column(Integer)
    form: Mapped[dict[str, Any]] = mapped_column(JSONB)
    upload: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    submitted_at: Mapped[datetime | None] = mapped_column(
        "submittedAt", legacy_timestamp
    )
    quality_queued_at: Mapped[datetime | None] = mapped_column(
        "qualityQueuedAt", TIMESTAMP(timezone=True, precision=3)
    )
    state_queued_at: Mapped[datetime | None] = mapped_column(
        "stateQueuedAt", TIMESTAMP(timezone=True, precision=3)
    )
    batch: Mapped[Batch] = relationship(back_populates="revisions")
    candidates: Mapped[list["Candidate"]] = relationship()
    approvals: Mapped[list["Approval"]] = relationship()
    audit: Mapped[list["AuditLog"]] = relationship()
    quality_review: Mapped["QualityReview | None"] = relationship()
    state_review: Mapped["StateReview | None"] = relationship()


class Candidate(Base):
    __tablename__ = "Candidate"
    __table_args__ = (
        Index(
            "Candidate_normalized_student_id_idx",
            text("""lower(btrim("data" ->> 'student_id'))"""),
        ),
        Index(
            "Candidate_normalized_email_idx",
            text("""lower(btrim("data" ->> 'email'))"""),
        ),
        Index(
            "Candidate_revisionId_rowNumber_key", "revisionId", "rowNumber", unique=True
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(
        "revisionId", foreign_key("BatchRevision.id", "Candidate_revisionId_fkey")
    )
    row_number: Mapped[int] = mapped_column("rowNumber", Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Approval(Base):
    __tablename__ = "Approval"
    __table_args__ = (
        Index("Approval_officerId_createdAt_idx", "officerId", "createdAt"),
        Index(
            "Approval_revisionId_officerId_key", "revisionId", "officerId", unique=True
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(
        "revisionId", foreign_key("BatchRevision.id", "Approval_revisionId_fkey")
    )
    officer_id: Mapped[str] = mapped_column(
        "officerId", foreign_key("User.id", "Approval_officerId_fkey")
    )
    decision: Mapped[Decision] = mapped_column(decision_type)
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", legacy_timestamp, server_default=text("CURRENT_TIMESTAMP")
    )
    officer: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "AuditLog"
    __table_args__ = (
        Index("AuditLog_revisionId_createdAt_idx", "revisionId", "createdAt"),
        CheckConstraint(
            """("actorId" IS NOT NULL AND "actorRole" IS NOT NULL) OR
               ("actorId" IS NULL AND "actorRole" IS NULL AND
                "action" = 'QUALITY_ROUTING_RECONCILED')""",
            name="AuditLog_actor_scope",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(
        "revisionId", foreign_key("BatchRevision.id", "AuditLog_revisionId_fkey")
    )
    actor_id: Mapped[str | None] = mapped_column(
        "actorId", foreign_key("User.id", "AuditLog_actorId_fkey")
    )
    actor_role: Mapped[Role | None] = mapped_column("actorRole", role_type)
    action: Mapped[str] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", legacy_timestamp, server_default=text("CURRENT_TIMESTAMP")
    )


class Certificate(Base):
    __tablename__ = "Certificate"
    __table_args__ = (Index("Certificate_batchId_key", "batchId", unique=True),)

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        "batchId", foreign_key("Batch.id", "Certificate_batchId_fkey")
    )
    issued_at: Mapped[datetime] = mapped_column("issuedAt", legacy_timestamp)


class QualityReview(Base):
    __tablename__ = "QualityReview"
    __table_args__ = (
        Index("QualityReview_reviewerId_createdAt_idx", "reviewerId", "createdAt"),
        CheckConstraint(
            """char_length("comment") <= 2000 AND
               ("decision" = 'APPROVE' OR "comment" ~ '[^[:space:]]')""",
            name="QualityReview_decision_comment_check",
        ),
    )

    revision_id: Mapped[str] = mapped_column(
        "revisionId",
        foreign_key("BatchRevision.id", "QualityReview_revisionId_fkey"),
        primary_key=True,
    )
    reviewer_id: Mapped[str] = mapped_column(
        "reviewerId", foreign_key("User.id", "QualityReview_reviewerId_fkey")
    )
    decision: Mapped[Decision] = mapped_column(decision_type)
    comment: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        "createdAt",
        TIMESTAMP(timezone=True, precision=3),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    reviewer: Mapped[User] = relationship()


class StateReview(Base):
    __tablename__ = "StateReview"
    __table_args__ = (
        Index("StateReview_reviewerId_createdAt_idx", "reviewerId", "createdAt"),
        CheckConstraint(
            """char_length("comment") <= 2000 AND
               ("decision" = 'APPROVE' OR "comment" ~ '[^[:space:]]')""",
            name="StateReview_decision_comment_check",
        ),
    )

    revision_id: Mapped[str] = mapped_column(
        "revisionId",
        foreign_key("BatchRevision.id", "StateReview_revisionId_fkey"),
        primary_key=True,
    )
    reviewer_id: Mapped[str] = mapped_column(
        "reviewerId", foreign_key("User.id", "StateReview_reviewerId_fkey")
    )
    decision: Mapped[Decision] = mapped_column(decision_type)
    comment: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        "createdAt",
        TIMESTAMP(timezone=True, precision=3),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    reviewer: Mapped[User] = relationship()


class IssuanceRequest(Base):
    """Durable work request created atomically with state approval."""

    __tablename__ = "IssuanceRequest"

    revision_id: Mapped[str] = mapped_column(
        "revisionId",
        foreign_key("StateReview.revisionId", "IssuanceRequest_revisionId_fkey"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        "createdAt",
        TIMESTAMP(timezone=True, precision=3),
        server_default=text("CURRENT_TIMESTAMP"),
    )


class StudentIdentity(Base):
    __tablename__ = "StudentIdentity"
    __table_args__ = (
        Index("StudentIdentity_candidateId_key", "candidateId", unique=True),
    )

    student_id: Mapped[str] = mapped_column("studentId", Text, primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        "candidateId", foreign_key("Candidate.id", "StudentIdentity_candidateId_fkey")
    )
    email: Mapped[str] = mapped_column(Text)
    candidate: Mapped[Candidate] = relationship()


class StudentActivation(Base):
    """Legacy storage retained for migration history. The API no longer reads it."""

    __tablename__ = "StudentActivation"
    __table_args__ = (
        Index("StudentActivation_challengeDigest_key", "challengeDigest", unique=True),
        Index("StudentActivation_grantDigest_key", "grantDigest", unique=True),
    )

    student_id: Mapped[str] = mapped_column(
        "studentId",
        foreign_key(
            "StudentIdentity.studentId", "StudentActivation_studentId_fkey", "CASCADE"
        ),
        primary_key=True,
    )
    challenge_digest: Mapped[str] = mapped_column("challengeDigest", Text)
    otp_digest: Mapped[str | None] = mapped_column("otpDigest", Text)
    expires_at: Mapped[datetime] = mapped_column("expiresAt", TIMESTAMP(timezone=True))
    requested_at: Mapped[datetime] = mapped_column(
        "requestedAt", TIMESTAMP(timezone=True)
    )
    window_at: Mapped[datetime] = mapped_column("windowAt", TIMESTAMP(timezone=True))
    requests: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer)
    grant_digest: Mapped[str | None] = mapped_column("grantDigest", Text)
    grant_expires_at: Mapped[datetime | None] = mapped_column(
        "grantExpiresAt", TIMESTAMP(timezone=True)
    )


class CandidateCertificate(Base):
    __tablename__ = "CandidateCertificate"
    __table_args__ = (
        Index("CandidateCertificate_candidateId_key", "candidateId", unique=True),
        Index("CandidateCertificate_number_key", "number", unique=True),
        CheckConstraint(
            "status IN ('ACTIVE', 'CANCELLED')",
            name="CandidateCertificate_status_check",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        "candidateId",
        foreign_key("Candidate.id", "CandidateCertificate_candidateId_fkey"),
    )
    number: Mapped[str] = mapped_column(Text)
    issued_at: Mapped[datetime] = mapped_column("issuedAt", TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="ACTIVE")


class StudentActivationCode(Base):
    __tablename__ = "StudentActivationCode"
    __table_args__ = (
        Index("StudentActivationCode_codeDigest_key", "codeDigest", unique=True),
        Index("StudentActivationCode_grantDigest_key", "grantDigest", unique=True),
    )

    candidate_id: Mapped[str] = mapped_column(
        "candidateId",
        foreign_key(
            "Candidate.id", "StudentActivationCode_candidateId_fkey", "CASCADE"
        ),
        primary_key=True,
    )
    code_digest: Mapped[str] = mapped_column("codeDigest", Text)
    expires_at: Mapped[datetime] = mapped_column("expiresAt", TIMESTAMP(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column("usedAt", TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column("createdAt", TIMESTAMP(timezone=True))
    created_by: Mapped[str] = mapped_column(
        "createdBy", foreign_key("User.id", "StudentActivationCode_createdBy_fkey")
    )
    grant_digest: Mapped[str | None] = mapped_column("grantDigest", Text)
    grant_expires_at: Mapped[datetime | None] = mapped_column(
        "grantExpiresAt", TIMESTAMP(timezone=True)
    )
