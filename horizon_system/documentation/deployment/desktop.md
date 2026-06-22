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
- The AIOS registry + indirection layer (`~/.horizon/`: `aios_registry.json`, `active_env.{ps1,sh}`, `bin/aios-exec.{ps1,sh}`) via `aios_switch.py init`
- Generates `~/.horizon/active_env.*` and prints the one-line profile include to add — it sets `HORIZON_ROOT` + derived vars for the active AIOS (see `system/aios_switching.md`)
- `~/.claude/CLAUDE.md` stub redirect
- `~/.claude/skills/` junction/symlink → `skills_sbin/`
- Machine-local user skills (`usrbin/usr_skills/` → `skills_sbin/`) registered via `register_user_skills.py`
- `~/.claude/settings.json` from template, pointed at the `aios-exec` wrapper
- Git hooks (DCO sign-off enforcement)
- Handoffs directory

---

## Adding Brains on Desktop

Brains on a desktop deployment are OS user accounts on the same machine.

```bash
python $HORIZON_SYSTEM/sbin/create_brain.py brain-name
```

Run as administrator (Windows) or with `sudo` (Linux/macOS). The script:
1. Creates an OS user account (`brain-name`) in the `brains` group, with a generated credential.
2. Creates `$HORIZON_ROOT/brains/brain-name/` with full access for that user.
3. Sets ACLs: `brains` group read + execute on `$HORIZON_BIN`/`skills_bin`, explicit Deny on `sbin`/`skills_sbin`/`logs` (see `security_invariants.md §2`).
4. Provisions any keys and tools specified.
5. **Configures the brain's harness to point at AIOS** (Phase 5 — see below).
6. Writes a `.aios_provision.json` manifest into the brain folder for auditors.

### How a brain's harness is wired to AIOS

**Brain users do not run `bootstrap.ps1`/`bootstrap.sh`.** Bootstrap is the *owner/admin* machine-setup step, run once. `create_brain.py` is the per-brain onboarding script — it configures each brain user's harness so that, the moment the brain logs in and launches the harness, it is already pointed at the AIOS layer.

The brain's config is **canonical in its workspace** `brains/<name>/.claude/`, and the brain's home `~/.claude` is a **junction/symlink to it** — so everything is surfaced at the user-level `~/.claude` regardless of the brain's cwd. Phase 5 deploys/links:

- `brains/<name>/.claude/CLAUDE.md` — from `brains/.aioscommon/brain_CLAUDE.md.template`. It `@`-imports `$HORIZON_ROOT/.claude/CLAUDE.md`, so the brain inherits the full AIOS config chain (agents.md, invariants, personalizations) plus its own identity/scope/skills block.
- `brains/<name>/.claude/settings.json` — from `brain_settings.json.template`: harness-layer permission scoping (allow the brain folder; deny `sbin`/writes to `horizon_system`). Defense-in-depth only — real isolation is the OS ACLs from step 3.
- `brains/<name>/.claude/skills` — a junction (Windows) / symlink (Unix) to `$HORIZON_SYSTEM/skills_bin/`, so the brain sees the group-readable skill tier (never `skills_sbin`).
- `<brain-home>/.claude` → junction/symlink → `brains/<name>/.claude/` — makes the above resolve from the brain's home directory.
- The brain user's **shell/PowerShell profile** — exports the `HORIZON_*` environment variables and `cd`s to the brain folder on interactive login.

So there is no separate "point the brain at AIOS" step: provisioning *is* that step. To customize a brain after provisioning, edit its `brains/<name>/.claude/CLAUDE.md` Role section (the template leaves a placeholder), not the AIOS layer.

On the desktop, you can switch to a brain session by logging in as that OS user (fast user switching) or by running the harness as that user (`runas /user:brain-name claude` on Windows).

To let a brain run **unattended** (a scheduled task or service launching the harness with no human present), provision it with `--automation scheduled` and register a Task Scheduler task — see `brain_automation.md`.

### Removing a brain

Deprovision a brain with the counterpart script (run elevated):

```bash
python $HORIZON_SYSTEM/sbin/remove_brain.py brain-name        # prompts to confirm
python $HORIZON_SYSTEM/sbin/remove_brain.py brain-name --yes  # non-interactive
python $HORIZON_SYSTEM/sbin/remove_brain.py brain-name --dry-run
```

It reverses `create_brain.py`: removes the OS user account, the per-brain group (`<name>_group` on Windows; the shared `brains` group is kept), the workspace folder `$HORIZON_ROOT/brains/brain-name/`, the user-profile config, and the stored credential. All links — the home `~/.claude` → workspace junction and the workspace `.claude/skills` → `skills_bin` junction — are deleted as reparse points **before** any recursive delete, so neither the workspace nor `skills_bin` is ever followed or destroyed.

---

## Desktop-Specific Features

| Feature | Desktop Behavior |
|---|---|
| **Sounds** | Event hooks play audio through the local sound device — works immediately. |
| **Statusline** | Statusline scripts render in the harness UI (Claude Code statusBar). |
| **Audit log** | Written to `$HORIZON_SYSTEM/logs/` — readable in any editor. |
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
