#!/usr/bin/env python3
"""Install the Horizon AIOS auto-sync scheduled task (Windows) or cron job (Unix)."""

import os
import sys
import platform
import subprocess
import textwrap
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent         # horizon_system/sbin/
HORIZON_SYSTEM = SCRIPT_DIR.parent                   # horizon_system/
HORIZON_ROOT = HORIZON_SYSTEM.parent                 # devroot/
HORIZON_ETC = HORIZON_SYSTEM / "ai_os_etc"
SBIN = SCRIPT_DIR
CONFIG_FILE = HORIZON_ETC / "aios_local.conf"

DEFAULTS = {
    "SYNC_AIOS_FROM_REMOTE": "yes",
    "AIOS_SYNC_FREQ": "daily",
    "AIOS_SYNC_TIME": "03:00",
    "AIOS_REPO_REMOTE": "origin",
    "AIOS_REPO_BRANCH": "main",
    "AIOS_LOG_DIR": "",
}

YES_FLAG = "--yes" in sys.argv


def read_config():
    config = dict(DEFAULTS)
    if not CONFIG_FILE.exists():
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
            if key in config:
                config[key] = value
    return config


def confirm(prompt):
    if YES_FLAG:
        print(f"{prompt} [auto-yes]")
        return True
    answer = input(f"{prompt} [y/N] ").strip().lower()
    return answer in ("y", "yes")


def parse_time(time_str):
    try:
        hour, minute = time_str.split(":")
        return int(hour), int(minute)
    except Exception:
        print(f"[WARN] Invalid AIOS_SYNC_TIME '{time_str}' — defaulting to 03:00")
        return 3, 0


def install_windows(config):
    runner = SBIN / "sync_aios_runner.ps1"
    freq = config["AIOS_SYNC_FREQ"].lower()
    hour, minute = parse_time(config["AIOS_SYNC_TIME"])
    task_name = "HorizonAIOS_Sync"

    # Check if task already exists
    check = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name],
        capture_output=True, text=True
    )
    if check.returncode == 0:
        if not confirm(f"Scheduled task '{task_name}' already exists. Overwrite?"):
            print("[INFO] Skipped — existing task left unchanged.")
            return

    # Build trigger type
    if freq == "hourly":
        trigger_type = "HOURLY"
        modifier = "1"
    elif freq == "weekly":
        trigger_type = "WEEKLY"
        modifier = "1"
    else:  # daily
        trigger_type = "DAILY"
        modifier = "1"

    start_time = f"{hour:02d}:{minute:02d}"

    cmd = [
        "schtasks", "/Create",
        "/TN", task_name,
        "/TR", f'powershell.exe -NonInteractive -File "{runner}"',
        "/SC", trigger_type,
        "/MO", modifier,
        "/ST", start_time,
        "/F",
        "/RL", "HIGHEST",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERR] Failed to register scheduled task: {result.stderr.strip()}")
        sys.exit(1)

    print(f"[OK] Scheduled task '{task_name}' registered — runs {freq} at {start_time}")

    # Register weekly log maintenance task
    maint_task_name = "HorizonAIOS_MaintainLogs"
    maint_runner = SBIN / "maintain_logs_runner.ps1"
    maint_cmd = [
        "schtasks", "/Create",
        "/TN", maint_task_name,
        "/TR", f'powershell.exe -NonInteractive -File "{maint_runner}"',
        "/SC", "WEEKLY",
        "/D", "SUN",
        "/ST", "04:00",
        "/F",
        "/RL", "HIGHEST",
    ]
    maint_result = subprocess.run(maint_cmd, capture_output=True, text=True)
    if maint_result.returncode != 0:
        print(f"[ERR] Failed to register maintenance task: {maint_result.stderr.strip()}")
        sys.exit(1)
    print(f"[OK] Scheduled task '{maint_task_name}' registered — runs weekly on Sunday at 04:00")

    log_dir = Path(config["AIOS_LOG_DIR"]) if config["AIOS_LOG_DIR"] else HORIZON_SYSTEM / "logs"
    print_next_steps(config, log_dir / "aios_sync.log")


