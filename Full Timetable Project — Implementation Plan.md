# Full Timetable Project — Implementation Plan

## 1. Purpose and scope

Build a reliable weekly timetable generator for the CSE department using **Python, CSV, MiniZinc, and the Gecode solver**. Python reads and validates the CSV data, converts it to MiniZinc input, runs the solver, checks the result independently, and exports a compact CSV that office staff can use to prepare the final routine. A printable PDF may be generated as an optional convenience.

The project deliberately does **not** include a web application, database, login system, fancy user interface, or automatic course/teacher preference system. The inputs and outputs remain ordinary CSV/text/PDF files. The first goal is a valid timetable satisfying every hard constraint; filling every teacher's maximum load and filling every timetable slot are not required.

## 2. What is being scheduled

The timetable covers eight batches:

| Batch ID | Meaning |
| --- | --- |
| `11` | 1st year, 1st semester |
| `12` | 1st year, 2nd semester |
| `21` | 2nd year, 1st semester |
| `22` | 2nd year, 2nd semester |
| `31` | 3rd year, 1st semester |
| `32` | 3rd year, 2nd semester |
| `41` | 4th year, 1st semester |
| `42` | 4th year, 2nd semester |

The course-code rules are used to assign offerings to batches, with the explicit exception that `CSE-4000` is offered to both batches `41` and `42`. The complete active dataset currently contains **52 offerings** across these batches. The six excluded codes—`0611CSE1222`, `0611(MIS)2103`, `CSE-1209`, `CSE-1210`, `CSE-1271`, and `CSE-1272`—must not appear in the active offerings or lab assignment data.

The agreed code mapping is: `CSE-1100` → batch 11 only; `CSE-12**` → batch 12; `CSE-21**` → batch 21; `CSE-22**` → batch 22; `CSE-31**` → batch 31; `CSE-32**` → batch 32; `CSE-41**` → batch 41; and `CSE-42**` → batch 42. `CSE-4000` is the explicit exception and is offered to both batches 41 and 42. A/B section modeling is deferred; each batch is one unsplit cohort, with implicit student division used only for parallel labs.

The uploaded `courses.csv` is the authoritative catalog. It must remain byte-for-byte unchanged unless the user later supplies a corrected catalog. Python must compare every offering with that catalog rather than silently changing course type, credit, contact hours, room requirements, or shared status to make a schedule work.

## 3. CSV inputs and ownership

All information is stored in CSV files. Python validates headers, row references, numeric fields, course patterns, and rule consistency before a solve starts.

| CSV file | Purpose |
| --- | --- |
| `courses.csv` | Authoritative course code, title, theory/lab type, credit, contact hours, room type, shared status, and department status. Preserve as supplied. |
| `batches.csv` | The eight batch IDs and student counts. Current assumed counts are 55 for batch 11 and 52 for batch 42; no batch exceeds 70. |
| `offerings.csv` | Which course is offered to which batch; number of weekly meetings, block length, required teacher count, per-teacher workload, and optional parallel-lab pairing. |
| `teachers.csv` | Teacher IDs, designations, base and hard weekly limits, allowed overload, and available weekdays. |
| `lab_teacher_assignments.csv` | Fixed two-teacher team for each lab course that is actually offered. Both teachers attend every meeting of that lab. |
| `parallel_lab_pairs.csv` | Labs that must run simultaneously for the same batch so students can divide into lab groups without separate section records. |
| `rooms.csv` | Room ID, capacity, type, and whether it can host theory and/or lab. |
| `periods.csv` | The six daily teaching periods and their start/end times. |

### Exact CSV structure

The headers below are taken from the current active CSVs. Keep the header names and column order when editing files; fields shown as optional should be left empty rather than deleting the column.

- **`batches.csv`** — header: `batch_id,study_year,semester,student_count`. `batch_id` is the key referenced by offerings and parallel lab pairs. Example row: `11,1,1,55`.

