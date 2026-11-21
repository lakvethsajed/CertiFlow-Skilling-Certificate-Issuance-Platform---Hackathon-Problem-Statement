from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Candidate, CandidateCertificate, StudentIdentity, User
from app.student_schemas import (
    StudentCertificate,
    StudentCertificatePage,
    StudentProfile,
)


def identity_for(db: Session, actor: User) -> StudentIdentity:
    identity = db.scalar(
        select(StudentIdentity).where(
            StudentIdentity.candidate_id == actor.candidate_id
        )
    )
    if not identity or identity.email != actor.email:
        raise HTTPException(403, "Student profile is not available.")
    return identity


def owned_certificates(identity: StudentIdentity) -> Select:
    return (
        select(CandidateCertificate, Candidate)
        .join(Candidate, Candidate.id == CandidateCertificate.candidate_id)
        .where(
            func.lower(func.btrim(Candidate.data["student_id"].astext))
            == identity.student_id,
            func.lower(func.btrim(Candidate.data["email"].astext)) == identity.email,
        )
    )


def profile(db: Session, actor: User) -> StudentProfile:
    identity = identity_for(db, actor)
    data = identity.candidate.data
    return StudentProfile(
        student_id=data["student_id"],
        name=data["student_name"],
        email=identity.email,
        phone_number=data.get("phone_number"),
        course=data.get("course_name"),
        total_issued=db.scalar(
            select(func.count()).select_from(owned_certificates(identity).subquery())
        )
        or 0,
    )


def describe(
    certificate: CandidateCertificate, candidate: Candidate
) -> StudentCertificate:
    return StudentCertificate(
        id=certificate.id,
        number=certificate.number,
        course=candidate.data["course_name"],
        assessment_date=candidate.data["assessment_date"],
        issued_at=certificate.issued_at,
        status=certificate.status,
    )


def list_certificates(
    db: Session, actor: User, page: int, page_size: int
) -> StudentCertificatePage:
    query = owned_certificates(identity_for(db, actor))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(CandidateCertificate.issued_at.desc(), CandidateCertificate.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return StudentCertificatePage(
        records=[describe(certificate, candidate) for certificate, candidate in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def find_certificate(
    db: Session, actor: User, certificate_id: str
) -> tuple[CandidateCertificate, Candidate]:
    row = db.execute(
        owned_certificates(identity_for(db, actor)).where(
            CandidateCertificate.id == certificate_id
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Certificate not found.")
    return row[0], row[1]
