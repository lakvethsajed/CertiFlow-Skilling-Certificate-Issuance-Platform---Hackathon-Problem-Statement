from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from app.services.student_activation import ExportedActivation

MARGIN = 36
SLIP_HEIGHT = 244
SLIPS_PER_PAGE = 3
INK = HexColor("#152840")
LINE = HexColor("#bac5d3")
ACCENT = HexColor("#edf1f6")
LABEL = HexColor("#475970")


def draw_fitted(
    pdf: Canvas, value: str, x: float, y: float, width: float, face: str, size: int
) -> None:
    line = " ".join(value.split())
    measured = stringWidth(line, face, size)
    pdf.setFont(face, min(size, size * width / measured) if measured else size)
    pdf.drawString(x, y, line)


def draw_slip(
    pdf: Canvas, row: ExportedActivation, top: float, width: float, website: str
) -> None:
    left = MARGIN + 15
    bottom = top - SLIP_HEIGHT + 10
    pdf.setStrokeColor(LINE)
    pdf.roundRect(MARGIN, bottom, width, SLIP_HEIGHT - 10, 6, fill=0)
    pdf.setFillColor(LABEL)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(left, top - 23, "CERTIFLOW")
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, top - 45, "Student account activation")
    for label, value, offset in (
        ("Student name", row.student_name, 67),
        ("Student ID", row.student_id, 83),
        ("Course", row.course, 99),
    ):
        pdf.setFillColor(LABEL)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(left, top - offset, label)
        pdf.setFillColor(INK)
        draw_fitted(
            pdf, value, left + 85, top - offset, width - 115, "Helvetica-Bold", 11
        )

    pdf.setFillColor(ACCENT)
    pdf.roundRect(left, top - 145, width - 30, 34, 4, stroke=0, fill=1)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(left + 10, top - 132, "Activation code")
    draw_fitted(pdf, row.code, left + 100, top - 134, width - 130, "Courier-Bold", 15)

    pdf.setFillColor(INK)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(left, top - 165, "1. Open the CertiFlow activation page.")
    draw_fitted(pdf, website, left + 13, top - 179, width - 43, "Helvetica-Bold", 10)
    pdf.linkURL(
        website, (left + 13, top - 182, left + width - 30, top - 169), relative=0
    )
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        left,
        top - 194,
        "2. Enter your Student ID and activation code, then create your password.",
    )
    pdf.drawString(
        left,
        top - 208,
        "3. Sign in with your registered email to access your certificates.",
    )
    pdf.setFillColor(LABEL)
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(
        left, top - 223, "Private - give this slip only to the student named above."
    )


def render_activation_slips(
    rows: list[ExportedActivation], portal_origin: str
) -> bytes:
    stream = BytesIO()
    width, height = A4
    pdf = Canvas(stream, pagesize=A4, pageCompression=1)
    pdf.setTitle("CertiFlow student activation slips")
    page_count = (len(rows) + SLIPS_PER_PAGE - 1) // SLIPS_PER_PAGE
    website = portal_origin.rstrip("/") + "/student/activate"
    for offset in range(0, len(rows), SLIPS_PER_PAGE):
        for index, row in enumerate(rows[offset : offset + SLIPS_PER_PAGE]):
            draw_slip(
                pdf,
                row,
                height - MARGIN - index * SLIP_HEIGHT,
                width - MARGIN * 2,
                website,
            )
        pdf.setFillColor(LABEL)
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(
            width - MARGIN, 38, f"Page {offset // SLIPS_PER_PAGE + 1} of {page_count}"
        )
        pdf.showPage()
    pdf.save()
    return stream.getvalue()