- **`courses.csv`** — header: `course_code,course_title,course_type,credit,contact_hours,required_room_type,shared,departmental`. `course_code` is the key; `course_type` is `theory` or `lab`; `credit` and `contact_hours` are numeric; `shared` and `departmental` are catalog flags. Example row: `CSE-1100,Introduction to Computer Systems Laboratory,lab,1.5,3,Lab,FALSE,YES`. This file is authoritative and must not be edited by the timetable program.

- **`offerings.csv`** — header: `offering_id,course_code,batch_id,course_type,sessions_per_week,periods_per_session,parallel_lab_pair_id,teacher_count_min,teacher_count_max,teacher_assignment_mode,staffing_rule,weekly_load_periods_per_teacher,distinct_session_days`. `offering_id` is the row key; `(course_code,batch_id)` must be unique. The course and batch values must exist in their source files. A blank `parallel_lab_pair_id` means there is no named parallel pair. `weekly_load_periods_per_teacher` is the weekly creditable workload for each teacher on that course, not the duration of one meeting. Example lab row: `OF001,CSE-1100,11,lab,2,3,,2,2,FIXED_IN_LAB_TEACHERS_CSV,FIXED_PAIR,6,true`.

- **`teachers.csv`** — header: `teacher_id,teacher_name,designation,base_max_weekly_load,hard_max_weekly_load,allowed_overload,available_days,required_course_day,required_block_periods,required_blocks_per_week,required_total_course_count,required_theory_course_count,required_single_course_load,only_course_type,fixed_lab_load_hours`. `teacher_id` is the key used by lab assignments and solver outputs. Load fields are numeric hours; `available_days` is `ANY` or a weekday list. The `required_*` and fixed-load columns retain teacher-specific rule/configuration metadata; the agreed External rule must be consistent with those fields and the corresponding model constraints.

- **`lab_teacher_assignments.csv`** — header: `course_code,teacher_1_id,teacher_2_id,testing_assignment`. One row per lab course actually offered; both teacher IDs must exist in `teachers.csv`, be distinct, and be non-External. The last column records that the current pair is provisional for testing. Example row: `CSE-1100,MRI,MS,provisional_balanced_pair`.

- **`parallel_lab_pairs.csv`** — header: `batch_id,parallel_lab_pair_id,lab_course_1,lab_course_2,sessions_per_week,periods_per_session,source`. Each row links two lab offerings in the same batch and specifies how many matching blocks they must share. Example row: `21,21P1,CSE-2102,CSE-2108,2,3,User-provided 21st-batch example image`.

- **`rooms.csv`** — header: `room_id,room_type,capacity,usable_for_theory,usable_for_lab`. `room_id` is the key; capacity is an integer; the two capability fields are true/false flags.

- **`periods.csv`** — header: `period_no,start_time,end_time`. `period_no` is consecutive from 1 to 6; the time strings define the printable start/end labels for each teaching period.

The main relationships are: `offerings.course_code` → `courses.course_code`; `offerings.batch_id` → `batches.batch_id`; each offered lab code → exactly one lab-teacher row; each teacher ID in that row → `teachers.teacher_id`; each parallel-pair course/batch → a matching lab offering; and room IDs in solver output → `rooms.room_id`. CSV values are read as text and then validated/converted to integers, decimals, booleans, or IDs in Python. Commas inside a course title or source description must use normal CSV quoting.

**Data treatment:** validate the eight required batch IDs and confirmed counts; ensure offering codes and batch IDs exist; reject duplicate offerings; ensure offered labs have exactly one fixed pair; check parallel-pair references; and reject room/teacher references that do not exist. A short demonstration dataset will live in a separate folder so it never replaces the full active dataset.

## 4. Weekly calendar and course meeting patterns

Classes run Sunday through Thursday, with six teaching periods per day. Tea and prayer breaks are not teaching periods. Three-period blocks can begin only at period 1 or period 4; two-period blocks cannot cross a break. Empty periods are allowed. The solver is not required to fill the weekly grid.

