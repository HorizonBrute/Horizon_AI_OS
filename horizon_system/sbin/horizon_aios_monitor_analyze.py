#!/usr/bin/env python3
"""
AIOS monitor log analyzer.

Reads horizon_aios_monitor.py JSON-line logs, checks for file change events and
monitor uptime gaps, and writes a summary to $HORIZON_SYSTEM/logs/horizon_aios_security.log.
Optionally emits alerts to the OS system log (syslog on Linux; Windows Event
Log if pywin32 is available).

Run as the administrative context on a schedule (cron / Task Scheduler).
See $HORIZON_DOCS/security/audit_logging.md for scheduling instructions.

Usage:
    python horizon_aios_monitor_analyze.py [--days N] [--log-dir PATH]
                                   [--security-log PATH] [--syslog]
"""

import json
import logging
import logging.handlers
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR     = Path(__file__).resolve().parent   # horizon_system/sbin/
HORIZON_SYSTEM = SCRIPT_DIR.parent                 # horizon_system/
HORIZON_ROOT   = HORIZON_SYSTEM.parent             # repo root
DEFAULT_MONITOR_LOG_DIR = HORIZON_SYSTEM / "logs" / "horizon_aios_monitor"
DEFAULT_SECURITY_LOG    = HORIZON_SYSTEM / "logs" / "horizon_aios_security.log"

FILE_EVENTS = {"created", "modified", "deleted", "moved"}


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _load_day(log_dir: Path, date: datetime) -> list[dict]:
    path = log_dir / f"monitor_{date.strftime('%Y%m%d')}.log"
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _analyze(records: list[dict], date_label: str) -> dict:
    """Return analysis dict for one day's records."""
    starts, stops = [], []
    file_events = []

    for r in records:
        ev = r.get("event", "")
        if ev == "monitor_start":
            starts.append(r["ts"])
        elif ev == "monitor_stop":
            stops.append(r["ts"])
        elif ev in FILE_EVENTS:
            file_events.append(r)

    return {
        "date": date_label,
        "starts": starts,
        "stops": stops,
        "file_events": file_events,
        "no_data": not records,
    }


def _write_security_log(path: Path, lines: list[str]):
    with path.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def _os_log(message: str, use_syslog: bool):
    """Emit to OS system log if available."""
    if not use_syslog:
        return
    logger = logging.getLogger("horizon_aios.monitor")
    if not logger.handlers:
        # Linux syslog — no extra deps
        try:
            h = logging.handlers.SysLogHandler(address="/dev/log")
            logger.addHandler(h)
        except (FileNotFoundError, OSError):
            pass
        # Windows Event Log — requires pywin32
        try:
            import win32evtlogutil  # noqa: F401
            h = logging.handlers.NTEventLogHandler("Horizon.AIOS Monitor")
            logger.addHandler(h)
        except ImportError:
            pass
    if logger.handlers:
        logger.warning(message)


def main():
    parser = argparse.ArgumentParser(description="AIOS monitor log analyzer")
    parser.add_argument("--days", type=int, default=2, metavar="N",
                        help="Number of days of logs to analyze (default: 2)")
    parser.add_argument("--log-dir", metavar="PATH",
                        help=f"Monitor log directory. Default: {DEFAULT_MONITOR_LOG_DIR}")
    parser.add_argument("--security-log", metavar="PATH",
                        help=f"Security log output. Default: {DEFAULT_SECURITY_LOG}")
    parser.add_argument("--syslog", action="store_true",
                        help="Also emit alerts to OS system log (syslog / Windows Event Log)")
    args = parser.parse_args()

    log_dir      = Path(args.log_dir or os.environ.get("AIOS_MONITOR_LOG_DIR") or DEFAULT_MONITOR_LOG_DIR)
    security_log = Path(args.security_log or DEFAULT_SECURITY_LOG)
    security_log.parent.mkdir(parents=True, exist_ok=True)

    now   = datetime.now(timezone.utc)
    days  = [now - timedelta(days=i) for i in range(args.days - 1, -1, -1)]
    lines = [f"", f"=== AIOS SECURITY ANALYSIS — {_ts()} ==="]

    total_file_events = 0
    alert = False

    for day in days:
        label   = day.strftime("%Y-%m-%d")
        records = _load_day(log_dir, day)
        result  = _analyze(records, label)

        lines.append(f"\n--- {label} ---")

        if result["no_data"]:
            lines.append(f"  COVERAGE GAP: no monitor log found for {label}")
            alert = True
        else:
            # Uptime
            if result["starts"]:
                for ts in result["starts"]:
                    lines.append(f"  monitor_start : {ts}")
            else:
                lines.append(f"  COVERAGE GAP  : no monitor_start recorded for {label}")
                alert = True

            if result["stops"]:
                for ts in result["stops"]:
                    lines.append(f"  monitor_stop  : {ts}")
            else:
                lines.append(f"  monitor_stop  : (not yet stopped — may still be running)")

            # File events
            n = len(result["file_events"])
            total_file_events += n
            if n:
                lines.append(f"  ALERT: {n} file change event(s) detected:")
                for ev in result["file_events"]:
                    dest = f" → {ev['dest']}" if "dest" in ev else ""
                    lines.append(f"    [{ev['ts']}] {ev['event']}: {ev['src']}{dest}")
                alert = True
            else:
                lines.append(f"  No file change events.")

    lines.append(f"\n  Total file change events across {args.days} day(s): {total_file_events}")
    lines.append(f"  Alert status: {'ALERT' if alert else 'OK'}")
    lines.append(f"=== END ===\n")

    _write_security_log(security_log, lines)
    print(f"Security log: {security_log}")
    print(f"Alert: {'YES' if alert else 'no'}")

    if alert and args.syslog:
        msg = f"AIOS monitor alert: {total_file_events} file change event(s) in $HORIZON_SYSTEM. See {security_log}"
        _os_log(msg, use_syslog=True)


if __name__ == "__main__":
    main()
