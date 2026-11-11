# MiniZinc models

- `timetable.mzn` is the working constraint model. It consumes `data/output/model_data.dzn`, generated from the validated CSV inputs by Python. See the project-root `README_SETUP.md` for the encoded hard rules and run commands.
- `smoke_test.mzn` only verifies MiniZinc/Gecode installation; it does not create a timetable.
