from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path


def _minizinc_executable() -> str | None:
    return shutil.which("minizinc")


def _run_minizinc(command: list[str], timeout_seconds: int | None) -> subprocess.CompletedProcess[str]:
    """Run MiniZinc and clean up its child solver process if a timeout occurs."""
    process_options: dict[str, object] = {}
    if os.name == "nt":
        process_options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        process_options["start_new_session"] = True

    proc = subprocess.Popen(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **process_options,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            # MiniZinc launches a separate Gecode process; terminate the whole tree.
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                text=True,
                capture_output=True,
                check=False,
            )
            if proc.poll() is None:
                proc.kill()
            stdout, stderr = proc.communicate()
        else:
            # MiniZinc and its FlatZinc solver share the new session/process group.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = proc.communicate()
        raise subprocess.TimeoutExpired(command, timeout_seconds, output=stdout, stderr=stderr)

    return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


def run_smoke_test(model_path: Path) -> tuple[bool, str]:
    executable = _minizinc_executable()
    if not executable:
        return False, "MiniZinc CLI was not found on PATH. Install MiniZinc with Gecode, then reopen the terminal."
    command = [executable, "--solver", "Gecode", str(model_path)]
    try:
        proc = _run_minizinc(command, timeout_seconds=60)
    except subprocess.TimeoutExpired:
        return False, "MiniZinc smoke test timed out after 60 seconds."
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return False, output.strip() or f"MiniZinc exited with status {proc.returncode}"
    if "MINIZINC_SMOKE_TEST_OK" not in output:
        return False, "MiniZinc returned without the expected smoke-test marker. Output:\n" + output
    return True, output.strip()


def run_timetable(model_path: Path, data_path: Path, timeout_seconds: int | None = None) -> tuple[bool, str]:
    executable = _minizinc_executable()
    if not executable:
        return False, "MiniZinc CLI was not found on PATH. Install MiniZinc with Gecode, then reopen the terminal."
    command = [executable, "--solver", "Gecode", str(model_path), str(data_path)]
    try:
        proc = _run_minizinc(command, timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        partial = (exc.output or "") + (exc.stderr or "")
        return False, f"Timetable solve timed out after {timeout_seconds} seconds.\n{partial}"
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return False, output.strip() or f"MiniZinc exited with status {proc.returncode}"
    if "=====UNSATISFIABLE=====" in output:
        return False, "MiniZinc reports the hard constraints are infeasible.\n" + output.strip()
    if "EVENT|" not in output:
        return False, "MiniZinc returned without schedule event rows. Output:\n" + output
    return True, output.strip()
