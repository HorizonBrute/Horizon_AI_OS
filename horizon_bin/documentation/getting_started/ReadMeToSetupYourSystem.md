# Horizon AIOS — System Setup Guide

Horizon AIOS is a portable, Git-versioned Claude Code "operating system." The repository functions as an OS layer: it version-controls all Claude Code configuration, hooks, sounds, statusline scripts, and AI behavior instructions in one place. Any project folder placed inside `Horizon_AI_OS_Root` automatically inherits the full AIOS environment — Claude Code settings, sounds, statusline, and global instructions — with no per-project wiring required. Projects that need their own independent Git history simply run `git init` inside their folder, which causes Git to exclude them from the OS repo automatically. The entire environment is reproducible on a new machine by cloning the repo and running a small bootstrap sequence.

---

## AGENT SETUP PROTOCOL

> This section is addressed to any agent reading this file to perform setup on behalf of a user.
> Follow these steps exactly and in order. Do not proceed past step A.2 until the user has confirmed.

**A.1** Before doing anything else, ask the user:

> "Where would you like to place your Horizon_AI_OS_Root directory on this system? This is the folder the Horizon AIOS repository will be cloned into — for example `C:\devroot` on Windows or `/home/username/devroot` on Linux/Mac. Please provide the full absolute path."

**A.2** Wait for the user's answer. Store it as `Horizon_AI_OS_Root`. Confirm back:

> "I'll use `{the path they gave}` as Horizon_AI_OS_Root. Proceeding with setup."

**A.3** Substitute `Horizon_AI_OS_Root` with the confirmed path in every command and file edit that follows in this document. Do not use `C:\devroot` or any other hardcoded path — only the path the user provided.

**A.4** Work through sections 1 through 10 of this document in order, completing each step before moving to the next.

---

## Presumptions / Dependencies

The following are required for Horizon AIOS to function. Verify each before beginning setup.

**Software**

P.1 **Git 2.9 or later** — version 2.9 introduced `core.hooksPath`, which is how the version-controlled pre-commit hook is wired in. Earlier versions will silently ignore the hook.

P.2 **Claude Code CLI** — the application this system configures. Must be installed before bootstrap.

P.3 **PowerShell** — required on Windows only. The Windows statusline script (`statusline-context-alerts.ps1`) and sound player both use PowerShell, which is built-in on Windows. On Linux and macOS, the bash statusline script and `play_sound.sh` are used instead — `pwsh` is not required on those platforms.

P.4 **GPG** — required for commit signing. `commit.gpgsign = true` is set globally, so all commits on the machine will be GPG-signed. A key must exist in the local keyring before the first commit.

P.5 **SSH client** — required for all remote Git operations. No HTTPS and no `gh` CLI are used anywhere in this system.

**Authentication**

P.6 An **SSH key pair** must exist (default: `~/.ssh/id_ed25519`) and the public key must be registered with the GitHub account (or other host) where the AIOS repo lives.

P.7 A **GPG key** must be generated and available in the local keyring. The key fingerprint must be entered in `horizon_bin/harness_configs/git/gitconfig` during setup.

**Platform**

P.8 Horizon AIOS supports **Windows, Linux, and macOS**. Platform routing is handled automatically:

P.8.1 **Sound playback** uses `horizon_bin/sounds/play_sound.sh`, which detects the OS at runtime and calls `Media.SoundPlayer` (Windows), `afplay` (macOS), or the first available Linux player from: `paplay` (PulseAudio), `aplay` (ALSA), `ffplay` (ffmpeg), `mpg123`. Hooks fail silently if no player is found.

P.8.2 **Statusline** uses `horizon_bin/statusline/statusline.sh`, a bash dispatcher that calls `statusline-context-alerts.ps1` (PowerShell, Windows) or `statusline-command.sh` (bash, Linux/macOS) depending on OS. Both scripts include threshold audio alerts.

P.8.3 **Linux audio dependency**: at least one of `paplay`, `aplay`, `ffplay`, or `mpg123` must be installed for sounds to play on Linux. Sounds are skipped silently if none are present.

P.9 **No administrator privileges are required**. The `settings.json` bootstrap uses a hard link rather than a symlink specifically because Windows file symlinks require elevated permissions. Hard links do not. On Linux/macOS, standard `ln` is used.

