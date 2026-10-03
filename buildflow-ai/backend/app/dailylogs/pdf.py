from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_pdf(*, org_name: str, project: dict, log: dict) -> bytes:
    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Heading2"], textColor=colors.HexColor("#1f3a5f"), spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    p = lambda t: Paragraph(escape(t).replace("\n", "<br/>") or "-", body)  # noqa: E731

    def table(rows, widths):
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef6")),
                               ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9),
                               ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"Daily Site Report {log['log_date']}", author=org_name)
    wf, mat = log["workforce"], log["materials"]
    story = [Paragraph(escape(org_name), ss["Title"]), Paragraph("Daily Site Report", ss["Heading3"]),
             table([["Project", f"{project['code']} - {project['name']}"], ["Date", str(log["log_date"])],
                    ["Weather", log["weather"] or "-"], ["Status", log["status"]]], [35 * mm, 135 * mm]),
             Paragraph("Workforce (from attendance)", h)]
    if wf["attendance_recorded"]:
        story.append(table([["On site", "Present", "Half day", "Absent", "Leave", "Overtime hrs"],
                            [wf["workers_on_site"], wf["present"], wf["half_day"], wf["absent"], wf["leave"],
                             wf["overtime_hours"]]], [28 * mm] * 6))
    else:
        story.append(p("No attendance sheet submitted for this date."))
    story += [Paragraph("Work completed", h), p(log["work_completed"])]
    if log["progress"]:
        story += [Paragraph("Quantities completed (BOQ)", h),
                  table([["Item", "Description", "Today", "Cumulative", "BOQ qty", "%"]] +
                        [[r["item_code"], Paragraph(escape(r["description"]), body), r["quantity_today"], r["cumulative"],
                          r["boq_quantity"], r["percent"]] for r in log["progress"]],
                        [20 * mm, 62 * mm, 22 * mm, 24 * mm, 24 * mm, 18 * mm])]
    story.append(Paragraph("Materials (from stock ledger)", h))
    rows = [["Movement", "Item", "Quantity"]]
    for label, key in (("Received", "received"), ("Issued to site", "issued"), ("Returned", "returned")):
        rows += [[label, f"{m['item_code']} - {m['item_name']}", m["quantity"]] for m in mat[key]]
    story.append(table(rows, [35 * mm, 100 * mm, 35 * mm]) if len(rows) > 1 else p("No material movements."))
    for title, key in (("Equipment", "equipment"), ("Issues / delays", "issues"), ("Safety", "safety"),
                       ("Quality", "quality"), ("Plan for tomorrow", "tomorrow_plan")):
        story += [Paragraph(title, h), p(log[key])]
    story += [Spacer(1, 18 * mm), table([["Prepared by (Site Engineer)", "Reviewed by (Project Manager)"], ["\n\n", "\n\n"]],
                                        [85 * mm, 85 * mm])]
    doc.build(story)
    return buf.getvalue()
