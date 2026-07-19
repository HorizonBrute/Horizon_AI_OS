#!/usr/bin/env python3
"""Install (or remove) the Horizon AIOS nightly maintenance schedule.

Schedules horizon_aios_nightly_maintenance.py to run unattended each night
(default 03:00): a health-check (doctor) followed by a permission-model
re-assert (harden), so routine drift self-corrects. Cross-platform: a crontab
entry on Unix/macOS, a Scheduled Task on Windows. Idempotent — a unique marker
comment (Unix) / fixed task name (Windows) prevents duplicate installs.

Flags:
  --yes            non-interactive (assume yes to any prompt)
  --time HH:MM     override the nightly run time (default 03:00)
  --remove         uninstall the schedule instead of installing it
"""

import argparse
import platform
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent          # horizon_system/sbin/
HORIZON_SYSTEM = SCRIPT_DIR.parent                    # horizon_system/
HORIZON_ROOT = HORIZON_SYSTEM.parent                  # devroot/
HORIZON_ETC = HORIZON_SYSTEM / "ai_os_etc"
SBIN = SCRIPT_DIR
CONFIG_FILE = HORIZON_ETC / "aios_local.conf"

RUNNER = SBIN / "horizon_aios_nightly_maintenance.py"
MARKER = "# HorizonAIOS_NightlyMaintenance"          # Unix cron idempotency marker
TASK_NAME = "HorizonAIOS_NightlyMaintenance"          # Windows scheduled-task name
DEFAULT_TIME = "03:00"


def read_log_dir():
    """Resolve AIOS_LOG_DIR from aios_local.conf (else $HORIZON_SYSTEM/logs)."""
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


def confirm(prompt, yes_flag):
    if yes_flag:
        print(f"{prompt} [auto-yes]")
        return True
    answer = input(f"{prompt} [y/N] ").strip().lower()
    return answer in ("y", "yes")


def parse_time(time_str):
    try:
        hour, minute = time_str.split(":")
        return int(hour), int(minute)
    except Exception:
        print(f"[WARN] Invalid --time '{time_str}' — defaulting to {DEFAULT_TIME}")
        h, m = DEFAULT_TIME.split(":")
        return int(h), int(m)


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def install_windows(hour, minute, yes_flag):
    check = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME],
        capture_output=True, text=True,
    )
    if check.returncode == 0:
        if not confirm(f"Scheduled task '{TASK_NAME}' already exists. Overwrite?", yes_flag):
            print("[INFO] Skipped — existing task left unchanged.")
            return

    start_time = f"{hour:02d}:{minute:02d}"
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", f'python "{RUNNER}"',
        "/SC", "DAILY",
        "/MO", "1",
        "/ST", start_time,
        "/F",
        "/RL", "HIGHEST",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERR] Failed to register scheduled task: {result.stderr.strip()}")
        sys.exit(1)
    print(f"[OK] Scheduled task '{TASK_NAME}' registered — runs daily at {start_time}")
    print_next_steps()


def remove_windows():
    check = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME],
        capture_output=True, text=True,
    )
    if check.returncode != 0:
        print(f"[INFO] Scheduled task '{TASK_NAME}' not present — nothing to remove.")
        return
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[ERR] Failed to delete scheduled task: {result.stderr.strip()}")
        sys.exit(1)
    print(f"[OK] Scheduled task '{TASK_NAME}' removed.")


# ---------------------------------------------------------------------------
# Unix / macOS (crontab)
# ---------------------------------------------------------------------------

def _current_crontab():
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return existing.stdout if existing.returncode == 0 else ""


def install_unix(hour, minute, log_file):
    cron_time = f"{minute} {hour} * * *"
    cron_line = f"{cron_time} /usr/bin/env python3 {RUNNER} >> {log_file} 2>&1"

    current = _current_crontab()
    if MARKER in current:
        print(f"[INFO] Cron entry already present (marker '{MARKER}' found). Skipping.")
    else:
        new_crontab = current.rstrip("\n") + f"\n{MARKER}\n{cron_line}\n"
        result = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
        if result.returncode != 0:
            print(f"[ERR] Failed to install cron entry: {result.stderr.strip()}")
            sys.exit(1)
        print(f"[OK] Cron entry installed — runs nightly at {hour:02d}:{minute:02d}")
    print_next_steps(log_file)


def remove_unix():
    current = _current_crontab()
    if MARKER not in current:
        print(f"[INFO] Cron entry not present (marker '{MARKER}' absent) — nothing to remove.")
        return
    # Drop the marker line and the command line that immediately follows it.
    lines = current.splitlines()
    kept = []
    skip_next = False
    for line in lines:
        if skip_next:
            skip_next = False
            continue
        if line.strip() == MARKER:
            skip_next = True   # also drop the cron command on the next line
            continue
        kept.append(line)
    new_crontab = ("\n".join(kept).rstrip("\n") + "\n") if kept else ""
    result = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"[ERR] Failed to update crontab: {result.stderr.strip()}")
        sys.exit(1)
    print(f"[OK] Cron entry removed (marker '{MARKER}').")


# ---------------------------------------------------------------------------

def print_next_steps(log_file=None):
    if log_file is None:
        log_file = read_log_dir() / "horizon_aios_nightly_maintenance.log"
    print(textwrap.dedent(f"""
    [NEXT STEPS] Nightly maintenance (doctor report + harden re-assert):

    1. It runs unattended and must be able to apply ACL changes — the schedule
       runs with the elevation of the installing account (root / Administrator).

    2. Test the runner manually before relying on automation:
         python {RUNNER} --dry-run
         python {RUNNER}

    3. Check maintenance logs at:
         {log_file}

    Opt out at onboarding with --no-nightly (bootstrap.sh) / -NoNightly
    (bootstrap.ps1), or remove later:
         python {SBIN / 'horizon_aios_setup_maintenance_schedule.py'} --remove
    """).strip())


def main():
    parser = argparse.ArgumentParser(
        description="Install or remove the Horizon AIOS nightly maintenance schedule.")
    parser.add_argument("--yes", action="store_true",
                        help="non-interactive (assume yes to any prompt).")
    parser.add_argument("--time", default=DEFAULT_TIME, metavar="HH:MM",
                        help=f"nightly run time (default {DEFAULT_TIME}).")
    parser.add_argument("--remove", action="store_true",
                        help="uninstall the schedule instead of installing it.")
    args = parser.parse_args()

    system = platform.system()
    if system not in ("Windows", "Linux", "Darwin"):
        print(f"[ERR] Unsupported platform: {system}")
        sys.exit(1)

    if args.remove:
        if system == "Windows":
            remove_windows()
        else:
            remove_unix()
        return

    hour, minute = parse_time(args.time)
    if system == "Windows":
        install_windows(hour, minute, args.yes)
    else:
        log_file = read_log_dir() / "horizon_aios_nightly_maintenance.log"
        install_unix(hour, minute, log_file)


if __name__ == "__main__":
    main()