### Theory courses

- A theory course is scheduled as one-period events according to its contact hours per week. For example, a three-contact-hour theory course has three weekly one-period meetings.

- A non-shared theory course has one teacher; that teacher receives the full contact-hour workload.

- A shared theory course has exactly two distinct teachers. Both teach the scheduled meetings and the workload per teacher is split evenly. A three-hour shared course contributes 1.5 workload hours to each teacher.

- Theory is scheduled in a single suitable room. A batch with more than 60 students must use room `202` (capacity 70).

### Lab courses

| Catalog rule | Weekly schedule | Workload charged to **each** of the two fixed lab teachers |
| --- | --- | --- |
| 1.50 credit / 3.00 contact hours | Two separate three-period blocks on different days | 6 hours total per teacher per week |
| 0.75 credit / 1.50 contact hours | One three-period consecutive block | 3 hours per teacher per week |
| 1.00 credit / 2.00 contact hours | One two-period block | 2 hours per teacher per week |

Both lab teachers attend every scheduled lab block. A lab teacher may also teach theory courses, provided their combined assigned workload remains under the applicable hard cap. Students may be divided internally by the department; the model does not create named lab sections. A specified pair of lab courses may be scheduled in the same time block, with each lab serving half of that batch's students.

## 5. Teacher workload and assignment rules

The solver assigns theory teachers; fixed lab pairs come from the CSV. Teachers do not select courses and have no preference constraints in this version.

- Lecturer, Assistant Professor, Associate Professor, and Professor hard caps are the base maximum plus **0.5 hour**.

- External teachers have a strict **3-hour maximum**, no overload allowance, and take exactly one non-shared three-hour theory course.

- An External teacher's three theory meetings must be on Thursday in three consecutive periods, either periods 1–3 or 4–6.

- There is no minimum workload: a teacher may be assigned less than their base maximum or even zero hours if the rest of the model permits it.

- Workload is counted once per course offering per teacher, not once per repeated weekly meeting. The MiniZinc model uses half-hour integer units so that values such as 1.5 and the +0.5 allowance are exact.

For example, a teacher assigned shared three-hour theory courses (1.5 hours each) and two weekly three-hour labs (6 hours each) has `1.5 + 6 + 1.5 + 6 + 1.5 = 16.5` hours. This must not exceed that teacher's hard cap.

## 6. Rooms and capacity

- Theory rooms must be theory-capable and have enough capacity for the batch. Room `202` is the required theory room for batches larger than 60.

- A lab room with capacity at least 50 may also be used for theory. A classroom is never used for a lab.

- Labs use a suitable lab room. If one lab room is too small, two different lab rooms may be assigned if their combined capacity is sufficient.

- When two labs for a batch run in parallel, each course's room(s) need to accommodate the implicit half-batch, not the full batch.

- No physical room may host overlapping events. If an event uses two rooms, both are reserved for the full block.

## 7. Hard constraints that a valid solution must satisfy

1. Every offering gets exactly the configured number of weekly meetings.

1. Every event is inside the Sunday–Thursday, six-period timetable and does not cross a break.

1. A batch cannot attend two overlapping classes, except for two distinct labs explicitly run as a parallel pair in the exact same time block.

1. Repeated meetings of a lab marked for distinct days must be placed on different weekdays.

1. A theory offering may occupy no more than two periods on any weekday. This is a hard rule; required consecutive lab blocks are exempt.

1. As a soft preference, minimize pairs of theory meetings for the same offering on the same weekday. A three-meeting theory course therefore prefers three distinct days when the rest of the constraints permit it.

1. A teacher cannot teach overlapping events and must be available on every assigned teaching day.

1. Theory teacher counts must match the course's shared/non-shared status; shared teachers must be distinct.

