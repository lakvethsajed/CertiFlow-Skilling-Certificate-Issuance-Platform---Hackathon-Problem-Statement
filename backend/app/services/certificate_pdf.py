import os
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import UUID

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from app.config import settings


def certificate_path(candidate_id: str) -> Path:
    root = settings().certificate_storage.resolve()
    path = (root / f"{UUID(candidate_id)}.pdf").resolve()
    if path.parent != root or path.name != f"{UUID(candidate_id)}.pdf":
        raise ValueError("Invalid certificate storage location.")
    return path


def render_certificate(
    destination: Path,
    *,
    name: str,
    course: str,
    centre: str,
    assessment_date: str,
    number: str,
    issued_at: datetime,
) -> None:
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, suffix=".pdf", delete=False
    ) as temp:
        temporary_path = Path(temp.name)
    try:
        page_width, page_height = landscape(A4)
        pdf = Canvas(str(temporary_path), pagesize=(page_width, page_height))
        pdf.setTitle(f"CertiFlow certificate {number}")
        navy = HexColor("#172843")
        gold = HexColor("#997429")
        pdf.setFillColor(HexColor("#f9f7ef"))
        pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)
        for margin, width in [(25, 2), (33, 0.6)]:
            pdf.setStrokeColor(gold)
            pdf.setLineWidth(width)
            pdf.rect(margin, margin, page_width - 2 * margin, page_height - 2 * margin)

        def text(value: str, y: float, size: int, font: str = "Helvetica") -> None:
            limit = page_width - 120
            width = pdfmetrics.stringWidth(value, font, size)
            fitted = min(size, size * limit / width) if width else size
            pdf.setFont(font, fitted)
            pdf.drawCentredString(page_width / 2, y, value)

        pdf.setFillColor(navy)
        text("CERTIFLOW  /  TRAINING CERTIFICATION", 494, 13, "Helvetica-Bold")
        text("Certificate of Completion", 423, 36, "Times-Bold")
        text("This certifies that", 371, 15)
        text(name, 320, 32, "Times-Bold")
        text("completed training in", 277, 15)
        text(course, 239, 22, "Helvetica-Bold")
        text(centre, 202, 15)
        pdf.setStrokeColor(gold)
        pdf.line(160, 166, page_width - 160, 166)
        text(
            f"Assessment date: {assessment_date}  |  Issued: {issued_at.date().isoformat()}",
            126,
            12,
        )
        text(f"Certificate number: {number}", 92, 11)
        pdf.showPage()
        pdf.save()
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
