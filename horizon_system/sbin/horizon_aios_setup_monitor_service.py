#!/usr/bin/env python3
"""
Install the Horizon AIOS filesystem monitor as a scheduled service.

Windows — two Task Scheduler tasks:
  AIOSMonitor         — at logon, elevated, runs horizon_aios_monitor_runner.ps1
  AIOSMonitorAnalyzer — daily at 06:00, elevated, runs horizon_aios_monitor_analyze_runner.ps1

The service account password is stored in the OS keyring (Windows Credential Manager /
macOS Keychain / Linux Secret Service) under:
  service  = "horizon_aios"
  username = "monitor_account:<account-name>"

Mirrors the brain credential pattern (horizon_aios_brain_credential.py).

Linux/macOS — two cron entries for the current user (no password/keyring needed).

Usage:
  python horizon_aios_setup_monitor_service.py install          [--user NAME] [--yes]
  python horizon_aios_setup_monitor_service.py uninstall
  python horizon_aios_setup_monitor_service.py status
  python horizon_aios_setup_monitor_service.py credential get   [--show]
  python horizon_aios_setup_monitor_service.py credential store [--user NAME]
  python horizon_aios_setup_monitor_service.py credential delete
"""

import getpass
import os
import platform
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR     = Path(__file__).resolve().parent   # horizon_system/sbin/
HORIZON_SYSTEM = SCRIPT_DIR.parent                 # horizon_system/
HORIZON_ROOT   = HORIZON_SYSTEM.parent             # repo root

MONITOR_RUNNER  = SCRIPT_DIR / "horizon_aios_monitor_runner.ps1"
ANALYZER_RUNNER = SCRIPT_DIR / "horizon_aios_monitor_analyze_runner.ps1"
MONITOR_TASK    = "AIOSMonitor"
ANALYZER_TASK   = "AIOSMonitorAnalyzer"

KEYRING_SERVICE  = "horizon_aios"
KEYRING_USERNAME = "monitor_account:{user}"


# ---------------------------------------------------------------------------
# Keyring helpers  (same pattern as horizon_aios_brain_credential.py)
# ---------------------------------------------------------------------------

_kr = None
try:
    import keyring as _kr
except ImportError:
    pass


def _kr_key(user: str) -> str:
    return KEYRING_USERNAME.format(user=user)


def _store_credential(user: str, password: str) -> bool:
    if _kr is None:
        print("[WARN] keyring not installed — credential not stored. pip install keyring", file=sys.stderr)
        return False
    try:
        _kr.set_password(KEYRING_SERVICE, _kr_key(user), password)
        return True
    except Exception as exc:
        print(f"[WARN] keyring store failed: {exc}", file=sys.stderr)
        return False


def _get_credential(user: str) -> str | None:
    if _kr is None:
        return None
    try:
        return _kr.get_password(KEYRING_SERVICE, _kr_key(user))
    except Exception:
        return None


def _delete_credential(user: str) -> bool:
    if _kr is None:
        print("[WARN] keyring not installed.", file=sys.stderr)
        return False
    try:
        _kr.delete_password(KEYRING_SERVICE, _kr_key(user))
        return True
    except Exception:
        return True   # treat missing entry as success


# ---------------------------------------------------------------------------
# Password prompt
# ---------------------------------------------------------------------------

def _prompt_password(user: str, yes: bool) -> str | None:
    """Return a password: from keyring if stored, otherwise prompt interactively."""
    stored = _get_credential(user)
    if stored:
        print(f"[INFO] Using stored credential for monitor_account:{user}")
        return stored
    if yes:
        print(f"[ERR] No stored credential for monitor_account:{user} and --yes given — run 'credential store' first.", file=sys.stderr)
        return None
    pw = getpass.getpass(f"Password for '{user}' (stored in keyring, not echoed): ")
    if not pw:
        print("[ERR] Empty password — aborted.", file=sys.stderr)
        return None
    if _store_credential(user, pw):
        print(f"[OK]  Credential stored in keyring as monitor_account:{user}")
    return pw


