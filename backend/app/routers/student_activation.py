import csv
import io
import re
from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.config import settings
from app.dependencies import CentreActor, Db
from app.services.activation_slip_pdf import render_activation_slips
from app.services.authentication import check_rate
from app.services.student_activation import (
    create_student_account,
    export_codes,
    verify_code,
)
from app.student_schemas import (
    ActivationGrant,
    ActivationPassword,
    ActivationStudent,
    ActivationVerification,
)

router = APIRouter(tags=["Student activation"])


@router.post("/student/activation/verify")
def verify(data: ActivationVerification, request: Request, db: Db) -> ActivationGrant:
    check_rate(request, scope="activation")
    return ActivationGrant(grant=verify_code(db, data))


@router.post("/student/activation/complete", status_code=204)
def complete(data: ActivationPassword, db: Db) -> Response:
    create_student_account(db, data)
    return Response(status_code=204)


def safe_cell(value: str) -> str:
    return "'" + value if re.match(r"^\s*[=+\-@]|^[\t\r\n]", value) else value


def download_codes(
    db: Db, actor: CentreActor, batch_id: UUID, student_id: str | None = None
) -> Response:
    rows = export_codes(db, actor, str(batch_id), student_id)
    stream = io.StringIO()
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
    writer.writerow(("student_id", "student_name", "course_name", "activation_code"))
    writer.writerows(
        tuple(
            safe_cell(value)
            for value in (row.student_id, row.student_name, row.course, row.code)
        )
        for row in rows
    )
    db.commit()
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="activation-codes-{batch_id}.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/centre/batches/{batch_id}/activation-codes/export")
def export(batch_id: UUID, db: Db, actor: CentreActor) -> Response:
    return download_codes(db, actor, batch_id)


@router.post("/centre/batches/{batch_id}/activation-codes/regenerate")
def regenerate(
    batch_id: UUID, data: ActivationStudent, db: Db, actor: CentreActor
) -> Response:
    return download_codes(db, actor, batch_id, data.student_id)


def download_slips(
    db: Db, actor: CentreActor, batch_id: UUID, candidate_id: UUID | None = None
) -> Response:
    rows = export_codes(
        db,
        actor,
        str(batch_id),
        candidate_id=str(candidate_id) if candidate_id else None,
        export_format="PDF",
    )
    content = render_activation_slips(rows, settings().app_origin)
    db.commit()
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="activation-slips-{candidate_id or batch_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/centre/batches/{batch_id}/activation-slips")
def export_slips(batch_id: UUID, db: Db, actor: CentreActor) -> Response:
    return download_slips(db, actor, batch_id)


@router.post("/centre/batches/{batch_id}/candidates/{candidate_id}/activation-slip")
def export_individual_slip(
    batch_id: UUID, candidate_id: UUID, db: Db, actor: CentreActor
) -> Response:
    return download_slips(db, actor, batch_id, candidate_id)
