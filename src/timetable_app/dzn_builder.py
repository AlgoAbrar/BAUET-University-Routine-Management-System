from __future__ import annotations

from pathlib import Path
import csv
import math

DAYS = ["SUN", "MON", "TUE", "WED", "THU"]
TYPE_CODE = {"theory": 1, "lab": 2}


def read_csv(folder: Path, name: str) -> list[dict[str, str]]:
    with (folder / name).open("r", encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.DictReader(f) if any((v or "").strip() for v in row.values())]


def number(value: str, what: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what} must be numeric, got {value!r}") from exc


def half_units(value: str, what: str) -> int:
    doubled = number(value, what) * 2
    rounded = round(doubled)
    if not math.isclose(doubled, rounded, abs_tol=1e-8):
        raise ValueError(f"{what}={value} is not representable in half-hour workload units")
    return int(rounded)


def dzn_array(name: str, values: list[object]) -> str:
    def fmt(x: object) -> str:
        if isinstance(x, bool):
            return "true" if x else "false"
        if isinstance(x, str):
            return '"' + x.replace('\\', '\\\\').replace('"', '\\"') + '"'
        return str(x)
    return f"{name} = [" + ", ".join(fmt(x) for x in values) + "];\n"


def dzn_bool_matrix(name: str, rows: list[list[bool]]) -> str:
    n_rows = len(rows)
    n_cols = len(rows[0]) if rows else 0
    values = ["true" if v else "false" for row in rows for v in row]
    return f"{name} = array2d(1..{n_rows}, 1..{n_cols}, [" + ", ".join(values) + "]);\n"


def dzn_int_matrix(name: str, rows: list[list[int]]) -> str:
    n_rows = len(rows)
    n_cols = len(rows[0]) if rows else 0
    values = [str(v) for row in rows for v in row]
    return f"{name} = array2d(1..{n_rows}, 1..{n_cols}, [" + ", ".join(values) + "]);\n"


