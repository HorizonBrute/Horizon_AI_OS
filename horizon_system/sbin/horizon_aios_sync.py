#!/usr/bin/env python3
"""Horizon AIOS upstream sync script. Lives in sbin — do not expose to brain users."""

import os
import sys
import argparse
import platform
import subprocess
import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent        # sbin/
HORIZON_SYSTEM = SCRIPT_DIR.parent                  # horizon_system/
HORIZON_ROOT = HORIZON_SYSTEM.parent                # devroot/
HORIZON_ETC = HORIZON_SYSTEM / "ai_os_etc"
CONFIG_FILE = HORIZON_ETC / "aios_local.conf"

# Schedule identifiers — must match horizon_aios_setup_sync_schedule.py.
WINDOWS_TASK_NAME = "HorizonAIOS_Sync"
CRON_MARKER = "# HorizonAIOS_Sync"

_log_file = None

DEFAULTS = {
    "SYNC_AIOS_FROM_REMOTE": "yes",
    "AIOS_SYNC_FREQ": "daily",
    "AIOS_SYNC_TIME": "03:00",
    "AIOS_REPO_REMOTE": "origin",
    "AIOS_REPO_BRANCH": "main",
    "AIOS_LOG_DIR": "",
}

ACCEPTED_KEYS = set(DEFAULTS.keys())


