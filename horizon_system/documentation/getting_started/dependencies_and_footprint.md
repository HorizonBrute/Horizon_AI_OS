# Horizon AIOS — Dependencies and System Footprint Reference

Declarative reference for what Horizon AIOS requires before installation and what
it changes on the machine. Use this document to answer "what do I need?" and "what
will change?" without reading through the procedural setup guide.

For step-by-step installation instructions, see
`getting_started/ReadMeToSetupYourSystem.md`.

---

## Section 1 — Dependencies

All dependencies must be satisfied before running bootstrap. No bootstrap step
installs these for you.

| Dependency | Required / Optional | Why needed | Windows | macOS | Linux |
|---|---|---|---|---|---|
| **Git 2.9+** | Required | `core.hooksPath` (introduced in 2.9) wires the version-controlled pre-commit hook; earlier versions silently ignore it | `winget install Git.Git` | `brew install git` | `apt install git` / `dnf install git` |
| **Claude Code CLI** | Required | The AI harness AIOS configures; must exist at `~/.claude/` before bootstrap | `npm install -g @anthropic-ai/claude-code` | Same | Same |
| **Python 3.6+** | Required | `bootstrap.ps1`/`bootstrap.sh` call `aios_switch.py`, `register_user_skills.py`, and `harden_aios.py`; `create_brain.py` uses stdlib only | `winget install Python.Python.3` | `brew install python3` | `apt install python3` |
| **Bash** | Required | Git hook scripts and the statusline dispatcher (`statusline.sh`) run in bash | Provided by Git for Windows (Git Bash) — no separate install | Built-in | Built-in |
| **PowerShell 5.1+** | Required on Windows; optional on macOS/Linux | Windows statusline (`statusline-context-alerts.ps1`) and sound playback use PowerShell; Linux/macOS use bash equivalents and do not require `pwsh` | Built-in (Windows PowerShell 5.1); PowerShell 7 optional | `brew install --cask powershell` (optional) | `apt install powershell` (optional) |
| **jq** | Required | Some statusline scripts parse JSON output from Claude Code | `winget install jqlang.jq` | `brew install jq` | `apt install jq` |
| **GPG** | Required | `commit.gpgsign = true` is set globally — every commit on the machine will be signed; a key must exist before the first commit | `winget install GnuPG.GnuPG` | `brew install gnupg` | `apt install gnupg` |
| **SSH client** | Required | All remote Git operations use SSH; no HTTPS and no `gh` CLI is used anywhere | Built-in (OpenSSH, Windows 10+) | Built-in | Built-in (`openssh-client`) |
| **SSH key pair** | Required | Public key must be registered with the Git host (`~/.ssh/id_ed25519` or similar) | `ssh-keygen -t ed25519` | Same | Same |
| **GPG key in local keyring** | Required | Fingerprint is written to `$HORIZON_BIN/harness_configs/git/gitconfig` during setup | `gpg --full-generate-key` | Same | Same |
| **`watchdog` Python library** | Optional | Required only by `sbin/monitor_aios.py` (filesystem audit monitor); the monitor is opt-in and not auto-started | `pip install watchdog` | `pip3 install watchdog` | `pip3 install watchdog` |
| **`keyring` Python library** | Optional | Used by `sbin/brain_credential.py` to store brain account passwords in the OS native keystore; brain provisioning continues (with a warning) if absent | `pip install keyring` | `pip3 install keyring` | `pip3 install keyring` |
| **Audio player** | Optional | Required for event hook sounds to play; hooks fail silently if no player is found | Built-in (`Media.SoundPlayer` via PowerShell) | Built-in (`afplay`) | One of: `paplay` (PulseAudio), `aplay` (ALSA), `ffplay` (ffmpeg), `mpg123` |
| **OS user/group management** | Required for brain provisioning only | `create_brain.py` creates OS user accounts and groups; requires the platform tools to be present | Built-in (`New-LocalUser`, `New-LocalGroup` PowerShell cmdlets) | Built-in (`dscl`, `dseditgroup`, `createhomedir`) | Built-in (`useradd`, `groupadd`, `usermod`) |
| **`icacls`** | Required for brain/harden on Windows | `harden_aios.py` and `create_brain.py` use `icacls` to set filesystem ACLs | Built-in | N/A | N/A |
| **`setfacl`** | Optional on Linux | Used by `harden_aios.py` for POSIX ACL hardening (additive mode); falls back to `chmod` mode bits if absent | N/A | N/A | `apt install acl` |
| **`chmod` / `chown`** | Required for brain/harden on Unix | Used by `harden_aios.py` and `create_brain.py` for permission hardening | N/A | Built-in | Built-in |
| **`openssl`** | Optional on Linux | Used to hash brain account passwords (`openssl passwd -6`); if absent, `useradd` creates a locked account and the password must be set manually | N/A | N/A | Built-in on most distros |

