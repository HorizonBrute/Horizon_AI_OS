# Horizon AIOS — System Setup Guide

Horizon AIOS is a portable, Git-versioned Claude Code "operating system." The repository functions as an OS layer: it version-controls all Claude Code configuration, hooks, sounds, statusline scripts, and AI behavior instructions in one place. Any project folder placed inside `$HORIZON_ROOT` automatically inherits the full AIOS environment — Claude Code settings, sounds, statusline, and global instructions — with no per-project wiring required. Projects that need their own independent Git history simply run `git init` inside their folder, which causes Git to exclude them from the OS repo automatically. The entire environment is reproducible on a new machine by cloning the repo and running a small bootstrap sequence.

This document serves two purposes simultaneously:

1. **Human SOP** — step-by-step instructions a person can follow.
2. **Agent-executable** — structured precisely enough that an AI agent can read it and implement each step without ambiguity.

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

P.6 **GPG** — required for commit signing. `commit.gpgsign = true` is set globally, so all commits on the machine will be GPG-signed. A key must exist in the local keyring before the first commit.

P.7 **SSH client** — required for all remote Git operations. No HTTPS and no `gh` CLI are used anywhere in this system.

**Authentication**

P.8 An **SSH key pair** must exist (default: `~/.ssh/id_ed25519`) and the public key must be registered with the GitHub account (or other host) where the AIOS repo lives.

Verify: `ssh -T git@github.com` — should return an authentication acknowledgement (not a permission denied error).

P.9 A **GPG key** must be generated and available in the local keyring. The key fingerprint must be entered in `$HORIZON_BIN/harness_configs/git/gitconfig` during setup.

Verify: `gpg --list-secret-keys --keyid-format LONG` — must show at least one secret key.

**Platform**

P.10 Horizon AIOS supports **Windows, Linux, and macOS**. Platform routing is handled automatically:

P.10.1 **Sound playback** uses `$HORIZON_BIN/sounds/play_sound.sh`, which detects the OS at runtime and calls `Media.SoundPlayer` (Windows), `afplay` (macOS), or the first available Linux player from: `paplay` (PulseAudio), `aplay` (ALSA), `ffplay` (ffmpeg), `mpg123`. Hooks fail silently if no player is found.

P.10.2 **Statusline** uses `$HORIZON_BIN/statusline/statusline.sh`, a bash dispatcher that calls `statusline-context-alerts.ps1` (PowerShell, Windows) or `statusline-command.sh` (bash, Linux/macOS) depending on OS. Both scripts include threshold audio alerts.

P.10.3 **Linux audio dependency**: at least one of `paplay`, `aplay`, `ffplay`, or `mpg123` must be installed for sounds to play on Linux. Sounds are skipped silently if none are present.

P.11 **No administrator privileges are required**. The `settings.json` bootstrap uses a hard link rather than a symlink specifically because Windows file symlinks require elevated permissions. Hard links do not. On Linux/macOS, standard `ln` is used.

P.12 **Developer Mode is not required**.

**Runtime**

P.13 **`$HORIZON_ROOT` must be a stable, permanent path.** All config files inside the repository embed this path as a literal string. If the root directory is moved or renamed after setup, path substitution must be re-run on every file listed in the Path Dependencies Catalog (see `$HORIZON_DOCS/system/system_configuration_reference.md`).

P.14 An **audio output device** must be present for sound hooks to play. If no device is available, the hooks fail silently — Claude Code operation is unaffected.

P.15 **`~/.claude/` must exist** before the bootstrap commands are run. Claude Code creates this directory on first launch. If it does not exist, run `claude` once and exit before proceeding with setup.

P.16 **`.git/info/exclude`** in the OS repo is managed automatically by the pre-commit hook (synced from `.gitignore.user`). Do not edit this file manually — changes will be overwritten on the next commit.

---

## 1. What Is $HORIZON_ROOT

`$HORIZON_ROOT` is the root folder of the Horizon AIOS installation on this machine. It is the absolute path where the Horizon AIOS repository lives. Every path reference inside the repository — in settings, scripts, and config files — is expressed relative to this root. When setting up a new machine, this path is chosen once and substituted everywhere.

`$HORIZON_ROOT` is itself a Git repository (the OS repo). It tracks the config and asset layer. Individual project folders placed inside it are expected to have their own Git repos and are automatically excluded from OS repo tracking the moment they are `git init`'d.

The following environment variables derive from `$HORIZON_ROOT` and must be set in your shell profile before proceeding:

