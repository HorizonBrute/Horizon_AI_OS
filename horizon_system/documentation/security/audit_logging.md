# Audit Logging — AIOS Filesystem Monitor

The AIOS filesystem monitor (`$HORIZON_SYSTEM/sbin/horizon_aios_monitor.py`) watches the
AIOS **system directories** for unexpected file changes and logs events as JSON
lines. It runs as the administrative context; brain accounts must not have write
access to the log directory (enforced by `horizon_aios_harden.py`).

---

## Default State

**AIOS ships with write logging to all AIOS system directories enabled by default.** The bootstrap registers the monitor as a scheduled task (Windows) or systemd service (Linux/macOS), so logging is active from first boot after setup — no extra configuration step required.

This is intentional: some basic logging on implementation is better than none. Write detection covers the primary integrity surface (unauthorized changes to the AIOS system layer) without making any presumptions about the broader environment. Deeper logging — read detection, brain-internal activity, project-folder access — requires OS-level audit infrastructure that varies by environment and is left to the operator (see *Log Analysis and Alerting* below).

**The monitor script is deliberately simple and easy to extend.** If the default watched paths or log destination do not fit your environment, editing `aios_monitor.conf` or the script itself is straightforward. The configuration file, CLI flags, and environment variables cover the most common extension patterns without touching the script at all.

**Dependency:** Logging is only active if the scheduled task or service was successfully registered during bootstrap. Verify with:

```powershell
# Windows
Get-ScheduledTask -TaskName "AIOSMonitor"
```
```sh
# Linux
systemctl status aios-monitor
```

If the task is absent or in an error state, logging is not running regardless of what the script can do. Re-register using the instructions in *Running as a Service* below.

---

## Quick Start

```sh
pip install watchdog
python $HORIZON_SYSTEM/sbin/horizon_aios_monitor.py
```

Logs write to `$HORIZON_SYSTEM/logs/horizon_aios_monitor/monitor_YYYYMMDD.log`.

---

## What Is Watched

By default the monitor watches the AIOS system directories — the OS layer's
integrity surface:

| Path | Recursive | Why |
|---|---|---|
| `$HORIZON_SYSTEM` | yes | The AIOS layer (`bin`, `sbin`, `skills_bin`, `skills_sbin`, `ai_os_etc`, …) |
| `$HORIZON_USRBIN` | yes | Shared tool repository + machine-local user skills |
| `$HORIZON_ROOT/.claude` | yes | OS-layer harness config |
| `$HORIZON_ROOT` | no | Top-level OS files (`agents.md`, `CLAUDE.md`, `.gitignore`) and structural changes — does **not** descend into `Projects/`, `brains/`, etc. |
| `$HORIZON_ROOT/brains/` | no | The brains root is functionally a system folder; structural changes (a brain folder created/deleted/renamed) are tracked |

The monitor's own log directory is always excluded (it sits inside the watched
tree; logging its own writes would loop).

**Brain internals are out of scope by default.** AIOS makes no presumption about
what happens *inside* a brain — the memory system, file layout, and what counts
as a problem there are the operator's domain. So brain home *contents* are not
watched unless you opt in with `--brain-dirs` (or `brain_dirs = true` in the
config), which escalates the brains-root watch to recursive.

