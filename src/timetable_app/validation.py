from __future__ import annotations

import csv
from pathlib import Path

REQUIRED_COLUMNS = {
    "batches.csv": {"batch_id", "study_year", "semester", "student_count"},
    "courses.csv": {"course_code", "course_title", "course_type", "credit", "contact_hours", "required_room_type", "shared", "departmental"},
    "offerings.csv": {"offering_id", "course_code", "batch_id", "course_type", "sessions_per_week", "periods_per_session", "parallel_lab_pair_id", "teacher_count_min", "teacher_count_max", "teacher_assignment_mode", "staffing_rule", "weekly_load_periods_per_teacher", "distinct_session_days"},
    "lab_teacher_assignments.csv": {"course_code", "teacher_1_id", "teacher_2_id"},
    "parallel_lab_pairs.csv": {"batch_id", "parallel_lab_pair_id", "lab_course_1", "lab_course_2", "sessions_per_week", "periods_per_session"},
    "teachers.csv": {"teacher_id", "designation", "base_max_weekly_load", "hard_max_weekly_load", "allowed_overload", "available_days"},
    "rooms.csv": {"room_id", "room_type", "capacity", "usable_for_theory", "usable_for_lab"},
    "periods.csv": {"period_no", "start_time", "end_time"},
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.DictReader(f) if any((v or "").strip() for v in row.values())]


