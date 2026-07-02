# Horizon AIOS — System Setup Guide

Horizon AIOS is a portable, Git-versioned Claude Code "operating system." The repository functions as an OS layer: it version-controls all Claude Code configuration, hooks, sounds, statusline scripts, and AI behavior instructions in one place. Any project folder placed inside `$HORIZON_ROOT` automatically inherits the full AIOS environment — Claude Code settings, sounds, statusline, and global instructions — with no per-project wiring required. Projects that need their own independent Git history simply run `git init` inside their folder, which causes Git to exclude them from the OS repo automatically. The entire environment is reproducible on a new machine by cloning the repo and running a small bootstrap sequence.

This document serves two purposes simultaneously:

1. **Human SOP** — step-by-step instructions a person can follow.
2. **Agent-executable** — structured precisely enough that an AI agent can read it and implement each step without ambiguity.

---

## Quick Start — `aios setup` (Recommended)

`aios setup` is the one-shot installer. It orchestrates the entire procedure below — it does not replace your understanding of it, but it automates every step. Run it from a clone of the AIOS repo (or standalone, in which case it offers to clone for you):

```bash
python "$HORIZON_SYSTEM/sbin/horizon_aios_switch.py" setup      # or: aios setup
```

What it does, idempotently and re-run safe:

1. **Preflight** — probes prerequisites (hard-fails on missing `git`/`claude`; warns on `jq`/`gpg`/`ssh`; gives SSH/GPG guidance — never generates keys).
2. **Root + clone** — prompts for `$HORIZON_ROOT`; inside an existing tree it skips cloning, standalone it offers to clone to the chosen root.
3. **Relocate** — if the chosen root differs from the current tree, calls `horizon_aios_relocate.py --apply`.
4. **Profile line** — idempotently adds the `active_env` source line to your shell profile.
5. **Bootstrap** — shells out to the **elevated** platform bootstrap (Windows: UAC relaunch; Unix: `sudo`) for sections 2–10 below.
6. **Git identity** — writes `user.name`/`user.email`/`user.signingkey` to a machine-local, gitignored include file (`ai_os_etc/git_identity.local.gitconfig`) wired via `git config --global include.path` (never edits the tracked gitconfig, never shows in `git status`); also ensures the §9 framework-gitconfig include.
7. **Git init**, **settings.local.json** stub, **model-prefs** and **`local.agents.md`** template materialization. First commit is opt-in (`--first-commit`; off by default so `--yes` completes without a GPG key).
8. **Verify gate** — runs `horizon_aios_doctor.py --post-setup` (non-fatal summary).