def install_unix(config, log_file):
    freq = config["AIOS_SYNC_FREQ"].lower()
    hour, minute = parse_time(config["AIOS_SYNC_TIME"])
    sync_script = SBIN / "sync_aios.py"
    marker = "# HorizonAIOS_Sync"

    if freq == "hourly":
        cron_time = "0 * * * *"
    elif freq == "weekly":
        cron_time = f"{minute} {hour} * * 0"
    else:
        cron_time = f"{minute} {hour} * * *"

    cron_line = f"{cron_time} /usr/bin/env python3 {sync_script} >> {log_file} 2>&1"

    # Read existing crontab
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = existing.stdout if existing.returncode == 0 else ""

    if marker in current:
        print(f"[INFO] Cron entry already present (marker '{marker}' found). Skipping.")
    else:
        new_crontab = current.rstrip("\n") + f"\n{marker}\n{cron_line}\n"
        result = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
        if result.returncode != 0:
            print(f"[ERR] Failed to install cron entry: {result.stderr.strip()}")
            sys.exit(1)
        print(f"[OK] Cron entry installed — runs {freq} at {hour:02d}:{minute:02d}")

    # Register weekly log maintenance cron entry
    maint_script = SBIN / "maintain_logs.py"
    maint_marker = "# HorizonAIOS_MaintainLogs"
    maint_cron_line = f"0 4 * * 0 /usr/bin/env python3 {maint_script}"

    # Re-read current crontab (may have changed above)
    existing2 = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current2 = existing2.stdout if existing2.returncode == 0 else ""

    if maint_marker in current2:
        print(f"[INFO] Maintenance cron entry already present (marker '{maint_marker}' found). Skipping.")
    else:
        new_crontab2 = current2.rstrip("\n") + f"\n{maint_marker}\n{maint_cron_line}\n"
        maint_result = subprocess.run(["crontab", "-"], input=new_crontab2, text=True, capture_output=True)
        if maint_result.returncode != 0:
            print(f"[ERR] Failed to install maintenance cron entry: {maint_result.stderr.strip()}")
            sys.exit(1)
        print("[OK] Maintenance cron entry installed — runs weekly on Sunday at 04:00")

    print_next_steps(config, log_file)


def print_next_steps(config, log_file=None):
    remote = config["AIOS_REPO_REMOTE"]
    if log_file is None:
        log_dir = Path(config["AIOS_LOG_DIR"]) if config["AIOS_LOG_DIR"] else HORIZON_SYSTEM / "logs"
        log_file = log_dir / "aios_sync.log"
    print(textwrap.dedent(f"""
    [NEXT STEPS] For unattended sync to work:

    1. Ensure your SSH key for remote '{remote}' is available without a passphrase prompt.
       - On Unix: use a passphrase-free deploy key, or configure ssh-agent to load it at
         login (e.g., ~/.ssh/config: AddKeysToAgent yes + UseKeychain yes on macOS).
       - On Windows: the OpenSSH Authentication Agent service must be running and the key
         loaded at login. Task runs only when you are logged in (default).

         For always-on (logged-out) sync: see horizon_system/documentation/sync_setup.md
         for the advanced stored-credential + deploy key setup.

    2. Test manually before relying on automation:
         python {SBIN / 'sync_aios.py'}

    3. Check sync logs at:
         {log_file}
    """).strip())


def main():
    config = read_config()

    log_dir = Path(config["AIOS_LOG_DIR"]) if config["AIOS_LOG_DIR"] else HORIZON_SYSTEM / "logs"
    log_file = log_dir / "aios_sync.log"

    if config["SYNC_AIOS_FROM_REMOTE"].lower() == "no":
        print("[INFO] SYNC_AIOS_FROM_REMOTE=no in aios_local.conf — scheduler not installed.")
        print("       Set SYNC_AIOS_FROM_REMOTE=yes and re-run to install.")
        sys.exit(0)

    system = platform.system()
    if system == "Windows":
        install_windows(config)
    elif system in ("Linux", "Darwin"):
        install_unix(config, log_file)
    else:
        print(f"[ERR] Unsupported platform: {system}")
        sys.exit(1)


if __name__ == "__main__":
    main()
