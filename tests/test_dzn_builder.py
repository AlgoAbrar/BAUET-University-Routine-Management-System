from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from timetable_app.dzn_builder import aggregate_workload_totals, build_dzn


class DznBuilderTests(unittest.TestCase):
    def test_builds_model_data_from_csvs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_dzn(ROOT / "data" / "input", Path(tmp) / "model_data.dzn")
            text = out.read_text(encoding="utf-8")
        self.assertIn("N_BATCHES = 8;", text)
        self.assertIn("N_OFFERS = 52;", text)
        self.assertIn("OFFER_DISTINCT_DAYS", text)
        self.assertIn("EVENT_OFFER", text)
        self.assertIn("LARGE_THEORY_ROOM =", text)

    def test_reports_current_aggregate_capacity(self):
        demand, capacity = aggregate_workload_totals(ROOT / "data" / "input")
        self.assertAlmostEqual(demand, 258.0)
        self.assertAlmostEqual(capacity, 333.0)
        self.assertGreaterEqual(capacity, demand)


if __name__ == "__main__":
    unittest.main()