Add `--yes` for a non-interactive run (accepts defaults, mirrors bootstrap's `--yes`). Onboarding asks whether this machine is primarily a server or an active-use workstation, and (workstation) which human accounts to enroll in the `horizon_humans` group; a non-interactive run must therefore pass `--yes` or `--profile server|workstation [--humans <name|sid> ...]`. See "Prerequisites — Elevated Privileges Required" below.

`aios setup` decouples the first signed commit from `--yes`. By default (and with `--yes`) no commit is created — GPG is not required for an unattended install. To create the first commit in the same pass, add `--first-commit`; to explicitly suppress it, use `--no-first-commit`. Run the commit manually later with `git commit -s` once a signing key is ready.

**The remainder of this document is the authoritative manual procedure** — the fallback when you cannot run `aios setup`, want to understand each step, or need to do one step by hand.

---

## AGENT SETUP PROTOCOL

> This section is addressed to any agent reading this file to perform setup on behalf of a user.
> Follow these steps exactly and in order. Do not proceed past step A.2 until the user has confirmed.

**A.1** Before doing anything else, ask the user:

> "Where would you like to place your $HORIZON_ROOT directory on this system? This is the folder the Horizon AIOS repository will be cloned into — for example `C:\devroot` on Windows or `/home/username/devroot` on Linux/Mac. Please provide the full absolute path."

**A.2** Wait for the user's answer. Store it as `$HORIZON_ROOT`. Confirm back:

> "I'll use `{the path they gave}` as $HORIZON_ROOT. Proceeding with setup."

**A.3** Substitute `$HORIZON_ROOT` with the confirmed path in every command and file edit that follows in this document. Do not use `C:\devroot` or any other hardcoded path — only the path the user provided.

**A.4** Work through sections 1 through 11 of this document in order, completing each step before moving to the next.

---

## Presumptions / Dependencies

The following are required for Horizon AIOS to function. Verify each before beginning setup.

**Software**

P.1 **Git 2.9 or later** — version 2.9 introduced `core.hooksPath`, which is how the version-controlled pre-commit hook is wired in. Earlier versions will silently ignore the hook.

Verify: `git --version` — must return `2.9.0` or higher.

P.2 **Claude Code CLI** — the application this system configures. Must be installed before bootstrap.

Verify: `claude --version`

P.3 **Bash environment** — required for hook scripts and statusline dispatch. On Windows, Git Bash satisfies this requirement. On Linux and macOS, the native shell is used.

Verify: `bash --version`

P.4 **jq** — required by some statusline scripts for JSON parsing.

Verify: `jq --version`

Install if missing: `winget install jqlang.jq` (Windows) or `brew install jq` (macOS) or `apt install jq` (Debian/Ubuntu).

P.5 **PowerShell** — required on Windows only. The Windows statusline script (`statusline-context-alerts.ps1`) and sound player both use PowerShell, which is built-in on Windows. On Linux and macOS, the bash statusline script and `play_sound.sh` are used instead — `pwsh` is not required on those platforms.

P.5.1 **`watchdog` Python library** — required only if you intend to use the AIOS filesystem monitor (`sbin/horizon_aios_monitor.py`). The monitor is opt-in and not auto-started. Install when ready to use it: `pip install watchdog`.

P.6 **GPG** — required for commit signing. `commit.gpgsign = true` is set globally, so all commits on the machine will be GPG-signed. A key must exist in the local keyring before the first commit.

P.7 **SSH client** — required for all remote Git operations. No HTTPS and no `gh` CLI are used anywhere in this system.

**Authentication**

P.8 An **SSH key pair** must exist (default: `~/.ssh/id_ed25519`) and the public key must be registered with the GitHub account (or other host) where the AIOS repo lives.

Verify: `ssh -T git@github.com` — should return an authentication acknowledgement (not a permission denied error).

P.9 A **GPG key** must be generated and available in the local keyring. The key fingerprint must be entered in `$HORIZON_SYSTEM/harness_configs/git/gitconfig` during setup.

Verify: `gpg --list-secret-keys --keyid-format LONG` — must show at least one secret key.

**Platform**

P.10 Horizon AIOS supports **Windows, Linux, and macOS**. Platform routing is handled automatically:

P.10.1 **Sound playback** uses `$HORIZON_SOUNDS/play_sound.sh` (`horizon_system/sounds/play_sound.sh`), which detects the OS at runtime and calls `Media.SoundPlayer` (Windows), `afplay` (macOS), or the first available Linux player from: `paplay` (PulseAudio), `aplay` (ALSA), `ffplay` (ffmpeg), `mpg123`. Hooks fail silently if no player is found.

P.10.2 **Statusline** uses `$HORIZON_BIN/statusline/statusline.sh`, a bash dispatcher that calls `statusline-context-alerts.ps1` (PowerShell, Windows) or `statusline-command.sh` (bash, Linux/macOS) depending on OS. Both scripts include threshold audio alerts.

P.10.3 **Linux audio dependency**: at least one of `paplay`, `aplay`, `ffplay`, or `mpg123` must be installed for sounds to play on Linux. Sounds are skipped silently if none are present.

P.11 **No administrator privileges are required for the Claude config wiring**. `~/.claude/settings.json` is a plain file copy of the template (no special permissions needed), and `~/.claude/skills/` is a directory symlink — neither requires elevation. (The full `bootstrap` script's ACL-hardening step does require admin/root, but the config wiring itself does not.)

P.12 **Developer Mode is not required**.

**Runtime**

P.13 **`$HORIZON_ROOT` is written into the machine-local config on first setup.** If you later need to move the repo to a new location, run `horizon_aios_relocate.py` to update all machine-local instance pointers automatically (see `$HORIZON_DOCS/system/system_configuration_reference.md` Section 3). Choose the path before bootstrap to avoid this step.

P.14 An **audio output device** must be present for sound hooks to play. If no device is available, the hooks fail silently — Claude Code operation is unaffected.

P.15 **`~/.claude/` must exist** before the bootstrap commands are run. Claude Code creates this directory on first launch. If it does not exist, run `claude` once and exit before proceeding with setup.

P.16 **`.git/info/exclude`** in the OS repo is managed automatically by the pre-commit hook (synced from `.gitignore.user`). Do not edit this file manually — changes will be overwritten on the next commit.

---

## Prerequisites — Elevated Privileges Required

Onboarding is the single secure entry point: bootstrap always creates the AIOS OS groups and applies the ACL model (there is no separate hardening step). Both bootstrap and brain provisioning run `horizon_aios_harden.py`, which sets OS-level filesystem ACLs. This requires administrator or root privileges. **Bootstrap will exit immediately with an error if not run elevated.**

Onboarding creates the AIOS-managed OS group **horizon_humans** ("Horizon.AIOS Actual Humans") on every install and asks whether the machine is primarily a server or an active-use workstation:

- **Server** — no humans enrolled; the group stays empty, so only the owner, SYSTEM, and Administrators can write to the AIOS tree.
- **Workstation** — enroll the human operator account(s) supplied by name or SID (cloud / Azure AD accounts are SIDs). Members of `horizon_humans` get Full control of the AIOS tree but are Read-Only on `brains/` (to write into a brain folder a human elevates to administrator or changes the permissions).

On Windows, onboarding breaks inheritance at `$HORIZON_ROOT` and re-grants only owner + SYSTEM + Administrators + `horizon_humans`, removing broad inherited write grants (e.g. Authenticated Users). Non-interactive runs must pass `--yes` or `--profile server|workstation [--humans <name|sid> ...]`. Enroll a human later with `bootstrap --add-human <name|sid>`. The chosen profile and enrolled humans are recorded in the gitignored marker `$HORIZON_ROOT/.horizon_aios_deployment.json`.

- **Windows:** Open PowerShell by right-clicking the Start button (or the PowerShell icon) and choosing **Run as administrator**. Then run:
  ```powershell
  & "$env:HORIZON_SYSTEM\sbin\bootstrap.ps1"
  ```
- **Linux:** Run bootstrap with `sudo`:
  ```bash
  sudo bash horizon_system/sbin/bootstrap.sh
  ```
- **macOS:** Same `sudo` model as Linux. `horizon_aios_harden.py` adapts its hardening to macOS ACL semantics automatically:
  ```bash
  sudo bash horizon_system/sbin/bootstrap.sh
  ```

All other bootstrap steps (CLAUDE.md redirect, skills symlink, git hooks, settings.json copy) are non-destructive and idempotent. The privilege requirement is solely for the OS-group creation and ACL steps that onboarding always applies.

---

## 1. What Is $HORIZON_ROOT

`$HORIZON_ROOT` is the root folder of the Horizon AIOS installation on this machine. It is the absolute path where the Horizon AIOS repository lives. Every path reference inside the repository — in settings, scripts, and config files — is expressed relative to this root. When setting up a new machine, this path is chosen once and substituted everywhere.

`$HORIZON_ROOT` is itself a Git repository (the OS repo). It tracks the config and asset layer. Individual project folders placed inside it are expected to have their own Git repos and are automatically excluded from OS repo tracking the moment they are `git init`'d.

The following environment variables derive from `$HORIZON_ROOT` and must be set in your shell profile before proceeding:

| Variable | Points To | Purpose |
|---|---|---|
| `$HORIZON_ROOT` | The repo root (e.g., `C:\devroot`) | Anchor for all other paths |
| `$HORIZON_SYSTEM` | `$HORIZON_ROOT/horizon_system` | Full AIOS system directory (mirrors Unix `/usr`) |
| `$HORIZON_BIN` | `$HORIZON_SYSTEM/bin` | User-callable executables |
| `$HORIZON_ETC` | `$HORIZON_SYSTEM/ai_os_etc` | OS configuration documents and invariants |
| `$HORIZON_DOCS` | `$HORIZON_SYSTEM/documentation` | User-facing documentation |

---

## 2. Prerequisites

Complete all prerequisites before beginning setup. Each must be true before proceeding.

2.1 **Git 2.9 or later** is installed and available on `PATH`. Version 2.9+ is required for `core.hooksPath`, which wires the version-controlled pre-commit hook. Verify: `git --version`

2.2 **SSH key** exists at `~/.ssh/id_ed25519` (or another key of your choice) and the corresponding public key is registered with your GitHub account (or whichever Git host the Horizon AIOS repo is on). Verify: `ssh -T git@github.com` should return an authentication success message.

2.3 **GPG key** is generated and available in your keyring. Commit signing is enabled globally. Verify: `gpg --list-secret-keys --keyid-format LONG` should show at least one secret key. Note the full fingerprint — you will need it in step 6.3.

2.4 **Claude Code** is installed. Verify: `claude --version`

2.5 **Bash** is available. On Windows, Git Bash satisfies this requirement. Verify: `bash --version`

2.6 **jq** is installed. Verify: `jq --version`. Install if missing: `winget install jqlang.jq` (Windows), `brew install jq` (macOS), `apt install jq` (Debian/Ubuntu).

2.7 **PowerShell** is available (Windows: built-in; Linux/Mac: install `pwsh`). The statusline script requires PowerShell.

---

## 3. Clone the Repository

3.1 Decide the absolute path where Horizon AIOS will live on this machine. This is `$HORIZON_ROOT`. Example: `C:\devroot` on Windows, `/home/username/devroot` on Linux/macOS. If you later move the repo, run `horizon_aios_relocate.py` to update machine-local pointers.

3.2 Create the parent directory if it does not already exist:

Windows (PowerShell):
```powershell
New-Item -ItemType Directory -Force "$HORIZON_ROOT"
```

Linux / macOS (bash):
```bash
mkdir -p "$HORIZON_ROOT"
```

3.3 Clone the Horizon AIOS repository into `$HORIZON_ROOT`:

```bash
git clone git@github.com:HorizonBrute/Horizon_AI_OS.git "$HORIZON_ROOT"
```

3.4 Confirm the clone succeeded by verifying these paths exist:

```
$HORIZON_ROOT/.claude/settings.json
$HORIZON_ROOT/.claude/CLAUDE.md
$HORIZON_BIN/statusline/statusline-context-alerts.ps1
$HORIZON_SYSTEM/harness_configs/git/hooks/pre-commit
$HORIZON_ROOT/.gitignore.user
```

---

## 4. Set Environment Variables

AIOS scripts and documentation reference `$HORIZON_ROOT`, `$HORIZON_SYSTEM`, `$HORIZON_BIN`, `$HORIZON_ETC`, and `$HORIZON_DOCS` (plus derived vars). Rather than hardcoding these in your profile, add **one line** that sources the active AIOS's generated environment file. This is what lets `aios switch <name>` repoint every new shell without editing your profile.

4.1 Add the source line to your shell profile (see `templates/profile_snippet.{ps1,sh}` for a copy-paste version).

**Windows (PowerShell `$PROFILE`):**

```powershell
if (Test-Path "$HOME\.horizon\active_env.ps1") { . "$HOME\.horizon\active_env.ps1" }
```

**Linux/macOS (`~/.bashrc`, `~/.zshrc`):**

```bash
[ -f "$HOME/.horizon/active_env.sh" ] && . "$HOME/.horizon/active_env.sh"
```

4.2 The `active_env.*` file is generated by the bootstrap script (Section 5, which runs `horizon_aios_switch.py init`) or manually via `python "$HORIZON_SYSTEM/sbin/horizon_aios_switch.py" init`. The `Test-Path` / `-f` guard makes the line a harmless no-op until then.

4.3 After bootstrap, reload your profile (`. $PROFILE` or `source ~/.bashrc`, or open a new terminal) and verify: `$env:HORIZON_ROOT` (PowerShell) or `echo $HORIZON_ROOT` (bash) should print the active AIOS root.

### 4.4 Switching AIOS

The `HORIZON_*` values follow whichever AIOS is active. To switch, run `aios switch <name>` (which regenerates `active_env.*`) and open a new shell to pick up the change. The registry of known AIOSs lives at `~/.horizon/aios_registry.json`. See `$HORIZON_DOCS/system/aios_switching.md` for the full model.

**Optional — default terminal working directory:** Add `Set-Location $env:HORIZON_ROOT` (PowerShell) or `cd "$HORIZON_ROOT"` (bash/zsh) at the end of your profile so every new terminal opens at the active AIOS root. This is personal preference and does not affect AIOS operation.

---

## 5. Run the Bootstrap Script (Recommended)

The bootstrap script automates Steps 6–8 below. Run it once after cloning. It is safe to run multiple times.

**Git Bash / macOS / Linux:**
```bash
bash "$HORIZON_SYSTEM/sbin/bootstrap.sh"
```

**PowerShell (Windows):**
```powershell
& "$env:HORIZON_SYSTEM\sbin\bootstrap.ps1"
```

The script will:
- Create `~/.claude/CLAUDE.md` with the `@` redirect (Step 6)
- Create `~/.claude/skills/` as a symlink pointing to `$HORIZON_SYSTEM/skills_sbin/` (Step 7)
- Register machine-local user skills (`usrbin/usr_skills/` → `skills_sbin/` symlinks) via `horizon_aios_register_user_skills.py` (best-effort; see Step 7)
- Initialize the AIOS registry + indirection layer (`horizon_aios_switch.py init`) and offer to copy `settings.json` from the template, pointed at the `aios-exec` wrapper (Step 6.2)
- Create `$HORIZON_ROOT/handoffs/` and `$HORIZON_SYSTEM/logs/`
- Wire git `core.hooksPath` and install DCO hooks
- Run a verification pass and print PASS/FAIL for each check

If you prefer to run each step manually (or the bootstrap script fails), follow Steps 6–8 individually below.

---

## 6. Bootstrap the Claude Code Global Configuration

Claude Code always reads its global configuration from `~/.claude/`. These two bootstrap steps redirect that global configuration into the repository so it is version-controlled.

6.1 **Bootstrap `~/.claude/CLAUDE.md`**

Create the file `~/.claude/CLAUDE.md` with a single line that includes the repository's CLAUDE.md.

Windows (PowerShell):

```powershell
Set-Content -Path "$HOME\.claude\CLAUDE.md" -Value "@$HORIZON_ROOT\.claude\CLAUDE.md"
```

Linux / macOS (bash):

```bash
echo "@$HORIZON_ROOT/.claude/CLAUDE.md" > "$HOME/.claude/CLAUDE.md"
```

This file must contain only that one line. Claude Code will follow the `@` include and load the full instructions from the repository. The canonical instructions live at `$HORIZON_ROOT/.claude/CLAUDE.md`.

6.2 **Bootstrap `~/.claude/settings.json`**

The global `~/.claude/settings.json` and the devroot `$HORIZON_ROOT/.claude/settings.json` serve different purposes and must remain separate files:

- `~/.claude/settings.json` (global) owns hooks, statusLine, and global permissions. It points at the machine-local `aios-exec` wrapper and must not be committed.
- `$HORIZON_ROOT/.claude/settings.json` (devroot project-level) owns only devroot-scoped permissions and is committed to the OS repo.

First generate the indirection layer (registry + `active_env` + wrappers), then copy the template and substitute the `AIOS_EXEC_WRAPPER` placeholder with the path to your `aios-exec` wrapper. On Windows use **forward slashes** — backslashes are invalid inside a JSON string, and `powershell.exe -File` accepts forward slashes.

Windows (PowerShell):

```powershell
python "$env:HORIZON_SYSTEM\sbin\horizon_aios_switch.py" init        # generates ~/.horizon/bin/aios-exec.ps1
$wrapper = ("$HOME\.horizon\bin\aios-exec.ps1") -replace '\\','/'
Copy-Item "$HORIZON_SYSTEM\templates\claude_code\settings.json" "$HOME\.claude\settings.json"
(Get-Content "$HOME\.claude\settings.json") -replace "AIOS_EXEC_WRAPPER", $wrapper | Set-Content "$HOME\.claude\settings.json"
```

Linux / macOS (bash) — note the Unix template (`settings_unix.json`):

```bash
python3 "$HORIZON_SYSTEM/sbin/horizon_aios_switch.py" init           # generates ~/.horizon/bin/aios-exec.sh
cp "$HORIZON_SYSTEM/templates/claude_code/settings_unix.json" "$HOME/.claude/settings.json"
sed -i "s|AIOS_EXEC_WRAPPER|$HOME/.horizon/bin/aios-exec.sh|g" "$HOME/.claude/settings.json"
```

Because settings.json points at the wrapper (which resolves the active AIOS at run time), it is AIOS-independent and never needs to change when you `aios switch`. The bootstrap script (Section 5) does all of this automatically. Do not link or copy `$HORIZON_ROOT/.claude/settings.json` to `~/.claude/settings.json` — they are different files with different owners.

6.3 Verify both files are in place.

Windows:

```powershell
Test-Path "$HOME\.claude\CLAUDE.md"
Test-Path "$HOME\.claude\settings.json"
```

Linux / macOS:

```bash
test -f "$HOME/.claude/CLAUDE.md" && echo "OK" || echo "MISSING"
test -f "$HOME/.claude/settings.json" && echo "OK" || echo "MISSING"
```

Both should confirm the files exist.

---

## 7. Skills Redirect

AIOS skills live in `$HORIZON_SYSTEM/skills_sbin/` (primary user) and `$HORIZON_SYSTEM/skills_bin/` (brain users). Claude Code reads skills from `~/.claude/skills/`. Bootstrap wires this by creating `~/.claude/skills/` as a symlink pointing directly to the source directory — there is no copy step. Skills are live on disk as soon as the repo is updated; only a session restart is needed to pick up changes.

7.1 The bootstrap script (Step 5) handles this automatically. To verify or create the redirect manually:

Windows (PowerShell — run as administrator; AIOS requires admin installation):
```powershell
# Remove existing directory if empty
Remove-Item "$HOME\.claude\skills" -ErrorAction SilentlyContinue
New-Item -ItemType SymbolicLink -Path "$HOME\.claude\skills" -Target "$env:HORIZON_SYSTEM\skills_sbin"
```

Linux / macOS (bash):
```bash
rm -rf ~/.claude/skills
ln -s "$HORIZON_SYSTEM/skills_sbin" ~/.claude/skills
```

7.2 Verify the redirect:
```bash
# Should show the symlink target, not a real directory listing
ls -la ~/.claude/skills
```
On Windows: `Get-Item "$HOME\.claude\skills" | Select-Object LinkType, Target`

7.3 Verify a skill is present: `ls ~/.claude/skills/handoff/SKILL.md`

7.4 **Skills load at session start, not hot-reloaded.** Start a new session after changes.

7.5 **Machine-local user skills.** Personal skills you want kept out of the OS repo (and safe from upstream syncs) live in `$HORIZON_USRBIN/usr_skills/<name>/SKILL.md`. `horizon_aios_register_user_skills.py` symlinks each into `skills_sbin/`, so they surface flat through the same `~/.claude/skills/` symlink alongside OS skills. Bootstrap runs it automatically (and it re-runs after each successful sync, since a sync can refresh `skills_sbin`). Run it manually any other time you add or remove a user skill:

```bash
python "$HORIZON_SYSTEM/sbin/horizon_aios_register_user_skills.py"   # or invoke /resync-user-skills
```

It is idempotent, prunes stale links, and refuses to shadow an OS skill of the same name. User skills are gitignored and never indexed. To author one, use `/skill-creation` (user tier).

7.6 Troubleshooting — if a skill is not recognized:

1. Confirm the symlink exists: `Get-Item "$HOME\.claude\skills"` (Windows) or `ls -la ~/.claude/skills` (Unix)
2. Start a **fresh** Claude Code session. Long-running sessions can miss newly available skills.
3. Confirm the `SKILL.md` has valid YAML frontmatter (`name:` and `description:` fields).
4. Run `horizon_aios_doctor.py`: `python "$env:HORIZON_SYSTEM\sbin\horizon_aios_doctor.py"`

---

## 8. Update Path-Sensitive Strings in the Repository

Some files require per-machine values (user identity, GPG key). The global `~/.claude/settings.json` uses the AIOS-independent `aios-exec` wrapper and needs no path substitution. Update the items below.

8.1 **`$HORIZON_ROOT/.claude/settings.json`** — no per-machine path substitution required.

The committed devroot file (`$HORIZON_ROOT/.claude/settings.json`) contains only devroot-scoped
permissions with no hardcoded paths. The machine-local global file (`~/.claude/settings.json`,
copied from the template during bootstrap) routes hooks and statusline through the stable
`~/.horizon/bin/aios-exec.{ps1,sh}` wrapper — a home-relative path that does not embed
`$HORIZON_ROOT`. No manual substitution is needed for either file.

If you are copying this AIOS install to a new root location after initial setup, use
`horizon_aios_relocate.py` to update the machine-local instance pointers automatically:

```powershell
python "$HORIZON_SYSTEM\sbin\horizon_aios_relocate.py" --new-root "C:\new\path" --apply
```

Run without `--apply` first to preview what would change.

8.2 **`$HORIZON_SYSTEM/harness_configs/git/gitconfig`** — the `excludesfile` field and user identity:

Open the file and set:

```
[user]
    name = Your Name
    email = your@email.com
    signingkey = YOUR_GPG_KEY_FINGERPRINT

[core]
    excludesfile = $HORIZON_ROOT/.gitignore_global
```

8.3 See `$HORIZON_DOCS/system/system_configuration_reference.md` Section 3 for the full Path Dependencies Catalog — every file that contains hardcoded paths.

---

## 9. Apply the Portable Git Configuration

9.1 Include the repository's gitconfig from your global git config:

```bash
git config --global include.path "$HORIZON_SYSTEM/harness_configs/git/gitconfig"
```

9.2 Verify git picks up the settings:

```bash
git config --global user.email
git config --global commit.gpgsign
```

Both should return the values from the repository's gitconfig.

---

## 10. Initialize the OS Git Repo

The OS repo at `$HORIZON_ROOT` tracks the AIOS config layer. This step initializes it on the new machine, wires the version-controlled pre-commit hook, and creates the first commit.

10.1 Initialize the repository:

```bash
cd "$HORIZON_ROOT"
git init
```

10.2 Wire the version-controlled hooks directory. This tells Git to use the hooks stored in the repository rather than `.git/hooks/`, so hook changes are committed and portable:

```bash
git config --local core.hooksPath ./horizon_system/harness_configs/git/hooks
```

10.3 Stage the OS layer files:

```bash
git add .claude/CLAUDE.md .claude/settings.json horizon_system/ handoffs/ .gitignore .gitignore.user.template
```

Do not stage `settings.local.json` or `.gitignore.user` — both are machine-local and excluded by `.gitignore` (only the tracked `.gitignore.user.template` is committed).

10.4 Create the initial commit. GPG signing fires automatically because `commit.gpgsign = true` is set in the global gitconfig:

```bash
git commit -m "Initial Horizon AIOS OS layer commit"
```

10.5 Verify the commit is GPG-signed:

```bash
git log --show-signature -1
```

The output should include a `gpg: Good signature` line.

---

## 11. Personal Ignore Layer — `.gitignore.user`

`$HORIZON_ROOT/.gitignore.user` is a machine-local file for user-personal ignore patterns. It is itself git-ignored (only `.gitignore.user.template` is tracked) and is separate from the system `.gitignore` so personal exclusions do not intermingle with OS-managed patterns. Bootstrap auto-creates it from the template on a fresh install (idempotent — never overwriting an existing file), so no manual copy is needed.

11.1 The pre-commit hook automatically syncs `.gitignore.user` to `.git/info/exclude` on every commit, so Git always respects the current contents. Changes made to `.gitignore.user` take effect at the next commit — there is no manual sync step.

11.2 To exclude a personal folder, add it to `.gitignore.user`:

```
MyPersonalNotes/
scratch/
```

The pre-commit hook picks the changes up on the next commit — no `git add` is needed (the file is git-ignored and intentionally never committed):

```bash
git commit -m "Some OS-layer change"   # any commit re-syncs .gitignore.user
```

Git will respect the new patterns from that commit forward.

11.3 `.gitignore.user` is **not** version-controlled — it is git-ignored and machine-local, so it does not travel with a clone. On a new machine, bootstrap recreates it from `.gitignore.user.template` automatically (only `.gitignore.user.template` is cloned with the repository). The pre-commit hook then activates its patterns on the first commit.

---

## 12. Create a Machine-Local `settings.local.json`

`settings.local.json` is not version-controlled. It holds permission overrides that are specific to this machine. Create it fresh on each machine:

12.1 Create the file at `$HORIZON_ROOT/.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": []
  }
}
```

12.2 Add machine-specific permission entries to the `allow` array as needed during normal use. Claude Code will prompt for permission on first use of any tool not yet in the list — approve it and it will be added automatically.

---

## 13. Project Isolation Pattern

Any folder inside `$HORIZON_ROOT` that needs its own independent Git history is isolated from the OS repo by running `git init` inside it. This is the universal opt-out mechanism — no `.gitignore` entry is required.

13.1 **How it works natively**: Git does not descend into subdirectories that contain their own `.git` folder. Once a subfolder is git-initted, its contents become invisible to the parent OS repo.

13.2 **The pre-commit hook handles the race condition**: If a folder was tracked by the OS repo and then later `git init`'d, its files remain in the OS index until removed. The pre-commit hook detects any tracked subdirectory that has acquired a `.git` folder and runs `git rm -r --cached` on it automatically before the commit completes. No manual cleanup is needed.

13.3 **Recursive exclusion**: The exclusion is recursive. If `ProjectParent/` contains `SubProject/` which gets `git init`'d, `SubProject/` is excluded. If `ProjectParent/` itself later gets `git init`'d, the entire `ProjectParent/` tree is excluded from that point forward.

13.4 **Excluding a parent folder with no direct `.git`**: To exclude an entire parent folder (such as a `RedTeam/` directory that will hold multiple independent projects), run `git init` inside the parent folder itself. This makes the parent a nested repo and excludes the entire subtree:

```bash
git init "$HORIZON_ROOT/RedTeam"
```

No remote is needed. The local `.git` is sufficient to trigger exclusion.

13.5 **Config inheritance**: Projects inside `$HORIZON_ROOT` automatically inherit the AIOS Claude Code environment — the global `settings.json` (hooks, sounds, statusline, permissions) and `CLAUDE.md` instructions apply in every subdirectory because Claude Code reads global config from `~/.claude/`, which is bootstrapped to point into the OS repo. No per-project configuration is needed to get the full AIOS experience.

---

## 14. Verify the Installation

14.1 Launch Claude Code from any directory:

```bash
claude
```

14.2 Confirm the statusline appears at the bottom of the terminal showing the current directory name, git branch (if in a repo), and a context usage bar. If the statusline is absent, check that `settings.json` `statusLine.command` points to the correct path.

14.3 Run the `/handoff` skill to confirm skills are loaded. Type `/handoff` in the Claude Code session. Claude should execute the handoff skill and write a file to `$HORIZON_ROOT/handoffs/`. If the skill is not recognized, see Section 7.6 troubleshooting — the most common cause is testing in the same long-running session used during setup rather than starting a fresh session.

14.4 Exit Claude Code cleanly. Confirm the WorkComplete sound plays. If no sound plays, verify the path in `hooks.Stop[0].hooks[0].command` in `settings.json`.

14.5 Trigger a permission request (run any tool not in the allow list). Confirm the InputNeeded sound plays.

14.6 Verify the OS repo commit is GPG-signed:

```bash
cd "$HORIZON_ROOT"
git log --show-signature -1
```

Confirm a `gpg: Good signature` line appears.

14.7 Verify the pre-commit hook is active:

```bash
git config --local core.hooksPath
```

Should return `./horizon_system/harness_configs/git/hooks`.

Setup is complete when all verification points pass.

---

## 15. Configure Model Preferences (post-install)

AIOS ships a BYO-model preference layer that routes agent spawns and task work
to the right model — cheap models for mechanical edits, capable ones for
architecture — without you naming a model every time.

15.1 Copy the tracked template to your gitignored extend file:

Windows (PowerShell):
```powershell
Copy-Item "$env:HORIZON_ETC\horizon_aios_model_prefs.local.template.md" `
          "$env:HORIZON_ETC\horizon_aios_model_prefs.local.md"
```

Linux / macOS (bash):
```bash
cp "$HORIZON_ETC/horizon_aios_model_prefs.local.template.md" \
   "$HORIZON_ETC/horizon_aios_model_prefs.local.md"
```

15.2 Run `/model-catalog-refresh` in a Claude Code session to fetch current
model ids and pricing from Anthropic, OpenAI, Gemini, and Ollama.

15.3 Fill in your group members (e.g. `#lowcost`, `#highcap`) and any
task-class routing rules using the ids from the catalog. Run `/model-prefs`
to edit or inspect the extend file interactively.

The extend file is gitignored and machine-local — no commit needed.

See `$HORIZON_DOCS/system/model_preferences.md` for the full reference
(member grammar, runtime qualification, fallback order, reliability notes).

If you are authoring skills, see `$HORIZON_DOCS/system/skill_model_groups.md` for
how skills declare their preferred model group.

---

## 16. Machine-Local Agent Instructions (`local.agents.md`)

`aios setup` materializes `local.agents.md` alongside every `agents.md` in the repo
(see `$HORIZON_ETC/file_structure_invariants.md` §12.6). This is the git-safe seam for
owner/machine-specific instructions that must not ship to other users.

16.1 Two files are created (if absent):
1. `$HORIZON_ROOT/local.agents.md`
2. `$HORIZON_ROOT/.claude/local.agents.md`

Each is copied from its sibling `local.agents.md.template` (tracked). The `local.agents.md`
files are gitignored and never overwritten by a sync.

16.2 **What belongs here:** owner identity, machine-specific rules, development
directives you do not want on other machines, or anything that applies to this install
only. Shipped, version-controlled defaults live in `agents.md`; personal overrides live
in `local.agents.md`. Keep it short — it loads into context every session.

16.3 Each `agents.md` `@`-imports its sibling `local.agents.md` last, so local content
overrides shipped content. `CLAUDE.md` is unaffected (it imports only its sibling
`agents.md` per §12 invariant).

16.4 To customize: edit `$HORIZON_ROOT/local.agents.md` or `$HORIZON_ROOT/.claude/local.agents.md`
directly. Never commit these files; add patterns to `$HORIZON_ROOT/.gitignore.user` if needed.

---

## Adding a New Project

Projects are folders inside `$HORIZON_ROOT`. They automatically inherit the full AIOS environment — no per-project wiring is needed.

1. Create the project folder:
   ```bash
   mkdir "$HORIZON_ROOT/MyProject"
   ```

2. If the project needs its own independent git history, initialize it:
   ```bash
   cd "$HORIZON_ROOT/MyProject"
   git init
   ```
   Once `git init`'d, the folder is invisible to the OS repo. No `.gitignore` entry is needed — Git does not descend into subdirectories with their own `.git`.

3. Optionally copy the `aios_overrides.md` template to the project root for project-specific AIOS configuration:
   ```bash
   cp "$HORIZON_SYSTEM/templates/aios_overrides.md" "$HORIZON_ROOT/MyProject/aios_overrides.md"
   ```
   Edit the file to set `handoffs_dir`, `objectives_dir`, `project_display_name`, or other overrides. See the template for documentation of all supported keys.

4. Optionally create a `.claude/CLAUDE.md` inside the project for project-specific AI instructions:
   ```bash
   mkdir -p "$HORIZON_ROOT/MyProject/.claude"
   # Edit $HORIZON_ROOT/MyProject/.claude/CLAUDE.md with project context
   ```
   Project-level CLAUDE.md is loaded by Claude Code on top of the global CLAUDE.md when working inside that project.

---

## Adding a New AI Harness

Horizon AIOS supports multiple AI harnesses. To add support for a new harness (e.g., Cursor, Windsurf, Ollama):

1. Create a harness config directory: `$HORIZON_SYSTEM/harness_configs/<harness_name>/` (for runtime config: sounds map, hooks, README) and/or `$HORIZON_SYSTEM/templates/<harness_name>/` (for setup templates copied at bootstrap).
2. Add a config template using `$HORIZON_SYSTEM` (and other runtime env vars) instead of hardcoded paths. Document all env vars used in a `README.md` in the same directory.
3. Wire event hooks to sounds in `$HORIZON_SYSTEM/sounds/`. Use root-level generic sounds for cross-harness compatibility. If the harness has vendor-voiced audio, add it to `$HORIZON_SYSTEM/sounds/<vendor>_event_sounds/`.
4. Add a statusline script to `$HORIZON_BIN/statusline/` if the harness supports one.
5. Document the harness in `$HORIZON_DOCS/`.

See `$HORIZON_ETC/ai_os_personalizations.md` Section 3 for the full harness addition protocol.

---

## Adding a Brain

A brain is an isolated AI persona running under a separate OS user account, scoped to its own directory subtree. All OS-level provisioning (user, groups, folder, permissions) is handled by `$HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py`.

### Dependencies

- **Python 3.6 or later** must be installed and on `PATH`. The script uses stdlib only — no third-party packages required.
- The script **must be run as Administrator** (Windows) or **root** (Unix). It creates OS user accounts and modifies ACLs, both of which require elevated privileges.

> **Harness installation is the Brain's own prerequisite — AIOS does not handle it.**
> A brain runs under a **separate OS user account**, and the default Claude Code install
> is **per-user**. A harness installed only for the owner is not guaranteed to be
> available to the brain user. Before a brain can actually run, that brain user must
> independently have a harness installed whose executable is on a `PATH` it can run with
> valid permissions — either its own per-user install or a system-/all-users install.
> `horizon_aios_create_brain.py` wires the brain's *config* (`.claude/CLAUDE.md`,
> `settings.json`, skills symlink) but does **not** install the brain's harness and does
> **not** verify the harness is pointed at the AIOS-redirected config. Both of those are
> deliberately left as operator responsibilities for now and may be automated for common
> harnesses in a future release. See `getting_started/dependencies_and_footprint.md` →
> "Harness installation is a per-user (and per-Brain) responsibility."

### What the script creates

Running `horizon_aios_create_brain.py` for a brain named `<brain-name>` produces:

1. **OS user account** `<brain-name>` — a local account with a password you provide interactively. On Linux the shell is set to `/bin/bash`.
2. **Group `brains`** (created once, shared by all brains) — members of this group receive read+execute access to `$HORIZON_BIN`. This is the "can use AIOS tooling" gate.
3. **Per-brain runtime group** `<brain-name>_group` (Windows) / `<brain-name>` (Unix) — the set of accounts that run *as* the brain; it receives full control on the brain's folder ("owns this brain's data"). The brain user is a member. The invoking primary user is a member **on Unix only** (there, group membership is the human's write path to the 770 folder). On **Windows the human is deliberately NOT a member** — the human gets folder full control via an explicit per-user ACE instead, so the security model can hold the runtime group read-only on the brain's edit-source (code + policy) without locking the human out. This is the writer≠runner rule; see `brains/<brain-name>/brain_bin/brain_security_model.md` §7.
4. **Brain folder** `$HORIZON_ROOT/brains/<brain-name>/` — created with parents. Permissions: owner+group full control, no access for others (mode 770 on Unix; `icacls` with `/inheritance:r` on Windows).
5. **Permissions on `$HORIZON_BIN`** — `brains` group is granted RX (additive; existing ACEs are not disturbed).
6. **Permissions on `$HORIZON_SYSTEM/sbin`** — explicitly set to owner-only (`chmod 700` on Unix; `icacls /inheritance:r /grant <primary-user>:(OI)(CI)F` on Windows) *after* the `$HORIZON_BIN` group grant, so that no inherited ACE can accidentally reach `sbin`. This step always runs last in Phase 3.

### Invocation

```bash
# Standard run (will prompt for password interactively)
python $HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py <brain-name>

# With an explicit HORIZON_ROOT (if running the script from outside the repo)
python $HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py <brain-name> --horizon-root /path/to/devroot

# Preview every action without executing (no changes made)
python $HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py <brain-name> --dry-run
```

On Windows, open an **Administrator** PowerShell or Command Prompt first:

```powershell
python "$env:HORIZON_SYSTEM\sbin\horizon_aios_create_brain.py" <brain-name>
```

On Unix:

```bash
sudo python "$HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py" <brain-name>
```

### Brain name rules

Brain names must match `^[a-z][a-z0-9_]{1,31}$`: start with a lowercase letter, followed by 1 to 31 lowercase letters, digits, or underscores. Total length: 2–32 characters. The script validates this and exits with a clear message if the name is invalid.

### After provisioning

The script handles the following automatically:
- Generates a cryptographically random 64-character account password and stores it in the OS native keystore (Windows Credential Manager / macOS Keychain / Linux Secret Service) via `horizon_aios_brain_credential.py` in sbin. The password is never written to any file and is never printed to the terminal.
- Deploys `.claude/CLAUDE.md` and `.claude/settings.json` from `.aioscommon` templates into the brain's folder.
- Writes a shell profile for the brain user that sets all `HORIZON_*` environment variables and changes the working directory to the brain's folder on interactive login.

Complete the brain's configuration manually after provisioning:

1. Customize `$HORIZON_ROOT/brains/<brain-name>/.claude/CLAUDE.md` to define the brain's persona and operational scope.
2. Customize `$HORIZON_ROOT/brains/<brain-name>/.claude/settings.json` to scope allowed tools.
3. Place any credentials this brain needs in the brain's own folder or the OS credential store.

**Account password:** Required for Windows `runas` invocations and Task Scheduler. Retrieve it from the OS keystore: `python $HORIZON_SYSTEM/sbin/horizon_aios_brain_credential.py get <brain-name>` (must be run as Administrator / root). To rotate the password (updates both the OS account and keystore): `python $HORIZON_SYSTEM/sbin/horizon_aios_brain_credential.py rotate <brain-name>`.

**Scheduled tasks and cron jobs:**
- Windows: Task Scheduler → "Run as user" → enter `<brain-name>` and retrieve password via `horizon_aios_brain_credential.py get <brain-name>` (run as Administrator).
- Linux/macOS: `sudo crontab -u <brain-name> -e` — no password needed when using sudo.

The script prints a summary and next-steps reminder at the end of every run.

### Error handling and rollback

The script runs in four phases (Preflight → User/Groups → Folders/Permissions → Verify) and wraps each phase in a try/except block. If a phase fails, it prints what completed, what failed, and manual cleanup instructions. **There is no automatic rollback** — this is by design, to avoid silently destroying partially-created state. Follow the printed cleanup instructions if you need to remove a partially provisioned brain.

See `$HORIZON_ETC/security_invariants.md` for the full ownership and ACL model, and `$HORIZON_ETC/ai_os_personalizations.md` Section 4 for the brain persona configuration protocol.

---

## Key File Locations

| What | Path |
|---|---|
| OS repo root | `$HORIZON_ROOT` |
| All OS tooling and assets | `$HORIZON_BIN` |
| OS invariant documents | `$HORIZON_ETC` |
| User-facing documentation | `$HORIZON_DOCS` |
| Global AI instructions (canonical) | `$HORIZON_ROOT/.claude/CLAUDE.md` |
| Global settings (canonical) | `$HORIZON_ROOT/.claude/settings.json` |
| Skills (primary user source) | `$HORIZON_SYSTEM/skills_sbin/` |
| Skills (brain user source) | `$HORIZON_SYSTEM/skills_bin/` |
| Skills (machine-local user tier) | `$HORIZON_USRBIN/usr_skills/` |
| Skills (Claude Code reads here — symlink) | `~/.claude/skills/` → `skills_sbin/` |
| Handoffs (default output) | `$HORIZON_ROOT/handoffs/` |
| Objectives (default store) | `$HORIZON_ROOT/objectives/` |
| Operational logs | `$HORIZON_SYSTEM/logs/` |
| Sounds (generic) | `$HORIZON_SYSTEM/sounds/*.wav` |
| Sounds (vendor-voiced) | `$HORIZON_SYSTEM/sounds/<vendor>_event_sounds/` |
| Statusline scripts | `$HORIZON_BIN/statusline/` |
| Harness config templates | `$HORIZON_SYSTEM/templates/` |
| aios_overrides.md template | `$HORIZON_SYSTEM/templates/aios_overrides.md` |
| Git hooks | `$HORIZON_SYSTEM/harness_configs/git/hooks/` |
| Git config (portable) | `$HORIZON_SYSTEM/harness_configs/git/gitconfig` |
| Full setup guide | `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md` |
| System config reference | `$HORIZON_DOCS/system/system_configuration_reference.md` |
| File structure invariants | `$HORIZON_ETC/file_structure_invariants.md` |
| Security invariants | `$HORIZON_ETC/security_invariants.md` |
| Personalization model | `$HORIZON_ETC/ai_os_personalizations.md` |