### Privilege requirement

Bootstrap and brain provisioning both call `harden_aios.py`, which sets OS-level
filesystem ACLs. This is a hard requirement — bootstrap exits immediately with an
error if not run elevated.

- **Windows:** Run bootstrap in an Administrator PowerShell (`Run as administrator`).
- **Linux/macOS:** Run bootstrap with `sudo bash horizon_system/sbin/bootstrap.sh`.

All other bootstrap steps (CLAUDE.md redirect, skills junction, settings.json copy,
git hooks, directories) are non-destructive and do not require elevation.

---

## Section 2 — System Footprint: AIOS Install

What changes on the machine when `bootstrap.ps1` / `bootstrap.sh` runs.

### Files created

| File | Windows | macOS | Linux | Notes |
|---|---|---|---|---|
| `~/.claude/CLAUDE.md` | Created | Created | Created | Single-line `@` redirect to `$HORIZON_ROOT/.claude/CLAUDE.md`; also appends a second `@` import for `$HORIZON_ROOT/.claude/CLAUDE.aios-dev.md` (owner-only dev context) |
| `~/.claude/settings.json` | Created (if absent; interactive prompt) | Created (if absent; interactive prompt) | Created (if absent; interactive prompt) | Copied from `$HORIZON_SYSTEM/templates/claude_code/settings.json` (Windows) or `settings_unix.json` (macOS/Linux); `AIOS_EXEC_WRAPPER` placeholder substituted with path to `~/.horizon/bin/aios-exec.{ps1,sh}` |
| `~/.horizon/aios_registry.json` | Created | Created | Created | AIOS named-registry; created by `aios_switch.py init` (Section 5 of bootstrap) |
| `~/.horizon/active_env.ps1` | Created | N/A | N/A | Sourced by PowerShell `$PROFILE` to load `HORIZON_*` env vars |
| `~/.horizon/active_env.sh` | N/A | Created | Created | Sourced by `~/.bashrc` / `~/.zshrc` to load `HORIZON_*` env vars |
| `~/.horizon/bin/aios-exec.ps1` | Created | N/A (`.sh` instead) | N/A (`.sh` instead) | Stable wrapper called by `settings.json`; resolves the active AIOS at run time so `aios switch` never rewrites settings |
| `~/.horizon/bin/aios-exec.sh` | N/A | Created | Created | Same wrapper purpose, POSIX shell |
| `$HORIZON_ETC/aios_local.conf` | Created from template (interactive prompt) | Created from template (interactive prompt) | Created from template (interactive prompt) | Machine-local AIOS config; copied from `$HORIZON_SYSTEM/templates/aios_local.conf.template` |
| `$HORIZON_ROOT/.git/hooks/pre-commit` | Copied | Copied | Copied | Installed by bootstrap into `.git/hooks/`; syncs `.gitignore.user` to `.git/info/exclude` on commit |
| `$HORIZON_ROOT/.git/hooks/commit-msg` | Copied | Copied | Copied | DCO sign-off enforcement |

### Directories created

| Directory | Windows | macOS | Linux | Notes |
|---|---|---|---|---|
| `$HORIZON_ROOT/handoffs/` | Created | Created | Created | Default output dir for `/handoff` skill |
| `$HORIZON_ROOT/objectives/` | Created | Created | Created | Default store for `/objective` skill |
| `$HORIZON_SYSTEM/logs/` | Created | Created | Created | Canonical audit and operational log directory (`$HORIZON_LOGS`); created by bootstrap and `harden_aios.py` if absent |
| `~/.claude/` | Created if absent | Created if absent | Created if absent | Bootstrap creates it if Claude Code has not been launched yet; Claude Code itself creates it on first launch |
| `~/.horizon/bin/` | Created | Created | Created | Created by `aios_switch.py init` alongside the wrapper scripts |

### Junctions / symlinks created

