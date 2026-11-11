from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from timetable_app.dzn_builder import aggregate_workload_totals, build_dzn
from timetable_app.minizinc_runner import run_smoke_test, run_timetable
from timetable_app.output import export_solution
from timetable_app.validation import validate_inputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate timetable inputs and run the MiniZinc timetable model.")
    parser.add_argument("--check-inputs", action="store_true", help="Validate all CSV input files")
    parser.add_argument("--smoke-test", action="store_true", help="Validate CSVs and run a tiny MiniZinc/Gecode test")
    parser.add_argument("--build-data", action="store_true", help="Validate CSVs and generate data/output/model_data.dzn")
    parser.add_argument("--solve", action="store_true", help="Build MiniZinc data and solve models/timetable.mzn")
    parser.add_argument("--timeout-seconds", type=int, default=0, help="Optional solver timeout; 0 means unlimited (default)")
    parser.add_argument("--input-dir", type=Path, default=Path("data/input"), help="CSV input directory (default: data/input)")
    parser.add_argument("--output-dir", type=Path, default=Path("data/output"), help="Generated output directory (default: data/output)")
    parser.add_argument("--csv-only", action="store_true", help="Export CSV reports only; do not create the PDF")
    args = parser.parse_args()
    if args.timeout_seconds < 0:
        parser.error("--timeout-seconds must be zero (unlimited) or a positive integer")

    input_dir = args.input_dir if args.input_dir.is_absolute() else ROOT / args.input_dir
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir

    def display_path(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    errors = validate_inputs(input_dir)
    if errors:
        print("Input validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("CSV input validation: PASS")

    if args.smoke_test:
        ok, message = run_smoke_test(ROOT / "models" / "smoke_test.mzn")
        print(message)
        if not ok:
            return 2
        print("Python → MiniZinc → Gecode smoke test: PASS")
        return 0

    if args.build_data or args.solve:
        try:
            data_path = build_dzn(input_dir, output_dir / "model_data.dzn")
        except (OSError, ValueError, KeyError) as exc:
            print(f"Could not generate MiniZinc data: {exc}")
            return 3
        print(f"MiniZinc data generated: {display_path(data_path)}")
        demand, capacity = aggregate_workload_totals(input_dir)
        print(f"Required workload demand: {demand:g} h/week; aggregate hard capacity: {capacity:g} h/week")
        if demand > capacity:
            print(f"WARNING: workload alone exceeds aggregate hard capacity by {demand-capacity:g} h/week; no timetable can satisfy the current caps.")
        if not args.solve:
            return 0
        timeout = args.timeout_seconds or None
        ok, output = run_timetable(ROOT / "models" / "timetable.mzn", data_path, timeout_seconds=timeout)
        result_path = output_dir / "solver_debug.txt"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(output + "\n", encoding="utf-8")
        print(f"Raw MiniZinc diagnostic output saved: {display_path(result_path)}")
        if not ok:
            print("MiniZinc did not return a feasible schedule:")
            print(output)
            return 4
        print("MiniZinc: feasible schedule found.")
        try:
            csv_path, office_path, workload_path, pdf_path = export_solution(
                output, input_dir, output_dir, write_pdf=not args.csv_only
            )
        except (OSError, ValueError, KeyError) as exc:
            print(f"The solver returned a schedule, but Python verification/export failed: {exc}")
            return 5
        print("Independent solution validation: PASS")
        if pdf_path is not None:
            print(f"Routine PDF: {display_path(pdf_path)}")
        routine_path = output_dir / "routine.csv"
        print(f"Readable comma-separated routine: {display_path(routine_path)}")
        print(f"Office-friendly CSV: {display_path(office_path)}")
        print(f"Detailed schedule CSV: {display_path(csv_path)}")
        print(f"Teacher workload CSV: {display_path(workload_path)}")
        print("\nRoutine preview (day, course, slots, time, batch, students, class type, title, teachers, room):")
        preview_lines = routine_path.read_text(encoding="utf-8").splitlines()
        for line in preview_lines[:9]:
            print(line)
        if len(preview_lines) > 9:
            print(f"... {len(preview_lines) - 9} more rows; open {display_path(routine_path)}")
        return 0

    print("No MiniZinc solve requested. Use --smoke-test, --build-data, or --solve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
