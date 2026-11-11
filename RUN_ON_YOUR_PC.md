# Run the timetable project on your PC (Windows)

The project uses **Python, MiniZinc, and Gecode**—no database, web server, or special UI. Python validates the CSV files, prepares MiniZinc data, verifies the returned routine, and writes human-readable CSV reports. PDF output is optional.

## 1. Download and extract

Extract the project to a simple folder, for example:

```text
C:\Users\YourName\Documents\minizinc_timetable_starter
```

Open PowerShell in that folder. In File Explorer, click the address bar, type `powershell`, and press Enter.

## 2. Install Python and MiniZinc

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/). Enable **Add Python to PATH**. Check:

```powershell
py --version
```

Install MiniZinc for Windows from [minizinc.org](https://www.minizinc.org/software.html), using an installer that includes Gecode. Then check:

```powershell
minizinc --version
minizinc --solvers
```

The solver list must include Gecode. If `minizinc` is not recognized, add the MiniZinc installation's `bin` directory to Windows `PATH`, then open a new PowerShell window.

## 3. Install the Python dependency

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, allow it for the current window only, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4. Check the setup

```powershell
python main.py --check-inputs
python -m unittest discover -s tests -v
python main.py --smoke-test
```

CSV validation, the unit tests, and the MiniZinc/Gecode smoke test should pass. The smoke test is not a timetable solve.

## 5. Run the medium showcase instance

The recommended presentation dataset is `data/medium_test/`: **10 offerings and 21 weekly meetings** across batches 21 and 22. It retains shared theory, two parallel lab pairs, fixed lab-teacher teams, the Room 202 rule for batch 21 (64 students), and all three requested lab patterns: 1.50-credit/3-hour, 0.75-credit/1.50-hour, and 1.00-credit/2-hour.

To regenerate the subset from the authoritative full input, then run it:

```powershell
python build_medium_dataset.py
python main.py --check-inputs --input-dir data/medium_test
python main.py --solve --csv-only --input-dir data/medium_test --output-dir data/medium_output --timeout-seconds 600
```

This medium instance solved and passed the independent Python verifier in about **0.9 seconds in the sandbox test**. Your PC's result may differ with its hardware and MiniZinc/Gecode version; the 600-second value is a maximum runtime, not an expected runtime. The model imposes a hard maximum of two theory periods per course offering per day and minimizes same-day repeats as a soft preference. Required multi-period lab blocks are exempt from the theory-only cap.

The routine files will be under `data\medium_output\`. The most office-friendly result is `routine.csv`; the compact office export is `office_schedule.csv`.

## 6. Run the full dataset (optional)

The full dataset is in `data/input/` and contains 52 offerings across all eight batches. It has not yet completed a full independently verified solve, so run it separately and do not treat its input-validation pass as proof of a routine:

```powershell
python main.py --solve --csv-only --timeout-seconds 3600
```

There is no time limit by default. Increase or remove the timeout only if you intentionally want a longer full-data run.

## Outputs

A successful solve writes the following files to the chosen output directory:

```text
routine.csv                 # full human-readable routine
schedule.csv                # one row per scheduled meeting
office_schedule.csv         # compact office columns, including Batch_ID
teacher_workloads.csv       # weekly load, base limit, hard limit, over-base amount
solver_debug.txt            # raw MiniZinc diagnostics; not the routine
```

Omit `--csv-only` if you also want `routine.pdf`. The CSV is the primary output so office staff can filter and reformat it.

## Data notes

`data/input/courses.csv` is preserved byte-for-byte from the uploaded course catalog. The six excluded courses remain absent from the active offerings. The medium subset contains only internal teachers, while the full input retains the External-teacher rules. Theory for any batch above 60 students must use Room 202. Lab rooms with capacity at least 50 may host theory, but classrooms cannot host labs. Teachers have workload ceilings but do not have to reach their maximum load.
