#!/usr/bin/env python3
"""
Install the Horizon AIOS filesystem monitor as a scheduled service.

Windows — three Task Scheduler tasks, all run as SYSTEM (/RL HIGHEST):
  AIOSMonitor         — at STARTUP (survives reboot); runs pythonw horizon_aios_monitor.py directly
  AIOSMonitorAnalyzer — daily at 06:00; runs pythonw horizon_aios_monitor_analyze.py directly
  AIOSMonitorWatchdog — hourly; runs horizon_aios_monitor_watchdog_runner.ps1, which restarts
                        AIOSMonitor if the monitor process is not running

Running as SYSTEM is deliberate: the monitor is a system audit service that must (a) write its
log under the hardened $HORIZON_SYSTEM/logs tree — where the harden posture DENIES write to the
horizon_humans group, so a human-owned task cannot write there — and (b) read across the whole
install. SYSTEM satisfies both and needs no stored password, so there is no service-account
credential to manage.

The monitor requires the third-party 'watchdog' package. Install ensures it is present in the
GLOBAL site-packages of the interpreter used here (a --user install would be invisible to the
SYSTEM-run task), so bootstrap must run this elevated.

Linux/macOS — three cron entries for the current user (no elevation/service account needed):
  monitor  @reboot (survives reboot), analyzer daily 06:00, and an hourly
  watchdog that restarts the monitor if its process is not running.

Usage:
  python horizon_aios_setup_monitor_service.py install   [--yes]
  python horizon_aios_setup_monitor_service.py uninstall
  python horizon_aios_setup_monitor_service.py status
"""

import platform
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR     = Path(__file__).resolve().parent   # horizon_system/sbin/
HORIZON_SYSTEM = SCRIPT_DIR.parent                 # horizon_system/
HORIZON_ROOT   = HORIZON_SYSTEM.parent             # repo root

MONITOR_SCRIPT  = SCRIPT_DIR / "horizon_aios_monitor.py"
ANALYZER_SCRIPT = SCRIPT_DIR / "horizon_aios_monitor_analyze.py"
WATCHDOG_RUNNER = SCRIPT_DIR / "horizon_aios_monitor_watchdog_runner.ps1"
MONITOR_TASK    = "AIOSMonitor"
ANALYZER_TASK   = "AIOSMonitorAnalyzer"
WATCHDOG_TASK   = "AIOSMonitorWatchdog"


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def ensure_watchdog() -> bool:
    """Ensure the 'watchdog' package is importable by THIS interpreter.

    Installs into the interpreter's own (global, when elevated) site-packages so a
    SYSTEM-run task can import it. A --user install would land in the invoking user's
    site-packages and be invisible to SYSTEM, so we deliberately do not pass --user.
    """
    try:
        import watchdog  # noqa: F401
        return True
    except ImportError:
        pass
    print("[INFO] Installing required 'watchdog' package ...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "watchdog"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[ERR] pip install watchdog failed: {r.stderr.strip()}", file=sys.stderr)
        return False
    print("[OK]  watchdog installed.")
    return True


# ---------------------------------------------------------------------------
# Windows Task Scheduler helpers
# ---------------------------------------------------------------------------

def _pythonw() -> str:
    """Windowless interpreter alongside the current one; fall back to python.exe.

    Using pythonw avoids a console window for the boot/scheduled task while keeping the
    task's Last Result tied to the real process exit code (no PowerShell wrapper to swallow it).
    """
    cand = Path(sys.executable).with_name("pythonw.exe")
    return str(cand) if cand.exists() else sys.executable


def _task_exists(task_name: str) -> bool:
    r = subprocess.run(["schtasks", "/Query", "/TN", task_name],
                       capture_output=True, text=True)
    return r.returncode == 0


def _schtasks_create(task_name: str, run_cmd: str, schedule_args: list[str]) -> bool:
    """Create a scheduled task that runs as SYSTEM (no password), highest privileges."""
    cmd = [
        "schtasks", "/Create",
        "/TN", task_name,
        "/TR", run_cmd,
        "/RU", "SYSTEM",
        "/RL", "HIGHEST",
        "/F",
    ] + schedule_args
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[ERR] schtasks /Create {task_name}: {r.stderr.strip()}", file=sys.stderr)
        return False
    return True


def _schtasks_delete(task_name: str) -> bool:
    r = subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"],
                       capture_output=True, text=True)
    return r.returncode == 0


# ---------------------------------------------------------------------------
# Install / uninstall / status
# ---------------------------------------------------------------------------