| Variable | Points To | Purpose |
|---|---|---|
| `$HORIZON_ROOT` | The repo root (e.g., `C:\devroot`) | Anchor for all other paths |
| `$HORIZON_BIN` | `$HORIZON_ROOT/horizon_bin` | Tooling, scripts, sounds, templates, assets |
| `$HORIZON_ETC` | `$HORIZON_ROOT/horizon_bin/ai_os_etc` | OS configuration documents and invariants |
| `$HORIZON_DOCS` | `$HORIZON_ROOT/horizon_bin/documentation` | User-facing documentation |

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

3.1 Decide the absolute path where Horizon AIOS will live on this machine. This is `$HORIZON_ROOT`. Example: `C:\devroot` on Windows, `/home/username/devroot` on Linux/macOS. This path must be stable — moving it later requires re-running path substitution on multiple files.

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
git clone git@github.com:HorizonBrute/HorizonAIOS.git "$HORIZON_ROOT"
```

Note: replace the URL with the actual repo URL once published. The placeholder above is the expected canonical location.

3.4 Confirm the clone succeeded by verifying these paths exist:

```
$HORIZON_ROOT/.claude/settings.json
$HORIZON_ROOT/.claude/CLAUDE.md
$HORIZON_BIN/statusline/statusline-context-alerts.ps1
$HORIZON_BIN/harness_configs/git/hooks/pre-commit
$HORIZON_ROOT/.gitignore.user
```

---

## 4. Set Environment Variables

AIOS scripts and documentation reference `$HORIZON_ROOT`, `$HORIZON_BIN`, `$HORIZON_ETC`, and `$HORIZON_DOCS`. These must be set in your shell profile so they are available in every terminal session.

4.1 Add the following to your shell profile (`~/.bashrc`, `~/.zshrc`, or equivalent). Replace the example path with your actual `$HORIZON_ROOT` path.

```bash
export HORIZON_ROOT="/path/to/your/devroot"
export HORIZON_BIN="$HORIZON_ROOT/horizon_bin"
export HORIZON_ETC="$HORIZON_ROOT/horizon_bin/ai_os_etc"
export HORIZON_DOCS="$HORIZON_ROOT/horizon_bin/documentation"
```

On Windows with Git Bash, add these lines to `~/.bash_profile` or `~/.bashrc` inside Git Bash. In PowerShell sessions, set them via System Environment Variables or your PowerShell profile (`$PROFILE`).

4.2 Reload your shell profile: `source ~/.bashrc` (or open a new terminal).

4.3 Verify: `echo $HORIZON_ROOT` should print the path you set.

### 4.4 Persist environment variables to your shell profile

The bootstrap script (Step 5) sets environment variables ephemerally for the current session only. It does **not** modify your shell profile. You must add the variables to your profile manually once per machine so they are available in every new terminal session.

**Windows (PowerShell profile):** Add the following to your PowerShell profile (open it with `notepad $PROFILE`):

```powershell
$env:HORIZON_ROOT = "C:\devroot"   # your actual path
$env:HORIZON_BIN  = "$env:HORIZON_ROOT\horizon_bin"
$env:HORIZON_ETC  = "$env:HORIZON_BIN\ai_os_etc"
$env:HORIZON_DOCS = "$env:HORIZON_BIN\documentation"
```

**Linux/macOS (bash/zsh profile):** Add the following to `~/.bashrc` or `~/.zshrc`:

```bash
export HORIZON_ROOT="$HOME/devroot"   # your actual path
export HORIZON_BIN="$HORIZON_ROOT/horizon_bin"
export HORIZON_ETC="$HORIZON_BIN/ai_os_etc"
export HORIZON_DOCS="$HORIZON_BIN/documentation"
```

After editing, reload your profile (`source ~/.bashrc` or open a new terminal) and verify with `echo $HORIZON_ROOT`.

---

## 5. Run the Bootstrap Script (Recommended)

The bootstrap script automates Steps 6–8 below. Run it once after cloning. It is safe to run multiple times.

**Git Bash / macOS / Linux:**
```bash
bash "$HORIZON_BIN/bootstrap.sh"
```

**PowerShell (Windows):**
```powershell
& "$env:HORIZON_BIN\bootstrap.ps1"
```

The script will:
- Create `~/.claude/CLAUDE.md` with the `@` redirect (Step 6)
- Deploy all skills from `$HORIZON_BIN/skills/` to `~/.claude/skills/` (Step 7)
- Offer to copy `settings.json` from the template (Step 8)
- Create `$HORIZON_ROOT/handoffs/`
- Wire git `core.hooksPath`
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

- `~/.claude/settings.json` (global) owns hooks, statusLine, and global permissions. It contains machine-specific paths and must not be committed.
- `$HORIZON_ROOT/.claude/settings.json` (devroot project-level) owns only devroot-scoped permissions and is committed to the OS repo.

Copy the global settings template and substitute the `HORIZON_BIN_PATH` placeholder with your actual `$HORIZON_BIN` path.

Windows (PowerShell):

```powershell
Copy-Item "$HORIZON_BIN\templates\claude_code\settings.json" "$HOME\.claude\settings.json"
(Get-Content "$HOME\.claude\settings.json") -replace "HORIZON_BIN_PATH", "$HORIZON_BIN" | Set-Content "$HOME\.claude\settings.json"
```

Linux / macOS (bash):

```bash
cp "$HORIZON_BIN/templates/claude_code/settings.json" "$HOME/.claude/settings.json"
sed -i "s|HORIZON_BIN_PATH|$HORIZON_BIN|g" "$HOME/.claude/settings.json"
```

Do not link or copy `$HORIZON_ROOT/.claude/settings.json` to `~/.claude/settings.json` — they are different files with different owners.

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

## 7. Deploy Skills

AIOS skills live at `$HORIZON_BIN/skills/`. Claude Code picks up skills from `~/.claude/skills/`. Deploy by copying or symlinking.

7.1 Create the target directory if it does not exist:

```bash
mkdir -p ~/.claude/skills
```

7.2 Copy all skill files into place. Repeat for each new skill when AIOS is updated:

```bash
cp "$HORIZON_BIN/skills/"*.md ~/.claude/skills/
```

Alternatively, create individual symlinks (preferred if you want changes to `$HORIZON_BIN/skills/` to take effect automatically):

Linux / macOS:
```bash
for f in "$HORIZON_BIN/skills/"*.md; do
  ln -sf "$f" ~/.claude/skills/
