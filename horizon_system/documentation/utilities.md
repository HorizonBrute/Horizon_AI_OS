# Horizon AIOS — Utilities Reference

Most utilities here live in `$HORIZON_SYSTEM/sbin/` (and `scripts/`) and are
administrative: they operate on the AIOS layer itself — hardening its
permissions, monitoring its integrity, maintaining its logs, provisioning brain
accounts and credentials, syncing upstream, and wiring its configuration. They
run as the primary OS user or elevated (Administrator/root) and are excluded
from brain accounts by explicit Deny ACLs enforced by `harden_aios.py`. A few
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

## doctor.py

**Path:** `$HORIZON_SYSTEM/sbin/doctor.py`

System health check. Verifies that the AIOS install is correctly bootstrapped:
environment variables are set and point to real directories, the skills junction
(`~/.claude/skills/`) resolves to `skills_sbin/`, git hooks are installed, the
local config file exists, the AIOS registry is valid and its active entry
points to a real AIOS root, and ACLs on `sbin/`, `skills_sbin/`, and `logs/`
include an explicit Deny for the `brains` group. Also checks monitor status
(advisory — a stopped monitor is a warning, not a failure).

**When to use it:** After initial bootstrap, after pulling an upstream update
that touches the bootstrap sequence, or whenever something behaves unexpectedly
and you need a quick status read.

**Key flags:** None — it runs all checks unconditionally and prints a summary.
Exit code is 1 if any check failed, 0 if only warnings or clean.

**Referenced by a skill?** No.

---

## monitor_aios.py

**Path:** `$HORIZON_SYSTEM/sbin/monitor_aios.py`

Filesystem integrity monitor. Watches the AIOS system directories for
unexpected creates, modifies, deletes, and moves, and appends each event as a
JSON line to a daily log file in `$HORIZON_SYSTEM/logs/aios_monitor/`. The
default watch set covers `$HORIZON_SYSTEM` (recursive), `$HORIZON_USRBIN`
(recursive), `$HORIZON_ROOT/.claude` (recursive), `$HORIZON_ROOT` top-level
(non-recursive), and the brains root (non-recursive, structural changes only).
Brain home contents are excluded by default; opt in with `--brain-dirs`.

Runs as the administrative context. Brain accounts must not have write access
to the log directory — `harden_aios.py` enforces this.

**When to use it:** Run it as a persistent background process (or service) on
any installation where audit logging is required. For full setup instructions
and log consumption guidance see `$HORIZON_DOCS/security/audit_logging.md`.

**Key flags:**

- `--watch PATH` — add an extra path to watch recursively (repeatable; additive)
- `--brain-dirs` — escalate brains-root watch to recursive (logs brain internals)
- `--no-brains-root` — disable the default brains-root watch
- `--config PATH` — config file (default: `$HORIZON_ETC/aios_monitor.conf`)
- `--log-dir PATH` — log directory (default: `$HORIZON_SYSTEM/logs/aios_monitor/`)

**Referenced by a skill?** No.

---

## harden_aios.py

**Path:** `$HORIZON_SYSTEM/sbin/harden_aios.py`

Applies the authoritative brains-group ACL model to the AIOS layer. Grants
the `brains` group Read+Execute on `bin/` and `skills_bin/`, applies a broad
no-write Deny across `$HORIZON_SYSTEM`, and adds an explicit full Deny on
`sbin/`, `skills_sbin/`, and `logs/`. On Windows it uses `icacls`; on Linux it
uses `setfacl` when available and falls back to `chmod`; on macOS it uses
`chmod`. Requires Administrator/root. Run by bootstrap (Section 9); re-run
after structural changes to `$HORIZON_SYSTEM`.

**When to use it:** Initial bootstrap, after adding or removing directories
under `$HORIZON_SYSTEM`, or when `doctor.py` reports a missing Deny ACE.

**Key flags:**

- `--strict` — additionally strip inherited ACEs (Windows: `/inheritance:r`;
  Unix: `chown -R` + mode bits) for a locked-down standalone install; default
  (additive) preserves existing ACLs and enforces the model by adding ACEs only
- `--dry-run` — print every action that would be taken without executing anything
- `--horizon-root PATH` — explicit root path; otherwise derived from the
  script's own location

**Referenced by a skill?** No.

---

## maintain_logs.py

**Path:** `$HORIZON_SYSTEM/sbin/maintain_logs.py`

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

## brain_credential.py

**Path:** `$HORIZON_SYSTEM/sbin/brain_credential.py`

Manages brain OS-account passwords in the native OS keystore (Windows
Credential Manager, macOS Keychain, Linux Secret Service via the `keyring`
library). Provides CLI commands to store, retrieve, rotate, delete, and list
brain credentials. `rotate` generates a cryptographically random 64-character
password, updates the OS account, and stores the new value in the keystore
atomically. Requires Administrator/root. Also importable as a library
(`from brain_credential import store_password`) for use by `create_brain.py`
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

## aios_switch.py

**Path:** `$HORIZON_SYSTEM/sbin/aios_switch.py`

Switches the local machine's Claude Code harness configuration to point at a
different named Horizon AIOS install. A machine is normally bound to one AIOS
by five pointers (environment variables, `~/.claude/CLAUDE.md`, the skills
junction, `settings.json` hooks, and the sync schedule). This tool rewrites the
volatile three — env snippet (`~/.horizon/active_env.{ps1,sh}`),
`~/.claude/CLAUDE.md`, and the `~/.claude/skills/` junction — while leaving
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

**Referenced by a skill?** No. See `$HORIZON_DOCS/system/aios_switching.md`
for the full switching guide.