def validate_inputs(input_dir: Path) -> list[str]:
    """Return errors; an empty list means the CSV package passes structural checks."""
    errors: list[str] = []
    tables: dict[str, list[dict[str, str]]] = {}

    for filename, required in REQUIRED_COLUMNS.items():
        path = input_dir / filename
        if not path.is_file():
            errors.append(f"Missing required file: {filename}")
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                headers = set(reader.fieldnames or [])
                missing = required - headers
                if missing:
                    errors.append(f"{filename}: missing columns {', '.join(sorted(missing))}")
                    continue
                tables[filename] = [r for r in reader if any((v or "").strip() for v in r.values())]
        except (OSError, UnicodeError, csv.Error) as exc:
            errors.append(f"Cannot read {filename}: {exc}")

    if errors:
        return errors

    batches = tables["batches.csv"]
    courses = tables["courses.csv"]
    offerings = tables["offerings.csv"]
    teachers = tables["teachers.csv"]
    rooms = tables["rooms.csv"]
    lab_assignments = tables["lab_teacher_assignments.csv"]
    pairs = tables["parallel_lab_pairs.csv"]
    periods = tables["periods.csv"]

    batch_ids = {r["batch_id"] for r in batches}
    course_ids = {r["course_code"] for r in courses}
    teacher_ids = {r["teacher_id"] for r in teachers}
    room_ids = {r["room_id"] for r in rooms}
    course_by_id = {r["course_code"]: r for r in courses}
    offering_by_course_batch = {(r["course_code"], r["batch_id"]): r for r in offerings}

    if batch_ids != {"11", "12", "21", "22", "31", "32", "41", "42"}:
        errors.append("batches.csv: expected exactly batch IDs 11,12,21,22,31,32,41,42")
    if len(batch_ids) != len(batches):
        errors.append("batches.csv: duplicate batch_id")
    if len(course_ids) != len(courses):
        errors.append("courses.csv: duplicate course_code")
    if len({r["offering_id"] for r in offerings}) != len(offerings):
        errors.append("offerings.csv: duplicate offering_id")
    if len({(r["course_code"], r["batch_id"]) for r in offerings}) != len(offerings):
        errors.append("offerings.csv: duplicate course/batch offering")

    for row in batches:
        try:
            n = int(row["student_count"])
            if n <= 0 or n > 70:
                errors.append(f"Batch {row['batch_id']}: student_count must be 1..70, got {n}")
        except ValueError:
            errors.append(f"Batch {row['batch_id']}: student_count must be an integer")
    for expected, count in (("11", 55), ("42", 52)):
        match = next((r for r in batches if r["batch_id"] == expected), None)
        if match and match["student_count"] != str(count):
            errors.append(f"Batch {expected}: expected confirmed test count {count}")

    for row in offerings:
        if row["course_code"] not in course_ids:
            errors.append(f"Offering {row['offering_id']}: unknown course {row['course_code']}")
        if row["batch_id"] not in batch_ids:
            errors.append(f"Offering {row['offering_id']}: unknown batch {row['batch_id']}")
        if row["course_type"] not in {"theory", "lab"}:
            errors.append(f"Offering {row['offering_id']}: invalid course_type")
        try:
            sessions, block_length = int(row["sessions_per_week"]), int(row["periods_per_session"])
            if sessions < 1 or block_length < 1:
                errors.append(f"Offering {row['offering_id']}: sessions and block length must be positive")
        except ValueError:
            errors.append(f"Offering {row['offering_id']}: sessions/block length must be integers")
        if row["course_type"] == "lab" and row["staffing_rule"] != "FIXED_PAIR":
            errors.append(f"Lab {row['course_code']}: expected FIXED_PAIR staffing rule")
        course = course_by_id.get(row["course_code"])
        if course:
            if row["course_type"] != course["course_type"].strip().lower():
                errors.append(f"Offering {row['offering_id']}: type differs from courses.csv")
            try:
                credit = float(course["credit"])
                contact = float(course["contact_hours"])
                sessions = int(row["sessions_per_week"])
                duration = int(row["periods_per_session"])
                load = float(row["weekly_load_periods_per_teacher"])
                shared = course["shared"].strip().lower() in {"true", "yes", "1"}
                if row["course_type"] == "lab":
                    expected = {
                        (1.5, 3.0): (2, 3, 6.0),
                        (0.75, 1.5): (1, 3, 3.0),
                        (1.0, 2.0): (1, 2, 2.0),
                    }.get((credit, contact))
                    if expected is None:
                        errors.append(f"Lab {row['course_code']}: unsupported credit/contact combination {credit}/{contact}")
                    elif (sessions, duration, load) != expected:
                        errors.append(f"Lab {row['course_code']}: expected sessions/duration/teacher-load {expected}")
                elif row["course_type"] == "theory":
                    expected_sessions = int(contact)
                    expected_load = contact / 2 if shared else contact
                    expected_teachers = 2 if shared else 1
                    if contact != expected_sessions or sessions != expected_sessions or duration != 1:
                        errors.append(f"Theory {row['course_code']}: sessions must equal contact hours, with one period per session")
                    if abs(load - expected_load) > 1e-8:
                        errors.append(f"Theory {row['course_code']}: workload per teacher must be {expected_load:g} hours")
                    if int(row["teacher_count_min"]) != expected_teachers or int(row["teacher_count_max"]) != expected_teachers:
                        errors.append(f"Theory {row['course_code']}: shared status requires exactly {expected_teachers} teacher(s)")
            except (ValueError, TypeError):
                errors.append(f"Offering {row['offering_id']}: invalid numeric credit/contact/session/workload value")

    lab_codes = {r["course_code"] for r in courses if r["course_type"] == "lab"}
    offered_lab_codes = {r["course_code"] for r in offerings if r["course_type"] == "lab"}
    assignment_codes = [r["course_code"] for r in lab_assignments]
    if set(assignment_codes) != offered_lab_codes:
        errors.append("lab_teacher_assignments.csv: must contain exactly one row per offered lab course")
    if len(assignment_codes) != len(set(assignment_codes)):
        errors.append("lab_teacher_assignments.csv: duplicate course_code")
    for row in lab_assignments:
        t1, t2 = row["teacher_1_id"].strip(), row["teacher_2_id"].strip()
        if not t1 or not t2:
            errors.append(f"Lab {row['course_code']}: fixed teacher pair is not filled")
        elif t1 == t2:
            errors.append(f"Lab {row['course_code']}: teachers must be distinct")
        elif t1 not in teacher_ids or t2 not in teacher_ids:
            errors.append(f"Lab {row['course_code']}: unknown teacher ID")
        elif "external" in next(r["designation"].lower() for r in teachers if r["teacher_id"] in (t1, t2)):
            errors.append(f"Lab {row['course_code']}: external teachers are reserved for theory")

    for row in pairs:
        for col in ("lab_course_1", "lab_course_2"):
            code = row[col]
            if code not in lab_codes:
                errors.append(f"Parallel pair {row['parallel_lab_pair_id']}: {code} is not a lab course")
            if (code, row["batch_id"]) not in offering_by_course_batch:
                errors.append(f"Parallel pair {row['parallel_lab_pair_id']}: {code} has no offering for batch {row['batch_id']}")
        if row["lab_course_1"] == row["lab_course_2"]:
            errors.append(f"Parallel pair {row['parallel_lab_pair_id']}: courses must differ")

    for row in teachers:
        try:
            base, hard, extra = map(float, (row["base_max_weekly_load"], row["hard_max_weekly_load"], row["allowed_overload"]))
        except ValueError:
            errors.append(f"Teacher {row['teacher_id']}: load limits must be numeric")
            continue
        designation = row["designation"].lower()
        may_overload = "external" not in designation and any(
            role in designation for role in ("lecturer", "assistant_professor", "associate_professor", "professor")
        )
        expected = 0.5 if may_overload else 0.0
        if abs(extra - expected) > 1e-8 or abs(hard - base - expected) > 1e-8:
            errors.append(f"Teacher {row['teacher_id']}: hard cap/overload does not match designation rule")
        if "external" in designation:
            if row.get("required_course_day") != "THU" or row.get("required_block_periods") != "3":
                errors.append(f"External {row['teacher_id']}: must have a 3-period Thursday requirement")

    for row in rooms:
        try:
            capacity = int(row["capacity"])
        except ValueError:
            errors.append(f"Room {row['room_id']}: capacity must be an integer")
            continue
        if row["room_type"] == "Classroom" and (row["usable_for_theory"].lower() != "true" or row["usable_for_lab"].lower() != "false"):
            errors.append(f"Room {row['room_id']}: classroom must be theory-only")
        if row["room_type"] == "Lab":
            expected_theory = "true" if capacity >= 50 else "false"
            if row["usable_for_lab"].lower() != "true" or row["usable_for_theory"].lower() != expected_theory:
                errors.append(f"Room {row['room_id']}: lab room capability flags do not match capacity rule")

    try:
        period_numbers = [int(r["period_no"]) for r in periods]
        if sorted(period_numbers) != list(range(1, len(periods) + 1)):
            errors.append("periods.csv: period_no values must be consecutive starting at 1")
    except ValueError:
        errors.append("periods.csv: period_no must be integer")

    return errors