**Excluded by design:** `$HORIZON_PROJECTS` (the user's personal workspace) and
`handoffs/` / `objectives/` (ephemeral session output) — they are not OS-layer
state. Add any of them explicitly if you want them logged (see below).

---

## Extending to Additional Paths

Three additive mechanisms, in precedence order (highest first):

1. **CLI** — repeat `--watch` (recursive), toggle brains with `--brain-dirs` /
   `--no-brains-root`:
   ```sh
   python horizon_aios_monitor.py --watch $HORIZON_PROJECTS/my-project --brain-dirs
   ```
2. **Environment** — `AIOS_MONITOR_PATHS` (OS path separator), plus
   `AIOS_MONITOR_BRAIN_DIRS=1` / `AIOS_MONITOR_BRAINS_ROOT=0`.
3. **Config file** — see below.

---

## Configuration File

`$HORIZON_SYSTEM/sbin/horizon_aios_monitor.py` reads `$HORIZON_ETC/aios_monitor.conf`
if present (override with `--config` or `AIOS_MONITOR_CONFIG`). Copy the
template to create it:

```sh
cp $HORIZON_SYSTEM/templates/aios_monitor.conf.template \
   $HORIZON_ETC/aios_monitor.conf
```

It is machine-local and gitignored (like `aios_local.conf`). Directives:

```ini
watch = /abs/path          # extra path to watch recursively (repeatable)
/abs/path                  # bare line — shorthand for "watch ="
brain_dirs = true          # also watch into brain home dirs (recursive)
watch_brains_root = false  # disable the default brains-root watch
log_dir = /abs/path        # override the log directory
```

---

## Log Format

Each line is a JSON object. Every record carries provenance — `source` and the
`horizon_root` it came from — so an aggregator can attribute events to a
specific AIOS install:

```json
{"ts": "2026-06-20T14:32:01.123456+00:00", "source": "Horizon.AIOS", "horizon_root": "C:\\devroot", "event": "monitor_start", "watching": [{"path": "C:\\devroot\\horizon_system", "recursive": true}], "brain_dirs": false, "config": null}
{"ts": "2026-06-20T14:32:03.123456+00:00", "source": "Horizon.AIOS", "horizon_root": "C:\\devroot", "event": "modified", "src": "C:\\devroot\\horizon_system\\bin\\foo.py"}
{"ts": "2026-06-20T14:32:05.654321+00:00", "source": "Horizon.AIOS", "horizon_root": "C:\\devroot", "event": "moved", "src": "/old", "dest": "/new"}
```

Events: `created`, `modified`, `deleted`, `moved`, plus lifecycle
`monitor_start` / `monitor_stop`.

**Note:** This monitor detects file changes (writes). Read detection requires
OS-level audit (Linux: `auditd` with `IN_ACCESS`; Windows: Security Audit /
Object Access). Enabling OS audit is optional and outside the AIOS scope.

---

## Consuming the Logs (Administrators / SIEM)

**Where the logs live.** Events are written to **disk** as newline-delimited
JSON (JSON Lines) — one file per UTC day:

```
$HORIZON_SYSTEM/logs/horizon_aios_monitor/monitor_YYYYMMDD.log
```

Each line is a complete JSON object (see *Log Format*). There is no database
and no network listener — the monitor only appends to these files. Every record
is self-describing: `source` is always `"Horizon.AIOS"` and `horizon_root`
identifies the install, so logs from multiple machines or installs can be
merged and still attributed unambiguously.

**Getting them into your logging pipeline.** Because the format is plain
JSON-lines on disk, any standard log shipper can tail the directory and forward
to your SIEM with no transformation:

| Tool | Pointer |
|---|---|
| Elastic **Filebeat** / **Winlogbeat** | `filebeat.inputs` → `type: filestream`, `paths: [".../logs/horizon_aios_monitor/monitor_*.log"]`, `parsers: [{ndjson: {}}]` |
| **Fluent Bit** / Fluentd | `[INPUT] tail` on `monitor_*.log`, `[FILTER] parser` = `json` |
| **NXLog** (common on Windows) | `im_file` reading the directory, `xm_json` to parse |
| **Vector** | `sources.aios.type = "file"`, `include = [".../monitor_*.log"]`, decode as JSON |
| **Splunk** Universal Forwarder | monitor stanza on the directory, `sourcetype=_json` |

Point any of them at `$HORIZON_SYSTEM/logs/horizon_aios_monitor/`. Filter on
`source="Horizon.AIOS"` to isolate AIOS integrity events in your SIEM.

**Pushing to the OS event log.** If you would rather consume events through the
native OS log (Windows Event Log / Linux syslog) than tail files, run the
analyzer with `--syslog` (see below) — it emits summaries to the OS log, which
your existing collector already ingests.

**Retention.** `horizon_aios_maintain_logs.py` prunes/rotates these files
(`AIOS_LOG_MAX_DAYS`, `AIOS_LOG_MAX_SIZE_MB`, `AIOS_LOG_MAX_ROTATIONS` in
`aios_local.conf`). If your SIEM is the system of record, ship before pruning.

---

## Running as a Service

### Windows — NSSM (recommended)

1. Install [NSSM](https://nssm.cc): `winget install nssm` or download manually.
2. Register the service:

```powershell
nssm install AIOSMonitor "<python-dir>\pythonw.exe" "$HORIZON_SYSTEM\sbin\horizon_aios_monitor.py"
nssm set AIOSMonitor AppDirectory $HORIZON_SYSTEM\sbin
nssm set AIOSMonitor ObjectName LocalSystem
nssm start AIOSMonitor
```

3. Log directory access is already correct under the harden posture: SYSTEM has
   FullControl on `$HORIZON_SYSTEM\logs` and the `horizon_humans` group is denied
   write there, so a SYSTEM-run monitor can write while human/brain accounts cannot.
   No extra `icacls` step is needed. (This is why the service runs as SYSTEM rather
   than a human account, which the humans-write DENY would block.)

### Windows — Task Scheduler (no extra dependency)

```powershell
$action = New-ScheduledTaskAction -Execute "<python-dir>\pythonw.exe" `
    -Argument "`"$HORIZON_SYSTEM\sbin\horizon_aios_monitor.py`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
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
ExecStart=python $HORIZON_SYSTEM/sbin/horizon_aios_monitor.py
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
ENV AIOS_MONITOR_LOG_DIR=/logs/horizon_aios_monitor
```

```yaml
# docker-compose.yml excerpt
volumes:
  - ./horizon_system:/horizon_system:ro
  - ./logs/horizon_aios_monitor:/logs/horizon_aios_monitor
```

---

---

## Log Analysis and Alerting

`$HORIZON_SYSTEM/sbin/horizon_aios_monitor_analyze.py` reads monitor logs, checks for
file change events and uptime gaps, and writes a human-readable summary to
`$HORIZON_SYSTEM/logs/horizon_aios_security.log`. Run it periodically from the administrative
context.

```sh
python $HORIZON_SYSTEM/sbin/horizon_aios_monitor_analyze.py          # last 2 days
python $HORIZON_SYSTEM/sbin/horizon_aios_monitor_analyze.py --days 7 # last 7 days
python $HORIZON_SYSTEM/sbin/horizon_aios_monitor_analyze.py --syslog  # also emit to OS log
```

The security log records:
- `monitor_start` / `monitor_stop` times per day (gaps indicate unmonitored periods)
- Any file change events (creates/modifies/deletes/moves) detected in watched paths
- Alert status: `OK` or `ALERT`

**Scheduling the analyzer (run it like a cron job):**

Windows Task Scheduler:
```powershell
$action = New-ScheduledTaskAction -Execute "<python-dir>\pythonw.exe" `
    -Argument "`"$HORIZON_SYSTEM\sbin\horizon_aios_monitor_analyze.py`""
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00"
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
Register-ScheduledTask -TaskName "AIOSMonitorAnalyzer" -Action $action `
    -Trigger $trigger -Principal $principal
```

Linux cron (daily at 6am):
```sh
0 6 * * * /usr/bin/python3 $HORIZON_SYSTEM/sbin/horizon_aios_monitor_analyze.py --syslog
```

**Note on read detection:** The monitor and analyzer detect file *changes*
(writes/creates/deletes). Detecting unauthorized *reads* requires OS-level
audit (`auditd` with `IN_ACCESS` on Linux; Windows Security Audit / Object
Access Auditing). Enabling OS audit is optional, outside the AIOS scope, and
documented in your OS vendor's security hardening guides.

---

## Logging Coverage and Existing Infrastructure

The built-in monitor covers write detection on AIOS system directories. Everything it does not cover — read detection, brain-internal activity, network access, process-level audit — is already handled by standard infrastructure-level logging tools: `auditd`, Windows Security Audit, EDR agents, network flow collectors. Those tools are not absent; they are already running in any environment with a baseline security posture.

What they need to cover the AIOS is the same thing they need for any new application onboarded into a secure environment: **an understanding of which files and directories are significant.** For AIOS, that is:

| Path | Why it matters |
|---|---|
| `$HORIZON_SYSTEM/` | The AIOS system layer — changes here are integrity events |
| `$HORIZON_SYSTEM/sbin/` and `skills_sbin/` | Owner-only privileged tooling |
| `$HORIZON_SYSTEM/logs/` | The audit log directory itself |
| `$HORIZON_ROOT/.claude/` | OS-layer harness configuration |
| `$HORIZON_ROOT/brains/` | Brain workspace root — structural changes (account created, deleted, renamed) |
| `brains/<name>/` | Individual brain workspace — if brain-level audit is required |

Point your existing tooling at these paths with the same rules you use for any sensitive application directory. No AIOS-specific integration is needed beyond that. The onboarding effort is the same as bringing any new service into your logging pipeline.

---

## Modifying or Disabling the Monitor

To extend the default watched paths, log destination, or behavior, edit `$HORIZON_ETC/aios_monitor.conf` (see *Configuration File* above) or pass CLI flags. No script changes are needed for common customizations.

To disable monitoring entirely: remove or disable the scheduled task / systemd service. The scripts will not run on their own.

```powershell
# Windows — disable
Unregister-ScheduledTask -TaskName "AIOSMonitor" -Confirm:$false
Unregister-ScheduledTask -TaskName "AIOSMonitorAnalyzer" -Confirm:$false
```
```sh
# Linux — disable
sudo systemctl disable --now aios-monitor
```
