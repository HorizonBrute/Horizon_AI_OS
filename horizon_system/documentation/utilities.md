# Horizon AIOS — Utilities Reference

Most utilities here live in `$HORIZON_SYSTEM/sbin/` and are
administrative: they operate on the AIOS layer itself — hardening its
permissions, monitoring its integrity, maintaining its logs, provisioning brain
accounts and credentials, syncing upstream, and wiring its configuration. They
run as the primary OS user or elevated (Administrator/root) and are excluded
from brain accounts by explicit Deny ACLs enforced by `horizon_aios_harden.py`. A few
unprivileged helpers in `$HORIZON_SYSTEM/bin/` (readable by brains) are also
catalogued where they are useful to invoke directly.

Several utilities are surfaced as Claude skills — when invoked through a skill,
Claude drives the script with appropriate arguments and interprets the output.
The scripts also work standalone from any shell.

---

## context_cost.py

**Path:** `$HORIZON_SYSTEM/bin/context_cost.py`

Measures the Claude Code harness context overhead (token count, word count,
KB) contributed by `CLAUDE.md`, `CLAUDE.local.md`, `agents.md`, and all
`@`-imports that the harness would load for a given path. It walks the ancestor
chain from the target directory up to the filesystem root and includes
`~/.claude/` as the global config layer, matching the harness's own lookup
order.

**When to use it:** When you want to know how much context a working directory
costs before starting a session, or after adding or modifying `CLAUDE.md`
files or `@`-imports to confirm the overhead stayed in budget (see
`dev_values.md` §2 on token economy).

**Key flags:**

- `[path]` — file or directory to evaluate; defaults to CWD
- `--json` — emit machine-readable JSON instead of the summary table

**Referenced by a skill?** Yes — the `context-cost` skill.

---

## horizon_aios_doctor.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_doctor.py`

System health check. Verifies that the AIOS install is correctly bootstrapped:
environment variables are set and point to real directories, the skills symlink
(`~/.claude/skills/`) resolves to `skills_sbin/`, git hooks are installed, the
local config file exists, the AIOS registry is valid and its active entry
points to a real AIOS root, and ACLs on `sbin/`, `skills_sbin/`, and `logs/`
include an explicit Deny for the `brains` group. The ACL checks read the same
config-driven posture the enforcer applies (via `horizon_aios_acl_posture.py` /
`file_acl_hardening.toml` + `.local` override), so verifier and enforcer can
never disagree; the four `horizon_humans` self-service areas and their `shared/`
drop-zones are verified from the same source. Also checks monitor status
(advisory — a stopped monitor is a warning, not a failure).

**When to use it:** After initial bootstrap, after pulling an upstream update
that touches the bootstrap sequence, or whenever something behaves unexpectedly
and you need a quick status read.

**Key flags:**

- `--post-setup` — after the standard checks, run three post-install
  verifications: a test sound through the canonical sound chokepoint
  (`resolve_sound.py`), statusline command resolution, and git
  `commit.gpgsign`. A muted sound config (`sounds_enabled` off) reports a
  clean `[SKIP]` rather than a failure; the summary then reports a skipped
  count alongside passed/warnings/failures.

Exit semantics are unchanged by `--post-setup`: exit 1 if any check FAILs, 0
otherwise (SKIP and WARN never fail the run).

**Referenced by a skill?** Yes — `/doctor`.

---

## horizon_aios_monitor.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_monitor.py`

Filesystem integrity monitor. Watches the AIOS system directories for
unexpected creates, modifies, deletes, and moves, and appends each event as a
JSON line to a daily log file in `$HORIZON_SYSTEM/logs/horizon_aios_monitor/`. The
default watch set covers `$HORIZON_SYSTEM` (recursive), `$HORIZON_USRBIN`
(recursive), `$HORIZON_ROOT/.claude` (recursive), `$HORIZON_ROOT` top-level
(non-recursive), and the brains root (non-recursive, structural changes only).
Brain home contents are excluded by default; opt in with `--brain-dirs`.

Runs as the administrative context. Brain accounts must not have write access
to the log directory — `horizon_aios_harden.py` enforces this.

**When to use it:** Run it as a persistent background process (or service) on
any installation where audit logging is required. For full setup instructions
and log consumption guidance see `$HORIZON_DOCS/security/audit_logging.md`.

