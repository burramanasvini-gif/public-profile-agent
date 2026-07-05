"""
report.py
---------
Renders a structured profile dict (matching schema.py) into:
  1. Markdown (human-readable, easy to diff/version-control)
  2. PDF (polished, shareable document)

Both renderers are pure functions of the same JSON, so the two output
formats never disagree with each other.
"""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .schema import NOT_AVAILABLE


def render_markdown(profile: dict) -> str:
    bd = profile["basic_details"]
    lines = [f"# Profile: {profile['full_name']}", ""]

    lines += ["## Executive Summary", "", profile["executive_summary"], ""]

    lines += ["## Basic Details", ""]
    lines += [
        f"- **Full Name:** {bd['full_name']}",
        f"- **Age / Date of Birth:** {bd['age_or_dob']}",
        f"- **Occupation:** {bd['occupation']}",
        f"- **Industry:** {bd['industry']}",
        f"- **Current City:** {bd['current_city']}",
        f"- **Current Country:** {bd['current_country']}",
        "",
    ]

    lines += ["## Biography / Summary", "", profile["biography"], ""]

    lines += ["## Career Timeline", ""]
    if profile["career_timeline"]:
        for item in profile["career_timeline"]:
            lines.append(f"- **{item['period']}** — {item['role_or_event']}")
    else:
        lines.append(f"_{NOT_AVAILABLE}_")
    lines.append("")

    lines += ["## Interests", ""]
    if profile["interests"]:
        lines += [f"- {i}" for i in profile["interests"]]
    else:
        lines.append(f"_{NOT_AVAILABLE}_")
    lines.append("")

    lines += ["## Network", ""]
    if profile["network"]:
        lines += [f"- {n}" for n in profile["network"]]
    else:
        lines.append(f"_{NOT_AVAILABLE}_")
    lines.append("")

    lines += ["## Recent News / Public Activity", ""]
    if profile["recent_activity"]:
        for item in profile["recent_activity"]:
            lines.append(f"- **{item['date']}** — {item['headline']}")
    else:
        lines.append(f"_{NOT_AVAILABLE}_")
    lines.append("")

    lines += ["## References / Source Links", ""]
    if profile["references"]:
        for ref in profile["references"]:
            lines.append(f"- [{ref['title']}]({ref['url']})")
    else:
        lines.append(f"_{NOT_AVAILABLE}_")
    lines.append("")

    return "\n".join(lines)


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ProfileTitle",
            fontName="Helvetica-Bold",
            fontSize=20,
            spaceAfter=4,
            textColor=colors.HexColor("#111111"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            fontName="Helvetica-Bold",
            fontSize=12.5,
            spaceBefore=14,
            spaceAfter=6,
            textColor=colors.HexColor("#111111"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyTextCustom",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#222222"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Muted",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            textColor=colors.HexColor("#666666"),
        )
    )
    return styles


def render_pdf(profile: dict, output_path: str) -> str:
    styles = _styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=f"Profile - {profile['full_name']}",
    )
    story = []
    bd = profile["basic_details"]

    story.append(Paragraph(f"Profile: {profile['full_name']}", styles["ProfileTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#111111")))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Executive Summary", styles["SectionHeading"]))
    story.append(Paragraph(profile["executive_summary"], styles["BodyTextCustom"]))

    story.append(Paragraph("Basic Details", styles["SectionHeading"]))
    table_data = [
        ["Full Name", bd["full_name"]],
        ["Age / Date of Birth", bd["age_or_dob"]],
        ["Occupation", bd["occupation"]],
        ["Industry", bd["industry"]],
        ["Current City", bd["current_city"]],
        ["Current Country", bd["current_country"]],
    ]
    t = Table(table_data, colWidths=[4.5 * cm, 11 * cm])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#dddddd")),
            ]
        )
    )
    story.append(t)

    story.append(Paragraph("Biography / Summary", styles["SectionHeading"]))
    story.append(Paragraph(profile["biography"].replace("\n", "<br/>"), styles["BodyTextCustom"]))

    story.append(Paragraph("Career Timeline", styles["SectionHeading"]))
    if profile["career_timeline"]:
        items = [
            ListItem(
                Paragraph(f"<b>{i['period']}</b> — {i['role_or_event']}", styles["BulletText"])
            )
            for i in profile["career_timeline"]
        ]
        story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
    else:
        story.append(Paragraph(NOT_AVAILABLE, styles["Muted"]))

    story.append(Paragraph("Interests", styles["SectionHeading"]))
    if profile["interests"]:
        items = [ListItem(Paragraph(i, styles["BulletText"])) for i in profile["interests"]]
        story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
    else:
        story.append(Paragraph(NOT_AVAILABLE, styles["Muted"]))

    story.append(Paragraph("Network", styles["SectionHeading"]))
    if profile["network"]:
        items = [ListItem(Paragraph(n, styles["BulletText"])) for n in profile["network"]]
        story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
    else:
        story.append(Paragraph(NOT_AVAILABLE, styles["Muted"]))

    story.append(Paragraph("Recent News / Public Activity", styles["SectionHeading"]))
    if profile["recent_activity"]:
        items = [
            ListItem(Paragraph(f"<b>{a['date']}</b> — {a['headline']}", styles["BulletText"]))
            for a in profile["recent_activity"]
        ]
        story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
    else:
        story.append(Paragraph(NOT_AVAILABLE, styles["Muted"]))

    story.append(Paragraph("References / Source Links", styles["SectionHeading"]))
    if profile["references"]:
        items = [
            ListItem(Paragraph(f"{r['title']} — {r['url']}", styles["BulletText"]))
            for r in profile["references"]
        ]
        story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
    else:
        story.append(Paragraph(NOT_AVAILABLE, styles["Muted"]))

    doc.build(story)
    return output_path
