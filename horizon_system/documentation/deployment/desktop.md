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
- Administrator / sudo access (required for onboarding — it creates the OS groups and applies the ACL model — and for brain provisioning; not needed for daily use as an enrolled human).

---

## Setup

Follow the full setup guide at `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md`.

Onboarding (bootstrap) is the single secure entry point. There is no separate "hardening" step: bootstrap always creates the AIOS OS groups and applies the ACL model, so the tree is locked down from the first run. Run it as administrator so the group/ACL steps succeed.

Summary:

```bash
# Clone the AIOS repo
git clone <your-aios-repo-url> C:\devroot   # Windows example

# Run bootstrap (as admin — it creates OS groups and applies the ACL model)
& C:\devroot\horizon_system\sbin\bootstrap.ps1    # Windows (PowerShell, as admin)
# OR
bash /path/to/horizon_system/sbin/bootstrap.sh    # macOS / Linux
```

### The onboarding question — server or workstation

Onboarding asks whether this machine is **primarily a server, or an active-use workstation with human users**, and creates an AIOS-managed OS group **horizon_humans** ("Horizon.AIOS Actual Humans") on every install:

- **Server** — enroll no humans. The group is left empty; only the owner, SYSTEM, and Administrators can write to the AIOS tree. A bare server reduces to admin-only write.
- **Workstation** — enroll the human operator account(s) supplied by name or SID (cloud / Azure AD accounts are SIDs). Members of `horizon_humans` get **Full control of the AIOS tree** but are **Read-Only on `brains/`** — to write into a brain folder a human elevates to administrator or changes the permissions.

The desktop is the workstation case: enroll yourself so you have full day-to-day control of the tree without admin, while brains stay protected.

Non-interactive runs must state the choice explicitly:

```bash
# Accept detected defaults
bootstrap.ps1 --yes
# Or declare the profile (humans optional, name or SID, repeatable)
bootstrap.ps1 --profile workstation --humans jane --humans S-1-12-1-...
bootstrap.sh  --profile server
```

Enroll a human later without re-onboarding:

```bash
bootstrap.ps1 --add-human jane          # by account name
bootstrap.ps1 --add-human S-1-12-1-...  # by SID (cloud / Azure AD)
```

Bootstrap sets up:
- The AIOS OS groups and the full ACL model (owner + SYSTEM + Administrators + `horizon_humans` on the tree; humans Read-Only on `brains/`). On Windows it breaks inheritance at `$HORIZON_ROOT` and re-grants only those principals, removing broad inherited write grants (e.g. Authenticated Users) from the AIOS tree
- A gitignored deployment marker `$HORIZON_ROOT/.horizon_aios_deployment.json` recording the profile + enrolled humans
- The AIOS registry + indirection layer (`~/.horizon/`: `aios_registry.json`, `active_env.{ps1,sh}`, `bin/aios-exec.{ps1,sh}`) via `horizon_aios_switch.py init`
- Generates `~/.horizon/active_env.*` and prints the one-line profile include to add — it sets `HORIZON_ROOT` + derived vars for the active AIOS (see `system/aios_switching.md`)
- `~/.claude/CLAUDE.md` stub redirect
- `~/.claude/skills/` symlink → `skills_sbin/`
- Machine-local user skills (`usrbin/usr_skills/` → `skills_sbin/`) registered via `horizon_aios_register_user_skills.py`
- `~/.claude/settings.json` from template, pointed at the `aios-exec` wrapper
- Git hooks (DCO sign-off enforcement)
- Handoffs directory

---

## Adding Brains on Desktop

Brains on a desktop deployment are OS user accounts on the same machine.

```bash
python $HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py brain-name
```

Run as administrator (Windows) or with `sudo` (Linux/macOS). The script:
1. Creates an OS user account (`brain-name`) in the `brains` group, with a generated credential.
2. Creates `$HORIZON_ROOT/brains/brain-name/` with full access for that user.
3. Sets ACLs: `brains` group read + execute on `$HORIZON_BIN`/`skills_bin`, explicit Deny on `sbin`/`skills_sbin`/`logs` (see `security_invariants.md §2`).
4. Provisions any keys and tools specified.
5. **Configures the brain's harness to point at AIOS** (Phase 5 — see below).
6. Writes a `.aios_provision.json` manifest into the brain folder for auditors.

### How a brain's harness is wired to AIOS

