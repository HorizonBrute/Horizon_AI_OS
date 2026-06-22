#!/usr/bin/env python3
"""
AIOS filesystem integrity monitor.

Watches $HORIZON_SYSTEM for unexpected file changes (create/modify/delete/move).
Logs events as JSON lines to $HORIZON_SYSTEM/logs/aios_monitor/.

Run as the administrative context. The log directory must not be writable by
brain accounts — enforce with OS filesystem permissions.

Usage:
    python monitor_aios.py [--watch PATH ...] [--log-dir PATH]

Defaults:
    --watch     $HORIZON_SYSTEM (this script's parent directory)
    --log-dir   $HORIZON_SYSTEM/logs/aios_monitor/

Additional watch paths (Docker, usrbin, project dirs):
    Repeat --watch for each path, or set AIOS_MONITOR_PATHS (OS path-separator-delimited).

Service installation:
    See $HORIZON_DOCS/security/audit_logging.md
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    sys.exit("watchdog not installed. Run: pip install watchdog")

SCRIPT_DIR     = Path(__file__).resolve().parent   # horizon_system/sbin/
HORIZON_SYSTEM = SCRIPT_DIR.parent                 # horizon_system/
HORIZON_ROOT   = HORIZON_SYSTEM.parent             # repo root
DEFAULT_LOG_DIR = HORIZON_SYSTEM / "logs" / "aios_monitor"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(log_path: Path, record: dict):
    with log_path.open("a", buffering=1) as f:
        f.write(json.dumps(record) + "\n")


class _Handler(FileSystemEventHandler):
    def __init__(self, log_path: Path):
        self._log = log_path.open("a", buffering=1)

    def __del__(self):
        try:
            if self._log and not self._log.closed:
                self._log.close()
        except Exception:  # noqa: BLE001
            pass

    def _write(self, event_type: str, src: str, dest: str = None):
        record = {"ts": _now(), "event": event_type, "src": src}
        if dest:
            record["dest"] = dest
        self._log.write(json.dumps(record) + "\n")

    def on_created(self, event):  self._write("created", event.src_path)
    def on_deleted(self, event):  self._write("deleted", event.src_path)
    def on_moved(self, event):    self._write("moved", event.src_path, event.dest_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._write("modified", event.src_path)


def main():
    parser = argparse.ArgumentParser(description="AIOS filesystem integrity monitor")
    parser.add_argument("--watch", action="append", metavar="PATH",
                        help="Path to watch (repeatable). Default: HORIZON_SYSTEM")
    parser.add_argument("--log-dir", metavar="PATH",
                        help=f"Log directory. Default: {DEFAULT_LOG_DIR}")
    args = parser.parse_args()

    watch_paths = args.watch or []
    if not watch_paths:
        env_extra = os.environ.get("AIOS_MONITOR_PATHS", "")
        watch_paths = [p for p in env_extra.split(os.pathsep) if p] if env_extra else [str(HORIZON_SYSTEM)]

    log_dir = Path(args.log_dir or os.environ.get("AIOS_MONITOR_LOG_DIR") or DEFAULT_LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"monitor_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"

    _append(log_file, {"ts": _now(), "event": "monitor_start", "watching": watch_paths})

    handler = _Handler(log_file)
    observer = Observer()
    for path in watch_paths:
        observer.schedule(handler, path, recursive=True)
        print(f"Watching : {path}")
    print(f"Log      : {log_file}")
    print("Press Ctrl+C to stop.")

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

    _append(log_file, {"ts": _now(), "event": "monitor_stop"})


if __name__ == "__main__":
    main()