1. Lab teacher assignments must exactly match the fixed pair in the input CSV; External teachers cannot be assigned to labs.

1. Each room must be eligible, large enough, and free for all periods of the event.

1. Room 202 must host theory for every batch above 60 students.

1. Each teacher's total weekly load must be at or below the hard cap; no minimum utilization is imposed.

1. Each External teacher must receive exactly one qualifying three-hour theory course on Thursday in a consecutive three-period block and no other course.

1. Parallel lab pairs must match session-by-session in day, start period, and duration; a third simultaneous lab for the same batch is disallowed.

The solve mode minimizes the number of same-day theory-meeting pairs while preserving every hard constraint. This is a soft day-spread preference, not a requirement that every three-meeting course be on three different days. Teacher load, room count, and filled-slot compactness are not optimized.

## 8. Python and MiniZinc responsibilities

### Python

Python handles deterministic data work and integration:

1. Read CSVs with UTF-8/BOM support and report actionable validation errors.

1. Verify course/offering consistency and the catalog-defined meeting/workload rules.

1. Convert IDs into stable integer indices and write `model_data.dzn`.

1. Invoke MiniZinc/Gecode, optionally with a user-specified time limit. The default solve has no time limit.

1. Parse the returned event assignments.

1. Independently re-check the solution instead of trusting the solver output alone.

1. Export office-facing CSV, detailed schedule CSV, teacher workload CSV, raw solver output, and optional PDF.

### MiniZinc

MiniZinc owns the combinatorial decisions and hard-constraint enforcement:

- Assign theory teachers.

- Choose day and start period for each meeting.

- Choose one room, or two rooms for a split lab when needed.

- Enforce clashes, availability, capacity, fixed lab teams, parallel labs, workload limits, course patterns, and External-teacher rules.

The Python verifier repeats the core checks independently after a feasible solution is returned. If verification fails, the program must stop and must not present an invalid schedule as final.

## 9. Output expected by office staff

The main output is `office_schedule.csv`, one row per scheduled meeting. It contains the requested fields plus `Batch_ID`, which is essential because the combined file contains eight batches:

```
Batch_ID,Day_Name,Course_code,Course_title,Assigned_Teacher_1,Assigned_Teacher_2,slot_taken,room
21,sun,CSE-2102,Data Structures and Algorithms I Laboratory,AR,FNN,"[4,5,6]",206/207
```

- `Day_Name` is lowercase (`sun`, `mon`, `tue`, `wed`, `thu`).

- `slot_taken` is the full period list for that one meeting: `[1]` for a one-period theory meeting, `[4,5,6]` for a three-period lab block.

- `room` is one room ID or two slash-separated room IDs when a split room assignment is necessary.

- A three-hour theory course appears as three one-period rows, because the model schedules three separate weekly meetings.

The clearest output is `routine.csv`: full day name, course code, slot range, clock time, batch, year/semester, student count, theory/lab type, course title, teacher names with IDs, and room. `office_schedule.csv` retains the original compact column order. Teacher names come from the `teacher_name` column in `teachers.csv`; full names should be entered there for any additional staff. `schedule.csv` gives detailed event rows, `teacher_workloads.csv` gives loads and caps, and `solver_debug.txt` contains raw MiniZinc diagnostics—not the routine. `routine.pdf` is optional; it is not required for the office workflow.

## 10. Implementation and verification phases

### Phase 1 — Freeze requirements and data rules

Confirm the eight batches, course-code mapping, excluded courses, current student counts, course meeting formulas, teacher caps, room policy, and exact External-teacher rule. Keep `courses.csv` unchanged. Record any later policy changes before altering the solver.

### Phase 2 — Validate and normalize CSV inputs

Run schema, reference, numeric, course-pattern, workload, teacher-pair, and room checks. Separate full production inputs from any judge/demo subset. Produce a clear list of errors and warnings before solving.

### Phase 3 — Build Python-to-MiniZinc data conversion