def log(level, message, also_print=True):
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"[{timestamp}] [{level}] {message}"
    if also_print:
        print(line)
    if _log_file is not None:
        _log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def read_config():
    config = dict(DEFAULTS)
    if not CONFIG_FILE.exists():
        log("WARN", f"aios_local.conf not found at {CONFIG_FILE} — using defaults")
        return config
    with open(CONFIG_FILE, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key in ACCEPTED_KEYS:
                config[key] = value
    return config


def run_git(*args):
    cmd = ["git", "-C", str(HORIZON_ROOT)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def resolve_log_file(config):
    """Resolve the sync log path the same way the sync run does."""
    log_dir = Path(config["AIOS_LOG_DIR"]) if config["AIOS_LOG_DIR"] else HORIZON_SYSTEM / "logs"
    return log_dir / "horizon_aios_sync.log"


def _last_log_outcome(log_file):
    """Inspect the sync log and report the last sync run's outcome.

    Returns a dict: {found, timestamp, succeeded, summary}. The sync run logs
    every terminal state — success ends with an '[OK]' "Synced to ..." line,
    failure ends with an '[ERR]' line. We scan from the bottom of the file.
    """
    result = {"found": False, "timestamp": None, "succeeded": None, "summary": None}
    if not log_file.exists():
        return result

    try:
        lines = [l.rstrip("\n") for l in log_file.read_text(encoding="utf-8").splitlines()]
    except OSError as exc:
        result["summary"] = f"could not read log: {exc}"
        return result

    # Walk backwards to the most recent terminal outcome line.
    for line in reversed(lines):
        if not line.strip():
            continue
        # Expected shape: [<iso-timestamp>] [<LEVEL>] <message>
        ts = None
        level = None
        msg = line
        if line.startswith("[") and "]" in line:
            ts = line[1:line.index("]")]
            rest = line[line.index("]") + 1:].lstrip()
            if rest.startswith("[") and "]" in rest:
                level = rest[1:rest.index("]")]
                msg = rest[rest.index("]") + 1:].strip()

        if level == "OK" and msg.startswith("Synced to"):
            result.update(found=True, timestamp=ts, succeeded=True, summary=msg)
            return result
        if level == "INFO" and "skipping sync" in msg.lower():
            # SYNC_AIOS_FROM_REMOTE=no — a clean, intentional no-op.
            result.update(found=True, timestamp=ts, succeeded=True, summary=msg)
            return result
        if level == "ERR":
            result.update(found=True, timestamp=ts, succeeded=False, summary=msg)
            return result

    return result


def _windows_schedule():
    """Return (installed, last_result, last_run, detail) for the Windows task."""
    query = subprocess.run(
        ["schtasks", "/Query", "/TN", WINDOWS_TASK_NAME, "/FO", "LIST", "/V"],
        capture_output=True, text=True,
    )
    if query.returncode != 0:
        return (False, None, None, None)

    last_result = None
    last_run = None
    for raw in query.stdout.splitlines():
        if ":" not in raw:
            continue
        field, _, value = raw.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "last result":
            last_result = value
        elif field == "last run time":
            last_run = value
    return (True, last_result, last_run, None)


def _unix_schedule():
    """Return (installed, last_result, last_run, detail) for the cron entry."""
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = existing.stdout if existing.returncode == 0 else ""
    installed = CRON_MARKER in current
    # cron records no per-job last-result/last-run; the sync log is the source.
    return (installed, None, None, None)


def run_status(config):
    """Read-only: report whether auto-sync is installed and its last outcome.

    Exit code: 0 = installed AND last run ok (or no run yet but installed);
    non-zero = not installed, or the last recorded run failed.
    """
    log_file = resolve_log_file(config)
    system = platform.system()

    if system == "Windows":
        installed, sched_result, sched_run, detail = _windows_schedule()
        sched_kind = f"Windows Task Scheduler task '{WINDOWS_TASK_NAME}'"
    elif system in ("Linux", "Darwin"):
        installed, sched_result, sched_run, detail = _unix_schedule()
        sched_kind = f"cron entry (marker '{CRON_MARKER}')"
    else:
        installed, sched_result, sched_run, detail = (False, None, None, None)
        sched_kind = f"unsupported platform '{system}'"

    outcome = _last_log_outcome(log_file)

    print("Horizon AIOS auto-sync status")
    print("-----------------------------")
    print(f"Platform        : {system}")
    print(f"Schedule        : {'INSTALLED' if installed else 'NOT INSTALLED'} ({sched_kind})")
    if config["SYNC_AIOS_FROM_REMOTE"].lower() == "no":
        print("Config          : SYNC_AIOS_FROM_REMOTE=no (auto-sync disabled in aios_local.conf)")
    if installed and sched_run:
        print(f"Scheduler run   : last run {sched_run}, last result {sched_result}")

    print(f"Log file        : {log_file}")
    if not outcome["found"]:
        print("Last sync run   : NONE recorded in log")
    else:
        state = "SUCCESS" if outcome["succeeded"] else "FAILED"
        when = outcome["timestamp"] or "unknown time"
        print(f"Last sync run   : {state} at {when}")
        if outcome["summary"]:
            print(f"  detail        : {outcome['summary']}")

    # Exit-code contract.
    if not installed:
        print("\nResult          : auto-sync is NOT installed.")
        print("                  Install with: python "
              f"{SCRIPT_DIR / 'horizon_aios_setup_sync_schedule.py'}")
        sys.exit(1)

    if outcome["found"] and outcome["succeeded"] is False:
        print("\nResult          : auto-sync is installed but the LAST RUN FAILED.")
        print(f"                  Review the log: {log_file}")
        sys.exit(2)

    if not outcome["found"]:
        print("\nResult          : auto-sync is installed; no run has been recorded yet.")
        sys.exit(0)

    print("\nResult          : auto-sync is installed and the last run succeeded.")
    sys.exit(0)


def run_sync():
    config = read_config()

    global _log_file
    _log_file = resolve_log_file(config)

    if config["SYNC_AIOS_FROM_REMOTE"].lower() == "no":
        log("INFO", "SYNC_AIOS_FROM_REMOTE=no — skipping sync")
        sys.exit(0)

    # Verify git is available
    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        log("ERR", "git not found on PATH")
        sys.exit(1)

    # Verify HORIZON_ROOT is a git repo
    if not (HORIZON_ROOT / ".git").exists():
        log("ERR", f"{HORIZON_ROOT} is not a git repository. Run 'git init' first.")
        sys.exit(1)

    remote = config["AIOS_REPO_REMOTE"]
    branch = config["AIOS_REPO_BRANCH"]

    # Check for uncommitted changes (staged or modified tracked files only; ignore untracked)
    status = run_git("status", "--porcelain")
    dirty_lines = [
        l for l in status.stdout.splitlines()
        if l[:2].strip() and not l.startswith("??")
    ]
    if dirty_lines:
        log("ERR", f"Uncommitted changes in {HORIZON_ROOT}. Commit or stash before syncing.")
        log("ERR", "Dirty files: " + ", ".join(l[3:] for l in dirty_lines))
        sys.exit(1)

    # Fetch
    fetch = run_git("fetch", remote)
    if fetch.returncode != 0:
        log("ERR", f"git fetch failed: {fetch.stderr.strip()}")
        sys.exit(1)
    log("OK", f"Fetched from {remote}")

    # Fast-forward merge only
    merge = run_git("merge", "--ff-only", f"{remote}/{branch}")
    if merge.returncode != 0:
        log("ERR", f"Fast-forward not possible. Local history has diverged from {remote}/{branch}.")
        log("ERR", f"Resolve manually: cd {HORIZON_ROOT} && git status")
        sys.exit(1)

    log("OK", f"Synced to {remote}/{branch}: {merge.stdout.strip()}")

    # A sync may have refreshed skills_sbin and dropped the untracked symlinks
    # that register machine-local user skills. Rebuild them from usr_skills (the
    # source of truth). Best-effort: a failure here must not fail the sync.
    reg_script = SCRIPT_DIR / "horizon_aios_register_user_skills.py"
    if reg_script.exists():
        reg = subprocess.run([sys.executable, str(reg_script)], capture_output=True, text=True)
        if reg.returncode == 0:
            log("OK", "Re-registered machine-local user skills")
        else:
            log("WARN", f"horizon_aios_register_user_skills.py failed: {reg.stderr.strip()}")

    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        prog="horizon_aios_sync.py",
        description="Horizon AIOS upstream sync. With no flags, performs a "
                    "fast-forward sync from the configured remote.",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Read-only: report whether auto-sync is installed and when it last "
             "ran/succeeded. Exit 0 = installed & ok; non-zero = not installed "
             "or last run failed. Does not trigger a sync.",
    )
    args = parser.parse_args()

    if args.status:
        run_status(read_config())
    else:
        run_sync()


if __name__ == "__main__":
    main()