done
```

Windows (PowerShell — requires developer mode or admin for symlinks; use copy if unavailable):
```powershell
foreach ($f in Get-ChildItem "$env:HORIZON_BIN\skills\*.md") {
  Copy-Item $f.FullName "$HOME\.claude\skills\"
}
```

7.3 Verify: `ls ~/.claude/skills/` should list `handoff.md` and any other skills in `$HORIZON_BIN/skills/`.

7.4 Important: **skills are loaded when a Claude Code session starts, not hot-reloaded.** If you deploy a skill while a session is running, start a new session before testing it.

7.5 Troubleshooting — if a skill is not recognized after deploying:

1. Confirm the file exists: `ls ~/.claude/skills/handoff.md`
2. Start a **fresh** Claude Code session (not a continuation of a long-running one). Skills are session-scoped and very long sessions can lose skill registration.
3. Confirm the skill file is valid: it must be a `.md` file whose content Claude Code can parse as a skill definition. The source-of-truth copy in `$HORIZON_BIN/skills/` is always canonical — if the deployed copy diverges, redeploy from source.
4. Run `doctor.py` to confirm skills are detected: `python "$HORIZON_BIN/sbin/doctor.py"`

---

## 8. Update Path-Sensitive Strings in the Repository

Several files inside the repository contain hardcoded paths that must reference `$HORIZON_ROOT` on this machine. Run each substitution below.

8.1 **`$HORIZON_ROOT/.claude/settings.json`** — contains four path references:

8.1.1 `statusLine.command` — path to `statusline-context-alerts.ps1`

8.1.2 `hooks.Stop[0].hooks[0].command` — path to `WorkComplete_ork.wav`

8.1.3 `hooks.PermissionRequest[0].hooks[0].command` — path to `InputNeeded.wav`

8.1.4 `hooks.StopFailure[0].hooks[0].command` — path to `APIFail.wav`

Open `settings.json` in an editor and replace every occurrence of the previous machine's root path with `$HORIZON_ROOT`. PowerShell one-liner:

```powershell
(Get-Content "$HORIZON_ROOT\.claude\settings.json") -replace [regex]::Escape("C:\devroot"), "$HORIZON_ROOT" | Set-Content "$HORIZON_ROOT\.claude\settings.json"
```

Linux / macOS (bash):
```bash
sed -i "s|/old/path/to/devroot|$HORIZON_ROOT|g" "$HORIZON_ROOT/.claude/settings.json"
```

Replace the old path with whatever root path is currently embedded in the file (check with `grep -n "devroot\|horizon" "$HORIZON_ROOT/.claude/settings.json" | head -20`).

8.2 **`$HORIZON_BIN/statusline/statusline-context-alerts.ps1`** — line containing the statusline threshold wav path:

```powershell
(Get-Content "$HORIZON_BIN\statusline\statusline-context-alerts.ps1") -replace [regex]::Escape("C:\devroot"), "$HORIZON_ROOT" | Set-Content "$HORIZON_BIN\statusline\statusline-context-alerts.ps1"
```

8.3 **`$HORIZON_BIN/harness_configs/git/gitconfig`** — the `excludesfile` field and user identity:

Open the file and set:

```
[user]
    name = Your Name
    email = your@email.com
    signingkey = YOUR_GPG_KEY_FINGERPRINT

