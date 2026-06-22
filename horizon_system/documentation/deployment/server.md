# Horizon AIOS — Server / Headless Deployment

The server deployment runs the AIOS on a remote or always-on machine without a desktop session. Brains run as OS user accounts, scheduled via cron / systemd (Linux) or Task Scheduler (Windows). Access is via SSH. The audit log is the primary operational interface — there is no UI, no sounds, no statusline.

**Status:** Not yet end-to-end verified. See `tested_configurations.md`.

---

## What "Server" Means Here

- No interactive desktop session. The harness (Claude Code CLI) is invoked over SSH or by a daemon.
- Brains run unattended as scheduled tasks or services under their own OS user accounts.
- No sound device — hook commands that play audio will fail or silently no-op. Disable them or suppress errors.
- No statusline — harness UI features (context bar, git display) do not render in a non-interactive session.
- The audit log (`$HORIZON_LOGS/aios_monitor/`) is the operational view: tail it to observe what agents are doing.

---

## Prerequisites

- Linux (Ubuntu 22.04+ recommended) or Windows Server.
- Git, Python 3.8+, your AI harness CLI installed.
- SSH server configured and accessible.
- Administrator / sudo access for brain provisioning.
- Optional: systemd (Linux) or Task Scheduler (Windows) for daemon-mode brains.

---

## Setup

Same bootstrap as desktop — run over SSH:

```bash
git clone <your-aios-repo-url> /opt/aios   # or your preferred path

# Linux / macOS
bash /opt/aios/horizon_system/sbin/bootstrap.sh

# Windows Server (PowerShell, as admin)
& C:\aios\horizon_system\sbin\bootstrap.ps1
```

After bootstrap, add the env vars to the system profile so they are available to all users and cron jobs:

```bash
# Linux: add to /etc/environment or /etc/profile.d/aios.sh
export HORIZON_ROOT=/opt/aios
export HORIZON_SYSTEM=$HORIZON_ROOT/horizon_system
export HORIZON_BIN=$HORIZON_SYSTEM/bin
export HORIZON_ETC=$HORIZON_SYSTEM/ai_os_etc
export HORIZON_DOCS=$HORIZON_SYSTEM/documentation
export HORIZON_SOUNDS=$HORIZON_SYSTEM/sounds
export HORIZON_LOGS=$HORIZON_SYSTEM/logs
```

> **Note:** These explicit system-profile exports are a deliberate simplification for a server pinned to a single AIOS (so the vars are available to all users and cron jobs). On a desktop or any machine that uses the AIOS switcher, prefer sourcing `~/.horizon/active_env.sh` instead (run `aios_switch.py init` once); `aios switch <name>` then repoints every shell without editing the system profile. See `system/aios_switching.md`.

### Disabling sounds on server

In `~/.claude/settings.json`, set hook commands to no-ops or remove the `Stop`, `PermissionRequest`, and `StopFailure` sound hooks entirely. The log hook (writing to `$HORIZON_LOGS`) should remain active.

---

## Provisioning Brains

Same as desktop — run as root/admin:

```bash
sudo python $HORIZON_SYSTEM/sbin/create_brain.py brain-name
```

This creates the OS user account, directory, and permissions. On server, brains run as daemon processes rather than interactive sessions.

---

## Running Brains as Daemons

### Linux — systemd service unit

Create `/etc/systemd/system/brain-BRAINNAME.service`:

```ini
[Unit]
Description=Horizon AIOS Brain — BRAINNAME
After=network.target

[Service]
Type=simple
User=BRAINNAME
Group=BRAINNAME
WorkingDirectory=/opt/aios/brains/BRAINNAME
Environment=HORIZON_ROOT=/opt/aios
Environment=HORIZON_SYSTEM=/opt/aios/horizon_system
Environment=ANTHROPIC_API_KEY=<inject from OS credential store or wrapper script>
ExecStart=/usr/local/bin/claude --dangerously-skip-permissions
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
systemctl daemon-reload
systemctl enable brain-BRAINNAME
systemctl start brain-BRAINNAME
```

### Windows Server — Task Scheduler (sketch)

Create a scheduled task that runs as the brain's OS user account:
- **Action:** `claude.exe --dangerously-skip-permissions`
- **Run as:** brain OS user account
- **Working directory:** `C:\aios\brains\BRAINNAME`
- **Trigger:** At startup, or on schedule

Use `schtasks /create` or the Task Scheduler GUI. Store the brain's API key in Windows Credential Manager and inject it via a wrapper script.

---

## Log Monitoring as the Operational Interface

The audit log is the primary way to observe what a brain is doing on a server:

```bash
# Watch live monitor events (file access, writes, creates)
tail -f $HORIZON_LOGS/aios_monitor/*.jsonl

# Watch hook events
tail -f $HORIZON_LOGS/hooks/*.log

# Watch brain-specific output
tail -f $HORIZON_LOGS/brains/BRAINNAME/*.log
```

Pipe to `jq` for structured queries:
```bash
tail -f $HORIZON_LOGS/aios_monitor/*.jsonl | jq 'select(.type == "created")'
```

Ensure `monitor_aios.py` is running as the administrative context (not as a brain user):
```bash
python $HORIZON_SYSTEM/sbin/monitor_aios.py &
```

---

## Multi-Operator Server Pattern

The AIOS model assumes one human operator per AIOS owner account. The owner's `~/.claude/settings.json` (global settings, hooks, statusLine) is per OS home directory. If two humans — for example, a primary admin and a co-worker — need to use the same AIOS installation on a shared server, follow this pattern:

**Do not share an OS account.** Each human operator needs their own OS user account on the server.

**Each person runs bootstrap under their own account:**

```bash
# As operator-1 (with sudo)
sudo bash /opt/aios/horizon_system/sbin/bootstrap.sh

# As operator-2 (with sudo, in a separate SSH session)
sudo bash /opt/aios/horizon_system/sbin/bootstrap.sh
```

Bootstrap installs each person's personal `~/.claude/settings.json` from the shared AIOS template. The devroot `.claude/settings.json` (permissions only, committed to the repo) is shared across all operators — that is intentional. Per-operator state (hooks, statusLine, global settings) lives in each account's own `~/.claude/`.

**Brains are not the right mechanism for human co-workers.** Brains are isolated AI agent accounts. Human operators need their own OS accounts with their own Claude Code sessions, their own SSH keys, and their own shell environments.

**`$HORIZON_ROOT` repository — two valid models:**

- **Shared storage:** `$HORIZON_ROOT` is mounted at the same path for all operators. Each operator's `~/.claude/` is their own (different home directory), so settings stay separate. All operators read from the same committed `.claude/settings.json` for devroot-scoped permissions.
- **Separate clones:** Each operator clones the AIOS repo to their own home directory or a path they control. The devroot `.claude/settings.json` is replicated from the repo in each clone. Updates require each operator to pull independently (or the sync schedule handles it).

Either model works. Shared storage is simpler for keeping all operators on the same AIOS version; separate clones give each operator independent upgrade control.

---

## Server vs. Desktop

| Concern | Server | Desktop |
|---|---|---|
| Session type | Headless / SSH | Interactive desktop app |
| Brains | Daemons (systemd / Task Scheduler) | OS users, launched interactively |
| Sounds | Not available — disable hooks | Native, first-class |
| Statusline | Not rendered | Renders in harness UI |
| Audit log | Primary operational view | Secondary (UI is primary) |
| Setup complexity | Bootstrap + system profile + daemon config | Bootstrap only |
| Always-on | Natural (server stays up) | Requires leaving machine on |