| Link | Windows | macOS | Linux | Notes |
|---|---|---|---|---|
| `~/.claude/skills/` | Directory junction → `$HORIZON_SYSTEM/skills_sbin/` | Symlink → `$HORIZON_SYSTEM/skills_sbin/` | Symlink → `$HORIZON_SYSTEM/skills_sbin/` | Created by Section 3 of bootstrap; no admin/root required for this step on any platform |

### OS-level changes

| Change | Windows | macOS | Linux |
|---|---|---|---|
| **System PATH** | `$HORIZON_BIN` added to Machine-scope PATH via `[System.Environment]::SetEnvironmentVariable("Path", ..., "Machine")`; stale `horizon_system\bin` entries removed first | `$HORIZON_BIN` written to `/etc/paths.d/horizon-aios` (for `zsh` via `path_helper`) and to `/etc/profile.d/horizon_aios.sh` | `$HORIZON_BIN` written to `/etc/profile.d/horizon_aios.sh` (mode 644); stale entries removed first |
| **Shell profile (per-user, owner only)** | User adds one line to PowerShell `$PROFILE`: `. "$HOME\.horizon\active_env.ps1"` | User adds one line to `~/.bashrc` or `~/.zshrc`: `. "$HOME/.horizon/active_env.sh"` | Same as macOS |
| **`/etc/profile.d/horizon_aios.sh`** | N/A | Created/updated (root-owned, 644) — also used alongside `/etc/paths.d/` | Created/updated (root-owned, 644) |
| **`/etc/paths.d/horizon-aios`** | N/A | Created/updated (644) | N/A |
| **`brains` OS group** | Created (`New-LocalGroup`) if absent | Created (`dseditgroup -o create`) if absent | Created (`groupadd`) if absent |

### Git config changes

| Setting | Scope | Value | Notes |
|---|---|---|---|
| `core.hooksPath` | Local (OS repo only) | `./horizon_system/harness_configs/git/hooks` | Set by Section 6 of bootstrap; tells Git to use the version-controlled hooks directory |
| `include.path` | Global (machine-wide) | `$HORIZON_BIN/harness_configs/git/gitconfig` | Set manually by the user per setup guide Step 9; pulls in `commit.gpgsign`, `user.signingkey`, `excludesfile` |
| `commit.gpgsign` | Global (via included gitconfig) | `true` | Every commit on the machine is GPG-signed after setup |
| `user.signingkey` | Global (via included gitconfig) | User's GPG fingerprint | Set during setup Step 8.2 |

### ACLs / permissions set by `harden_aios.py`

`harden_aios.py` runs as the final bootstrap step. It enforces the brains-group ACL
model on `$HORIZON_SYSTEM`. It has two modes: **additive** (default — preserves all
existing ACLs, adds ACEs only) and **strict** (`--strict` — drops inherited ACEs and
rebuilds from scratch).

**Default (additive) mode — what is added:**

| Directory | Windows (`icacls`) | Linux (`setfacl` / `chmod`) | macOS (`chmod`) |
|---|---|---|---|
| `$HORIZON_SYSTEM` (root, inheritable) | `brains` group: inheritable Deny on write/create/delete mask `(WD,AD,WEA,WA,DE,DC)` | `setfacl -R -m g:brains:r-x` + default ACL; or `chmod -R go-w` if `setfacl` absent | `chmod -R go-w` |
| `$HORIZON_BIN` | `brains` group: `(OI)(CI)RX` (Read+Execute, explicit grant) | `chown :brains`; `chmod g+rX` | Same |
| `$HORIZON_SYSTEM/skills_bin/` | `brains` group: `(OI)(CI)RX` (explicit grant) | `chown :brains`; `chmod g+rX` | Same |
| `$HORIZON_SYSTEM/sbin/` | `brains` group: `(OI)(CI)F` Deny (full, explicit; applied after grants) | `setfacl -R -m g:brains:---` + default; or `chmod 700` | `chmod 700` |
| `$HORIZON_SYSTEM/skills_sbin/` | `brains` group: `(OI)(CI)F` Deny (full, explicit; applied after grants) | Same as `sbin/` | Same |
| `$HORIZON_SYSTEM/logs/` | `brains` group: `(OI)(CI)F` Deny (full, explicit; applied after grants) | Same as `sbin/` | Same |

On Windows, owner + `SYSTEM` (`*S-1-5-18`) + `Administrators` (`*S-1-5-32-544`)
always retain Full control and are never removed, in either mode.

