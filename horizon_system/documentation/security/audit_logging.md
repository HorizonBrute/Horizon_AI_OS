# Audit Logging — AIOS Filesystem Monitor

The AIOS filesystem monitor (`$HORIZON_SYSTEM/sbin/monitor_aios.py`) watches
`$HORIZON_SYSTEM` for unexpected file changes and logs events as JSON lines.
It runs as the administrative context; brain accounts must not have write
access to the log directory.

---

## Quick Start

```sh
pip install watchdog
python $HORIZON_SYSTEM/sbin/monitor_aios.py
```

Logs write to `$HORIZON_ROOT/logs/aios_monitor/monitor_YYYYMMDD.log`.

---

## Extending to Additional Paths

Watch extra paths by repeating `--watch`:

```sh
python monitor_aios.py --watch $HORIZON_USRBIN --watch $HORIZON_PROJECTS/my-project
```

Or set `AIOS_MONITOR_PATHS` (OS path separator) in the environment and run
with no arguments.

---

## Log Format

Each line is a JSON object:

```json
{"ts": "2026-06-20T14:32:01.123456+00:00", "event": "modified", "src": "/path/to/file"}
{"ts": "2026-06-20T14:32:05.654321+00:00", "event": "moved", "src": "/old", "dest": "/new"}
```

Events: `created`, `modified`, `deleted`, `moved`.

**Note:** This monitor detects file changes (writes). Read detection requires
OS-level audit (Linux: `auditd` with `IN_ACCESS`; Windows: Security Audit /
Object Access). Enabling OS audit is optional and outside the AIOS scope.

---

## Running as a Service

### Windows — NSSM (recommended)

1. Install [NSSM](https://nssm.cc): `winget install nssm` or download manually.
2. Register the service:

```powershell
nssm install AIOSMonitor powershell -File "$HORIZON_SYSTEM\sbin\monitor_aios_runner.ps1"
nssm set AIOSMonitor AppDirectory $HORIZON_SYSTEM\sbin
nssm set AIOSMonitor ObjectName ".\<admin-account>" "<password>"
nssm start AIOSMonitor
```

3. Set log directory ownership so the service account can write but brain
   accounts cannot:

```powershell
icacls "$HORIZON_ROOT\logs\aios_monitor" /grant "<admin-account>:(OI)(CI)F" /inheritance:r
```

### Windows — Task Scheduler (no extra dependency)

```powershell
$action = New-ScheduledTaskAction -Execute "powershell" `
    -Argument "-File `"$HORIZON_SYSTEM\sbin\monitor_aios_runner.ps1`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "<admin-account>" -RunLevel Highest
Register-ScheduledTask -TaskName "AIOSMonitor" -Action $action -Trigger $trigger -Principal $principal
```

### Linux — systemd

```ini
# /etc/systemd/system/aios-monitor.service
[Unit]
Description=AIOS Filesystem Monitor
After=network.target

[Service]
Type=simple
User=<admin-account>
ExecStart=python $HORIZON_SYSTEM/sbin/monitor_aios.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```sh
sudo systemctl enable --now aios-monitor
```

### Docker

Pass the paths in as environment variables and mount the log directory:

```dockerfile
ENV AIOS_MONITOR_PATHS=/horizon_system
ENV AIOS_MONITOR_LOG_DIR=/logs/aios_monitor
```

```yaml
# docker-compose.yml excerpt
volumes:
  - ./horizon_system:/horizon_system:ro
  - ./logs/aios_monitor:/logs/aios_monitor
```

---

---

## Log Analysis and Alerting

`$HORIZON_SYSTEM/sbin/analyze_aios_monitor.py` reads monitor logs, checks for
file change events and uptime gaps, and writes a human-readable summary to
`$HORIZON_ROOT/logs/security.log`. Run it periodically from the administrative
context.

```sh
python $HORIZON_SYSTEM/sbin/analyze_aios_monitor.py          # last 2 days
python $HORIZON_SYSTEM/sbin/analyze_aios_monitor.py --days 7 # last 7 days
python $HORIZON_SYSTEM/sbin/analyze_aios_monitor.py --syslog  # also emit to OS log
```

The security log records:
- `monitor_start` / `monitor_stop` times per day (gaps indicate unmonitored periods)
- Any file change events (creates/modifies/deletes/moves) detected in watched paths
- Alert status: `OK` or `ALERT`

**Scheduling the analyzer (run it like a cron job):**

Windows Task Scheduler:
```powershell
$action = New-ScheduledTaskAction -Execute "powershell" `
    -Argument "-File `"$HORIZON_SYSTEM\sbin\analyze_aios_monitor_runner.ps1`""
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00"
$principal = New-ScheduledTaskPrincipal -UserId "<admin-account>" -RunLevel Highest
Register-ScheduledTask -TaskName "AIOSMonitorAnalyzer" -Action $action `
    -Trigger $trigger -Principal $principal
```

Linux cron (daily at 6am):
```sh
0 6 * * * /usr/bin/python3 $HORIZON_SYSTEM/sbin/analyze_aios_monitor.py --syslog
```

**Note on read detection:** The monitor and analyzer detect file *changes*
(writes/creates/deletes). Detecting unauthorized *reads* requires OS-level
audit (`auditd` with `IN_ACCESS` on Linux; Windows Security Audit / Object
Access Auditing). Enabling OS audit is optional, outside the AIOS scope, and
documented in your OS vendor's security hardening guides.

---

## Opt-Out

Do not start `monitor_aios.py`. Do not schedule `analyze_aios_monitor.py`.
No other configuration needed — neither script is auto-started by AIOS.
