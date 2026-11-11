# Python + MiniZinc University Timetable

This project reads CSV inputs, prepares MiniZinc data in Python, solves the weekly routine with MiniZinc/Gecode, independently verifies the schedule, and exports human-readable CSV files for department staff. PDF generation is optional; no custom UI is required.

The recommended showcase is `data/medium_test/`: 10 offerings and 21 weekly meetings across batches 21 and 22. It includes shared theory, parallel labs, a 64-student Room 202 case, and the 1.50-, 0.75-, and 1.00-credit lab patterns. The verified run exports `routine.csv`, `office_schedule.csv`, `schedule.csv`, and `teacher_workloads.csv`.

The model limits each theory offering to at most two periods per day (hard constraint) and minimizes same-day repeats as a soft preference. Required consecutive lab blocks are exempt from the theory-only cap. The full 52-offering input remains under `data/input/`; a complete full-data solve has not yet been verified.

The uploaded `courses.csv` is preserved byte-for-byte. The medium dataset can be regenerated with `python build_medium_dataset.py`. Read [README_SETUP.md](README_SETUP.md) for model details and [RUN_ON_YOUR_PC.md](RUN_ON_YOUR_PC.md) for installation and run commands. The saved medium outputs are in `data/medium_output/` after running the showcase solve.
