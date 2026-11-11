from pathlib import Path
import csv
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from timetable_app.output import _write_office_schedule, _write_routine_csv, _write_routine_pdf, parse_last_solution, validate_solution


class OutputTests(unittest.TestCase):
    def test_parser_uses_last_optimization_solution(self):
        text = """STATUS=OPTIMAL_OR_FEASIBLE
EVENT|1|1|1|1|1|1|0|1|0
----------
STATUS=OPTIMAL_OR_FEASIBLE
EVENT|1|1|2|2|1|2|0|2|0
----------
==========
"""
        events = parse_last_solution(text)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["day_idx"], 2)
        self.assertEqual(events[0]["room1_idx"], 2)

    def test_verifier_rejects_more_than_two_theory_periods_per_day(self):
        events = [
            {"event_id": event_id, "offer_idx": 1, "day_idx": 1,
             "start_period": event_id, "duration": 1, "teacher1_idx": 1,
             "teacher2_idx": 2, "room1_idx": 12, "room2_idx": 0}
            for event_id in (1, 2, 3)
        ]
        errors = validate_solution(events, ROOT / "data" / "medium_test")
        self.assertTrue(any("more than two theory periods" in error for error in errors))

    def test_printable_pdf_is_created(self):
        periods = [
            {"start_time": "08:15", "end_time": "09:10"},
            {"start_time": "09:15", "end_time": "10:10"},
            {"start_time": "10:15", "end_time": "11:10"},
            {"start_time": "11:40", "end_time": "12:35"},
            {"start_time": "12:40", "end_time": "13:35"},
            {"start_time": "14:00", "end_time": "14:55"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "routine.pdf"
            _write_routine_pdf(path, [], [{"batch_id": "11", "student_count": "55"}], [], {}, {}, periods)
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 500)

    def test_office_schedule_csv_has_requested_fields(self):
        event = {
            "batch_id": "21", "day_idx": 1, "day": "SUN", "start_period": 4,
            "duration": 3, "course_code": "CSE-2102",
            "course_title": "Data Structures and Algorithms I Laboratory",
            "teacher1_id": "AR", "teacher2_id": "FNN", "room1_id": "206", "room2_id": "207",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "office_schedule.csv"
            _write_office_schedule(path, [event])
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, ["Batch_ID", "Day_Name", "Course_code", "Course_title", "Assigned_Teacher_1", "Assigned_Teacher_2", "slot_taken", "room"])
                row = next(reader)
        self.assertEqual(row["Batch_ID"], "21")
        self.assertEqual(row["Day_Name"], "sun")
        self.assertEqual(row["slot_taken"], "[4,5,6]")
        self.assertEqual(row["room"], "206/207")

    def test_routine_csv_is_easy_to_scan_and_valid_csv(self):
        event = {
            "batch_id": "21", "day_idx": 1, "day": "SUN", "day_name": "Sunday",
            "study_year": "2", "semester": "1", "student_count": "64", "course_type": "lab",
            "period_label": "4-6",
            "time_text": "11:40 AM–1:35 PM; 2:00 PM–2:55 PM", "start_period": 4,
            "duration": 3, "course_code": "CSE-2102",
            "course_title": "Data Structures, Algorithms and Laboratory",
            "teacher1_id": "AR", "teacher2_id": "FNN", "room1_id": "206", "room2_id": "207",
            "teacher1_name": "Ananya Sarker (AS)", "teacher2_name": "Pollob Chandra Ray (PCR)",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "routine.csv"
            _write_routine_csv(path, [event])
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, ["Day", "Course Code", "Slots", "Time", "Batch", "Year", "Semester", "Students", "Class Type", "Course Title", "Teacher 1", "Teacher 2", "Room"])
                row = next(reader)
        self.assertEqual((row["Day"], row["Course Code"], row["Slots"], row["Batch"]),
                         ("Sunday", "CSE-2102", "4-6", "Batch 21"))
        self.assertEqual((row["Students"], row["Class Type"]), ("64", "Lab"))
        self.assertEqual(row["Time"], "11:40 AM–1:35 PM; 2:00 PM–2:55 PM")
        self.assertEqual(row["Course Title"], "Data Structures, Algorithms and Laboratory")
        self.assertEqual((row["Teacher 1"], row["Teacher 2"]),
                         ("Ananya Sarker (AS)", "Pollob Chandra Ray (PCR)"))
        self.assertEqual(row["Room"], "Room 206/207")


if __name__ == "__main__":
    unittest.main()
