#!/usr/bin/env python3
"""Horizon AIOS nightly maintenance runner.

Invoked unattended by the maintenance scheduler (cron on Unix/macOS, Task
Scheduler on Windows — see horizon_aios_setup_maintenance_schedule.py). Runs the
routine housekeeping steps in order, non-interactively, so ordinary
configuration/permission drift self-corrects overnight:

  1. horizon_aios_doctor.py  — report drift; the pass/warn/fail summary is
     captured to the log. A non-zero doctor result (failures found) is recorded
     but does NOT abort the run — the point is to then re-assert the model.
  2. horizon_aios_harden.py  — re-assert the brains-group ACL / permission model
     (idempotent, non-interactive; additive mode preserves existing ACLs).

Safe to run repeatedly. Exits 0 unless the runner itself errors — a step
reporting its own findings (e.g. doctor exit 1) does not, by itself, fail the
run. Use --dry-run to print the steps without executing them.
"""

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent          # horizon_system/sbin/
HORIZON_SYSTEM = SCRIPT_DIR.parent                    # horizon_system/
HORIZON_ROOT = HORIZON_SYSTEM.parent                  # devroot/
HORIZON_ETC = HORIZON_SYSTEM / "ai_os_etc"
CONFIG_FILE = HORIZON_ETC / "aios_local.conf"


def build_child_env(log_dir):
    """Cron runs with a minimal environment, but horizon_aios_doctor.py reads the
    HORIZON_* dir vars from the environment (it has no __file__ fallback), so its
    ACL/isolation checks would be skipped if we don't set them. Derive the same
    paths bootstrap exports (from this script's location) and hand them to the
    child steps. harden self-resolves from __file__, so this is belt-and-braces
    for it and essential for doctor."""
    env = dict(os.environ)
    env.update({
        "HORIZON_SYSTEM":   str(HORIZON_SYSTEM),
        "HORIZON_ROOT":     str(HORIZON_ROOT),
        "HORIZON_BIN":      str(HORIZON_SYSTEM / "bin"),
        "HORIZON_ETC":      str(HORIZON_ETC),
        "HORIZON_DOCS":     str(HORIZON_SYSTEM / "documentation"),
        "HORIZON_SOUNDS":   str(HORIZON_SYSTEM / "sounds"),
        "HORIZON_LOGS":     str(log_dir),
        "HORIZON_USRBIN":   str(HORIZON_ROOT / "usrbin"),
        "HORIZON_PROJECTS": str(HORIZON_ROOT / "projects"),
    })
    return env

DOCTOR = SCRIPT_DIR / "horizon_aios_doctor.py"
HARDEN = SCRIPT_DIR / "horizon_aios_harden.py"


def resolve_log_dir():
    """Locate the logs dir the way the other sbin scripts do: AIOS_LOG_DIR from
    aios_local.conf if set, else $HORIZON_SYSTEM/logs."""
    log_dir = ""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() == "AIOS_LOG_DIR":
                    log_dir = value.strip().strip("'\"")
    return Path(log_dir) if log_dir else HORIZON_SYSTEM / "logs"


def log(handle, msg):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line)
    if handle is not None:
        handle.write(line + "\n")
        handle.flush()


def run_step(handle, name, script, args, dry_run, env=None):
    """Run one maintenance step. Captures its output to the log. A non-zero exit
    from the step is logged but NOT propagated — the runner only fails if it
    cannot launch the step at all."""
    if not script.exists():
        log(handle, f"[WARN] {name}: script not found at {script} — skipping.")
        return
    python = sys.executable or "python3"
    cmd = [python, str(script)] + list(args)
    log(handle, f"[STEP] {name}: {' '.join(cmd)}")
    if dry_run:
        log(handle, f"[DRY-RUN] would run {name}")
        return
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if handle is not None and result.stdout:
        handle.write(result.stdout)
        if not result.stdout.endswith("\n"):
            handle.write("\n")
        handle.flush()
    if result.stderr:
        log(handle, f"[{name} stderr] {result.stderr.strip()}")
    # Surface the step's final line (e.g. doctor's pass/warn/fail summary) for
    # quick log scanning.
    tail = result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else ""
    log(handle, f"[DONE] {name}: exit={result.returncode}" + (f"  ({tail})" if tail else ""))


def main():
    parser = argparse.ArgumentParser(
        description="Horizon AIOS nightly maintenance runner (doctor report + "
                    "harden re-assert). Runs unattended; safe to repeat.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the steps that would run without executing them.")
    args = parser.parse_args()

    log_dir = resolve_log_dir()
    log_file = log_dir / "horizon_aios_nightly_maintenance.log"
    handle = None
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handle = open(log_file, "a", encoding="utf-8")
    except OSError as exc:
        print(f"[WARN] Could not open log file {log_file}: {exc} — logging to stdout only.")

    child_env = build_child_env(log_dir)
    exit_code = 0
    try:
        log(handle, "=== Horizon AIOS nightly maintenance: start ===")
        # 1. Doctor — report drift; a non-zero result must NOT abort the run.
        run_step(handle, "doctor", DOCTOR, [], args.dry_run, env=child_env)
        # 2. Harden — re-assert the permission model (idempotent, non-interactive).
        run_step(handle, "harden", HARDEN, [], args.dry_run, env=child_env)
        log(handle, "=== Horizon AIOS nightly maintenance: done ===")
    except Exception as exc:  # noqa: BLE001 — runner-level failure only
        log(handle, f"[FATAL] nightly maintenance runner error: {exc}")
        exit_code = 1
    finally:
        if handle is not None:
            handle.close()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
