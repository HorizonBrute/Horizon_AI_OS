# Horizon AIOS — Desktop Deployment

The desktop deployment is the primary and most personal Horizon AIOS model. The AIOS runs on the user's own machine, brains run as OS user accounts on the same machine, and the AI harness runs as a desktop application the user interacts with directly.

This is the "run my life / run my business" model: always-on, always local, tightly integrated with the user's day-to-day environment.

**Status:** Verified (Windows 11 + Claude Code). See `tested_configurations.md`.

---

## What "Desktop" Means Here

Desktop deployment is not just installation mode — it is a design philosophy:

- The AIOS is installed on the machine the user works on, not on a remote server they SSH into.
- The AI harness is a desktop app (e.g., Claude Code desktop for Windows/macOS) or a terminal running in the user's own session.
- Brains run as separate OS user accounts on the same machine — the user can see them in Task Manager / `ps`, monitor them in real time, and interact with them through the harness.
- The audit log is a local file the user can read in any text editor.
- Sounds, statusline, and UI hooks are first-class citizens — they fire in the user's session.

This is the opposite of an invisible cloud service. The AIOS is visible infrastructure the user owns and controls.

---

## Prerequisites

- Windows 11 (verified) or macOS / Linux (partial — see `tested_configurations.md`).
- Git installed.
- Python 3.8+ installed.
- Your AI harness installed (Claude Code desktop app, or CLI equivalent).
- Administrator / sudo access (required for brain provisioning only, not for daily use).

---

## Setup

Follow the full setup guide at `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md`.

Summary:

```bash
# Clone the AIOS repo
git clone <your-aios-repo-url> C:\devroot   # Windows example

# Run bootstrap
& C:\devroot\horizon_system\sbin\bootstrap.ps1    # Windows (PowerShell, as admin for brain steps)
# OR
bash /path/to/horizon_system/sbin/bootstrap.sh    # macOS / Linux
```

Bootstrap sets up:
- Shell / PowerShell env vars (`HORIZON_ROOT`, `HORIZON_SYSTEM`, etc.)
- `~/.claude/CLAUDE.md` stub redirect
- `~/.claude/skills/` junction/symlink → `skills_sbin/`
- `~/.claude/settings.json` from template
- Git hooks (DCO sign-off enforcement)
- Handoffs directory

---

## Adding Brains on Desktop

Brains on a desktop deployment are OS user accounts on the same machine.

```bash
python $HORIZON_SYSTEM/scripts/create_brain.py brain-name
```

Run as administrator (Windows) or with `sudo` (Linux/macOS). The script:
1. Creates an OS user account (`brain-name`).
2. Creates `$HORIZON_ROOT/brains/brain-name/` with full access for that user.
3. Sets `$HORIZON_BIN` group permissions (read + execute; Deny on `sbin`).
4. Provisions any keys and tools specified.

On the desktop, you can switch to a brain session by logging in as that OS user (fast user switching) or by running the harness as that user (`runas /user:brain-name claude` on Windows).

---

## Desktop-Specific Features

| Feature | Desktop Behavior |
|---|---|
| **Sounds** | Event hooks play audio through the local sound device — works immediately. |
| **Statusline** | Statusline scripts render in the harness UI (Claude Code statusBar). |
| **Audit log** | Written to `$HORIZON_ROOT/logs/` — readable in any editor. |
| **Monitor** | `monitor_aios.py` runs in a background terminal; alerts visible on-screen. |
| **Handoffs** | Written to `$HORIZON_ROOT/handoffs/` — local file, immediately accessible. |
| **Brains** | OS user accounts — visible in user management tools; no extra tooling needed. |

---

## Desktop vs. Docker

| Concern | Desktop | Docker |
|---|---|---|
| Brain isolation | OS user accounts on same machine | Separate containers |
| Always-on brains | Task Scheduler / cron / systemd | Container `restart: unless-stopped` |
| Harness UI | Desktop app / native terminal | `docker exec -it` |
| Sounds + statusline | Native, first-class | Not available inside container |
| Audit log | Local file | Named Docker volume |
| Setup complexity | Bootstrap script | `docker compose up` |

For brains that need to run unattended or at scale, move them to the server or Docker model. The desktop model is best for interactive, developer-driven, or personal-assistant brains where the user is in the loop.
