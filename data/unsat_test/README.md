# Intentionally Unsatisfiable Test Dataset

This dataset is copied from `medium_half` (15 offerings, 32 weekly meetings). It is intentionally infeasible for a single explicit reason: fixed lab instructor `AR` for `CSE-2102` has a blank `available_days` field, which maps to no available teaching days. Since the instructor is a mandatory member of that lab's fixed pair, the model cannot schedule the lab.

This is a test fixture, not a valid timetable input for scheduling operations. The other CSV structures and constraints are unchanged.

To run the existing project without changing code:

```bash
python main.py --check-inputs --input-dir data/unsat_test
python main.py --solve --csv-only --input-dir data/unsat_test --output-dir data/unsat_output --timeout-seconds 60
```

Expected solver result: UNSATISFIABLE.