[core]
    excludesfile = $HORIZON_ROOT/.gitignore_global
```

8.4 See `$HORIZON_DOCS/system/system_configuration_reference.md` Section 3 for the full Path Dependencies Catalog — every file that contains hardcoded paths.

---

## 9. Apply the Portable Git Configuration

9.1 Include the repository's gitconfig from your global git config:

```bash
git config --global include.path "$HORIZON_BIN/harness_configs/git/gitconfig"
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
git config --local core.hooksPath ./horizon_bin/harness_configs/git/hooks
```

10.3 Stage the OS layer files:

```bash
git add .claude/CLAUDE.md .claude/settings.json horizon_bin/ handoffs/ .gitignore .gitignore.user
```

Do not stage `settings.local.json` — it is machine-local and excluded by `.gitignore`.

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

`$HORIZON_ROOT/.gitignore.user` is a tracked file for user-personal ignore patterns. It is separate from the system `.gitignore` so personal exclusions do not intermingle with OS-managed patterns.

11.1 The pre-commit hook automatically syncs `.gitignore.user` to `.git/info/exclude` on every commit, so Git always respects the current contents. Changes made to `.gitignore.user` take effect at the next commit — there is no manual sync step.

11.2 To exclude a personal folder, add it to `.gitignore.user`:

```
MyPersonalNotes/
scratch/
```

Then commit:

```bash
git add .gitignore.user
git commit -m "Add personal ignore patterns"
```

Git will respect the new patterns from that commit forward.

11.3 `.gitignore.user` is version-controlled and therefore portable. On a new machine it is cloned with the rest of the repository and activated automatically on the first commit.

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

14.3 Run the `/handoff` skill to confirm skills are loaded. Type `/handoff` in the Claude Code session. Claude should execute the handoff skill and write a file to `$HORIZON_ROOT/handoffs/`. If the skill is not recognized, see Section 7.5 troubleshooting — the most common cause is testing in the same long-running session used during setup rather than starting a fresh session.

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

Should return `./horizon_bin/harness_configs/git/hooks`.

Setup is complete when all verification points pass.

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
   cp "$HORIZON_BIN/templates/aios_overrides.md" "$HORIZON_ROOT/MyProject/aios_overrides.md"
   ```
   Edit the file to set `handoffs_dir`, `project_display_name`, or other overrides. See the template for documentation of all supported keys.

4. Optionally create a `.claude/CLAUDE.md` inside the project for project-specific AI instructions:
   ```bash
   mkdir -p "$HORIZON_ROOT/MyProject/.claude"
   # Edit $HORIZON_ROOT/MyProject/.claude/CLAUDE.md with project context
   ```
   Project-level CLAUDE.md is loaded by Claude Code on top of the global CLAUDE.md when working inside that project.

---

## Adding a New AI Harness

Horizon AIOS supports multiple AI harnesses. To add support for a new harness (e.g., Cursor, Windsurf, Ollama):

1. Create a template directory: `$HORIZON_BIN/templates/<harness_name>/`
2. Add a config template using `HORIZON_BIN_PATH` and other placeholders instead of real paths. Document all placeholders in a `README.md` in the same directory.
3. Wire event hooks to sounds in `$HORIZON_BIN/sounds/`. Use root-level generic sounds for cross-harness compatibility. If the harness has vendor-voiced audio, add it to `$HORIZON_BIN/sounds/<vendor>_event_sounds/`.
4. Add a statusline script to `$HORIZON_BIN/statusline/` if the harness supports one.
5. Document the harness in `$HORIZON_DOCS/`.

