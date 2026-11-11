from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from timetable_app.validation import validate_inputs


class InputValidationTests(unittest.TestCase):
    def test_project_csvs_pass_structural_validation(self):
        self.assertEqual(validate_inputs(ROOT / "data" / "input"), [])


if __name__ == "__main__":
    unittest.main()