Deny ACEs are applied after all grants in every case — this ordering is a security
invariant so no inherited permission can accidentally reach a privileged directory.

### What is NOT changed

- No system-wide package installs (no `apt install`, `brew install`, `winget` runs are made by bootstrap).
- No registry writes beyond the Machine-scope PATH entry on Windows.
- No Windows services are installed or registered.
- No scheduled tasks or cron jobs are created (the optional sync scheduler `setup_sync_schedule.py` is a separate opt-in step).
- `$HORIZON_ROOT/.claude/settings.json` (devroot project-level) is not modified; it is version-controlled and owns only devroot-scoped permissions. Only `~/.claude/settings.json` (global) is created/modified.
- The OS repo's `settings.local.json` is never created by bootstrap — this file is machine-local and must be created manually per machine.

---

## Section 3 — System Footprint: Adding One Brain

What changes when `python $HORIZON_SYSTEM/sbin/create_brain.py <brain-name>` runs.
Must be run as Administrator (Windows) or root (Unix).

### OS user account created

| Detail | Windows | macOS | Linux |
|---|---|---|---|
| Command | `New-LocalUser` (PowerShell) | `dscl .` sequence | `useradd --create-home --shell /bin/bash` |
| Account name | `<brain-name>` | `<brain-name>` | `<brain-name>` |
| Home directory | `C:\Users\<brain-name>` (OS default) | `/Users/<brain-name>` (via `createhomedir`) | `/home/<brain-name>` |
| Shell | Default (PowerShell) | `/bin/bash` | `/bin/bash` |
| Password | Random 64-char (URL-safe base64, `secrets.token_urlsafe(48)`); never printed; stored in OS keystore | Same | Same; hashed with `openssl passwd -6` for `useradd --password`; if `openssl` is absent, account is created locked (`!`) and must be unlocked manually |
| `PasswordNeverExpires` | Set | N/A | N/A |

### OS group changes

| Group | Windows | macOS | Linux |
|---|---|---|---|
| `brains` (shared, created once) | Created via `New-LocalGroup` if absent; `<brain-name>` added as member | Created via `dseditgroup -o create` if absent; `<brain-name>` added | Created via `groupadd` if absent; `<brain-name>` added via `usermod -aG` |
| `<brain-name>_group` (Windows) / `<brain-name>` (Unix) | Created as `<brain-name>_group` via `New-LocalGroup` — Windows shares a namespace for local users and groups, so the group is named `<brain-name>_group` to avoid colliding with the `<brain-name>` user account; both `<brain-name>` user and the invoking (owner) user are added as members | Created as `<brain-name>` via `dseditgroup`; both `<brain-name>` user and the invoking (owner) user are added | Created as `<brain-name>` via `groupadd`; both `<brain-name>` user and invoking user added via `usermod -aG` |

### Directories created

