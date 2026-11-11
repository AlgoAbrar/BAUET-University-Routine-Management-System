# 3x Medium Showcase Dataset

This dataset is exactly three times the original medium showcase by offering and weekly meeting counts: **30 offerings and 63 weekly meetings**. It uses selected records from the authoritative `data/input/` CSVs, with no invented courses or teacher assignments.

It includes all eight batches, both CSE-4000 offerings (batches 41 and 42), both specified batch-21 parallel lab pairs, the Room 202 requirement for batch 21, shared theory, fixed lab-teacher pairs, and 1.50-, 0.75-, and 1.00-credit lab patterns. External teachers are omitted in this demonstration subset. The course catalog is copied byte-for-byte from the authoritative input.

From the project root, validate and build MiniZinc data with:

```bash
python main.py --check-inputs --input-dir data/medium_3x
python main.py --build-data --input-dir data/medium_3x --output-dir data/medium_3x_output
```

To attempt the solve on a local computer and export office-friendly CSVs:

```bash
python main.py --solve --csv-only --input-dir data/medium_3x --output-dir data/medium_3x_output --timeout-seconds 600
```

The 600-second limit is a timeout ceiling, not a runtime guarantee. This larger dataset has not been solver-verified; solve time depends on hardware, Gecode version, and search behavior. A successful output is independently checked by Python before export.