P.10 **Developer Mode is not required**.

**Runtime**

P.11 **`Horizon_AI_OS_Root` must be a stable, permanent path.** All config files inside the repository embed this path as a literal string. If the root directory is moved or renamed after setup, path substitution must be re-run on every file listed in the Path Dependencies Catalog (see `horizon_bin/documentation/system/system_configuration_reference.md`).

P.12 An **audio output device** must be present for sound hooks to play. If no device is available, the hooks fail silently — Claude Code operation is unaffected.

P.13 **`~/.claude/` must exist** before the bootstrap commands are run. Claude Code creates this directory on first launch. If it does not exist, run `claude` once and exit before proceeding with setup.

P.14 **`.git/info/exclude`** in the OS repo is managed automatically by the pre-commit hook (synced from `.gitignore.user`). Do not edit this file manually — changes will be overwritten on the next commit.

---

## 1. What Is Horizon_AI_OS_Root

`Horizon_AI_OS_Root` is the root folder of the Horizon AIOS installation on this machine. It is the absolute path where the Horizon AIOS repository lives. Every path reference inside the repository — in settings, scripts, and config files — is expressed relative to this root. When setting up a new machine, this path is chosen once and substituted everywhere.

`Horizon_AI_OS_Root` is itself a Git repository (the OS repo). It tracks the config and asset layer. Individual project folders placed inside it are expected to have their own Git repos and are automatically excluded from OS repo tracking the moment they are `git init`'d.

---

## 2. Prerequisites

Complete all prerequisites before beginning setup. Each must be true before proceeding.

2.1 **Git 2.9 or later** is installed and available on `PATH`. Version 2.9+ is required for `core.hooksPath`, which wires the version-controlled pre-commit hook. Verify: `git --version`

2.2 **SSH key** exists at `~/.ssh/id_ed25519` (or another key of your choice) and the corresponding public key is registered with your GitHub account (or whichever Git host the Horizon AIOS repo is on). Verify: `ssh -T git@github.com` should return an authentication success message.

2.3 **GPG key** is generated and available in your keyring. Commit signing is enabled globally. Verify: `gpg --list-secret-keys --keyid-format LONG` should show at least one secret key. Note the full fingerprint — you will need it in step 5.3.

2.4 **Claude Code** is installed. Verify: `claude --version`

2.5 **PowerShell** is available (Windows: built-in; Linux/Mac: install `pwsh`). The statusline script requires PowerShell.

---

## 3. Clone the Repository

3.1 Create the parent directory if it does not already exist:

```powershell
New-Item -ItemType Directory -Force "{Horizon_AI_OS_Root}"
```

3.2 Clone the Horizon AIOS repository into `Horizon_AI_OS_Root`:

```bash
git clone git@github.com:HorizonBrute/HorizonAIOS.git "{Horizon_AI_OS_Root}"
```

3.3 Confirm the clone succeeded by verifying these paths exist:

```
{Horizon_AI_OS_Root}\.claude\settings.json
{Horizon_AI_OS_Root}\.claude\CLAUDE.md
{Horizon_AI_OS_Root}\horizon_bin\statusline\statusline-context-alerts.ps1
{Horizon_AI_OS_Root}\horizon_bin\harness_configs\git\hooks\pre-commit
{Horizon_AI_OS_Root}\.gitignore.user
```

---

## 4. Bootstrap the Claude Code Global Configuration

Claude Code always reads its global configuration from `~/.claude/`. These two bootstrap steps redirect that global configuration into the repository so it is version-controlled.

4.1 **Bootstrap `~/.claude/CLAUDE.md`**

Create the file `~/.claude/CLAUDE.md` with a single line that includes the repository's CLAUDE.md.

Windows (PowerShell):

```powershell
Set-Content -Path "$HOME\.claude\CLAUDE.md" -Value "@{Horizon_AI_OS_Root}\.claude\CLAUDE.md"
```

Linux / macOS (bash):

```bash
echo "@{Horizon_AI_OS_Root}/.claude/CLAUDE.md" > "$HOME/.claude/CLAUDE.md"
```

This file must contain only that one line. Claude Code will follow the `@` include and load the full instructions from the repository.

4.2 **Bootstrap `~/.claude/settings.json`**