**Key flags:**

- `--watch PATH` — add an extra path to watch recursively (repeatable; additive)
- `--brain-dirs` — escalate brains-root watch to recursive (logs brain internals)
- `--no-brains-root` — disable the default brains-root watch
- `--config PATH` — config file (default: `$HORIZON_ETC/aios_monitor.conf`)
- `--log-dir PATH` — log directory (default: `$HORIZON_SYSTEM/logs/horizon_aios_monitor/`)

**Referenced by a skill?** Yes — `/monitor`.

---

## horizon_aios_harden.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_harden.py`

Applies the authoritative AIOS ACL posture. The posture is **config-driven**:
it is declared as abstract-intent rules in `$HORIZON_ETC/file_acl_hardening.toml`
(shipped default) deep-merged with the gitignored
`$HORIZON_ETC/file_acl_hardening.local.toml` (deployer override, local wins), and
translated to the native mechanism per OS by the shared
`horizon_aios_acl_posture.py` engine — `icacls` (Windows), `setfacl` (Linux),
`chmod +a` (macOS). The posture grants the `brains` group Read+Execute on `bin/`
and `skills_bin/`, a broad no-write Deny across `$HORIZON_SYSTEM`, and an explicit
full Deny on `sbin/`, `skills_sbin/`, and `logs/`; it also enforces the
`horizon_humans` self-service isolation on the four human areas (`projects/`,
`handoffs/`, `objectives/`, `usrbin/`) plus each area's group-shared `shared/`
drop-zone. If the config is missing or corrupt the engine FAILs SECURE to an
embedded copy of the shipped posture, so hardening never silently no-ops.
Requires Administrator/root. Run by bootstrap (Section 9); re-run after structural
changes to `$HORIZON_SYSTEM`. Customize the stance by editing
`file_acl_hardening.local.toml`, never the tracked default (the sync reclaims it).

**When to use it:** Initial bootstrap, after adding or removing directories
under `$HORIZON_SYSTEM`, or when `horizon_aios_doctor.py` reports a missing Deny ACE.

**Key flags:**

- `--strict` — additionally strip inherited ACEs (Windows: `/inheritance:r`;
  Unix: `chown -R` + mode bits) for a locked-down standalone install; default
  (additive) preserves existing ACLs and enforces the model by adding ACEs only
- `--dry-run` — print every action that would be taken without executing anything
- `--horizon-root PATH` — explicit root path; otherwise derived from the
  script's own location

**Referenced by a skill?** No.

---

## horizon_aios_acl_posture.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_acl_posture.py`

The shared ACL-posture engine consumed by **both** `horizon_aios_harden.py`
(apply) and `horizon_aios_doctor.py` (verify), so enforcer and verifier can never
disagree about the stance. It (1) loads the shipped default
`$HORIZON_ETC/file_acl_hardening.toml`, (2) deep-merges the gitignored deployer
override `$HORIZON_ETC/file_acl_hardening.local.toml` over it keyed by rule/group
`name` (local wins; `disabled = true` drops a rule), (3) FAILs SECURE to an
embedded copy of the shipped posture if the default is missing/corrupt or
`tomllib` is unavailable, and (4) translates each abstract-intent rule to native
ops per OS — `setfacl` (Linux), `chmod +a` (macOS), `icacls` with OWNER RIGHTS
`S-1-3-4` for child isolation (Windows). Not normally run directly; it is a
library. Standalone it offers a self-check and a translated-command dump for
review.

**Key flags:**

- `--self-check` — verify the embedded fail-secure fallback still matches the
  shipped `file_acl_hardening.toml`, then exit (non-zero on drift)
- `--os {Linux,Darwin,Windows}` — force an OS for the translated-command dump
  (defaults to the host OS)
- `--owner NAME` — owner principal used in the Windows dump
- `--horizon-root PATH` — explicit root; otherwise derived from the script's
  own location

**Referenced by a skill?** No (indirectly, via `/harden` and `/doctor`, which
drive the two consumers).

---

## horizon_aios_maintain_logs.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_maintain_logs.py`

