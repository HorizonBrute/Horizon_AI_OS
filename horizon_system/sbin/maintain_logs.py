#!/usr/bin/env python3
"""Horizon AIOS log maintenance — prune old logs and rotate oversized files."""

import sys
import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
HORIZON_SYSTEM = SCRIPT_DIR.parent
HORIZON_ROOT = HORIZON_SYSTEM.parent
HORIZON_ETC = HORIZON_SYSTEM / "ai_os_etc"
CONFIG_FILE = HORIZON_ETC / "aios_local.conf"

DEFAULTS = {
    "AIOS_LOG_DIR": "",
    "AIOS_LOG_MAX_DAYS": "30",
    "AIOS_LOG_MAX_SIZE_MB": "10",
    "AIOS_LOG_MAX_ROTATIONS": "5",
    "AIOS_HANDOFFS_MAX_SIZE_MB": "500",
}


def read_config():
    config = dict(DEFAULTS)
    if not CONFIG_FILE.exists():
        return config
    with open(CONFIG_FILE, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key in config:
                config[key] = value
    return config


def rotate_file(path: Path, max_rotations: int):
    for i in range(max_rotations - 1, 0, -1):
        src = path.parent / f"{path.name}.{i}"
        dst = path.parent / f"{path.name}.{i + 1}"
        if src.exists():
            if dst.exists():
                dst.unlink()
            src.rename(dst)
    rotated = path.parent / f"{path.name}.1"
    if rotated.exists():
        rotated.unlink()
    path.rename(rotated)
    print(f"[ROTATE] {path.name} -> {path.name}.1")


def prune_old(log_dir: Path, max_days: int):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=max_days)
    for f in log_dir.rglob("*"):
        if f.is_file() and f.name not in (".gitkeep", "README.md"):
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                print(f"[PRUNE] {f.relative_to(log_dir)} (age > {max_days}d)")


def rotate_large(log_dir: Path, max_size_bytes: int, max_rotations: int):
    for f in log_dir.rglob("*.log"):
        if f.exists() and f.stat().st_size > max_size_bytes:
            rotate_file(f, max_rotations)


def prune_handoffs(handoffs_dir: Path, max_size_bytes: int):
    if not handoffs_dir.exists():
        return
    # Collect all files sorted oldest-first by modification time
    files = sorted(
        [f for f in handoffs_dir.rglob("*") if f.is_file()],
        key=lambda f: f.stat().st_mtime
    )
    total = sum(f.stat().st_size for f in files)
    for f in files:
        if total <= max_size_bytes:
            break
        size = f.stat().st_size
        f.unlink()
        total -= size
        print(f"[PRUNE] handoffs/{f.name} (size budget exceeded)")


def main():
    config = read_config()
    log_dir = Path(config["AIOS_LOG_DIR"]) if config["AIOS_LOG_DIR"] else HORIZON_ROOT / "logs"

    if not log_dir.exists():
        print(f"[INFO] Log directory {log_dir} does not exist — nothing to maintain.")
        sys.exit(0)

    max_days = int(config["AIOS_LOG_MAX_DAYS"]) if config["AIOS_LOG_MAX_DAYS"] != "0" else 0
    max_size_mb = int(config["AIOS_LOG_MAX_SIZE_MB"]) if config["AIOS_LOG_MAX_SIZE_MB"] != "0" else 0
    max_rotations = int(config["AIOS_LOG_MAX_ROTATIONS"])

    if max_size_mb:
        rotate_large(log_dir, max_size_mb * 1024 * 1024, max_rotations)
    if max_days:
        prune_old(log_dir, max_days)

    max_handoffs_mb = int(config["AIOS_HANDOFFS_MAX_SIZE_MB"]) if config["AIOS_HANDOFFS_MAX_SIZE_MB"] != "0" else 0
    if max_handoffs_mb:
        handoffs_dir = HORIZON_ROOT / "handoffs"
        prune_handoffs(handoffs_dir, max_handoffs_mb * 1024 * 1024)

    print("[OK] Log maintenance complete.")


if __name__ == "__main__":
    main()
