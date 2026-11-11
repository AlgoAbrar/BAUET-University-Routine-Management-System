# Half-Size Showcase Dataset

This is the reduced alternative to `data/medium_3x/`: **15 offerings** (half of 30) and **32 weekly meetings** (about half of 63), selected from the authoritative project CSVs. No courses or teacher assignments are fabricated.

It covers batches 21, 22, 41, and 42; retains both batch-21 parallel-lab pairs, Room 202 for batch 21, 0.75- and 1.00-credit lab patterns, and CSE-4000 in both fourth-year batches. External teachers are omitted from this demonstration subset. `courses.csv` is byte-for-byte identical to the full input catalog.

Validate and build MiniZinc data from the project root:

```bash
python main.py --check-inputs --input-dir data/medium_half
python main.py --build-data --input-dir data/medium_half --output-dir data/medium_half_output
```

Attempt the solve and export office CSVs:

```bash
python main.py --solve --csv-only --input-dir data/medium_half --output-dir data/medium_half_output --timeout-seconds 600
```

A 600-second setting is a timeout ceiling, not a runtime guarantee. Run this smaller instance locally and check for the Python independent-verification PASS before treating any CSV as a valid routine.