Prunes and rotates the AIOS log directory. Deletes log files older than the
configured retention window (`AIOS_LOG_MAX_DAYS`, default 30 days), rotates
oversized `.log` files (`AIOS_LOG_MAX_SIZE_MB`, default 10 MB) up to a
configurable number of generations, and separately prunes the `handoffs/`
directory by total size budget (`AIOS_HANDOFFS_MAX_SIZE_MB`, default 500 MB)
and the `objectives/` directory by age (`AIOS_OBJECTIVES_MAX_DAYS`, default 90
days). All thresholds are read from `$HORIZON_ETC/aios_local.conf` and can be
set to `0` to disable that category. Requires Administrator/root because it
modifies ACL-protected log paths.

**When to use it:** Schedule as a recurring task (e.g., weekly) to prevent
unbounded log growth. Also run manually after a prolonged monitor run or before
a disk-space-sensitive operation.

**Key flags:** None — all configuration is in `aios_local.conf`.

**Referenced by a skill?** No.

---

## horizon_aios_brain_credential.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_brain_credential.py`

Manages brain OS-account passwords in the native OS keystore (Windows
Credential Manager, macOS Keychain, Linux Secret Service via the `keyring`
library). Provides CLI commands to store, retrieve, rotate, delete, and list
brain credentials. `rotate` generates a cryptographically random 64-character
password, updates the OS account, and stores the new value in the keystore
atomically. Requires Administrator/root. Also importable as a library
(`from brain_credential import store_password`) for use by `horizon_aios_create_brain.py`
during provisioning.

**When to use it:** After creating a brain account, when rotating credentials
per policy, or when recovering a stored password (use `get --show` with
caution).

**Key flags:**

- `get <brain-name> [--show]` — retrieve credential; masked unless `--show`
- `rotate <brain-name>` — generate and store a new password
- `delete <brain-name>` — remove credential from keystore
- `list` — list brain names with stored credentials (backend-dependent)

**Referenced by a skill?** No.

---

## horizon_aios_switch.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_switch.py`

Switches the local machine's Claude Code harness configuration to point at a
different named Horizon AIOS install. A machine is normally bound to one AIOS
by five pointers (environment variables, `~/.claude/CLAUDE.md`, the skills
symlink, `settings.json` hooks, and the sync schedule). This tool rewrites the
volatile three — env snippet (`~/.horizon/active_env.{ps1,sh}`),
`~/.claude/CLAUDE.md`, and the `~/.claude/skills/` symlink — while leaving
`settings.json` stable by routing it through AIOS-independent wrapper scripts
in `~/.horizon/bin/`. The registry at `~/.horizon/aios_registry.json` records
all known AIOS installs and the active one; it self-heals if missing.

**When to use it:** When running more than one AIOS install on the same machine
(e.g., a dev fork alongside a production install) and switching which one the
harness uses. Also used during initial bootstrap (`init` subcommand) to
generate the env snippets and wrapper scripts for the first time.

**Key flags (subcommands):**

- `list` — show all registered AIOSs; active marked with `*`
- `current` — print the active AIOS name and root
- `init` — register this tree and generate env/wrappers (bootstrap entry point)
- `register <name> <path>` — add or replace a named AIOS in the registry
- `unregister <name>` — remove a registration (files untouched)
- `switch <name> [--dry-run]` — repoint all pointers to the named AIOS
- `setup [--yes]` — one-shot new-machine installer: orchestrates the full setup
  procedure (preflight, root resolution, profile line, bootstrap, git identity,
  local settings, model prefs, doctor `--post-setup` gate); unprivileged and
  idempotent. See `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md`.
- `uninstall [--dry-run] [--yes]` — delegate to `uninstall.ps1` / `uninstall.sh`
  to remove the bootstrap footprint (a real removal must be run elevated;
  `--dry-run` previews and needs none)

Short-form commands are available once `$HORIZON_BIN` is on PATH (bootstrap
adds it): `aios switch home`, `aios list`, etc. The wrappers `aios` (bash)
and `aios.ps1` (PowerShell) in `$HORIZON_BIN` delegate to this script and
derive their path from their own location, so they work from any AIOS root.

**Referenced by a skill?** No. See `$HORIZON_DOCS/system/aios_switching.md`
for the full switching guide.

---

## horizon_aios_relocate.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_relocate.py`