def build_dzn(input_dir: Path, output_path: Path) -> Path:
    """Build the exact parameter file consumed by models/timetable.mzn."""
    batches = read_csv(input_dir, "batches.csv")
    courses = read_csv(input_dir, "courses.csv")
    offerings = read_csv(input_dir, "offerings.csv")
    lab_assignments = read_csv(input_dir, "lab_teacher_assignments.csv")
    pairs = read_csv(input_dir, "parallel_lab_pairs.csv")
    teachers = read_csv(input_dir, "teachers.csv")
    rooms = read_csv(input_dir, "rooms.csv")
    periods = read_csv(input_dir, "periods.csv")

    batch_ids = [r["batch_id"] for r in batches]
    course_by_code = {r["course_code"]: r for r in courses}
    teacher_ids = [r["teacher_id"] for r in teachers]
    teacher_index = {tid: i + 1 for i, tid in enumerate(teacher_ids)}
    batch_index = {bid: i + 1 for i, bid in enumerate(batch_ids)}
    offer_index = {(r["course_code"], r["batch_id"]): i + 1 for i, r in enumerate(offerings)}
    lab_teacher_by_course = {r["course_code"]: (r["teacher_1_id"], r["teacher_2_id"]) for r in lab_assignments}

    if len(periods) != 6:
        raise ValueError("This model currently expects six teaching periods per day")
    if len(DAYS) != 5:
        raise AssertionError("Unexpected day set")

    sessions = [int(r["sessions_per_week"]) for r in offerings]
    durations = [int(r["periods_per_session"]) for r in offerings]
    max_sessions = max(sessions)
    offer_event_rows: list[list[int]] = []
    event_offer: list[int] = []
    event_session: list[int] = []
    for oi, (offer, count) in enumerate(zip(offerings, sessions), start=1):
        row = []
        for si in range(1, max_sessions + 1):
            if si <= count:
                event_id = len(event_offer) + 1
                row.append(event_id)
                event_offer.append(oi)
                event_session.append(si)
            else:
                row.append(0)
        offer_event_rows.append(row)

    offer_batch = [batch_index[r["batch_id"]] for r in offerings]
    offer_type = [TYPE_CODE[r["course_type"].lower()] for r in offerings]
    offer_shared = [course_by_code[r["course_code"]]["shared"].strip().lower() in {"true", "yes", "1"} for r in offerings]
    teacher_count = []
    load_half = []
    contact_half = []
    fixed1, fixed2 = [], []
    for offer in offerings:
        tmin, tmax = int(offer["teacher_count_min"]), int(offer["teacher_count_max"])
        if tmin != tmax:
            raise ValueError(f"Offering {offer['offering_id']}: this model version expects an exact teacher count")
        teacher_count.append(tmin)
        load_half.append(half_units(offer["weekly_load_periods_per_teacher"], f"{offer['course_code']} teacher workload"))
        contact_half.append(half_units(course_by_code[offer["course_code"]]["contact_hours"], f"{offer['course_code']} contact hours"))
        if offer["course_type"] == "lab":
            if offer["course_code"] not in lab_teacher_by_course:
                raise ValueError(f"Missing fixed lab teacher pair for {offer['course_code']}")
            a, b = lab_teacher_by_course[offer["course_code"]]
            if a not in teacher_index or b not in teacher_index:
                raise ValueError(f"Unknown lab teacher for {offer['course_code']}: {a}, {b}")
            fixed1.append(teacher_index[a]); fixed2.append(teacher_index[b])
        else:
            fixed1.append(0); fixed2.append(0)

    pair_offer1, pair_offer2, pair_sessions = [], [], []
    for pair in pairs:
        key1 = (pair["lab_course_1"], pair["batch_id"])
        key2 = (pair["lab_course_2"], pair["batch_id"])
        if key1 not in offer_index or key2 not in offer_index:
            raise ValueError(f"Parallel pair {pair['parallel_lab_pair_id']} references a missing offering")
        o1, o2 = offer_index[key1], offer_index[key2]
        s1, s2 = sessions[o1 - 1], sessions[o2 - 1]
        d1, d2 = durations[o1 - 1], durations[o2 - 1]
        ns = int(pair["sessions_per_week"])
        if s1 != s2 or s1 != ns or d1 != d2 or d1 != int(pair["periods_per_session"]):
            raise ValueError(f"Parallel pair {pair['parallel_lab_pair_id']} has inconsistent meeting counts or block lengths")
        pair_offer1.append(o1); pair_offer2.append(o2); pair_sessions.append(ns)

    teacher_base = [half_units(r["base_max_weekly_load"], f"{r['teacher_id']} base cap") for r in teachers]
    teacher_hard = [half_units(r["hard_max_weekly_load"], f"{r['teacher_id']} hard cap") for r in teachers]
    teacher_extra = [half_units(r["allowed_overload"], f"{r['teacher_id']} allowed overload") for r in teachers]
    teacher_external = ["external" in r["designation"].lower() for r in teachers]
    available_rows = []
    for r in teachers:
        raw = r["available_days"].strip().upper()
        if raw == "ANY":
            available = set(DAYS)
        else:
            available = {x.strip() for x in raw.replace(";", ",").split(",") if x.strip()}
        unknown = available - set(DAYS)
        if unknown:
            raise ValueError(f"Teacher {r['teacher_id']} has unknown availability day(s): {sorted(unknown)}")
        available_rows.append([day in available for day in DAYS])

    room_ids = [int(r["room_id"]) for r in rooms]
    if 202 not in room_ids:
        raise ValueError("rooms.csv must include the 70-seat theory room 202")
    room_capacity = [int(r["capacity"]) for r in rooms]
    room_theory = [r["usable_for_theory"].lower() == "true" for r in rooms]
    room_lab = [r["usable_for_lab"].lower() == "true" for r in rooms]

    # DZN uses 0-based-independent MiniZinc indices; the Python index maps above are one-based.
    lines = [
        f"N_BATCHES = {len(batches)};\n", f"N_OFFERS = {len(offerings)};\n",
        f"N_TEACHERS = {len(teachers)};\n", f"N_ROOMS = {len(rooms)};\n",
        f"N_PERIODS = {len(periods)};\n", f"N_DAYS = {len(DAYS)};\n",
        f"MAX_SESSIONS = {max_sessions};\n", f"N_PARALLEL_PAIRS = {len(pairs)};\n",
        dzn_array("BATCH_SIZE", [int(r["student_count"]) for r in batches]),
        dzn_array("OFFER_BATCH", offer_batch), dzn_array("OFFER_TYPE", offer_type),
        dzn_array("OFFER_SHARED", offer_shared), dzn_array("OFFER_SESSIONS", sessions),
        dzn_array("EVENT_OFFER", event_offer),
        dzn_array("OFFER_DISTINCT_DAYS", [r["distinct_session_days"].strip().lower() in {"true", "yes", "1"} for r in offerings]),
        dzn_array("OFFER_DURATION", durations), dzn_array("OFFER_TEACHER_COUNT", teacher_count),
        dzn_array("OFFER_LOAD_HALF_UNITS", load_half), dzn_array("OFFER_CONTACT_HALF_UNITS", contact_half),
        dzn_array("FIXED_TEACHER_1", fixed1), dzn_array("FIXED_TEACHER_2", fixed2),
        dzn_int_matrix("OFFER_EVENT_BY_SESSION", offer_event_rows),
        dzn_array("PAIR_OFFER_1", pair_offer1), dzn_array("PAIR_OFFER_2", pair_offer2),
        dzn_array("PAIR_SESSIONS", pair_sessions),
        dzn_array("TEACHER_BASE_HALF_UNITS", teacher_base), dzn_array("TEACHER_HARD_HALF_UNITS", teacher_hard),
        dzn_array("TEACHER_EXTRA_HALF_UNITS", teacher_extra), dzn_array("TEACHER_IS_EXTERNAL", teacher_external),
        dzn_bool_matrix("TEACHER_AVAILABLE", available_rows), dzn_array("ROOM_ID", room_ids),
        dzn_array("ROOM_CAPACITY", room_capacity), dzn_array("ROOM_FOR_THEORY", room_theory),
        dzn_array("ROOM_FOR_LAB", room_lab),
        f"LARGE_THEORY_ROOM = {room_ids.index(202) + 1};\n",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def aggregate_workload_totals(input_dir: Path) -> tuple[float, float]:
    """Return mandatory teacher workload and total hard capacity in hours."""
    offerings = read_csv(input_dir, "offerings.csv")
    teachers = read_csv(input_dir, "teachers.csv")
    demand = sum(
        number(row["weekly_load_periods_per_teacher"], f"{row['course_code']} workload")
        * int(row["teacher_count_min"])
        for row in offerings
    )
    capacity = sum(number(row["hard_max_weekly_load"], f"{row['teacher_id']} hard cap") for row in teachers)
    return demand, capacity
