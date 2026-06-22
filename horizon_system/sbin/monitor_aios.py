#!/usr/bin/env python3
"""
AIOS filesystem integrity monitor.

Watches the AIOS layer for unexpected file changes (create/modify/delete/move)
and logs events as JSON lines to $HORIZON_SYSTEM/logs/aios_monitor/.

By default it watches the AIOS *system directories* — the OS layer's integrity
surface:
  - $HORIZON_SYSTEM            (recursive) — the AIOS layer (bin/sbin/skills/etc)
  - $HORIZON_USRBIN            (recursive) — shared tool repo + machine-local
                               user skills
  - $HORIZON_ROOT/.claude      (recursive) — OS-layer harness config
  - $HORIZON_ROOT              (non-recursive) — top-level OS files
                               (agents.md, CLAUDE.md, .gitignore) and structural
                               changes; does NOT descend into Projects/brains/etc
  - $HORIZON_ROOT/brains/      (non-recursive) — the brains root is functionally
                               a system folder, so structural changes (a brain
                               folder created/deleted/renamed) are tracked. AIOS
                               makes NO presumption about what happens *inside* a
                               brain — that is the operator's domain — so brain
                               home contents are NOT watched unless asked.

Excluded by design: $HORIZON_PROJECTS (the user's personal workspace) and
handoffs/ & objectives/ (ephemeral session output) — not OS-layer state. Add
any of them via --watch or the config file if you want them logged.

Run as the administrative context. The log directory must not be writable by
brain accounts (enforced by harden_aios.py).

Usage:
    python monitor_aios.py [--watch PATH ...] [--brain-dirs] [--no-brains-root]
                           [--config PATH] [--log-dir PATH]

Resolution precedence (highest first): CLI flags > environment > config file >
built-in defaults. --watch / config paths are ADDITIVE to the defaults.

  --brain-dirs       Also watch INTO each brain home directory (recursive),
                     not just the brains root. Opts in to logging brain
                     internals. (env: AIOS_MONITOR_BRAIN_DIRS=1)
  --no-brains-root   Do not watch the brains root at all.
  --config PATH      Config file. Default: $HORIZON_ETC/aios_monitor.conf
                     (env: AIOS_MONITOR_CONFIG)
  --watch PATH       Extra path to watch, recursively (repeatable).
                     (env: AIOS_MONITOR_PATHS, OS path-separator-delimited)
  --log-dir PATH     Log directory. Default: $HORIZON_SYSTEM/logs/aios_monitor/
                     (env: AIOS_MONITOR_LOG_DIR)

Service installation and log consumption (SIEM/forwarders):
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
HORIZON_ETC    = HORIZON_SYSTEM / "ai_os_etc"
HORIZON_BRAINS = HORIZON_ROOT / "brains"
DEFAULT_LOG_DIR = HORIZON_SYSTEM / "logs" / "aios_monitor"
DEFAULT_CONFIG  = HORIZON_ETC / "aios_monitor.conf"

# Provenance stamped on every record so consumers can unambiguously attribute
# events to this AIOS install (see audit_logging.md → Consuming the logs).
SOURCE       = "horizon-aios"

_TRUE = {"1", "true", "yes", "on"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(event_type: str, **fields) -> dict:
    """Build a log record with provenance fields first."""
    rec = {"ts": _now(), "source": SOURCE, "horizon_root": str(HORIZON_ROOT),
           "event": event_type}
    rec.update(fields)
    return rec


def _append(log_path: Path, record: dict):
    with log_path.open("a", buffering=1) as f:
        f.write(json.dumps(record) + "\n")


class _Handler(FileSystemEventHandler):
    def __init__(self, log_path: Path, ignore_dir: Path):
        self._log = log_path.open("a", buffering=1)
        # Ignore events under our own log directory — it sits inside the watched
        # tree, so logging our own writes would create a feedback loop.
        self._ignore = os.path.abspath(str(ignore_dir))

    def __del__(self):
        try:
            if self._log and not self._log.closed:
                self._log.close()
        except Exception:  # noqa: BLE001
            pass

    def _ignored(self, path: str) -> bool:
        try:
            return os.path.commonpath([self._ignore, os.path.abspath(path)]) == self._ignore
        except ValueError:  # different drive / unrelated path
            return False

    def __del__(self):
        try:
            if self._log and not self._log.closed:
                self._log.close()
        except Exception:  # noqa: BLE001
            pass

    def _write(self, event_type: str, src: str, dest: str = None):
        if self._ignored(src):
            return
        record = _record(event_type, src=src)
        if dest:
            record["dest"] = dest
        self._log.write(json.dumps(record) + "\n")

    def on_created(self, event):  self._write("created", event.src_path)
    def on_deleted(self, event):  self._write("deleted", event.src_path)
    def on_moved(self, event):    self._write("moved", event.src_path, event.dest_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._write("modified", event.src_path)


def _read_config(path: Path):
    """
    Parse the monitor config file. Format (one directive per line; '#' comments):
        watch = /abs/path          # extra path to watch recursively (repeatable)
        /abs/path                  # bare line is shorthand for 'watch ='
        brain_dirs = true          # watch into brain home dirs (recursive)
        watch_brains_root = false  # disable the default brains-root watch
        log_dir = /abs/path        # override the log directory
    Returns a dict; booleans are None when unset so callers can apply precedence.
    """
    cfg = {"watch": [], "brain_dirs": None, "watch_brains_root": None,
           "log_dir": None}
    if not path or not Path(path).is_file():
        return cfg
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key, val = key.strip().lower(), val.strip()
            else:
                key, val = "watch", line
            if key == "watch" and val:
                cfg["watch"].append(val)
            elif key in ("brain_dirs", "watch_brains_root"):
                cfg[key] = val.lower() in _TRUE
            elif key == "log_dir" and val:
                cfg["log_dir"] = val
    return cfg


def _env_bool(name):
    val = os.environ.get(name)
    if val is None:
        return None
    return val.lower() in _TRUE


def _system_specs():
    """
    The AIOS system directories watched by default — the OS layer's integrity
    surface. Each entry is (path, recursive); non-existent paths are skipped at
    schedule time. The brains root is handled separately (it is toggleable).
    Excluded by design: $HORIZON_PROJECTS, handoffs/, objectives/ (not OS state)
    and brain home *contents* (operator's domain; opt in via --brain-dirs).
    """
    return [
        (HORIZON_SYSTEM,            True),   # AIOS layer (bin/sbin/skills/etc)
        (HORIZON_ROOT / "usrbin",   True),   # shared tools + machine-local user skills
        (HORIZON_ROOT / ".claude",  True),   # OS-layer harness config
        (HORIZON_ROOT,              False),  # top-level OS files (agents.md, CLAUDE.md, …)
    ]


def main():
    parser = argparse.ArgumentParser(description="AIOS filesystem integrity monitor")
    parser.add_argument("--watch", action="append", metavar="PATH",
                        help="Extra path to watch recursively (repeatable, additive).")
    parser.add_argument("--brain-dirs", action="store_true", default=False,
                        help="Also watch into brain home directories (recursive).")
    parser.add_argument("--no-brains-root", action="store_true", default=False,
                        help="Do not watch the brains root directory.")
    parser.add_argument("--config", metavar="PATH",
                        help=f"Config file. Default: {DEFAULT_CONFIG}")
    parser.add_argument("--log-dir", metavar="PATH",
                        help=f"Log directory. Default: {DEFAULT_LOG_DIR}")
    args = parser.parse_args()

    config_path = Path(args.config or os.environ.get("AIOS_MONITOR_CONFIG")
                       or DEFAULT_CONFIG)
    cfg = _read_config(config_path)

    # Resolve toggles: CLI > env > config > default.
    brain_dirs = (args.brain_dirs or _env_bool("AIOS_MONITOR_BRAIN_DIRS")
                  or cfg["brain_dirs"] or False)
    if args.no_brains_root:
        watch_brains_root = False
    else:
        env_wbr = _env_bool("AIOS_MONITOR_BRAINS_ROOT")
        watch_brains_root = next((v for v in (env_wbr, cfg["watch_brains_root"])
                                  if v is not None), True)

    # Build the watch set as {abs_path: recursive}; recursive=True wins on dupes.
    specs = {}

    def add(path, recursive):
        if not path:
            return
        key = str(Path(path))
        specs[key] = specs.get(key, False) or recursive

    # Default base watch: the AIOS system directories (the OS-layer surface).
    for path, recursive in _system_specs():
        add(path, recursive)

    # Brains root: on by default, non-recursive (structural awareness only);
    # --brain-dirs escalates to recursive (watch brain home contents).
    if watch_brains_root and HORIZON_BRAINS.is_dir():
        add(HORIZON_BRAINS, bool(brain_dirs))

    # Additive extra paths from env then CLI (both recursive).
    env_extra = os.environ.get("AIOS_MONITOR_PATHS", "")
    for p in (q for q in env_extra.split(os.pathsep) if q):
        add(p, True)
    for p in (args.watch or []):
        add(p, True)

    # Drop paths that do not exist (e.g. usrbin/.claude on a minimal install);
    # observer.schedule() raises on a missing dir. Warn so typos are visible.
    scheduled = {}
    for path, recursive in sorted(specs.items()):
        if Path(path).is_dir():
            scheduled[path] = recursive
        else:
            print(f"Skipping : {path}  (not found)")

    log_dir = Path(args.log_dir or os.environ.get("AIOS_MONITOR_LOG_DIR")
                   or cfg["log_dir"] or DEFAULT_LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"monitor_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"

    watching = [{"path": p, "recursive": r} for p, r in sorted(scheduled.items())]
    _append(log_file, _record("monitor_start", watching=watching,
                              brain_dirs=bool(brain_dirs),
                              config=str(config_path) if config_path.is_file() else None))

    handler = _Handler(log_file, log_dir)
    observer = Observer()
    for path, recursive in sorted(scheduled.items()):
        observer.schedule(handler, path, recursive=recursive)
        print(f"Watching : {path}  (recursive={recursive})")
    print(f"Log      : {log_file}")
    print(f"Source   : {SOURCE} @ {HORIZON_ROOT}")
    print("Press Ctrl+C to stop.")

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

    _append(log_file, _record("monitor_stop"))


if __name__ == "__main__":
    main()