Updates the machine-local instance pointers when an AIOS install is moved to a
new root path (e.g., `C:\devroot` → `D:\aios`). Auto-detects the old root from
`~/.horizon/aios_registry.json` and rewrites it in: the registry, `active_env.{ps1,sh}`,
`~/.claude/CLAUDE.md`, and (if present) `aios_local.conf`. Framework source
files are deliberately left alone — they derive `HORIZON_*` from their own
location, not from hardcoded paths. Also detects if the `~/.claude/skills`
symlink needs re-pointing and prints the exact `horizon_aios_switch.py` command
to fix it.

**Safety:** dry-run is the **default**. Run without `--apply` first to preview
every change. Pass `--apply` only when the output looks correct.

**When to use it:** After physically moving or renaming the AIOS root directory,
to update all machine-local pointers in one step instead of manually editing
each file.

**Key flags:**

- `--new-root PATH` — target root the install now lives at (default: the root
  derived from the script's own location, so running it from the new location
  auto-detects the target)
- `--old-root PATH` — override old root detection (default: read from registry)
- `--apply` — write changes; without this flag the tool runs in dry-run mode
- `--home PATH` — override home directory for locating `~/.horizon/` and `~/.claude/`

**Referenced by a skill?** No.

---

## uninstall.ps1 / uninstall.sh

**Path:** `$HORIZON_SYSTEM/sbin/uninstall.ps1` (Windows) / `$HORIZON_SYSTEM/sbin/uninstall.sh` (Linux/macOS)

Section-by-section mirror of `bootstrap.ps1` / `bootstrap.sh` — reverses every
configuration bootstrap wrote. Requires Administrator (Windows) or root (Linux/macOS)
because ACL reversal needs elevation.

Removes: skills symlink (`~/.claude/skills/`), CLAUDE.md redirect, active-env
snippets, aios-exec wrappers, AIOS registry, `aios_local.conf`, `.git/hooks/commit-msg`
and `pre-commit`, `core.hooksPath` git config, system PATH entry
(`$HORIZON_BIN` from Machine-scope PATH on Windows; `/etc/profile.d/horizon_aios.sh`
and `/etc/paths.d/horizon-aios` on Linux/macOS), `$HORIZON_SYSTEM/logs/` /
`handoffs/` / `objectives/` if empty, brains-group ACEs from `$HORIZON_SYSTEM`
subtrees, and the on-by-default nightly maintenance schedule (best-effort, via
`horizon_aios_setup_maintenance_schedule.py --remove`). Offers optional deletion of
`~/.claude/settings.json`.

Emits `[MANUAL]` advisories for the steps that cannot be automated: shell profile
line, global gitconfig `include.path`, sync schedule/cron, `brains` OS group, and
brain user accounts.

Does **not** delete the AIOS repo, brain home directories, or non-empty user data.

**When to use it:** When decommissioning AIOS from a machine.

**Invocation:** Run `aios uninstall [--dry-run] [--yes]` (delegates to the platform
script via `horizon_aios_switch.py`), or invoke the script directly. A real removal must be
run elevated; `--dry-run` needs no elevation.

**Key flags (both scripts):**

- `--dry-run` — preview every action without making any changes (no elevation needed)
- `--yes` / `-y` — skip interactive confirmations (non-interactive)

Unknown arguments are rejected (exit code 2) rather than silently ignored.

**Referenced by a skill?** No. See `$HORIZON_DOCS/system/aios_switching.md` §Uninstalling.

---

## horizon_aios_register_user_skills.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_register_user_skills.py`

Aggregates the owner's complete skill view into `skills_sbin/` by creating
per-skill symlinks for skills from two sources:
`$HORIZON_SYSTEM/skills_bin/` (brain-tier skills tracked in the OS repo) and
`$HORIZON_USRBIN/usr_skills/` (machine-local owner skills, gitignored). Skills
from both sources appear flat alongside the native `skills_sbin/` skills that
`~/.claude/skills/` already exposes. The script is idempotent: stale links are
pruned, existing correct links are left in place, and a native OS skill of the
same name always takes precedence over an aggregated link.

**When to use it:** After an upstream sync that adds or removes skills in
`skills_bin/`, after creating a machine-local skill in `usr_skills/`, or
whenever the `/resync-user-skills` skill reports drift.

