from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.dependencies import CandidateActor, Db
from app.services import student_portal
from app.services.certificate_pdf import certificate_path
from app.student_schemas import (
    StudentCertificate,
    StudentCertificatePage,
    StudentProfile,
)

router = APIRouter(prefix="/student", tags=["Student portal"])


@router.get("/profile")
def profile(db: Db, actor: CandidateActor) -> StudentProfile:
    return student_portal.profile(db, actor)


@router.get("/certificates")
def certificates(
    db: Db,
    actor: CandidateActor,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StudentCertificatePage:
    return student_portal.list_certificates(db, actor, page, page_size)


@router.get("/certificates/{certificate_id}")
def details(certificate_id: UUID, db: Db, actor: CandidateActor) -> StudentCertificate:
    return student_portal.describe(
        *student_portal.find_certificate(db, actor, str(certificate_id))
    )


@router.get("/certificates/{certificate_id}/download")
def download(certificate_id: UUID, db: Db, actor: CandidateActor) -> FileResponse:
    certificate, candidate = student_portal.find_certificate(
        db, actor, str(certificate_id)
    )
    if certificate.status != "ACTIVE":
        raise HTTPException(409, "This certificate is cancelled.")
    try:
        path = certificate_path(candidate.id)
    except ValueError:
        raise HTTPException(404, "Certificate PDF is unavailable.") from None
    if not path.is_file():
        raise HTTPException(404, "Certificate PDF is unavailable.")
    return FileResponse(
        path, media_type="application/pdf", filename=f"{certificate.number}.pdf"
    )
