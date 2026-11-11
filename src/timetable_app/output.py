from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DAYS = {1: "SUN", 2: "MON", 3: "TUE", 4: "WED", 5: "THU"}
DAY_NAMES = {1: "Sunday", 2: "Monday", 3: "Tuesday", 4: "Wednesday", 5: "Thursday"}


def read_csv(folder: Path, name: str) -> list[dict[str, str]]:
    with (folder / name).open("r", encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]


def parse_last_solution(output: str) -> list[dict[str, int]]:
    """Parse the last MiniZinc optimization solution from EVENT| rows."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if line == "----------":
            if any(x.startswith("EVENT|") for x in current):
                blocks.append(current)
            current = []
        elif line.startswith("EVENT|"):
            current.append(line)
    if any(x.startswith("EVENT|") for x in current):
        blocks.append(current)
    if not blocks:
        raise ValueError("No complete MiniZinc EVENT rows were found in solver output")

    result = []
    for line in blocks[-1]:
        parts = line.split("|")
        if len(parts) != 10:
            raise ValueError(f"Malformed MiniZinc event row: {line}")
        _, event, offer, day, start, duration, teacher1, teacher2, room1, room2 = parts
        result.append({
            "event_id": int(event), "offer_idx": int(offer), "day_idx": int(day),
            "start_period": int(start), "duration": int(duration),
            "teacher1_idx": int(teacher1), "teacher2_idx": int(teacher2),
            "room1_idx": int(room1), "room2_idx": int(room2),
        })
    return result


def _overlap(a: dict[str, int], b: dict[str, int]) -> bool:
    return (a["day_idx"] == b["day_idx"] and
            a["start_period"] <= b["start_period"] + b["duration"] - 1 and
            b["start_period"] <= a["start_period"] + a["duration"] - 1)


def validate_solution(events: list[dict[str, int]], input_dir: Path) -> list[str]:
    errors: list[str] = []
    batches = read_csv(input_dir, "batches.csv")
    courses = read_csv(input_dir, "courses.csv")
    offerings = read_csv(input_dir, "offerings.csv")
    teachers = read_csv(input_dir, "teachers.csv")
    labs = read_csv(input_dir, "lab_teacher_assignments.csv")
    pairs = read_csv(input_dir, "parallel_lab_pairs.csv")
    rooms = read_csv(input_dir, "rooms.csv")
    periods = read_csv(input_dir, "periods.csv")

    if not offerings or not events:
        return ["No offerings or solved events were provided"]
    if len({e["event_id"] for e in events}) != len(events):
        errors.append("Duplicate event_id in solver output")
    offer_by_idx = {i + 1: row for i, row in enumerate(offerings)}
    course_by_code = {row["course_code"]: row for row in courses}
    batch_size = {row["batch_id"]: int(row["student_count"]) for row in batches}
    teacher_by_idx = {i + 1: row for i, row in enumerate(teachers)}
    room_by_idx = {i + 1: row for i, row in enumerate(rooms)}
    lab_teacher_by_code = {r["course_code"]: (r["teacher_1_id"], r["teacher_2_id"]) for r in labs}

    expected = sum(int(o["sessions_per_week"]) for o in offerings)
    if len(events) != expected:
        errors.append(f"Expected {expected} events, solver output has {len(events)}")
    counts = defaultdict(int)
    by_offer = defaultdict(list)
    for e in events:
        offer = offer_by_idx.get(e["offer_idx"])
        if offer is None:
            errors.append(f"Event {e['event_id']}: unknown offering index {e['offer_idx']}")
            continue
        by_offer[e["offer_idx"]].append(e)
        counts[e["offer_idx"]] += 1
        code, batch = offer["course_code"], offer["batch_id"]
        course = course_by_code[code]
        etype = offer["course_type"]
        if e["day_idx"] not in DAYS:
            errors.append(f"Event {e['event_id']}: invalid day index")
        else:
            for tidx in (e["teacher1_idx"], e["teacher2_idx"]):
                teacher = teacher_by_idx.get(tidx)
                if teacher:
                    available = teacher["available_days"].upper()
                    if available not in ("ANY", "ALL", "") and DAYS[e["day_idx"]] not in {x.strip() for x in available.replace(";", ",").split(",")}:
                        errors.append(f"Teacher {teacher['teacher_id']} is unavailable on {DAYS[e['day_idx']]}")
        if e["start_period"] < 1 or e["start_period"] + e["duration"] - 1 > len(periods):
            errors.append(f"Event {e['event_id']}: outside the class-period grid")
        elif e["duration"] == 3 and e["start_period"] not in (1, 4):
            errors.append(f"Event {e['event_id']}: 3-period block crosses a break")
        elif e["duration"] == 2 and e["start_period"] not in (1, 2, 4, 5):
            errors.append(f"Event {e['event_id']}: 2-period block crosses a break")
        if etype == "theory" and e["room2_idx"] != 0:
            errors.append(f"Event {e['event_id']}: theory must use exactly one room")
        if etype == "lab":
            fixed = lab_teacher_by_code.get(code)
            t1 = teacher_by_idx.get(e["teacher1_idx"], {}).get("teacher_id")
            t2 = teacher_by_idx.get(e["teacher2_idx"], {}).get("teacher_id")
            if fixed and (t1, t2) != fixed:
                errors.append(f"Lab {code}: solver teacher pair differs from fixed CSV pair")

        assigned_rooms = [e["room1_idx"]] + ([e["room2_idx"]] if e["room2_idx"] else [])
        if e["room1_idx"] not in room_by_idx:
            errors.append(f"Event {e['event_id']}: unknown room 1 index")
            continue
        if e["room2_idx"] and e["room2_idx"] not in room_by_idx:
            errors.append(f"Event {e['event_id']}: unknown room 2 index")
            continue
        if len(assigned_rooms) != len(set(assigned_rooms)):
            errors.append(f"Event {e['event_id']}: room 1 and room 2 must differ")
        selected_rooms = [room_by_idx[r] for r in assigned_rooms]
        if etype == "theory":
            need = batch_size[batch]
            for room in selected_rooms:
                if room["usable_for_theory"].lower() != "true":
                    errors.append(f"Theory {code}: room {room['room_id']} is not theory-capable")
            if sum(int(r["capacity"]) for r in selected_rooms) < need:
                errors.append(f"Theory {code}: assigned rooms lack capacity for batch {batch}")
            if need > 60 and selected_rooms[0]["room_id"] != "202":
                errors.append(f"Theory {code}: batch above 60 must use room 202")
        else:
            if any(r["usable_for_lab"].lower() != "true" for r in selected_rooms):
                errors.append(f"Lab {code}: assigned room is not lab-capable")
            parallel = any(
                other["event_id"] != e["event_id"] and other["offer_idx"] != e["offer_idx"] and
                offer_by_idx.get(other["offer_idx"], {}).get("batch_id") == batch and
                offer_by_idx.get(other["offer_idx"], {}).get("course_type") == "lab" and
                other["day_idx"] == e["day_idx"] and other["start_period"] == e["start_period"] and
                other["duration"] == e["duration"]
                for other in events
            )
            required = (batch_size[batch] + 1) // 2 if parallel else batch_size[batch]
            if sum(int(r["capacity"]) for r in selected_rooms) < required:
                errors.append(f"Lab {code}: assigned lab rooms lack capacity for {required} students")

    for i, offer in enumerate(offerings, start=1):
        if counts[i] != int(offer["sessions_per_week"]):
            errors.append(f"{offer['course_code']} batch {offer['batch_id']}: expected {offer['sessions_per_week']} meetings, got {counts[i]}")
        codes = [e["event_id"] for e in by_offer.get(i, [])]
        if len(codes) != len(set(codes)):
            errors.append(f"Offering {offer['offering_id']}: duplicate event")
        if offer["distinct_session_days"].lower() == "true":
            days = [e["day_idx"] for e in by_offer.get(i, [])]
            if len(days) != len(set(days)):
                errors.append(f"{offer['course_code']}: sessions must be on distinct days")
        if offer["course_type"].strip().lower() == "theory":
            periods_per_day = defaultdict(int)
            for event in by_offer.get(i, []):
                periods_per_day[event["day_idx"]] += event["duration"]
            for day, occupied in periods_per_day.items():
                if occupied > 2:
                    errors.append(
                        f"{offer['course_code']} batch {offer['batch_id']}: "
                        f"more than two theory periods scheduled on day {day}"
                    )

    # Same-batch overlaps are permitted only as an exact two-lab parallel block.
    for ix, e1 in enumerate(events):
        o1 = offer_by_idx.get(e1["offer_idx"])
        if not o1:
            continue
        for e2 in events[ix + 1:]:
            o2 = offer_by_idx.get(e2["offer_idx"])
            if not o2:
                continue
            if o1["batch_id"] == o2["batch_id"] and _overlap(e1, e2):
                allowed = (o1["course_type"] == o2["course_type"] == "lab" and
                           e1["offer_idx"] != e2["offer_idx"] and
                           e1["start_period"] == e2["start_period"] and
                           e1["duration"] == e2["duration"])
                if not allowed:
                    errors.append(f"Batch {o1['batch_id']}: invalid overlap between {o1['course_code']} and {o2['course_code']}")

            if _overlap(e1, e2):
                teachers1 = {e1["teacher1_idx"]} | ({e1["teacher2_idx"]} if e1["teacher2_idx"] else set())
                teachers2 = {e2["teacher1_idx"]} | ({e2["teacher2_idx"]} if e2["teacher2_idx"] else set())
                if teachers1 & teachers2:
                    errors.append(f"Teacher overlap between events {e1['event_id']} and {e2['event_id']}")
                rooms1 = {e1["room1_idx"]} | ({e1["room2_idx"]} if e1["room2_idx"] else set())
                rooms2 = {e2["room1_idx"]} | ({e2["room2_idx"]} if e2["room2_idx"] else set())
                if rooms1 & rooms2:
                    errors.append(f"Room overlap between events {e1['event_id']} and {e2['event_id']}")

    # Parallel pairs in the source must match session-by-session.
    offer_index = {(r["course_code"], r["batch_id"]): i + 1 for i, r in enumerate(offerings)}
    for p in pairs:
        a, b = offer_index.get((p["lab_course_1"], p["batch_id"])), offer_index.get((p["lab_course_2"], p["batch_id"]))
        if not a or not b:
            errors.append(f"Parallel pair {p['parallel_lab_pair_id']}: offering missing")
            continue
        events_a = sorted(by_offer[a], key=lambda x: x["event_id"])
        events_b = sorted(by_offer[b], key=lambda x: x["event_id"])
        if len(events_a) != len(events_b):
            errors.append(f"Parallel pair {p['parallel_lab_pair_id']}: meeting count differs")
        else:
            for ea, eb in zip(events_a, events_b):
                if (ea["day_idx"], ea["start_period"], ea["duration"]) != (eb["day_idx"], eb["start_period"], eb["duration"]):
                    errors.append(f"Parallel pair {p['parallel_lab_pair_id']}: sessions are not aligned")

    # Workload is counted once per offering per assigned teacher, not per repeated session event.
    load = defaultdict(float)
    assigned_offers = defaultdict(list)
    for offer_idx, offer in enumerate(offerings, start=1):
        ev = by_offer.get(offer_idx, [])
        if not ev:
            continue
        t1, t2 = ev[0]["teacher1_idx"], ev[0]["teacher2_idx"]
        per_teacher = float(offer["weekly_load_periods_per_teacher"])
        for tidx in (t1, t2):
            if tidx:
                load[tidx] += per_teacher
                assigned_offers[tidx].append(offer)
    workload_rows = []
    for idx, teacher in teacher_by_idx.items():
        total = load[idx]
        base, hard = float(teacher["base_max_weekly_load"]), float(teacher["hard_max_weekly_load"])
        if total > hard + 1e-8:
            errors.append(f"Teacher {teacher['teacher_id']}: {total:g} h exceeds hard cap {hard:g}")
        if "external" in teacher["designation"].lower():
            courses_for_teacher = assigned_offers[idx]
            if len(courses_for_teacher) != 1 or total != 3 or courses_for_teacher[0]["course_type"] != "theory":
                errors.append(f"External {teacher['teacher_id']}: must have exactly one 3-hour theory course")
            elif courses_for_teacher:
                external_events = by_offer.get(offerings.index(courses_for_teacher[0]) + 1, [])
                ordered = sorted(external_events, key=lambda x: x["start_period"])
                if (len(ordered) != 3 or any(e["day_idx"] != 5 for e in ordered) or
                    ordered[0]["start_period"] not in (1, 4) or
                    [e["start_period"] for e in ordered] != list(range(ordered[0]["start_period"], ordered[0]["start_period"] + 3))):
                    errors.append(f"External {teacher['teacher_id']}: course must be three consecutive periods on Thursday")
        workload_rows.append({
            "teacher_id": teacher["teacher_id"], "designation": teacher["designation"],
            "base_limit": f"{base:g}", "hard_limit": f"{hard:g}",
            "weekly_load": f"{total:g}", "over_base": f"{max(0, total-base):g}",
        })
    return errors


def _period_text(periods: list[dict[str, str]], period: int) -> str:
    row = periods[period - 1]
    return f"{row['start_time']}–{row['end_time']}"


def _teacher_display_name(teacher: dict[str, str]) -> str:
    teacher_id = teacher["teacher_id"].strip()
    name = (teacher.get("teacher_name") or "").strip()
    if not name or name.casefold() == teacher_id.casefold():
        return teacher_id
    return f"{name} ({teacher_id})"


def _clock_text(value: str) -> str:
    return datetime.strptime(value, "%H:%M").strftime("%I:%M %p").lstrip("0")


def _period_block_time(start_period: int, duration: int, periods: list[dict[str, str]]) -> str:
    segments: list[tuple[str, str]] = []
    segment_start = periods[start_period - 1]["start_time"]
    previous_end = segment_start
    previous_period_no = start_period
    for period_no in range(start_period, start_period + duration):
        current = periods[period_no - 1]
        if period_no > start_period and periods[period_no - 2]["end_time"] != current["start_time"]:
            segments.append((segment_start, periods[period_no - 2]["end_time"]))
            segment_start = current["start_time"]
        previous_end = current["end_time"]
        previous_period_no = period_no
    segments.append((segment_start, previous_end))
    return "; ".join(f"{_clock_text(start)}–{_clock_text(end)}" for start, end in segments)


def export_solution(output: str, input_dir: Path, output_dir: Path, write_pdf: bool = True) -> tuple[Path, Path, Path, Path | None]:
    events = parse_last_solution(output)
    errors = validate_solution(events, input_dir)
    if errors:
        raise ValueError("Independent solution validation failed:\n- " + "\n- ".join(errors[:50]))

    batches = read_csv(input_dir, "batches.csv")
    courses = read_csv(input_dir, "courses.csv")
    offerings = read_csv(input_dir, "offerings.csv")
    teachers = read_csv(input_dir, "teachers.csv")
    rooms = read_csv(input_dir, "rooms.csv")
    periods = read_csv(input_dir, "periods.csv")
    course_by_code = {r["course_code"]: r for r in courses}
    batch_by_id = {r["batch_id"]: r for r in batches}
    teacher_by_idx = {i + 1: r for i, r in enumerate(teachers)}
    room_by_idx = {i + 1: r for i, r in enumerate(rooms)}
    offer_by_idx = {i + 1: r for i, r in enumerate(offerings)}

    normalized = []
    for e in events:
        offer = offer_by_idx[e["offer_idx"]]
        course = course_by_code[offer["course_code"]]
        batch = offer["batch_id"]
        teacher1 = teacher_by_idx[e["teacher1_idx"]]
        teacher2 = teacher_by_idx[e["teacher2_idx"]] if e["teacher2_idx"] else None
        t1 = teacher1["teacher_id"]
        t2 = teacher2["teacher_id"] if teacher2 else ""
        r1 = room_by_idx[e["room1_idx"]]["room_id"]
        r2 = room_by_idx[e["room2_idx"]]["room_id"] if e["room2_idx"] else ""
        batch_row = batch_by_id[batch]
        normalized.append({
            **e, "batch_id": batch, "course_code": offer["course_code"],
            "course_title": course["course_title"], "course_type": offer["course_type"],
            "teacher1_id": t1, "teacher2_id": t2, "room1_id": r1, "room2_id": r2,
            "teacher1_name": _teacher_display_name(teacher1),
            "teacher2_name": _teacher_display_name(teacher2) if teacher2 else "",
            "study_year": batch_row["study_year"], "semester": batch_row["semester"],
            "student_count": batch_row["student_count"],
            "day": DAYS[e["day_idx"]], "start_time": periods[e["start_period"]-1]["start_time"],
            "end_time": periods[e["start_period"]+e["duration"]-2]["end_time"],
            "day_name": DAY_NAMES[e["day_idx"]],
            "period_label": str(e["start_period"]) if e["duration"] == 1 else f"{e['start_period']}-{e['start_period'] + e['duration'] - 1}",
            "time_text": _period_block_time(e["start_period"], e["duration"], periods),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "schedule.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fields = ["event_id", "batch_id", "course_code", "course_title", "course_type", "day", "start_period", "duration", "start_time", "end_time", "teacher1_id", "teacher2_id", "room1_id", "room2_id"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for e in sorted(normalized, key=lambda x: (x["batch_id"], x["day_idx"], x["start_period"], x["course_code"])):
            writer.writerow({k: e[k] for k in fields})

    office_path = output_dir / "office_schedule.csv"
    _write_office_schedule(office_path, normalized)
    routine_path = output_dir / "routine.csv"
    _write_routine_csv(routine_path, normalized)

    workload = defaultdict(float)
    for offer_idx, offer in enumerate(offerings, start=1):
        evs = [e for e in normalized if e["offer_idx"] == offer_idx]
        if evs:
            load = float(offer["weekly_load_periods_per_teacher"])
            workload[evs[0]["teacher1_idx"]] += load
            if evs[0]["teacher2_idx"]:
                workload[evs[0]["teacher2_idx"]] += load
    load_path = output_dir / "teacher_workloads.csv"
    with load_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["teacher_id", "designation", "base_limit", "hard_limit", "weekly_load", "over_base"])
        writer.writeheader()
        for idx, teacher in teacher_by_idx.items():
            total = workload[idx]
            base = float(teacher["base_max_weekly_load"])
            writer.writerow({"teacher_id": teacher["teacher_id"], "designation": teacher["designation"],
                             "base_limit": teacher["base_max_weekly_load"], "hard_limit": teacher["hard_max_weekly_load"],
                             "weekly_load": f"{total:g}", "over_base": f"{max(0,total-base):g}"})

    pdf_path = output_dir / "routine.pdf" if write_pdf else None
    if pdf_path is not None:
        _write_routine_pdf(pdf_path, normalized, batches, offerings, course_by_code, teacher_by_idx, periods)
    return csv_path, office_path, load_path, pdf_path


def _write_office_schedule(path: Path, events: list[dict]) -> None:
    """Write the compact event list requested for office staff to build routines."""
    fields = ["Batch_ID", "Day_Name", "Course_code", "Course_title", "Assigned_Teacher_1", "Assigned_Teacher_2", "slot_taken", "room"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for e in sorted(events, key=lambda x: (x["batch_id"], x["day_idx"], x["start_period"], x["course_code"])):
            slots = ",".join(str(p) for p in range(e["start_period"], e["start_period"] + e["duration"]))
            room = str(e["room1_id"]) + ("/" + str(e["room2_id"]) if e["room2_id"] else "")
            writer.writerow({
                "Batch_ID": e["batch_id"], "Day_Name": e["day"].lower(),
                "Course_code": e["course_code"], "Course_title": e["course_title"],
                "Assigned_Teacher_1": e["teacher1_id"], "Assigned_Teacher_2": e["teacher2_id"],
                "slot_taken": f"[{slots}]", "room": room,
            })


def _write_routine_csv(path: Path, events: list[dict]) -> None:
    """Write an office-friendly CSV with readable labels and schedule context."""
    fields = ["Day", "Course Code", "Slots", "Time", "Batch", "Year", "Semester",
              "Students", "Class Type", "Course Title", "Teacher 1", "Teacher 2", "Room"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for e in sorted(events, key=lambda x: (x["day_idx"], x["start_period"], x["batch_id"], x["course_code"])):
            room = str(e["room1_id"]) + ("/" + str(e["room2_id"]) if e["room2_id"] else "")
            writer.writerow({
                "Day": e.get("day_name", DAY_NAMES[e["day_idx"]]),
                "Course Code": e["course_code"], "Slots": e.get("period_label", str(e["start_period"])) ,
                "Time": e.get("time_text", ""), "Batch": f"Batch {e['batch_id']}",
                "Year": e.get("study_year", ""), "Semester": e.get("semester", ""),
                "Students": e.get("student_count", ""), "Class Type": e.get("course_type", "").title(),
                "Course Title": e["course_title"],
                "Teacher 1": e.get("teacher1_name", e.get("teacher1_id", "")),
                "Teacher 2": e.get("teacher2_name", e.get("teacher2_id", "")),
                "Room": f"Room {room}",
            })


def _write_routine_pdf(pdf_path: Path, events: list[dict], batches: list[dict], offerings: list[dict], course_by_code: dict, teacher_by_idx: dict, periods: list[dict]) -> None:
    page = landscape(A4)
    doc = SimpleDocTemplate(str(pdf_path), pagesize=page, rightMargin=12*mm, leftMargin=12*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("RoutineTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=16, leading=19, alignment=TA_CENTER, spaceAfter=4)
    subtitle_style = ParagraphStyle("RoutineSub", parent=styles["Normal"], fontSize=8, leading=10, alignment=TA_CENTER, spaceAfter=7)
    cell_style = ParagraphStyle("RoutineCell", parent=styles["Normal"], fontName="Helvetica", fontSize=6.2, leading=7.4, alignment=TA_CENTER)
    start_style = ParagraphStyle("RoutineStart", parent=cell_style, fontName="Helvetica-Bold", alignment=TA_LEFT)
    head_style = ParagraphStyle("RoutineHead", parent=cell_style, fontName="Helvetica-Bold", fontSize=6.2, leading=7, textColor=colors.white)
    legend_style = ParagraphStyle("RoutineLegend", parent=styles["Normal"], fontSize=6.7, leading=8)
    story = []

    # A dedicated tea-break column follows period 3, and a prayer-break column follows period 5.
    header = ["DAY"]
    for pno in range(1, 7):
        header.append(Paragraph(_period_text(periods, pno), head_style))
        if pno == 3:
            header.append(Paragraph("TEA<br/>BREAK<br/>11:10–11:40", head_style))
        if pno == 5:
            header.append(Paragraph("PRAYER<br/>BREAK<br/>13:35–14:00", head_style))
    widths = [22*mm] + [35.5*mm]*3 + [18*mm] + [35.5*mm]*2 + [20*mm] + [35.5*mm]
    # Layout column index corresponding to each class-period number.
    period_col = {1: 1, 2: 2, 3: 3, 4: 5, 5: 6, 6: 8}

    for bi, batch in enumerate(batches):
        bid = batch["batch_id"]
        story.append(Paragraph(f"Batch {bid} — Timetable", title_style))
        story.append(Paragraph(f"Students: {batch['student_count']} &nbsp;&nbsp; | &nbsp;&nbsp; Sunday–Thursday &nbsp;&nbsp; | &nbsp;&nbsp; Class periods exclude tea and prayer breaks", subtitle_style))
        grid = [[Paragraph(escape(str(x)), head_style) if not isinstance(x, Paragraph) else x for x in header]]
        batch_events = [e for e in events if e["batch_id"] == bid]
        # Map events by the starting slot; parallel lab events are displayed together in that cell.
        starts: dict[tuple[int,int], list[dict]] = defaultdict(list)
        continuations: dict[tuple[int,int], list[dict]] = defaultdict(list)
        for e in batch_events:
            for offset in range(e["duration"]):
                slot = e["start_period"] + offset
                if offset == 0:
                    starts[(e["day_idx"], slot)].append(e)
                else:
                    continuations[(e["day_idx"], slot)].append(e)
        for day_idx in range(1, 6):
            row: list[object] = [Paragraph(DAYS[day_idx], cell_style)]
            for pno in range(1, 7):
                cell_events = starts.get((day_idx,pno), [])
                cont_events = continuations.get((day_idx,pno), [])
                if cell_events:
                    lines = []
                    for e in sorted(cell_events, key=lambda x: x["course_code"]):
                        teachers = e["teacher1_id"] + (" / " + e["teacher2_id"] if e["teacher2_id"] else "")
                        if e["room2_id"]:
                            room_text = f"R{e['room1_id']} ({e['teacher1_id']}) / R{e['room2_id']} ({e['teacher2_id']})"
                        else:
                            room_text = f"R{e['room1_id']}"
                        lines.append(f"<b>{escape(e['course_code'])}</b><br/>{escape(e['course_title'])}<br/>{escape(teachers)}<br/>{escape(room_text)}")
                    cell = Paragraph("<br/><br/>".join(lines), start_style)
                elif cont_events:
                    labels = "<br/>".join("continued: " + escape(e["course_code"]) for e in sorted(cont_events, key=lambda x:x["course_code"]))
                    cell = Paragraph(labels, cell_style)
                else:
                    cell = ""
                row.append(cell)
                if pno == 3:
                    row.append(Paragraph("Tea", cell_style))
                if pno == 5:
                    row.append(Paragraph("Prayer", cell_style))
            grid.append(row)

        table = Table(grid, colWidths=widths, rowHeights=[18*mm] + [18.5*mm]*5, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#23415C")),
            ("BACKGROUND", (4,1), (4,-1), colors.HexColor("#E9EEF2")),
            ("BACKGROUND", (7,1), (7,-1), colors.HexColor("#E9EEF2")),
            ("GRID", (0,0), (-1,-1), 0.45, colors.HexColor("#73808C")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("LEFTPADDING", (0,0), (-1,-1), 2), ("RIGHTPADDING", (0,0), (-1,-1), 2),
            ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ]))
        story.append(table)
        story.append(Spacer(1, 4*mm))
        course_codes = sorted({e["course_code"] for e in batch_events})
        legend_data = [[Paragraph("COURSE", head_style), Paragraph("TITLE", head_style), Paragraph("TEACHER(S)", head_style)]]
        offering_codes = {o["course_code"] for o in offerings if o["batch_id"] == bid}
        for code in sorted(offering_codes):
            course = course_by_code[code]
            relevant = [e for e in batch_events if e["course_code"] == code]
            if relevant:
                teacher_ids = relevant[0]["teacher1_id"] + (" / " + relevant[0]["teacher2_id"] if relevant[0]["teacher2_id"] else "")
            else:
                teacher_ids = ""
            legend_data.append([Paragraph(escape(code), legend_style), Paragraph(escape(course["course_title"]), legend_style), Paragraph(escape(teacher_ids), legend_style)])
        legend = Table(legend_data, colWidths=[33*mm, 145*mm, 70*mm], repeatRows=1)
        legend.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#526D82")),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#AAB4BD")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3),
            ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ]))
        story.append(Paragraph("Course legend", styles["Heading3"]))
        story.append(legend)
        if bi < len(batches)-1:
            story.append(PageBreak())

    doc.build(story)
