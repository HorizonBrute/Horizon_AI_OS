---
name: monitor
description: Start or explain the Horizon AIOS filesystem integrity monitor — watches the AIOS system directories for create/modify/delete/move events and appends them as JSON lines to the audit log. Use when the user types /monitor, asks to "start the monitor", "watch the AIOS for changes", "enable filesystem audit logging", or check what the monitor watches.
tools: Bash, Read
---

# Skill: /monitor

Start the Horizon AIOS filesystem integrity monitor (`monitor_aios.py`), which watches the AIOS system directories and appends each create/modify/delete/move event as a JSON line to a daily log in `$HORIZON_SYSTEM/logs/aios_monitor/`.

---

## When to invoke

The user types `/monitor`, or asks to "start the monitor", "watch the AIOS for changes", "enable filesystem audit logging", or asks what the monitor watches.

---

## Arguments

`/monitor [--watch PATH ...] [--brain-dirs] [--no-brains-root] [--config PATH] [--log-dir PATH]`

All optional; flags are passed straight through to the script (additive to the defaults).

---

## Step-by-step execution

### Step 1 — Check elevation

The monitor must write to the ACL-protected log directory, which brain accounts cannot. Starting the watcher requires the **administrative context** (Administrator on Windows, root on Unix). If the session is not elevated, do NOT silently start it — tell the user it must be run from an elevated terminal and stop, or offer to print the exact command for them to run there.

### Step 2 — Start the watcher

```
python "$HORIZON_SYSTEM/sbin/monitor_aios.py"
```

Append any flags the user gave. The process runs until interrupted (Ctrl+C) — it is a long-running foreground watcher. Run it in the background if the user wants the session to stay interactive, and report the log path it prints (`Log : ...`).

### Step 3 — Report

Relay the `Watching :` / `Log :` / `Source :` lines the script prints on start so the user can confirm the watch set and where events land.

---

## Notes for the executing agent

- Requires elevation to start (writes the protected audit log). `harden_aios.py` is what denies brains write access to that log dir.
- Default watch set: `$HORIZON_SYSTEM` (recursive), `$HORIZON_ROOT/usrbin` (recursive), `$HORIZON_ROOT/.claude` (recursive), `$HORIZON_ROOT` top-level (non-recursive), `$HORIZON_ROOT/memory` (non-recursive), and the brains root (non-recursive, structural only). Brain home *contents* are excluded — opt in with `--brain-dirs`.
- Resolution precedence is CLI > env > config file (`$HORIZON_ETC/aios_monitor.conf`) > built-in defaults. `--watch` and config paths are additive.
- Requires the `watchdog` package; the script exits with an install hint if it is missing.
- For service installation and log consumption see `$HORIZON_DOCS/security/audit_logging.md`. Do not reimplement the watch logic — run the script.