If `~/.claude/settings.json` already exists, remove it first.

Windows (PowerShell):

```powershell
Remove-Item "$HOME\.claude\settings.json" -Force -ErrorAction SilentlyContinue
New-Item -ItemType HardLink -Path "$HOME\.claude\settings.json" -Target "{Horizon_AI_OS_Root}\.claude\settings.json"
```

Linux / macOS (bash):

```bash
rm -f "$HOME/.claude/settings.json"
ln "{Horizon_AI_OS_Root}/.claude/settings.json" "$HOME/.claude/settings.json"
```

A hard link is used instead of a symlink so no elevated privileges are required on any platform. Any edit to either path is immediately reflected in the other — there is no sync step.

4.3 Verify both files are in place.

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

## 5. Update Path-Sensitive Strings in the Repository

Several files inside the repository contain hardcoded paths that must reference `Horizon_AI_OS_Root` on this machine. Run each substitution below, replacing `{Horizon_AI_OS_Root}` with your actual path. On Windows, use backslashes in the replacement values.

5.1 **`{Horizon_AI_OS_Root}\.claude\settings.json`** — contains four path references:

5.1.1 `statusLine.command` — path to `statusline-context-alerts.ps1`

5.1.2 `hooks.Stop[0].hooks[0].command` — path to `WorkComplete_ork.wav`

5.1.3 `hooks.PermissionRequest[0].hooks[0].command` — path to `InputNeeded.wav`

5.1.4 `hooks.StopFailure[0].hooks[0].command` — path to `APIFail.wav`

Open `settings.json` in an editor and replace every occurrence of the previous machine's root path with `{Horizon_AI_OS_Root}`. PowerShell one-liner:

```powershell
(Get-Content "{Horizon_AI_OS_Root}\.claude\settings.json") -replace [regex]::Escape("C:\devroot"), "{Horizon_AI_OS_Root}" | Set-Content "{Horizon_AI_OS_Root}\.claude\settings.json"
```

5.2 **`{Horizon_AI_OS_Root}\horizon_bin\statusline\statusline-context-alerts.ps1`** — line containing `claude_at_${new_threshold}_statusline.wav` path:

```powershell
(Get-Content "{Horizon_AI_OS_Root}\horizon_bin\statusline\statusline-context-alerts.ps1") -replace [regex]::Escape("C:\devroot"), "{Horizon_AI_OS_Root}" | Set-Content "{Horizon_AI_OS_Root}\horizon_bin\statusline\statusline-context-alerts.ps1"
```

5.3 **`{Horizon_AI_OS_Root}\horizon_bin\harness_configs\git\gitconfig`** — the `excludesfile` field and user identity:

Open the file and set:

```
[user]
    name = Your Name
    email = your@email.com
    signingkey = YOUR_GPG_KEY_FINGERPRINT

[core]
    excludesfile = {Horizon_AI_OS_Root}\.gitignore_global
```

---

## 6. Apply the Portable Git Configuration

6.1 Include the repository's gitconfig from your global git config:

```bash
git config --global include.path "{Horizon_AI_OS_Root}/horizon_bin/harness_configs/git/gitconfig"
```

6.2 Verify git picks up the settings:

```bash
git config --global user.email
git config --global commit.gpgsign
```

Both should return the values from the repository's gitconfig.

---

## 7. Initialize the OS Git Repo

The OS repo at `Horizon_AI_OS_Root` tracks the AIOS config layer. This step initializes it on the new machine, wires the version-controlled pre-commit hook, and creates the first commit.

7.1 Initialize the repository:

```bash
cd "{Horizon_AI_OS_Root}"
git init
```

7.2 Wire the version-controlled hooks directory. This tells Git to use the hooks stored in the repository rather than `.git/hooks/`, so hook changes are committed and portable:

```bash
git config --local core.hooksPath ./horizon_bin/harness_configs/git/hooks
```

7.3 Stage the OS layer files:

```bash
git add .claude/CLAUDE.md .claude/settings.json horizon_bin/ handoffs/ .gitignore .gitignore.user
```

Do not stage `settings.local.json` — it is machine-local and excluded by `.gitignore`.

7.4 Create the initial commit. GPG signing fires automatically because `commit.gpgsign = true` is set in the global gitconfig:

