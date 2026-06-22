# Horizon AIOS — Utilities Reference

The scripts in `$HORIZON_SYSTEM/sbin/` are administrative utilities that
operate on the AIOS layer itself: hardening its permissions, monitoring its
integrity, maintaining its logs, managing brain credentials, and wiring its
configuration. They run as the primary OS user or elevated (Administrator/root)
and are excluded from brain accounts by explicit Deny ACLs enforced by
`harden_aios.py`.

Several utilities are surfaced as Claude skills — when invoked through a skill,
Claude drives the script with appropriate arguments and interprets the output.
The scripts also work standalone from any shell.

---

## context_cost.py

**Path:** `$HORIZON_SYSTEM/sbin/context_cost.py`

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