**Brain users do not run `bootstrap.ps1`/`bootstrap.sh`.** Bootstrap is the *owner/admin* machine-setup step, run once. `horizon_aios_create_brain.py` is the per-brain onboarding script — it configures each brain user's harness so that, the moment the brain logs in and launches the harness, it is already pointed at the AIOS layer.

The brain's config is **canonical in its workspace root** `brains/<name>/`. Because the harness auto-loads `CLAUDE.md` from the cwd and every ancestor directory, a brain session (cwd = its workspace root) inherits the AIOS root `CLAUDE.md` chain from `$HORIZON_ROOT/` automatically, then layers its own root config on top. The brain's home `~/.claude` is a **symlink to `brains/<name>/.claude/`**, so the skills tier and harness settings surface at the user level regardless of cwd. Phase 5 deploys/links (every deployed file has `[BRAIN_NAME]` and `[HORIZON_ROOT_PATH]`→`$HORIZON_ROOT` resolved; `[BRAIN_DESCRIPTION]` is left for the operator):

- **Brain-root config** — loaded as project files from the workspace root, all from `brains/.aioscommon/*.template`:
  - `brains/<name>/CLAUDE.md` — thin entry; `@`-imports the brain's `agents.md`, `brain_invariants.md`, and `brain_core.md`.
  - `brains/<name>/agents.md` — `@`-imports the brain's invariants, the `.aioscommon` overrides, and `brain_core.md`.
  - `brains/<name>/brain_core.md` — the brain's identity, role, knowledge locations, and behaviors (carries a `[BRAIN_DESCRIPTION]` placeholder and `TODO` sections to fill in).
  - `brains/<name>/brain_invariants.md` — the brain's hard rules (security-invariant reference plus brain-specific invariants).
- **`.aioscommon/`** — local override seam:
  - `settings.json` — reference permission scoping for applications that read it (allow the brain folder; deny `sbin`/writes to `horizon_system`). Defense-in-depth only — real isolation is the OS ACLs from step 3.
  - `local.agent_teams.md`, `agents.local.md`, `.gitkeep` — brain-local team/agent overrides (start empty).
- **`.claude/`** — harness-local layer:
  - `settings.local.json` — Claude Code permissions for the brain's interactive sessions.
  - `skills` — a symlink to `$HORIZON_SYSTEM/skills_bin/`, so the brain sees the group-readable skill tier (never `skills_sbin`).
- `<brain-home>/.claude` → symlink → `brains/<name>/.claude/` — surfaces the skills tier + harness settings from the brain's home directory.
- The brain user's **shell/PowerShell profile** — exports the `HORIZON_*` environment variables and `cd`s to the brain folder on interactive login.

So there is no separate "point the brain at AIOS" step: provisioning *is* that step. To customize a brain after provisioning, fill in its `brains/<name>/brain_core.md` (identity / role / knowledge) and `brain_invariants.md`, not the AIOS layer.

On the desktop, you can switch to a brain session by logging in as that OS user (fast user switching) or by running the harness as that user (`runas /user:brain-name claude` on Windows).

To let a brain run **unattended** (a scheduled task or service launching the harness with no human present), provision it with `--automation scheduled` and register a Task Scheduler task — see `brain_automation.md`.

### Removing a brain

Deprovision a brain with the counterpart script (run elevated):

```bash
python $HORIZON_SYSTEM/sbin/horizon_aios_remove_brain.py brain-name        # prompts to confirm
python $HORIZON_SYSTEM/sbin/horizon_aios_remove_brain.py brain-name --yes  # non-interactive
python $HORIZON_SYSTEM/sbin/horizon_aios_remove_brain.py brain-name --dry-run
```

It reverses `horizon_aios_create_brain.py`: removes the OS user account, the per-brain group (`<name>_group` on Windows; the shared `brains` group is kept), the workspace folder `$HORIZON_ROOT/brains/brain-name/`, the user-profile config, and the stored credential. All links — the home `~/.claude` → workspace symlink and the workspace `.claude/skills` → `skills_bin` symlink — are deleted as reparse points **before** any recursive delete, so neither the workspace nor `skills_bin` is ever followed or destroyed.

---

## Desktop-Specific Features

| Feature | Desktop Behavior |
|---|---|
| **Sounds** | Event hooks play audio through the local sound device — works immediately. |
| **Statusline** | Statusline scripts render in the harness UI (Claude Code statusBar). |
| **Audit log** | Written to `$HORIZON_SYSTEM/logs/` — readable in any editor. |
| **Monitor** | `horizon_aios_monitor.py` runs in a background terminal; alerts visible on-screen. |
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
