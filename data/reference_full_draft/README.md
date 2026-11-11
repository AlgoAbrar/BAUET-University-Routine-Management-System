# Full-curriculum reference CSVs

These eight CSV files preserve the full-scale input set from the supplied archive, with the updated course catalog copied byte-for-byte from the user's 2026-11-02 upload. The six excluded course codes are removed from the offers and lab-assignment table: `0611CSE1222`, `0611(MIS)2103`, `CSE-1209`, `CSE-1210`, `CSE-1271`, and `CSE-1272`. The reference data also uses the confirmed batch 11 and 42 sizes (55 and 52), provisional fixed lab-teacher pairs, the role-wide +0.5-hour cap for non-External staff, and the strict 3-hour External cap.

The current snapshot has 51 catalog courses, 52 offerings and 21 lab courses. Applying the 0.75-credit lab rule (one 3-period meeting per week; 3 hours charged to each teacher) gives 258 required teacher-hours/week against 333 aggregate hard-cap hours/week. This aggregate capacity comparison is necessary but not sufficient: room, day/time, teacher availability, fixed lab-pair and External-teacher constraints must still be solved and independently verified.

To run the reference CSVs, back up `data/input/`, copy these eight CSV files into `data/input/`, then run `python main.py --check-inputs` and `python main.py --solve`. Keep this directory as the recovery copy. Lab-teacher pairs are provisional testing assignments and may be changed later; the uploaded `courses.csv` is left untouched.
