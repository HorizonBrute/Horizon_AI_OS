#!/usr/bin/env python3
"""Horizon AIOS upstream sync script. Lives in sbin — do not expose to brain users."""

import os
import sys
import subprocess
import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent        # sbin/
HORIZON_BIN = SCRIPT_DIR.parent                     # horizon_bin/
HORIZON_ROOT = HORIZON_BIN.parent                   # devroot/
HORIZON_ETC = HORIZON_BIN / "ai_os_etc"
CONFIG_FILE = HORIZON_ETC / "aios_local.conf"

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


def main():
    config = read_config()

    global _log_file
    log_dir = Path(config["AIOS_LOG_DIR"]) if config["AIOS_LOG_DIR"] else HORIZON_BIN / "logs"
    _log_file = log_dir / "aios_sync.log"

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
    sys.exit(0)


if __name__ == "__main__":
    main()
