#!/usr/bin/env python3
"""Install the Horizon AIOS monitor scheduled tasks (Windows) or report systemd instructions (Unix).

Creates two Windows Task Scheduler entries:
  AIOSMonitor        — triggers AtStartup, runs horizon_aios_monitor_runner.ps1 silently
  AIOSMonitorAnalyzer — triggers Daily at 06:00, runs horizon_aios_monitor_analyze_runner.ps1 silently

Both tasks use LogonType Interactive (no stored password required); they run elevated
when the user is logged on — correct for a personal workstation.

CLI flags:
  --yes        Auto-confirm all prompts
  --uninstall  Remove both tasks and the keyring record
  --status     Query task state and show the recorded account

Keyring service : 'horizon_aios'
Keyring key     : 'monitor_account:<windows_username>'
Keyring value   : the username string (a tracking record, not a password)
"""

import os
import platform
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent         # horizon_system/sbin/
HORIZON_SYSTEM = SCRIPT_DIR.parent                   # horizon_system/
HORIZON_ROOT = HORIZON_SYSTEM.parent                 # devroot/
SBIN = SCRIPT_DIR

KEYRING_SERVICE = 'horizon_aios'
TASK_MONITOR = "AIOSMonitor"
TASK_ANALYZER = "AIOSMonitorAnalyzer"
MONITOR_RUNNER = SBIN / "horizon_aios_monitor_runner.ps1"
ANALYZER_RUNNER = SBIN / "horizon_aios_monitor_analyze_runner.ps1"

YES_FLAG = "--yes" in sys.argv

# ---------------------------------------------------------------------------
# Keyring availability
# ---------------------------------------------------------------------------

_KEYRING_AVAILABLE = False
_keyring = None

try:
    import keyring as _keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    pass


def _warn_no_keyring() -> None:
    print(
        "[WARN] No keyring backend available. Install 'keyring' (pip install keyring) "
        "to persist the monitor account record.",
        file=sys.stderr,
    )


def store_monitor_account(username: str) -> bool:
    if not _KEYRING_AVAILABLE:
        _warn_no_keyring()
        return False
    try:
        _keyring.set_password(KEYRING_SERVICE, f"monitor_account:{username}", username)
        return True
    except Exception as exc:
        print(f"[WARN] keyring.set_password failed: {exc}", file=sys.stderr)
        return False


def get_monitor_account(username: str):
    if not _KEYRING_AVAILABLE:
        return None
    try:
        return _keyring.get_password(KEYRING_SERVICE, f"monitor_account:{username}")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def confirm(prompt: str) -> bool:
    if YES_FLAG:
        print(f"{prompt} [auto-yes]")
        return True
    answer = input(f"{prompt} [y/N] ").strip().lower()
    return answer in ("y", "yes")


def get_current_username() -> str:
    return os.environ.get("USERNAME") or os.getlogin()


def check_task_exists(task_name: str) -> bool:
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name],
        capture_output=True, text=True,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Task registration
# ---------------------------------------------------------------------------

def register_task_windows(task_name: str, runner_path: Path, is_startup: bool, username: str) -> bool:
    if is_startup:
        trigger_expr = "New-ScheduledTaskTrigger -AtStartup"
    else:
        trigger_expr = "New-ScheduledTaskTrigger -Daily -At '06:00'"

    ps_cmd = textwrap.dedent(f"""
        $action    = New-ScheduledTaskAction -Execute 'powershell.exe' `
                         -Argument '-NonInteractive -WindowStyle Hidden -File "{runner_path}"'
        $trigger   = {trigger_expr}
        $principal = New-ScheduledTaskPrincipal -UserId '{username}' -LogonType Interactive -RunLevel Highest
        Register-ScheduledTask -TaskName '{task_name}' `
            -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
    """).strip()

    result = subprocess.run(
        ["powershell.exe", "-NonInteractive", "-Command", ps_cmd],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[ERR] Failed to register '{task_name}': {result.stderr.strip()}")
        return False
    return True


# ---------------------------------------------------------------------------
# Install / uninstall / status
# ---------------------------------------------------------------------------

def install_windows() -> None:
    username = get_current_username()

    for task_name, runner, is_startup in [
        (TASK_MONITOR, MONITOR_RUNNER, True),
        (TASK_ANALYZER, ANALYZER_RUNNER, False),
    ]:
        if check_task_exists(task_name):
            if not confirm(f"Task '{task_name}' already exists. Overwrite?"):
                print(f"[INFO] Skipped — existing task '{task_name}' left unchanged.")
                continue

        ok = register_task_windows(task_name, runner, is_startup, username)
        if not ok:
            print(f"[ERR] Aborting — could not register '{task_name}'.")
            sys.exit(1)

        trigger_desc = "at startup" if is_startup else "daily at 06:00"
        print(f"[OK] Task '{task_name}' registered — runs {trigger_desc} (hidden window)")

    store_monitor_account(username)

    log_dir = HORIZON_SYSTEM / "logs"
    print(textwrap.dedent(f"""
    [NEXT STEPS]
      - Open Task Scheduler and verify both '{TASK_MONITOR}' and '{TASK_ANALYZER}' are listed.
      - Monitor runs at next startup; force a test: schtasks /Run /TN {TASK_MONITOR}
      - Check logs at: {log_dir}
    """).strip())


def install_unix() -> None:
    print("[INFO] Unix: use systemd (see audit_logging.md for the unit file template).")
    sys.exit(0)


def cmd_uninstall() -> None:
    for task_name in (TASK_MONITOR, TASK_ANALYZER):
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"[OK] Removed task '{task_name}'")
        else:
            stderr = result.stderr.strip()
            if "cannot find" in stderr.lower() or "does not exist" in stderr.lower():
                print(f"[INFO] Task '{task_name}' was not present — skipped.")
            else:
                print(f"[WARN] Could not remove '{task_name}': {stderr}")

    username = get_current_username()
    if _KEYRING_AVAILABLE:
        try:
            _keyring.delete_password(KEYRING_SERVICE, f"monitor_account:{username}")
            print(f"[OK] Removed keyring entry for monitor_account:{username}")
        except Exception:
            pass  # not present — fine


def cmd_status() -> None:
    for task_name in (TASK_MONITOR, TASK_ANALYZER):
        if check_task_exists(task_name):
            print(f"[OK]      {task_name} — installed")
        else:
            print(f"[MISSING] {task_name} — not found in Task Scheduler")

    username = get_current_username()
    stored = get_monitor_account(username)
    if stored:
        print(f"[INFO] Keyring record: monitor_account:{username} = {stored}")
    else:
        print(f"[INFO] No keyring record found for monitor_account:{username}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if "--uninstall" in sys.argv:
        cmd_uninstall()
        return

    if "--status" in sys.argv:
        cmd_status()
        return

    system = platform.system()
    if system == "Windows":
        install_windows()
    else:
        install_unix()


if __name__ == "__main__":
    main()