| Directory | Permissions (Windows) | Permissions (Unix) | Notes |
|---|---|---|---|
| `$HORIZON_ROOT/brains/<brain-name>/` | `icacls /inheritance:r`; `<brain-name>:(OI)(CI)F`; `<invoking-user>:(OI)(CI)F`; `SYSTEM:(OI)(CI)F`; `Administrators:(OI)(CI)F` | `chown -R <brain-name>:<brain-name>`; `chmod 770` | Created with `os.makedirs`; parents created if absent |
| `$HORIZON_ROOT/brains/<brain-name>/.claude/` | Inherits brain folder ACLs | `chown <brain-name>:<brain-name>` | Created by Phase 5 (template deployment) |
| `<brain-home>/.claude/` | Created by Phase 3 (`C:\Users\<brain-name>\.claude\`) | Created by Phase 3 | Holds the brain's `~/.claude/skills` junction/symlink |

### ACLs set (per-brain, in addition to AIOS-layer hardening)

All Deny ACEs are applied after all grants — ordering is a security invariant.

| Directory | Windows | Linux | macOS |
|---|---|---|---|
| `$HORIZON_ROOT/brains/<brain-name>/` | `icacls /inheritance:r` + explicit grants for brain user, owner, SYSTEM, Administrators (Full control) | `chown -R <brain-name>:<brain-name>`; `chmod 770` | Same as Linux |
| `$HORIZON_BIN` | `brains` group: `(OI)(CI)RX` (additive; existing ACEs not disturbed) | `chown :brains`; `chmod g+rx` | Same |
| `$HORIZON_SYSTEM/skills_bin/` | `brains` group: `(OI)(CI)RX` (additive) | `chown :brains`; `chmod g+rx` | Same |
| `$HORIZON_SYSTEM/sbin/` | `brains` group: `(OI)(CI)F` Deny (additive, explicit; applied last) | `chmod 700` (applied last) | Same |
| `$HORIZON_SYSTEM/skills_sbin/` | `brains` group: `(OI)(CI)F` Deny (additive, explicit; applied last) | `chmod 700` (applied last) | Same |
| `$HORIZON_SYSTEM/logs/` | `brains` group: `(OI)(CI)F` Deny (additive, explicit; applied last) | `chmod 700` (applied last) | Same |

### Skills junction / symlink created

| Link | Windows | macOS | Linux |
|---|---|---|---|
| `<brain-home>/.claude/skills/` | Directory junction → `$HORIZON_SYSTEM/skills_bin/` (via `mklink /J`) | Symlink → `$HORIZON_SYSTEM/skills_bin/` (via `ln -sfn`) | Same as macOS |

The brain's skills junction points to `skills_bin/` (not `skills_sbin/`) — brains
access only the group-readable skill tier; `skills_sbin/` is explicitly denied.

### Credential stored

| Platform | Store | Mechanism |
|---|---|---|
| Windows | Windows Credential Manager | `keyring` library (via `brain_credential.py`) |
| macOS | Keychain | `keyring` library |
| Linux | Secret Service (e.g., GNOME Keyring, KWallet) | `keyring` library |

The password is auto-generated (64 chars, `secrets.token_urlsafe(48)`) and is never
written to any file and never printed to the terminal. Retrieve it with:
`python $HORIZON_SYSTEM/sbin/brain_credential.py get <brain-name>` (requires
Administrator / root).

If the `keyring` library is absent, a warning is printed and the password is not
stored — it must be set manually: `passwd <brain-name>` (Unix) or
`Set-LocalUser -Name <brain-name> -Password (...)` (Windows).

### Files written inside the brain folder

| File | Source | Notes |
|---|---|---|
| `$HORIZON_ROOT/brains/<brain-name>/.claude/CLAUDE.md` | `$HORIZON_ROOT/brains/.aioscommon/brain_CLAUDE.md.template` | `[BRAIN_NAME]` and `[HORIZON_ROOT_PATH]` placeholders substituted; customize after provisioning to define the brain's persona |
| `$HORIZON_ROOT/brains/<brain-name>/.claude/settings.json` | `$HORIZON_ROOT/brains/.aioscommon/brain_settings.json.template` | `[BRAIN_NAME]` and `[HORIZON_ROOT_PATH]` placeholders substituted; customize to scope allowed tools |
| `$HORIZON_ROOT/brains/<brain-name>/.aios_provision.json` | Generated by `create_brain.py` Phase 5 | Machine-readable provisioning manifest (timestamp, invoking user, groups, paths, credential store note) for auditors |

### Shell profile written (brain user's login environment)

| Platform | File(s) written | Content |
|---|---|---|
| Windows | `C:\Users\<brain-name>\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` and `...\PowerShell\Microsoft.PowerShell_profile.ps1` | Sets all `$env:HORIZON_*` variables and `Set-Location` to brain folder |
| Linux | `<brain-home>/.bashrc` | Exports all `HORIZON_*` env vars, sets `HORIZON_BRAIN_NAME` and `HORIZON_BRAIN_HOME`, `cd`s to brain folder |
| macOS | `<brain-home>/.zshrc` and `<brain-home>/.bash_profile` | Same content as Linux |

### Hooks / services

No hooks, services, scheduled tasks, or cron jobs are created by `create_brain.py`.
A brain can be wired to Task Scheduler (Windows) or cron/systemd (Unix) after
provisioning — this is a manual post-provisioning step. The filesystem monitor
(`sbin/monitor_aios.py`) is a separate opt-in tool and is not auto-started.

---

## See Also

- `getting_started/ReadMeToSetupYourSystem.md` — procedural step-by-step instructions for AIOS installation
- `documentation/utilities.md` — quick-lookup catalog for `harden_aios.py`, `create_brain.py`, `brain_credential.py`, and all other `sbin/` utilities
- `ai_os_etc/security_invariants.md` — the ACL ownership model, the three-tier principal hierarchy, and why the Deny-after-grant ordering is a hard invariant