# ---------------------------------------------------------------------------
# Windows Task Scheduler helpers
# ---------------------------------------------------------------------------

def _task_exists(task_name: str) -> bool:
    r = subprocess.run(["schtasks", "/Query", "/TN", task_name],
                       capture_output=True, text=True)
    return r.returncode == 0


def _schtasks_create(task_name: str, runner: Path, schedule_args: list[str],
                     user: str, password: str) -> bool:
    cmd = [
        "schtasks", "/Create",
        "/TN", task_name,
        "/TR", f'powershell.exe -NonInteractive -File "{runner}"',
        "/RU", f".\\{user}",
        "/RP", password,
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

def install_windows(user: str, yes: bool) -> int:
    pw = _prompt_password(user, yes)
    if pw is None:
        return 1

    ok = True
    for task, runner, sched in [
        (MONITOR_TASK,  MONITOR_RUNNER,  ["/SC", "ONLOGON"]),
        (ANALYZER_TASK, ANALYZER_RUNNER, ["/SC", "DAILY", "/ST", "06:00"]),
    ]:
        if _task_exists(task) and not yes:
            ans = input(f"Task '{task}' already exists. Overwrite? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print(f"[INFO] Skipped '{task}'.")
                continue
        if _schtasks_create(task, runner, sched, user, pw):
            label = "at logon" if "ONLOGON" in sched else "daily at 06:00"
            print(f"[OK]  Task '{task}' registered — runs {label}, elevated as {user}")
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
    for task in (MONITOR_TASK, ANALYZER_TASK):
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
    for task in (MONITOR_TASK, ANALYZER_TASK):
        exists = _task_exists(task)
        tag = "[OK] " if exists else "[--]"
        print(f"{tag} Task Scheduler: {task} {'registered' if exists else 'NOT registered'}")
    stored_user = getpass.getuser()
    cred = _get_credential(stored_user)
    print(f"{'[OK] ' if cred else '[--]'} Keyring: monitor_account:{stored_user} {'stored' if cred else 'NOT stored'}")
    return 0


def install_unix(user: str) -> int:
    monitor_script  = SCRIPT_DIR / "horizon_aios_monitor.py"
    analyzer_script = SCRIPT_DIR / "horizon_aios_monitor_analyze.py"
    py = sys.executable
    marker_m = "# HorizonAIOS_Monitor"
    marker_a = "# HorizonAIOS_MonitorAnalyzer"

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
    markers = {"# HorizonAIOS_Monitor", "# HorizonAIOS_MonitorAnalyzer"}
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
    show = "--show" in args
    args = [a for a in args if a not in ("--yes", "--show")]

    user_flag = None
    for i, a in enumerate(args):
        if a == "--user" and i + 1 < len(args):
            user_flag = args[i + 1]
    if user_flag:
        idx = args.index("--user")
        args = args[:idx] + args[idx + 2:]

    if not args:
        usage()
        return 1

    cmd = args[0]
    system = platform.system()

    # --- credential sub-commands (cross-platform) ---
    if cmd == "credential":
        if len(args) < 2:
            usage()
            return 1
        sub = args[1]
        user = user_flag or getpass.getuser()

        if sub == "get":
            pw = _get_credential(user)
            if pw is None:
                print(f"[ERR] No credential stored for monitor_account:{user}", file=sys.stderr)
                return 1
            if show:
                print(pw)
            else:
                print(f"[OK]  Credential found for monitor_account:{user}  (pass --show to reveal)")
            return 0

        if sub == "store":
            pw = getpass.getpass(f"Password for '{user}': ")
            if not pw:
                print("[ERR] Empty password — aborted.", file=sys.stderr)
                return 1
            return 0 if _store_credential(user, pw) else 1

        if sub == "delete":
            return 0 if _delete_credential(user) else 1

        print(f"[ERR] Unknown credential sub-command: {sub}", file=sys.stderr)
        return 1

    # --- install / uninstall / status ---
    user = user_flag or getpass.getuser()

    if cmd == "install":
        if system == "Windows":
            return install_windows(user, yes)
        return install_unix(user)

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
