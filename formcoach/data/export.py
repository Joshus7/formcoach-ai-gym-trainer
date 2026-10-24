"""CSV export of sessions/history and a one-page PDF session summary (reportlab)."""
from __future__ import annotations

import csv
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..core.exercises import EXERCISES
from ..core.session import Session
from .db import Database

REP_FIELDS = ["session_started", "exercise", "rep", "score", "valid", "faults", "duration_s"]


def _name(exercise: str) -> str:
    return EXERCISES[exercise].name if exercise in EXERCISES else exercise


def session_to_csv(s: Session, path: str | Path, fault_messages: dict[str, str] | None = None) -> Path:
    path = Path(path)
    msgs = fault_messages or {}
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(REP_FIELDS)
        for r in s.reps:
            w.writerow([s.started_at.isoformat(timespec="seconds"), s.exercise, r.index, r.score,
                        "yes" if r.valid else "no rep", "; ".join(msgs.get(f, f) for f in r.faults),
                        round(r.duration, 2)])
    return path


def history_to_csv(db: Database, user_id: int | None, path: str | Path, exercise: str | None = None) -> Path:
    path = Path(path)
    sessions = db.list_sessions(user_id, exercise)
    cols = ["id", "exercise", "started_at", "ended_at", "total_reps", "no_reps", "avg_score", "duration_s",
            "tut_s", "sets_completed", "most_common_fault", "source"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["user"] + cols)
        for s in sessions:
            w.writerow([db.user_name(s["user_id"])] + [s[c] for c in cols])
    return path


def session_to_pdf(s: Session, path: str | Path, user_name: str = "",
                   fault_messages: dict[str, str] | None = None) -> Path:
    """One A4 page: header, key numbers, rep-score chart, most common mistakes, rep table."""
    path = Path(path)
    msgs = fault_messages or {}
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm, title="FormCoach session summary")
    story = [Paragraph(f"FormCoach - {_name(s.exercise)} session", styles["Title"]),
             Paragraph(f"{user_name + ' - ' if user_name else ''}{s.started_at:%A %d %B %Y, %H:%M}",
                       styles["Normal"]), Spacer(1, 6 * mm)]

    m, sec = divmod(int(round(s.duration_s)), 60)
    best, worst = s.best_rep, s.worst_rep
    stats = [["Total reps", str(s.good_reps), "No-reps", str(s.no_reps)],
             ["Average score", f"{s.avg_score:.0f}", "Duration", f"{m}:{sec:02d}"],
             ["Best rep", f"#{best.index} ({best.score})" if best else "-",
              "Worst rep", f"#{worst.index} ({worst.score})" if worst else "-"],
             ["Time under tension", f"{s.time_under_tension_s:.0f} s", "Sets completed", str(s.sets_completed)]]
    t = Table(stats, colWidths=[42 * mm, 42 * mm, 42 * mm, 42 * mm])
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 10),
                           ("TEXTCOLOR", (0, 0), (0, -1), colors.grey), ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
                           ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"), ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
    story += [t, Spacer(1, 6 * mm)]

    if s.reps:
        d = Drawing(170 * mm, 55 * mm)
        chart = VerticalBarChart()
        chart.x, chart.y, chart.width, chart.height = 10 * mm, 8 * mm, 155 * mm, 42 * mm
        chart.data = [[r.score for r in s.reps]]
        chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, 100, 25
        step = max(1, len(s.reps) // 20)
        chart.categoryAxis.categoryNames = [str(r.index) if (r.index - 1) % step == 0 else "" for r in s.reps]
        chart.bars.strokeColor = None
        for i, r in enumerate(s.reps):
            chart.bars[(0, i)].fillColor = colors.HexColor("#16a36a" if r.valid else "#e07b00")
        d.add(chart)
        story += [Paragraph("Score per rep (orange = no rep)", styles["Heading3"]), d, Spacer(1, 4 * mm)]

    counts = s.fault_counts.most_common(3)
    story.append(Paragraph("Most common mistakes", styles["Heading3"]))
    story.append(Paragraph("<br/>".join(f"{msgs.get(f, f)} - {n} of {len(s.reps)} reps" for f, n in counts)
                           if counts else "None - clean workout!", styles["Normal"]))
    story.append(Spacer(1, 4 * mm))

    rows = [["Rep", "Score", "Result", "Faults"]]
    max_rows = 18  # keep it to one page
    for r in s.reps[:max_rows]:
        rows.append([str(r.index), str(r.score), "OK" if r.valid else "NO REP",
                     ", ".join(msgs.get(f, f) for f in r.faults) or "-"])
    if len(s.reps) > max_rows:
        rows.append(["...", "", "", f"{len(s.reps) - max_rows} more reps in the CSV export"])
    rt = Table(rows, colWidths=[15 * mm, 18 * mm, 22 * mm, 113 * mm])
    rt.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f6")),
                            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story.append(rt)
    doc.build(story)
    return path