def install_windows(yes: bool) -> int:
    if not ensure_watchdog():
        return 1

    pythonw = _pythonw()
    tasks = [
        (MONITOR_TASK,
         f'"{pythonw}" "{MONITOR_SCRIPT}"',
         ["/SC", "ONSTART"],
         "at startup (survives reboot)"),
        (ANALYZER_TASK,
         f'"{pythonw}" "{ANALYZER_SCRIPT}"',
         ["/SC", "DAILY", "/ST", "06:00"],
         "daily at 06:00"),
        (WATCHDOG_TASK,
         f'powershell.exe -NonInteractive -ExecutionPolicy Bypass -File "{WATCHDOG_RUNNER}"',
         ["/SC", "HOURLY", "/MO", "1"],
         "hourly (watchdog: restarts monitor if stopped)"),
    ]

    ok = True
    for task, run_cmd, sched, label in tasks:
        if _task_exists(task) and not yes:
            ans = input(f"Task '{task}' already exists. Overwrite? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print(f"[INFO] Skipped '{task}'.")
                continue
        if _schtasks_create(task, run_cmd, sched):
            print(f"[OK]  Task '{task}' registered — runs {label}, as SYSTEM")
        else:
            ok = False

    if ok:
        print(f"\nMonitor log dir: {HORIZON_SYSTEM / 'logs' / 'horizon_aios_monitor'}")
        print(f"Analyzer report: {HORIZON_SYSTEM / 'logs' / 'horizon_aios_security.log'}")
        print("Start now without rebooting:")
        print(f"  schtasks /Run /TN {MONITOR_TASK}")
    return 0 if ok else 1


def uninstall_windows() -> int:
    ok = True
    for task in (MONITOR_TASK, ANALYZER_TASK, WATCHDOG_TASK):
        if _task_exists(task):
            if _schtasks_delete(task):
                print(f"[OK]  Task '{task}' removed.")
            else:
                print(f"[ERR] Failed to remove '{task}'.", file=sys.stderr)
                ok = False
        else:
            print(f"[INFO] Task '{task}' not found — skipped.")
    return 0 if ok else 1


def status_windows() -> int:
    for task in (MONITOR_TASK, ANALYZER_TASK, WATCHDOG_TASK):
        exists = _task_exists(task)
        tag = "[OK] " if exists else "[--]"
        print(f"{tag} Task Scheduler: {task} {'registered' if exists else 'NOT registered'}")
    return 0


def install_unix() -> int:
    if not ensure_watchdog():
        return 1

    monitor_script  = SCRIPT_DIR / "horizon_aios_monitor.py"
    analyzer_script = SCRIPT_DIR / "horizon_aios_monitor_analyze.py"
    py = sys.executable
    marker_m = "# HorizonAIOS_Monitor"
    marker_a = "# HorizonAIOS_MonitorAnalyzer"
    marker_w = "# HorizonAIOS_MonitorWatchdog"

    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = existing.stdout if existing.returncode == 0 else ""

    new = current.rstrip("\n")
    added = []

    if marker_m not in current:
        new += f"\n{marker_m}\n@reboot {py} {monitor_script}\n"
        added.append("monitor (@reboot)")

    if marker_a not in current:
        new += f"\n{marker_a}\n0 6 * * * {py} {analyzer_script}\n"
        added.append("analyzer (daily 06:00)")

    if marker_w not in current:
        # Hourly watchdog: if no horizon_aios_monitor.py process is running,
        # (re)start it detached. Survives crashes between reboots.
        watchdog = (f"0 * * * * pgrep -f {monitor_script} >/dev/null 2>&1 || "
                    f"nohup {py} {monitor_script} >/dev/null 2>&1 &")
        new += f"\n{marker_w}\n{watchdog}\n"
        added.append("watchdog (hourly restart-if-stopped)")

    if not added:
        print("[INFO] Cron entries already present — nothing to do.")
        return 0

    r = subprocess.run(["crontab", "-"], input=new, text=True, capture_output=True)
    if r.returncode != 0:
        print(f"[ERR] crontab write failed: {r.stderr.strip()}", file=sys.stderr)
        return 1

    for label in added:
        print(f"[OK]  Cron entry installed: {label}")
    return 0


def uninstall_unix() -> int:
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if existing.returncode != 0:
        print("[INFO] No crontab found.")
        return 0
    markers = {"# HorizonAIOS_Monitor", "# HorizonAIOS_MonitorAnalyzer",
               "# HorizonAIOS_MonitorWatchdog"}
    lines = existing.stdout.splitlines(keepends=True)
    skip_next = False
    kept, removed = [], 0
    for line in lines:
        if line.strip() in markers:
            skip_next = True
            removed += 1
            continue
        if skip_next:
            skip_next = False
            removed += 1
            continue
        kept.append(line)
    if removed == 0:
        print("[INFO] No monitor cron entries found.")
        return 0
    r = subprocess.run(["crontab", "-"], input="".join(kept), text=True, capture_output=True)
    if r.returncode != 0:
        print(f"[ERR] crontab write failed: {r.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"[OK]  Removed {removed} monitor cron line(s).")
    return 0


def status_unix() -> int:
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = existing.stdout if existing.returncode == 0 else ""
    for marker, label in [
        ("# HorizonAIOS_Monitor", "monitor (@reboot)"),
        ("# HorizonAIOS_MonitorAnalyzer", "analyzer (daily 06:00)"),
        ("# HorizonAIOS_MonitorWatchdog", "watchdog (hourly restart-if-stopped)"),
    ]:
        found = marker in current
        print(f"{'[OK] ' if found else '[--]'} cron: {label} {'installed' if found else 'NOT installed'}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def usage() -> None:
    print(__doc__.strip(), file=sys.stderr)


def main() -> int:
    args = sys.argv[1:]
    yes  = "--yes" in args
    args = [a for a in args if a != "--yes"]

    if not args:
        usage()
        return 1

    cmd = args[0]
    system = platform.system()

    if cmd == "install":
        if system == "Windows":
            return install_windows(yes)
        return install_unix()

    if cmd == "uninstall":
        if system == "Windows":
            return uninstall_windows()
        return uninstall_unix()

    if cmd == "status":
        if system == "Windows":
            return status_windows()
        return status_unix()

    print(f"[ERR] Unknown command: {cmd}", file=sys.stderr)
    usage()
    return 1


if __name__ == "__main__":
    sys.exit(main())