Generate a deterministic DZN file containing batches, offerings, flattened weekly events, fixed lab teams, parallel pairs, availability, workload limits, room data, and periods. Unit-test the mapping so each offering and event index matches the source CSV.

### Phase 4 — Complete and check the MiniZinc hard model

Encode every constraint in Section 7, begin with satisfaction rather than optimization, then test with tiny cases and targeted edge cases (shared theory, 0.75 lab, parallel labs, room split, batch over 60, and External Thursday block). Keep empty timetable slots legal.

### Phase 5 — Independent solution verification and CSV export

Parse a solver result only when all event rows are present. Run the independent Python checker. On success, export `office_schedule.csv`, detailed CSV, workloads, raw output, and optionally PDF. On timeout, infeasibility, or verification failure, report the issue and do not create a misleading final schedule.

### Phase 6 — Build a separate, fast judge prototype

**Completed for the small prototype:** a separate standalone project was created at `timetable_judge_demo/` with four offerings and six weekly events, no External teachers, all eight batch rows, and the uploaded catalog unchanged. It solves with MiniZinc/Gecode and passes independent Python verification; the documented command has a 10-minute timeout ceiling. This tiny fixture demonstrates shared theory, a fixed-pair 0.75-credit lab, the large-batch theory-room rule, teacher workloads, and CSE-4000 in both fourth-year semesters. It is deliberately not the full semester routine, and constraints for parallel labs and other absent data patterns remain in the model but are not exercised by this fixture.

### Phase 6b — Build a medium showcase dataset

**Completed:** `data/medium_test/` contains 10 offerings and 21 weekly meetings from batches 21 and 22. It exercises shared theory, two parallel lab pairs, the Room 202 rule for batch 21 (64 students), and 1.50-, 0.75-, and 1.00-credit lab patterns. It excludes External teachers for a focused demonstration, preserves all eight batch rows and the full `courses.csv`, and solves with a zero same-day theory penalty. The Python verifier passed; the measured end-to-end sandbox run was about 0.9 seconds. A local timeout of 600 seconds is provided in the PC guide, but runtime still depends on hardware and solver version.

### Phase 7 — Full-data acceptance run

Run the complete 52-offering dataset on a suitable local computer. Confirm that the solver returns a feasible result, independently validate every constraint, inspect the CSV rows for all eight batches, and review teacher loads. If infeasible, diagnose the conflicting inputs/constraints rather than weakening a hard rule without authorization.

## 11. Acceptance checklist

The project is ready for routine use when:

- All CSVs validate, and the uploaded `courses.csv` remains byte-for-byte unchanged.

- Unit tests cover validation, DZN generation, solution parsing, and the office CSV format.

- The MiniZinc model type-checks and the Python-to-MiniZinc smoke test passes.

- The short judge dataset solves within its agreed demonstration time and creates a verified CSV.

- The medium showcase solves and passes the Python verifier while respecting the two-period theory daily cap; its soft day-spread penalty is reported.

- The full dataset either produces a verified timetable or reports a specific, diagnosable infeasibility/timeout; no unverified schedule is labelled final.

- Every output row has the correct batch, course title, teacher IDs, period list, and room assignment.

## 12. Current status and known risk

The small, standalone judge prototype and the 10-offering medium showcase are verified. The medium instance passes CSV validation, the updated unit tests, the actual MiniZinc/Gecode solve, and independent Python schedule verification; its objective reaches a same-day theory penalty of zero. It produces office-friendly CSV output and includes all requested special lab patterns. The full 52-offering dataset still has **not** been verified by a complete solve; neither demo should be presented as the complete semester routine. Continue with full-data solving and performance/infeasibility diagnosis separately.

The full data's aggregate required workload is 258 hours/week versus 333 hours/week of aggregate hard-cap capacity. This is a useful necessary check, but it is not proof that all scheduling, teacher, room, availability, and External-teacher constraints can be satisfied together.