**Key flags:**

- `--dry-run` — print what would change without modifying anything
- `--check` — report drift and exit 1 if out of sync; exit 0 if clean (used
  by the `/resync-user-skills` skill's check mode)

**Referenced by a skill?** Yes — the `resync-user-skills` skill.

---

## horizon_aios_create_brain.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py`

Provisions a new AI brain: creates the `<brain-name>` OS user, the shared
`brains` group (Read+Execute on `bin/` and `skills_bin/`) and a per-brain group
(`<brain-name>_group` on Windows to avoid the shared user/group namespace;
`<brain-name>` on Linux/macOS), the workspace at `$HORIZON_ROOT/brains/<brain-name>/`,
and a login shell profile that exports the `HORIZON_*` vars and cds into the
brain folder. The account password is auto-generated (random 64-char) and stored
in the OS native keystore via `horizon_aios_brain_credential.py`. The `sbin/skills_sbin/logs`
Deny ACEs are always (re)applied after all grants, per the security invariants.
Requires Administrator/root; stdlib only (Python 3.6+).

**When to use it:** When standing up a new isolated brain account.

**Key flags:**

- `<brain-name>` — required positional name (lowercase, `[a-z][a-z0-9_]{1,31}`)
- `--horizon-root PATH` — explicit root; otherwise derived from script location
- `--dry-run` — print every action without making changes

**Referenced by a skill?** No.

---

## horizon_aios_remove_brain.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_remove_brain.py`

Deprovisioning counterpart to `horizon_aios_create_brain.py`. Removes a brain's OS user
account, its per-brain group (`<brain-name>_group` on Windows, `<brain-name>` on
Linux/macOS), its workspace folder, its user-profile config
(including the `~/.claude/skills` symlink, deleted as a reparse point so the
`skills_bin` target is never followed), and its stored credential. The
shared `brains` group is left intact. Validates the name and refuses reserved
names (brains, root/administrator, the invoking user, etc.). Requires
Administrator/root.

**When to use it:** When retiring a brain account created by `horizon_aios_create_brain.py`.

**Key flags:**

- `<brain-name>` — required positional name
- `--horizon-root PATH` — explicit root; otherwise derived from script location
- `--yes` — skip the confirmation prompt
- `--dry-run` — print what would be removed without changing anything

**Referenced by a skill?** No.

---

## horizon_aios_brain_logon_rights.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_brain_logon_rights.py`

Surgical helper for the opt-in brain *automation* tiers: grants, revokes, or
queries a single Windows LSA logon right on one brain account via
`LsaAddAccountRights` / `LsaRemoveAccountRights` / `LsaEnumerateAccountRights`,
touching nothing else in local security policy (mirrors the additive-ACL model
in `horizon_aios_harden.py`). `SeBatchLogonRight` ("Log on as a batch job") backs the
`scheduled` tier; `SeServiceLogonRight` is reserved for a future `daemon` tier.
Normally invoked for you by `horizon_aios_create_brain.py --automation scheduled` and revoked
by `horizon_aios_remove_brain.py` on teardown; use it directly only for manual right
management. **Windows only** (no-op/NotImplementedError elsewhere). Requires
elevation. See `$HORIZON_DOCS/deployment/brain_automation.md`.

**When to use it:** To grant, check, or revoke a brain's logon right by hand
(e.g. the reserved service tier) outside the normal `--automation` flow.

**Key flags:**

- `grant|check|revoke <brain>` — the action and target account
- `--right NAME` — target a specific LSA right (default `SeBatchLogonRight`)

**Referenced by a skill?** No. See `$HORIZON_DOCS/deployment/brain_automation.md`.

---

## horizon_aios_verify_isolation.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_verify_isolation.py`

Verifies the central AIOS isolation claim — a brain OS account can read
`$HORIZON_BIN` but is denied `$HORIZON_SYSTEM/sbin` (verification criterion #5).
Runs in two modes. **Default (safe)** is non-destructive and needs no elevation:
it confirms the static ACL posture — an explicit, non-inherited `brains` Deny on
`sbin`/`skills_sbin`/`logs` (Windows, via `Get-Acl`, the same check
`horizon_aios_doctor.py` makes) or owner-only mode `0o700` (Unix). **Live mode
(`--live`)** is the opt-in, elevated, destructive proof: it provisions a throwaway
brain, logs on *as* that brain to empirically read `bin` (expect OK) and `sbin`
(expect denied), then removes it. Because live mode adds and deletes an OS user
and requires Administrator/root, the account-touching behaviour is gated behind
`--live`; the default does nothing to user accounts. Windows is fully
implemented and verified; Linux/macOS have the safe check and a live-probe
framework (`runuser`/`su`/`sudo -u`) not yet validated on real hardware.

**When to use it:** Quick, safe re-confirmation that hardening is intact (default
mode, any time); or the full empirical isolation proof on a test machine when
validating a fresh install or change (`--live`, elevated). Useful to contributors
validating the security model.

**Key flags:**

- *(none)* — default safe ACL check, non-destructive, no elevation
- `--live` — opt-in: provision a throwaway brain, run the as-the-brain probe,
  remove it (requires elevation)
- `--brain-name NAME` — throwaway account name for `--live` (default `aios_isotest`)
- `--keep` — `--live`: leave the brain provisioned for inspection
- `--yes` / `-y` — skip the `--live` confirmation prompt
- `--dry-run` — print what `--live` would do without changing anything
- `--horizon-root PATH` — explicit root; otherwise derived from script location

**Referenced by a skill?** No. See `$HORIZON_DOCS/security/brain_isolation_test.md`.

---

## horizon_aios_sync.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_sync.py`

Pulls AIOS updates into the local tree via a **two-lane sync**. Reads sync
settings from `$HORIZON_ETC/aios_local.conf`. The **official lane**
(`AIOS_OFFICIAL_REMOTE` / `AIOS_OFFICIAL_BRANCH`) is authoritative: it OVERWRITES
every path except `projects/`, `usrbin/`, `brains/` via a scoped hard-restore
(`git checkout <ref> -- <official paths>`) and commits the result. The
**personal lane** (`AIOS_PERSONAL_REMOTE` / `AIOS_PERSONAL_BRANCH`) covers exactly
those three personal paths and is local-wins: it keeps local by default, allows a
fast-forward-only advance with `SYNC_PERSONAL_FROM_REMOTE=yes`, and overwrites
only under `--force-personal`. `SYNC_AIOS_FROM_REMOTE=no` disables both lanes.
The deprecated `AIOS_REPO_REMOTE` / `AIOS_REPO_BRANCH` keys are honored as
back-compat aliases mapped onto the official lane. Activity is logged to the
configured AIOS log dir; after a sync the script re-registers machine-local user
skills. Its automated commits pass `git commit --no-verify` to bypass the DCO
`commit-msg` hook (machine housekeeping, not a human contribution). This is the
script driven by the auto-sync scheduled task; run it manually to sync on demand.

**When to use it:** To pull the latest AIOS layer manually, or as the body of the
scheduled sync job installed by `horizon_aios_setup_sync_schedule.py`.

**Key flags:**

- `--lane official | personal | both` — select which lane(s) to run (default
  `both`).
- `--force-personal` — DANGER: overwrite local `projects/`, `usrbin/`, `brains/`
  from the personal remote (discards local personal changes).
- `--status` — read-only health check: reports whether auto-sync is installed,
  both lanes' configuration, and when it last ran/succeeded. Never triggers a
  sync. (See `sync_setup.md` for the exit-code contract.)
- `--help` — usage.

Default (no flags) runs both lanes; all sync behaviour comes from
`aios_local.conf`.

**Referenced by a skill?** No.

---

## horizon_aios_setup_sync_schedule.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_setup_sync_schedule.py`

Installs (or updates) the recurring auto-sync job that runs `horizon_aios_sync.py`: a
Windows Scheduled Task or a Unix cron entry. Reads the schedule settings
(`AIOS_SYNC_FREQ`, `AIOS_SYNC_TIME`, …) from `$HORIZON_ETC/aios_local.conf` and
registers the task accordingly. Requires the privilege needed to register a
system task (Administrator/root).

**When to use it:** During bootstrap, or after changing the sync frequency/time
in `aios_local.conf` and wanting the schedule re-registered.

**Key flags:**

- `--yes` — auto-confirm prompts (non-interactive install)

**Referenced by a skill?** No.

---

## horizon_aios_setup_maintenance_schedule.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_setup_maintenance_schedule.py`

Installs (or removes) the **nightly maintenance** schedule that runs
`horizon_aios_nightly_maintenance.py`: a Windows Scheduled Task
(`HorizonAIOS_NightlyMaintenance`) or a Unix/macOS cron entry (marked
`# HorizonAIOS_NightlyMaintenance`), defaulting to ~03:00. Idempotent — the
marker comment / fixed task name prevents duplicate installs on re-run. Requires
the privilege needed to register a system task (Administrator/root). Installed
on by default at onboarding; opt out with bootstrap's `--no-nightly` /
`-NoNightly`.

**When to use it:** Automatically at bootstrap, or manually to (re-)install or
uninstall the nightly job.

**Key flags:**

- `--yes` — auto-confirm prompts (non-interactive install)
- `--time HH:MM` — override the nightly run time (default `03:00`)
- `--remove` — uninstall the schedule (cron marker / scheduled task)

**Referenced by a skill?** No.

---

## horizon_aios_nightly_maintenance.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_nightly_maintenance.py`

The unattended runner invoked by the nightly maintenance schedule. Runs, in
order and non-interactively: (1) `horizon_aios_doctor.py` to report drift
(the pass/warn/fail summary is captured to the log; a non-zero doctor result is
recorded but does **not** abort the run), then (2) `horizon_aios_harden.py` to
re-assert the brains-group ACL / permission model (idempotent). Logs each step
to `$HORIZON_SYSTEM/logs/horizon_aios_nightly_maintenance.log` (honouring
`AIOS_LOG_DIR`). Safe to run repeatedly; exits 0 unless the runner itself errors.

**When to use it:** Automatically each night via the schedule; run manually
(optionally `--dry-run`) to verify maintenance behaviour on demand.

**Key flags:**

- `--dry-run` — print the steps that would run without executing them

**Referenced by a skill?** No.

---

## horizon_aios_redirect_memory.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_redirect_memory.py`

Redirects the owner's harness per-project state — conversation transcripts and
agent memory — into the AIOS by replacing `~/.claude/projects/` with a symlink
to `$HORIZON_ROOT/memory/`, so the state is governed
by the AIOS gitignore, sync-exclusion, and monitor rules. Backup-first and
idempotent: it copies existing content to `~/.claude/projects.backup-<timestamp>`,
*moves* it into the memory root (skipping name collisions), then links. Run with
Claude Code CLOSED, then restart it. Brains are handled separately by
`horizon_aios_create_brain.py`. See `$HORIZON_DOCS/system/memory.md`.

**When to use it:** Once on the owner's machine to bring harness memory under
AIOS governance; safe to re-run (it no-ops if already linked).

**Key flags:**

- `--horizon-root PATH` — target root (default: `$HORIZON_ROOT`, else derived)
- `--dry-run` — show actions, change nothing
- `--no-backup` — skip the pre-migration safety copy

**Referenced by a skill?** No. See `$HORIZON_DOCS/system/memory.md`.

---

## horizon_aios_backup_user_data.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_backup_user_data.py`

Backs up your gitignored user data (`memory/`, `handoffs/`, `objectives/`) to
**your own** git remote without ever editing the framework `.gitignore`. It
force-adds the data paths into a temporary git index, builds a commit containing
only those paths, and pushes it to a per-machine branch (`aios-backup/<hostname>`
by default) — the working tree, staging area, and framework branch are never
touched, so it is safe to run from an active session. **Refuses** to push to the
public Horizon upstream (exit 2) to avoid publishing private transcripts. Reads
`AIOS_BACKUP_REMOTE` / `AIOS_BACKUP_BRANCH` / `AIOS_BACKUP_PATHS` from
`aios_local.conf`. See `$HORIZON_DOCS/system/distribution_and_updates.md`.

**When to use it:** To version-control your memory/handoffs/objectives on your
own remote for backup and cross-machine awareness; manually or on a schedule.

**Key flags:**

- `--remote R` — git remote name or URL (or `AIOS_BACKUP_REMOTE`); required
- `--branch B` — backup branch (default `aios-backup/<host>`)
- `--paths P …` — paths to back up (default `memory handoffs objectives`)
- `--message M` — commit message (default: timestamped)
- `--dry-run` — show what would be backed up; do not commit or push

**Referenced by a skill?** No. See `$HORIZON_DOCS/system/distribution_and_updates.md`.

---

## horizon_aios_monitor_analyze.py

**Path:** `$HORIZON_SYSTEM/sbin/horizon_aios_monitor_analyze.py`

Reads the JSON-line logs produced by `horizon_aios_monitor.py`, summarizes file-change
events and monitor uptime gaps, and appends a report to
`$HORIZON_SYSTEM/logs/horizon_aios_security.log`. Can optionally forward alerts to the OS
system log (syslog on Linux; Windows Event Log when `pywin32` is present). Meant
to run as the administrative context on a schedule. See
`$HORIZON_DOCS/security/audit_logging.md` for scheduling guidance.

**When to use it:** Periodically (e.g., daily) to triage monitor output into a
single security log, or ad hoc to review recent integrity events.

**Key flags:**

- `--days N` — number of days back to analyze
- `--log-dir PATH` — monitor log dir (default: `logs/horizon_aios_monitor/`)
- `--security-log PATH` — output report path (default: `logs/horizon_aios_security.log`)
- `--syslog` — also emit alerts to the OS system log

**Referenced by a skill?** No.

---

## monitor_status.py

**Path:** `$HORIZON_SYSTEM/bin/monitor_status.py`

Tiny status probe: reports whether a `horizon_aios_monitor.py` process is currently
running. Prints `running`, `stopped`, or `unknown`. Cross-platform (CIM query on
Windows, `pgrep` on Unix). Used by `horizon_aios_doctor.py` and the status line to surface
monitor health without requiring elevation.

**When to use it:** For a quick check that the integrity monitor is up.

**Key flags:** None.

**Referenced by a skill?** No.

---

## resolve_agent_teams.py

**Path:** `$HORIZON_SYSTEM/bin/resolve_agent_teams.py`

Resolves the Agent Teams in effect for a given path. Walks the scope cascade from
the path up to `$HORIZON_ROOT`, reads the shipped `agent_teams.md` plus every
machine-local `local.agent_teams.md` override (root, `.claude/`, and any
project/brain/subfolder scope), and reports each source with its team names — in
`--json`, also each team's roles, model groups, and loop flag — plus the resolved
set (most-specific scope wins; same-name overrides shipped, new names unioned).
Only definition files are read; a file merely named `agent_teams.md` elsewhere
(e.g. the doc under `documentation/`) is excluded.

**When to use it:** The deterministic discovery behind a bare `/agent-teams` — the
skill calls it so the model does not hand-glob. Run by hand to see which teams
apply in a directory.

**Key flags:**

- `[path]` — directory (or file) to resolve the cascade for (default: cwd)
- `--root DIR` — override `$HORIZON_ROOT` instead of auto-resolving
- `--flags` — print the full SAILL flag vocabulary (from `agent_team_flags.md` and any in-scope `local.agent_team_flags.md`); does not resolve teams
- `--json` — emit structured JSON (sources + resolved set, with roles/groups/loop/flags)

---

## resolve_sound.py

**Path:** `$HORIZON_SYSTEM/bin/resolve_sound.py`

Resolves an AIOS event name (e.g. `task_complete`) to an absolute sound-file
path using the nearest `aios_sounds.conf` ancestor override, then the
per-harness `sounds.map`, then the system default `sounds/sounds.map`. Prints the
path or nothing (a missing sound is not an error — always exit 0). Intended to be
called from harness hooks, which pipe its output to `sounds/play_sound.sh`.

Honors the `sounds_enabled` mute flag before resolving: `sounds_enabled = false`
in the master `sounds/aios_sounds.conf` silences every event everywhere (absolute);
the same key in a per-project `aios_sounds.conf` mutes only that subtree. When
muted it prints nothing. See file_structure_invariants §10.6.

**When to use it:** From a notification hook to look up which sound to play for an
event; rarely run by hand.

**Key flags:**

- `<event>` — required event name to resolve
- `--harness NAME` — consult the named harness's `sounds.map` layer
- `--cwd PATH` — directory whose ancestor chain is searched for overrides

**Referenced by a skill?** No.
