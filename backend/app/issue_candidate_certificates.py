import argparse
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import engine, utc_now
from app.models import (
    Batch,
    BatchStatus,
    CandidateCertificate,
    Decision,
    IssuanceRequest,
)
from app.services.batches import current_revision
from app.services.certificate_pdf import certificate_path, render_certificate


def issue(db: Session, batch_id: str) -> int:
    batch = db.scalar(
        select(Batch).where(Batch.id == batch_id).with_for_update(of=Batch)
    )
    if not batch or batch.status not in {
        BatchStatus.FINAL_APPROVED,
        BatchStatus.CERTIFICATES_GENERATED,
    }:
        raise ValueError("Batch is not finally approved.")
    revision = current_revision(db, batch)
    if (
        not revision.state_review
        or revision.state_review.decision != Decision.APPROVE
        or not db.get(IssuanceRequest, revision.id)
        or not revision.candidates
    ):
        raise ValueError("No eligible issuance request exists for this revision.")
    issued = 0
    for candidate in revision.candidates:
        existing = db.scalar(
            select(CandidateCertificate).where(
                CandidateCertificate.candidate_id == candidate.id
            )
        )
        if existing and existing.status == "CANCELLED":
            continue
        path = certificate_path(candidate.id)
        certificate = existing or CandidateCertificate(
            candidate_id=candidate.id,
            number=f"CF-{uuid4().hex.upper()}",
            issued_at=utc_now(),
        )
        if not existing or not path.is_file():
            render_certificate(
                path,
                name=candidate.data["student_name"],
                course=candidate.data["course_name"],
                centre=batch.centre.name,
                assessment_date=candidate.data["assessment_date"],
                number=certificate.number,
                issued_at=certificate.issued_at,
            )
        if not existing:
            db.add(certificate)
            issued += 1
    if batch.status != BatchStatus.CERTIFICATES_GENERATED:
        batch.status = BatchStatus.CERTIFICATES_GENERATED
        batch.version += 1
    db.commit()
    return issued


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate private PDFs for a finally approved batch."
    )
    parser.add_argument("batch_id", type=UUID)
    args = parser.parse_args()
    with Session(engine()) as db:
        try:
            print(f"Issued {issue(db, str(args.batch_id))} new certificates.")
        except ValueError as error:
            raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