See `$HORIZON_ETC/ai_os_personalizations.md` Section 3 for the full harness addition protocol.

---

## Adding a Brain

A brain is an isolated AI persona running under a separate OS user account, scoped to its own directory subtree. All OS-level provisioning (user, groups, folder, permissions) is handled by `$HORIZON_BIN/scripts/create_brain.py`.

### Dependencies

- **Python 3.6 or later** must be installed and on `PATH`. The script uses stdlib only — no third-party packages required.
- The script **must be run as Administrator** (Windows) or **root** (Unix). It creates OS user accounts and modifies ACLs, both of which require elevated privileges.

### What the script creates

Running `create_brain.py` for a brain named `<brain-name>` produces:

1. **OS user account** `<brain-name>` — a local account with a password you provide interactively. On Linux the shell is set to `/bin/bash`.
2. **Group `brains`** (created once, shared by all brains) — members of this group receive read+execute access to `$HORIZON_BIN`. This is the "can use AIOS tooling" gate.
3. **Group `<brain-name>`** (brain-specific) — the brain user and the invoking primary user are both members. This group receives full control on the brain's folder. This is the "owns this brain's data" gate.
4. **Brain folder** `$HORIZON_ROOT/brains/<brain-name>/` — created with parents. Permissions: owner+group full control, no access for others (mode 770 on Unix; `icacls` with `/inheritance:r` on Windows).
5. **Permissions on `$HORIZON_BIN`** — `brains` group is granted RX (additive; existing ACEs are not disturbed).
6. **Permissions on `$HORIZON_BIN/sbin`** — explicitly set to owner-only (`chmod 700` on Unix; `icacls /inheritance:r /grant <primary-user>:(OI)(CI)F` on Windows) *after* the `horizon_bin` group grant, so that no inherited ACE can accidentally reach `sbin`. This step always runs last in Phase 3.

### Invocation

```bash
# Standard run (will prompt for password interactively)
python $HORIZON_BIN/scripts/create_brain.py <brain-name>

# With an explicit HORIZON_ROOT (if running the script from outside the repo)
python $HORIZON_BIN/scripts/create_brain.py <brain-name> --horizon-root /path/to/devroot

# Preview every action without executing (no changes made)
python $HORIZON_BIN/scripts/create_brain.py <brain-name> --dry-run
```

On Windows, open an **Administrator** PowerShell or Command Prompt first:

```powershell
python "$env:HORIZON_BIN\scripts\create_brain.py" <brain-name>
```

On Unix:

```bash
sudo python "$HORIZON_BIN/scripts/create_brain.py" <brain-name>
```

### Brain name rules

Brain names must match `^[a-z][a-z0-9_]{1,31}$`: start with a lowercase letter, followed by 1 to 31 lowercase letters, digits, or underscores. Total length: 2–32 characters. The script validates this and exits with a clear message if the name is invalid.

### After provisioning

Once the script finishes, complete the brain's configuration manually:

1. Create `$HORIZON_ROOT/brains/<brain-name>/.claude/settings.json` scoped to the brain's allowed tools and permissions.
2. Create `$HORIZON_ROOT/brains/<brain-name>/CLAUDE.md` defining the brain's persona and operational scope. You may start with `@$HORIZON_ROOT/.claude/CLAUDE.md` to inherit system-level instructions.

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
| Skills (source of truth) | `$HORIZON_BIN/skills/` |
| Skills (deployed, Claude Code reads here) | `~/.claude/skills/` |
| Handoffs (default output) | `$HORIZON_ROOT/handoffs/` |
| Sounds (generic) | `$HORIZON_BIN/sounds/*.wav` |
| Sounds (vendor-voiced) | `$HORIZON_BIN/sounds/<vendor>_event_sounds/` |
| Statusline scripts | `$HORIZON_BIN/statusline/` |
| Harness config templates | `$HORIZON_BIN/templates/` |
| aios_overrides.md template | `$HORIZON_BIN/templates/aios_overrides.md` |
| Git hooks | `$HORIZON_BIN/harness_configs/git/hooks/` |
| Git config (portable) | `$HORIZON_BIN/harness_configs/git/gitconfig` |
| Full setup guide | `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md` |
| System config reference | `$HORIZON_DOCS/system/system_configuration_reference.md` |
| File structure invariants | `$HORIZON_ETC/file_structure_invariants.md` |
| Security invariants | `$HORIZON_ETC/security_invariants.md` |
| Personalization model | `$HORIZON_ETC/ai_os_personalizations.md` |