```bash
git commit -m "Initial Horizon AIOS OS layer commit"
```

7.5 Verify the commit is GPG-signed:

```bash
git log --show-signature -1
```

The output should include a `gpg: Good signature` line.

---

## 8. Personal Ignore Layer — `.gitignore.user`

`{Horizon_AI_OS_Root}\.gitignore.user` is a tracked file for user-personal ignore patterns. It is separate from the system `.gitignore` so personal exclusions do not intermingle with OS-managed patterns.

8.1 The pre-commit hook automatically syncs `.gitignore.user` to `.git/info/exclude` on every commit, so Git always respects the current contents. Changes made to `.gitignore.user` take effect at the next commit — there is no manual sync step.

8.2 To exclude a personal folder, add it to `.gitignore.user`:

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

8.3 `.gitignore.user` is version-controlled and therefore portable. On a new machine it is cloned with the rest of the repository and activated automatically on the first commit.

---

## 9. Project Isolation Pattern

Any folder inside `Horizon_AI_OS_Root` that needs its own independent Git history is isolated from the OS repo by running `git init` inside it. This is the universal opt-out mechanism — no `.gitignore` entry is required.

9.1 **How it works natively**: Git does not descend into subdirectories that contain their own `.git` folder. Once a subfolder is git-initted, its contents become invisible to the parent OS repo.

9.2 **The pre-commit hook handles the race condition**: If a folder was tracked by the OS repo and then later `git init`'d, its files remain in the OS index until removed. The pre-commit hook detects any tracked subdirectory that has acquired a `.git` folder and runs `git rm -r --cached` on it automatically before the commit completes. No manual cleanup is needed.

9.3 **Recursive exclusion**: The exclusion is recursive. If `ProjectParent/` contains `SubProject/` which gets `git init`'d, `SubProject/` is excluded. If `ProjectParent/` itself later gets `git init`'d, the entire `ProjectParent/` tree is excluded from that point forward.

9.4 **Excluding a parent folder with no direct `.git`**: To exclude an entire parent folder (such as a `RedTeam/` directory that will hold multiple independent projects), run `git init` inside the parent folder itself. This makes the parent a nested repo and excludes the entire subtree:

```bash
git init "{Horizon_AI_OS_Root}/RedTeam"
```

No remote is needed. The local `.git` is sufficient to trigger exclusion.

9.5 **Config inheritance**: Projects inside `Horizon_AI_OS_Root` automatically inherit the AIOS Claude Code environment — the global `settings.json` (hooks, sounds, statusline, permissions) and `CLAUDE.md` instructions apply in every subdirectory because Claude Code reads global config from `~/.claude/`, which is bootstrapped to point into the OS repo. No per-project configuration is needed to get the full AIOS experience.

---

## 10. Create a Machine-Local `settings.local.json`

`settings.local.json` is not version-controlled. It holds permission overrides that are specific to this machine. Create it fresh on each machine:

10.1 Create the file at `{Horizon_AI_OS_Root}\.claude\settings.local.json`:

```json
{
  "permissions": {
    "allow": []
  }
}
```

10.2 Add machine-specific permission entries to the `allow` array as needed during normal use. Claude Code will prompt for permission on first use of any tool not yet in the list — approve it and it will be added automatically.

---

## 11. Verify the Installation

11.1 Launch Claude Code from any directory:

```bash
claude
```

11.2 Confirm the statusline appears at the bottom of the terminal showing the current directory name, git branch (if in a repo), and a context usage bar. If the statusline is absent, check that `settings.json` `statusLine.command` points to the correct path.

11.3 Exit Claude Code cleanly. Confirm the WorkComplete sound plays. If no sound plays, verify the path in `hooks.Stop[0].hooks[0].command` in `settings.json`.

11.4 Trigger a permission request (run any tool not in the allow list). Confirm the InputNeeded sound plays.

11.5 Verify the OS repo commit is GPG-signed:

```bash
cd "{Horizon_AI_OS_Root}"
git log --show-signature -1
```

Confirm a `gpg: Good signature` line appears.

11.6 Verify the pre-commit hook is active:

```bash
git config --local core.hooksPath
```

Should return `./horizon_bin/harness_configs/git/hooks`.

Setup is complete.