---

## register_user_skills.py

**Path:** `$HORIZON_SYSTEM/sbin/register_user_skills.py`

Aggregates the owner's complete skill view into `skills_sbin/` by creating
per-skill junctions (Windows) or symlinks (Unix) for skills from two sources:
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

## create_brain.py

**Path:** `$HORIZON_SYSTEM/scripts/create_brain.py`

Provisions a new AI brain: creates the `<brain-name>` OS user, the shared
`brains` group (Read+Execute on `bin/` and `skills_bin/`) and a per-brain group
(rwx on the brain folder), the workspace at `$HORIZON_ROOT/brains/<brain-name>/`,
and a login shell profile that exports the `HORIZON_*` vars and cds into the
brain folder. The account password is auto-generated (random 64-char) and stored
in the OS native keystore via `brain_credential.py`. The `sbin/skills_sbin/logs`
Deny ACEs are always (re)applied after all grants, per the security invariants.
Requires Administrator/root; stdlib only (Python 3.6+).

**When to use it:** When standing up a new isolated brain account.

**Key flags:**

- `<brain-name>` — required positional name (lowercase, `[a-z][a-z0-9_]{1,31}`)
- `--horizon-root PATH` — explicit root; otherwise derived from script location
- `--dry-run` — print every action without making changes

**Referenced by a skill?** No.

---

## remove_brain.py

**Path:** `$HORIZON_SYSTEM/scripts/remove_brain.py`

Deprovisioning counterpart to `create_brain.py`. Removes a brain's OS user
account, its per-brain group, its workspace folder, its user-profile config
(including the `~/.claude/skills` junction, deleted with a reparse-point `rmdir`
so the `skills_bin` target is never followed), and its stored credential. The
shared `brains` group is left intact. Validates the name and refuses reserved
names (brains, root/administrator, the invoking user, etc.). Requires
Administrator/root.

**When to use it:** When retiring a brain account created by `create_brain.py`.

**Key flags:**

- `<brain-name>` — required positional name
- `--horizon-root PATH` — explicit root; otherwise derived from script location
- `--yes` — skip the confirmation prompt
- `--dry-run` — print what would be removed without changing anything

**Referenced by a skill?** No.

---

## sync_aios.py

**Path:** `$HORIZON_SYSTEM/sbin/sync_aios.py`

Pulls upstream AIOS updates into the local tree. Reads sync settings from
`$HORIZON_ETC/aios_local.conf` (`SYNC_AIOS_FROM_REMOTE`, `AIOS_REPO_REMOTE`,
`AIOS_REPO_BRANCH`, …), verifies git is available and the working tree is clean,
and performs a fast-forward-only merge from the configured remote/branch so a
scheduled run can never create a merge commit or clobber local work. Activity is
logged to the configured AIOS log dir. This is the script driven by the auto-sync
scheduled task; run it manually to sync on demand.

**When to use it:** To pull the latest AIOS layer manually, or as the body of the
scheduled sync job installed by `setup_sync_schedule.py`.

**Key flags:** None — all behaviour comes from `aios_local.conf`.

**Referenced by a skill?** No.

---

## setup_sync_schedule.py

**Path:** `$HORIZON_SYSTEM/sbin/setup_sync_schedule.py`

Installs (or updates) the recurring auto-sync job that runs `sync_aios.py`: a
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

## analyze_aios_monitor.py

**Path:** `$HORIZON_SYSTEM/sbin/analyze_aios_monitor.py`

Reads the JSON-line logs produced by `monitor_aios.py`, summarizes file-change
events and monitor uptime gaps, and appends a report to
`$HORIZON_SYSTEM/logs/security.log`. Can optionally forward alerts to the OS
system log (syslog on Linux; Windows Event Log when `pywin32` is present). Meant
to run as the administrative context on a schedule. See
`$HORIZON_DOCS/security/audit_logging.md` for scheduling guidance.

**When to use it:** Periodically (e.g., daily) to triage monitor output into a
single security log, or ad hoc to review recent integrity events.

**Key flags:**

- `--days N` — number of days back to analyze
- `--log-dir PATH` — monitor log dir (default: `logs/aios_monitor/`)
- `--security-log PATH` — output report path (default: `logs/security.log`)
- `--syslog` — also emit alerts to the OS system log

**Referenced by a skill?** No.

---

## monitor_status.py

**Path:** `$HORIZON_SYSTEM/bin/monitor_status.py`

Tiny status probe: reports whether a `monitor_aios.py` process is currently
running. Prints `running`, `stopped`, or `unknown`. Cross-platform (CIM query on
Windows, `pgrep` on Unix). Used by `doctor.py` and the status line to surface
monitor health without requiring elevation.

**When to use it:** For a quick check that the integrity monitor is up.

**Key flags:** None.

**Referenced by a skill?** No.

---

## resolve_sound.py

**Path:** `$HORIZON_SYSTEM/bin/resolve_sound.py`

Resolves an AIOS event name (e.g. `task_complete`) to an absolute sound-file
path using the nearest `aios_sounds.conf` ancestor override, then the
per-harness `sounds.map`, then the system default `sounds/sounds.map`. Prints the
path or nothing (a missing sound is not an error — always exit 0). Intended to be
called from harness hooks, which pipe its output to `sounds/play_sound.sh`.

**When to use it:** From a notification hook to look up which sound to play for an
event; rarely run by hand.

**Key flags:**

- `<event>` — required event name to resolve
- `--harness NAME` — consult the named harness's `sounds.map` layer
- `--cwd PATH` — directory whose ancestor chain is searched for overrides

**Referenced by a skill?** No.
