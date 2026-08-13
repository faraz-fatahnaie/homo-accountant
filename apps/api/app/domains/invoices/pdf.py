"""Persian RTL invoice PDF generation (reportlab + Vazirmatn).

Persian text is shaped (arabic_reshaper) and reordered (python-bidi) before
drawing; the Vazirmatn TTF fonts are bundled under app/core/fonts (OFL 1.1).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Literal

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

_FONT_DIR = Path(__file__).resolve().parents[2] / "core" / "fonts"
_FONT_REGULAR = _FONT_DIR / "Vazirmatn-Regular.ttf"
_FONT_BOLD = _FONT_DIR / "Vazirmatn-Bold.ttf"

_REGISTERED = False


def _ensure_fonts() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    pdfmetrics.registerFont(TTFont("Vazirmatn", str(_FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("Vazirmatn-Bold", str(_FONT_BOLD)))
    _REGISTERED = True


def shape(text: str) -> str:
    """Reshape + bidi-reorder a Persian string for RTL drawing."""
    reshaped = arabic_reshaper.reshape(text)
    return str(get_display(reshaped))


def _style(
    name: str, size: int, bold: bool = False, align: Literal[0, 1, 2, 4] = 0
) -> ParagraphStyle:
    return ParagraphStyle(
        name=name,
        fontName="Vazirmatn-Bold" if bold else "Vazirmatn",
        fontSize=size,
        leading=size * 1.7,
        alignment=align,
        textColor=colors.HexColor("#1c2430"),
        wordWrap="RTL",
    )


def _fa_num(n: int | str) -> str:
    fa = "۰۱۲۳۴۵۶۷۸۹"
    return "".join(fa[int(c)] if c.isdigit() else c for c in str(n))


def _money(n: int) -> str:
    s = f"{n:,}".replace(",", "٬")
    return _fa_num(s)


def render_invoice_pdf(
    *,
    company_name: str,
    invoice_number: str,
    customer_name: str,
    issue_date: str,
    due_date: str,
    items: list[dict[str, object]],
    total: int,
    paid: int,
    balance: int,
    notes: str | None,
    payment_instructions: str | None,
) -> bytes:
    """Return the PDF bytes for an invoice."""
    _ensure_fonts()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"صورتحساب {invoice_number}",
        author=company_name,
    )
    story: list[Flowable] = []

    # header
    header = Table(
        [
            [
                Paragraph(shape(company_name), _style("hdr1", 16, bold=True)),
                Paragraph(shape("صورتحساب فروش"), _style("hdr2", 16, bold=True, align=2)),
            ],
        ],
        colWidths=[90 * mm, 90 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#C9C4B2")),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 6 * mm))

    # meta
    meta_rows = [
        [
            Paragraph(shape("شماره:"), _style("m", 10, bold=True)),
            Paragraph(shape(invoice_number), _style("mv", 10, align=2)),
        ],
        [
            Paragraph(shape("مشتری:"), _style("m", 10, bold=True)),
            Paragraph(shape(customer_name), _style("mv", 10, align=2)),
        ],
        [
            Paragraph(shape("تاریخ صدور:"), _style("m", 10, bold=True)),
            Paragraph(shape(issue_date), _style("mv", 10, align=2)),
        ],
        [
            Paragraph(shape("سررسید:"), _style("m", 10, bold=True)),
            Paragraph(shape(due_date), _style("mv", 10, align=2)),
        ],
    ]
    meta = Table(meta_rows, colWidths=[30 * mm, 150 * mm])
    meta.setStyle(
        TableStyle(
            [
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ]
        )
    )
    story.append(meta)
    story.append(Spacer(1, 6 * mm))

    # items table
    header_cells = ["شرح", "تعداد", "قیمت واحد", "مبلغ"]
    table_data = [[Paragraph(shape(c), _style("th", 9, bold=True)) for c in header_cells]]
    for it in items:
        table_data.append(
            [
                Paragraph(shape(str(it["description"])), _style("td", 9)),
                Paragraph(shape(_fa_num(str(it["quantity"]))), _style("tdn", 9, align=2)),
                Paragraph(shape(_money(int(str(it["unit_price"])))), _style("tdn", 9, align=2)),
                Paragraph(shape(_money(int(str(it["line_total"])))), _style("tdn", 9, align=2)),
            ]
        )
    t = Table(table_data, colWidths=[90 * mm, 30 * mm, 40 * mm, 40 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0EDE4")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D8CF")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    # totals
    totals_rows = [
        [
            Paragraph(shape("جمع کل:"), _style("t", 10, bold=True)),
            Paragraph(shape(f"{_money(total)} ریال"), _style("tv", 10, bold=True, align=2)),
        ],
        [
            Paragraph(shape("پرداختشده:"), _style("t", 10)),
            Paragraph(shape(f"{_money(paid)} ریال"), _style("tv", 10, align=2)),
        ],
        [
            Paragraph(shape("مانده:"), _style("t", 10, bold=True)),
            Paragraph(shape(f"{_money(balance)} ریال"), _style("tv", 10, bold=True, align=2)),
        ],
    ]
    totals = Table(totals_rows, colWidths=[100 * mm, 80 * mm])
    totals.setStyle(
        TableStyle(
            [
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(totals)

    if payment_instructions:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(shape(f"دستور پرداخت: {payment_instructions}"), _style("note", 9)))
    if notes:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(shape(notes), _style("note", 9)))

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(shape("با تشکر از خرید شما"), _style("foot", 9, align=1)))

    doc.build(story)
    result = buf.getvalue()
    buf.close()
    return result
