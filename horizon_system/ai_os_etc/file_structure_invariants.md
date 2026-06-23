# File Structure Invariants — Horizon AIOS

---

## 1. Environment Variables

Hardcoded paths are forbidden in committed files. Use these variables exclusively:

| Variable | Points To | Purpose |
|---|---|---|
| `$HORIZON_ROOT` | The repo root (e.g., `C:\devroot`) | Anchor for all other paths |
| `$HORIZON_SYSTEM` | `$HORIZON_ROOT\horizon_system` | OS system directory — all AIOS assets and tooling |
| `$HORIZON_BIN` | `$HORIZON_ROOT\horizon_system\bin` | User-callable executables; brains have R+X here |
| `$HORIZON_SBIN` | `$HORIZON_ROOT\horizon_system\sbin` | Owner-only privileged scripts; brains: DENY (never on a brain PATH) |
| `$HORIZON_ETC` | `$HORIZON_ROOT\horizon_system\ai_os_etc` | OS configuration documents and invariants |
| `$HORIZON_DOCS` | `$HORIZON_ROOT\horizon_system\documentation` | User-facing documentation |
| `$HORIZON_SOUNDS` | `$HORIZON_SYSTEM\sounds` | Sound files, maps, and vendor audio |
| `$HORIZON_LOGS` | `$HORIZON_ROOT\horizon_system\logs` | Centralized audit and operational logs; brains: DENY |
| `$HORIZON_USRBIN` | `$HORIZON_ROOT\usrbin` | Common application installs shared across brains and projects |
| `$HORIZON_PROJECTS` | `$HORIZON_ROOT\Projects` | Primary user's personal project workspace |
| `$HORIZON_BRAIN_HOME` | Brain user's OS home directory | Brain user's home directory (set only within a brain session; not available in the owner session) |

Rules:
- Scripts resolve these variables at startup; never hardcode paths.
- Templates use placeholder strings (e.g., `AIOS_EXEC_WRAPPER` in the Claude Code settings template) substituted at setup time in local, non-committed copies.
- $HORIZON_ROOT is the only machine-specific variable; all others derive from it.
- Machine-local switcher state lives outside `$HORIZON_ROOT` in `~/.horizon/`: the registry `aios_registry.json`, the generated `active_env.{ps1,sh}`, and the `bin/aios-exec.{ps1,sh}` wrappers. Created by `horizon_aios_switch.py init`; never committed, never synced — analogous to `~/.claude/`. See `documentation/system/aios_switching.md`.

---

## 2. Directory Tree

```
$HORIZON_ROOT/                          # OS repo root; primary user owns everything
├── agents.md                           # Cross-harness canonical agent instructions (Codex, OpenHands, etc.)
├── CLAUDE.md                           # Claude Code counterpart to agents.md — imports it explicitly
├── .claude/
│   ├── CLAUDE.md                       # Thin Claude Code entry point; imports $HORIZON_ROOT/CLAUDE.md
│   ├── CLAUDE.aios-dev.md              # Owner-only AIOS-dev directives; imported by the OWNER stub only, never by brains
│   └── settings.json                   # Devroot-scoped permissions (no hooks, no statusLine)
├── handoffs/                           # Default output directory for /handoff skill (see Section 7)
├── memory/                             # Redirected per-project harness state (transcripts + agent memory); gitignored; ~/.claude/projects junctions here (see documentation/system/memory.md)
├── objectives/                         # Default store for /objective skill — durable multi-session goals (see Section 7)
├── horizon_system/                     # $HORIZON_SYSTEM — OS system directory
│   ├── VERSION                         # Canonical version file (SemVer)
│   ├── bin/                            # $HORIZON_BIN — user-callable executables; brains: R+X
│   │   ├── resolve_sound.py            # Resolver: event name → absolute sound path (see Section 10)
│   │   ├── monitor_status.py           # One-word monitor status check (see agents.md Session Start)
│   │   ├── context_cost.py             # Harness context-overhead measurement (see documentation/context_loading.md)
│   │   └── statusline/                 # Status line scripts for harness UI (see Section 11)
│   ├── sbin/                           # Owner-only privileged scripts; brains: DENY
│   │   ├── bootstrap.ps1               # Windows bootstrap (PowerShell)
│   │   ├── bootstrap.sh                # Unix/Linux/macOS bootstrap
│   │   ├── bootstrap_docker.sh         # Docker bootstrap wrapper
│   │   ├── horizon_aios_doctor.py                   # System health check
│   │   ├── horizon_aios_harden.py              # Apply brains-group ACLs to the AIOS layer (run from bootstrap)
│   │   ├── horizon_aios_monitor.py             # Filesystem audit monitor
│   │   ├── horizon_aios_maintain_logs.py            # Log pruning and rotation
│   │   ├── horizon_aios_register_user_skills.py     # (Re)link usr_skills into skills_sbin (see Section 7)
│   │   ├── horizon_aios_setup_sync_schedule.py      # Upstream sync scheduler
│   │   ├── horizon_aios_switch.py              # AIOS named-registry switcher (see documentation/system/aios_switching.md)
│   │   ├── horizon_aios_create_brain.py             # Provision a brain OS user + scoped folder/ACLs (admin)
│   │   ├── horizon_aios_remove_brain.py             # Deprovision a brain (reverses horizon_aios_create_brain.py) (admin)
│   │   ├── horizon_aios_brain_credential.py         # Brain account credential manager (OS keystore)
│   │   └── [other privileged scripts]
│   ├── skills_bin/                     # Group-readable AIOS skills; brains: R+X explicit (see Section 7)
│   │   └── index.md                    # Skills index — check this first; update when adding a skill
│   ├── skills_sbin/                    # Owner-only privileged skills; brains: DENY (see Section 7)
│   │   ├── index.md
│   │   ├── .gitignore                  # Whitelist: tracks OS skills, ignores user-skill junctions (see Section 7)
│   │   ├── handoff/                    # /handoff skill (owner-only)
│   │   │   └── SKILL.md
│   │   ├── objective/                  # /objective skill (owner-only)
│   │   │   └── SKILL.md
│   │   ├── resync-user-skills/         # /resync-user-skills skill (owner-only)
│   │   │   └── SKILL.md
│   │   └── skill-creation/             # /skill-creation skill (owner-only)
│   │       └── SKILL.md
│   ├── ai_os_etc/                      # $HORIZON_ETC — invariant OS documents (this file lives here)
│   │   ├── security_invariants.md
│   │   ├── file_structure_invariants.md
│   │   ├── ai_os_personalizations.md
│   │   ├── horizon_aios_agents.md      # Agent instructions (harness-agnostic)
│   │   └── horizon_aios_model_prefs.md # User-editable agent model preferences
│   ├── documentation/                  # $HORIZON_DOCS — user-facing docs (full catalog: documentation/index.md)
│   │   ├── index.md                    # Documentation index — every doc, referenceable by path (CC-G4)
│   │   ├── authoring/                  # Authoring guides (e.g. CLAUDE.md authoring)
│   │   ├── build_decisions/            # Architecture decision log
│   │   ├── deployment/                 # Deployment guides by mode (desktop, server, docker)
│   │   ├── development_tools/          # AIOS-dev tooling specs (e.g. consistency_checks.md)
│   │   ├── getting_started/            # Setup guide
│   │   ├── security/                   # Security and audit-logging docs
│   │   ├── system/                     # System config reference, AIOS switching
│   │   └── *.md                        # Root docs: philosophy, dev_values, utilities, context_loading, etc.
│   ├── sounds/                         # Audio assets for event hooks
│   │   ├── sounds.map                  # AIOS default event→sound mapping (see Section 10)
│   │   ├── *.wav                       # Generic, vendor-agnostic sounds
│   │   └── <vendor>_event_sounds/      # Vendor-specific voiced audio (see Section 3)
│   ├── templates/                      # Setup templates for harnesses and brains
│   │   ├── claude_code/                # Claude Code-specific templates
│   │   ├── docker/                     # Docker deployment templates (Dockerfile, docker-compose.yml, .dockerignore)
│   │   ├── aios_overrides.md           # Template for project-level AIOS config overrides
│   │   ├── aios_sounds.conf            # Template for per-project sound overrides (see Section 10)
│   │   ├── aios_statusline.conf        # Template for per-project statusline config (see Section 11)
│   │   ├── aios_monitor.conf.template  # Template for filesystem-monitor config (see security/audit_logging.md)
│   │   └── profile_snippet.{ps1,sh}    # One-line profile include sourcing ~/.horizon/active_env.* (AIOS switcher)
│   ├── harness_configs/                # Harness-specific config (sounds maps, etc.)
│   └── logs/                           # $HORIZON_LOGS — canonical audit/operational logs; brains: DENY; scaffold tracked, content gitignored
├── usrbin/                             # $HORIZON_USRBIN — tool repository; admin draws from here to provision brains (see Section 8)
│   ├── usr_skills/                     # Machine-local user skills; gitignored; linked into skills_sbin (see Section 7)
│   │   └── <skill-name>/SKILL.md
│   └── [installed tools and apps]/     # Admin: full access. Brains: no default access — provisioned selectively per brain.
├── brains/                             # Brain home directories (gitignored per brain, but .aioscommon is tracked)
│   └── .aioscommon/                    # Shared brain provisioning templates — tracked in git; used by horizon_aios_create_brain.py Phase 5
│       ├── brain_CLAUDE.md.template    # Template deployed to brains/<name>/.claude/CLAUDE.md on provisioning
│       └── brain_settings.json.template # Template deployed to brains/<name>/.claude/settings.json on provisioning
└── Projects/                           # $HORIZON_PROJECTS — primary user's project workspace (see Section 8)
    └── [project folders]/              # Primary user sets filesystem permissions per project; no default convention
        ├── aios_overrides.md           # Optional — project-level AIOS config overrides (see Section 7)
        ├── aios_sounds.conf            # Optional — per-project sound overrides (see Section 10)
        └── aios_statusline.conf        # Optional — per-project statusline config (see Section 11)
```

Adding new content categories requires updating this document and the directory tree simultaneously.

---

## 3. Sounds Directory Convention

**Tier 1 — Root (`$HORIZON_SOUNDS/*.wav`):**
- Generic sounds with no vendor-specific voice or branding.
- Any AI harness integration may use these sounds.
- Examples: `work_complete.wav` (generic completion sound), `api_fail.wav` (generic failure sound).
- New sounds added here must be usable without referencing a specific AI product by voice or name.

**Tier 2 — Vendor subdirectories (`$HORIZON_SOUNDS/<vendor>_event_sounds/`):**
- Audio that contains voiced references to a specific AI product or vendor (e.g., "Claude Code is waiting for your input").
- Named using the pattern `<vendor>_event_sounds/` where `<vendor>` matches the harness vendor name in lowercase (e.g., `claude_event_sounds/`, `ollama_event_sounds/`).
- These sounds are only appropriate for use with the matching harness.
- Community contributors adding support for a new harness should create a new vendor subdirectory if they have vendor-voiced audio to contribute.

Scripts that wire sounds to hooks must reference the appropriate tier. If a hook is shared across harnesses, it must use a root-level generic sound, not a vendor subdirectory sound.

---

## 4. Project Inheritance Model

- $HORIZON_ROOT is the outermost scope. Config here applies OS-wide unless overridden.
- Project folders inside $HORIZON_ROOT may be independent git repositories with their own `.claude/` directories.
- A project's `.claude/settings.json` overrides or extends devroot settings for that project only.
- A project's `CLAUDE.md` adds project-specific instructions on top of the canonical `$HORIZON_ROOT/.claude/CLAUDE.md`.
- AI harnesses that support hierarchical config (e.g., Claude Code) load configs from innermost to outermost: project → devroot → global (~/.claude).

**Cross-harness instruction file:** `$HORIZON_ROOT/agents.md` is the canonical agent instruction file for harnesses that read `agents.md` (e.g., Codex, OpenHands). `$HORIZON_ROOT/CLAUDE.md` is its Claude Code counterpart — a filesystem neighbor that explicitly imports `agents.md`. `$HORIZON_ROOT/.claude/CLAUDE.md` is a thin entry point that imports `$HORIZON_ROOT/CLAUDE.md`. Harness-specific extensions live in `$HORIZON_BIN/harness_configs/<harness>/` and do not override agents.md — they supplement it.

**Owner-only development context:** `$HORIZON_ROOT/.claude/CLAUDE.aios-dev.md` holds AIOS-*development* directives (e.g., keep `documentation/index.md` current; run `/horizon_aios_dev_consistency_check`). It is imported **only by the owner/maintainer's machine-local `~/.claude/CLAUDE.md`** — bootstrap adds that import. Brains never import it: `brain_CLAUDE.md.template` chains only the runtime config, so development rules stay out of brain/runtime context. This is the seam for any "applies when *building* the AIOS, not when *using* it" instruction — put it here, never in `agents.md`/`CLAUDE.md`, which every brain loads.

Invariant: project-level config may restrict or extend permissions but must not own hooks or statusLine — those belong to global (~/.claude/settings.json). The devroot layer owns devroot-scoped permissions only.

---

## 5. What the OS Repo Tracks vs Ignores

Tracks:

- All files under `$HORIZON_BIN/` (scripts, sounds, templates, docs, invariants).
- `$HORIZON_ROOT/.claude/CLAUDE.md` and `$HORIZON_ROOT/.claude/settings.json`.
- `.gitignore` itself.

The OS repo does not track (must be gitignored):

- Brain folders and all their contents.
- Local settings overrides (any `*.local.json` or `*.local` variants).
- API keys, tokens, credentials, `.env` files.
- Session data, conversation logs, cache directories — including `$HORIZON_ROOT/memory/`, where the owner's `~/.claude/projects` is junctioned (redirected per-project transcripts + agent memory; ships the mechanism, never content — see `documentation/system/memory.md`).
- OS-specific generated files (`.DS_Store`, `Thumbs.db`, etc.).
- Any file containing a hardcoded real path to this machine's filesystem.

---

## 6. Naming Conventions for Vendor Subdirectories

All vendor-specific subdirectories inside $HORIZON_BIN follow the pattern:

```
<vendor>_event_sounds/
```

Where `<vendor>` is:
- Lowercase.
- The canonical short name of the AI product or vendor (not the company name unless they are the same).
- No spaces — use underscores.

Examples:
- `claude_event_sounds/` — for Anthropic Claude / Claude Code voiced audio.
- `ollama_event_sounds/` — for Ollama voiced audio.
- `codex_event_sounds/` — for OpenAI Codex voiced audio.

This convention applies to all vendor-scoped subdirectories in $HORIZON_SYSTEM, not just sounds. If a new category of vendor-specific asset is added, the subdirectory name follows the same `<vendor>_<category>/` pattern.

**Horizon AIOS artifact naming (branding).** AIOS's own admin-visible artifacts — privileged utility scripts in `sbin/` and the audit/operational log files and directories under `logs/` — carry the `horizon_aios_` filename prefix (lowercase, underscores) so a process listing or a loose log file self-identifies as Horizon AIOS. Stable functional identifiers are exempt (public entry points `bootstrap.*`/`uninstall.*`, the `aios` wrapper, the `brains` group, `aios_*.conf`, `AIOS_*` env vars, scheduled-task names). This is the filename half of the **Branding & Identification invariant** — see `security_invariants.md §8`, which is authoritative and also covers the `Horizon.AIOS` token in log records, OS-object descriptions, and event channels.

---

## 7. Skills, Handoffs, and Project Overrides

### 7.1 Skills

AIOS skills define slash commands (e.g., `/handoff`) available in Claude Code sessions. Each skill is a **directory** (not a flat `.md` file) containing a `SKILL.md` with YAML frontmatter (`name:`, `description:`, optional `tools:`).

Skills come in two classes — OS skills (tracked, shared, overwritable by upstream sync) and user skills (machine-local, gitignored, never synced) — across three source directories:

| Directory | Class | Access | Purpose |
|---|---|---|---|
| `$HORIZON_SYSTEM/skills_bin/<name>/SKILL.md` | OS | Group-readable — all brains may execute | Standard skills |
| `$HORIZON_SYSTEM/skills_sbin/<name>/SKILL.md` | OS | Owner-only — brain users denied access | Privileged skills |
| `$HORIZON_USRBIN/usr_skills/<name>/SKILL.md` | User | Owner-only — machine-local, gitignored | Personal skills kept out of the OS repo and safe from sync |

Each OS directory contains an `index.md` listing its skills. **Always check `index.md` first** before searching individual skill files. **When adding an OS skill, update the index in the same commit.** User skills are not indexed (machine-local).

The same rule governs documentation: any change that adds, moves, renames, or removes a document under `documentation/` (or an authority/invariant doc under `ai_os_etc/`) must update `documentation/index.md` in the **same change** via `/horizon_aios_documentation_index_update` — treat the index entry as part of the doc, exactly as `skill-creation` treats `skills_sbin/index.md`. (Enforced by CC-G4 in `documentation/development_tools/consistency_checks.md`.)

`~/.claude/skills/` is a junction (Windows) or symlink (Unix/macOS) resolving to the appropriate skill tier. For the **primary user** it points to `$HORIZON_SYSTEM/skills_sbin/` (bootstrap creates it). For a **brain**, the brain's home `~/.claude` is itself a symlink/junction to its workspace `brains/<name>/.claude/`, and inside that, `skills/` is a junction to `$HORIZON_SYSTEM/skills_bin/` — so the brain's identity (`CLAUDE.md`, `settings.json`) and skills are surfaced together at the user-level `~/.claude` regardless of cwd. `horizon_aios_create_brain.py` Phase 5 (`_link_brain_claude`) creates both links; `horizon_aios_remove_brain.py` deletes them as reparse points (never following them into the workspace or `skills_bin`). Skills are live on disk with no copy step — only a Claude Code session restart is needed after adding or editing a skill.

**Discovery assumption (operator responsibility if the harness changes).** AIOS skill discovery — for both the owner and brains — relies on onboarding *linking* the home `~/.claude/skills` into the AIOS skill tier (owner → `skills_sbin` aggregate; brain → `skills_bin`) and on the harness auto-discovering `SKILL.md` directories there. AIOS guarantees the link; it does not control the harness's discovery behavior. If a different or updated harness stops scanning `~/.claude/skills`, re-establishing discovery is an operator configuration item, not something AIOS enforces.

**Owner-view aggregation.** The primary user's `~/.claude/skills` points at `skills_sbin`, so the owner sees the brain tier and machine-local skills only if they are linked into that view. `$HORIZON_SYSTEM/sbin/horizon_aios_register_user_skills.py` (run directly or via `/resync-user-skills`) creates a per-skill junction `skills_sbin/<name>` → source for every skill in `skills_bin/` (brain tier) and `usr_skills/` (machine-local), so the owner sees all three tiers flat in one namespace — like `/usr/bin` on root's PATH while `/usr/sbin` stays root-only. **Brains are unaffected:** their `~/.claude/skills` points at `skills_bin` only, so they never see `skills_sbin` or `usr_skills`. The script is idempotent: it (re)links every source `<name>/` that has a `SKILL.md`, prunes stale links, and refuses to shadow a real `skills_sbin` OS skill. It runs automatically from `bootstrap` and at the end of a successful `horizon_aios_sync.py` (both best-effort — they never fail on it), so the links self-heal after a sync refreshes `skills_sbin`. Run it manually (or `/resync-user-skills`) any time you add or remove a skill mid-session.

**Invariant — git must not capture aggregation junctions.** git traverses Windows junctions, so `skills_sbin/.gitignore` is a whitelist: it ignores everything, then re-includes each tracked OS skill (and `index.md`, `.gitignore`). The junctions linking `skills_bin`/`usr_skills` skills into the owner view are thus invisible to git. When adding a new `skills_sbin` OS skill, add it to this whitelist in the same commit or it will be silently untracked.

Invariant: never edit skills directly in `~/.claude/skills/`. Always edit at the source in the repo. There is no deployed copy — the junction points directly to the source.

**Claude Code marketplace plugins.** Claude Code also loads slash commands from marketplace plugins installed separately (e.g., via `claude plugin install`). These plugins appear alongside AIOS skills in the harness UI but are not stored in `skills_sbin/` or `skills_bin/` — they live in the Claude Code plugin directory outside `$HORIZON_ROOT`. Skills such as `code-review`, `update-config`, and `verify` that appear in the harness but are not found in `skills_sbin/` are marketplace plugins, not AIOS skills. The two systems coexist; AIOS skills and marketplace plugins share the same slash command namespace in the harness.

### 7.2 Handoffs Directory

`$HORIZON_ROOT/handoffs/` is the default output directory for the `/handoff` skill. Gitignored; machine-local; not tracked by the OS repo.

The `/handoff` skill searches upward from the current working directory for a project-level `aios_overrides.md` file to determine where to write handoff documents. If no override is found, it defaults to `$HORIZON_ROOT/handoffs/`.

### 7.3 Objectives Directory

`$HORIZON_ROOT/objectives/` is the default store for the `/objective` skill — durable, multi-session goals holding long-term context. Gitignored, machine-local, not tracked by the OS repo. Resolution mirrors handoffs: walk upward for `aios_overrides.md` → `objectives_dir` key, else default.

Durable but ephemeral by design. Pruned by age (last modification) via `horizon_aios_maintain_logs.py` using `AIOS_OBJECTIVES_MAX_DAYS` (default 90); `index.md` is never pruned. No completion or status concept — an objective is retired by ceasing to reference it. Handoffs chain an objective forward by recording its number, name, and path; the objective carries the durable goal a single handoff is too short-lived to hold.

### 7.4 `aios_overrides.md` — Project-Level Config Overrides

Optional per-project file that overrides AIOS defaults. Project-owned (committed to the project repo, not the OS repo).

Key properties:
- Location: `<project-root>/aios_overrides.md` — never inside `.claude/`
- Format: simple `key: value` pairs, one per line, `#` comment lines ignored
- Discovery: AIOS skills walk upward from the current working directory to find it, stopping at `$HORIZON_ROOT`
- Template: `$HORIZON_SYSTEM/templates/aios_overrides.md` — copy to project root and configure

Currently supported keys:
- `handoffs_dir` — override the handoffs output directory for this project
- `objectives_dir` — override the objectives store directory for this project
- `project_display_name` — friendly name for handoff doc headers (defaults to directory basename)

The template file is fully annotated.

---

## 8. usrbin and Projects

### 8.1 usrbin — Shared Application Installs (`$HORIZON_USRBIN`)

`$HORIZON_ROOT/usrbin/` is the AIOS equivalent of Linux `/usr/bin` — user-installed applications that multiple brains or projects may consume (not OS-layer tooling, which belongs in `$HORIZON_BIN`).

**Filesystem permissions (set by the administrative context using OS tools):**
- Administrative context: read, write, execute
- Brain accounts: no default access

`$HORIZON_USRBIN` is a tool repository for the administrative context to draw from when provisioning brains. Brains do not get blanket access to this directory. The administrative context selects specific tools and provisions them into each brain's environment (see `security_invariants.md §4`).

Check `$HORIZON_USRBIN` before installing new tools.

### 8.2 Projects — Primary User Workspace (`$HORIZON_PROJECTS`)

`$HORIZON_ROOT/Projects/` is the primary user's home-directory equivalent — personal development work and projects unrelated to AIOS. Each project folder is independent and may be its own git repository.

**Filesystem permissions:** No convention set at the `Projects/` level. The primary user sets permissions per project folder using OS tools. Brains are neither granted nor denied access by default.

**Single-user model:** AIOS currently presumes one primary user. The multi-user extension is multiple OS accounts each with their own brain user profile, all sharing the same AIOS configuration layer. Common configuration == one OS across multiple users; per-user state lives in each account's profile, not in `$HORIZON_ROOT`.

**Automated brains:** Because each brain is a native OS user account, a brain can be run as a scheduled task or automated agent — Task Scheduler (Windows) or cron/systemd (Unix) — once it is trusted for its expert function. The brain account's filesystem scope is the sandbox. No additional isolation mechanism is needed; the OS enforces it. This is the same model as a service account running a daemon.

---

## 10. Sound Configuration

AIOS maps named events to sound files through a three-layer resolution chain. Hook scripts call `resolve_sound.py` rather than hardcoding paths.

### 10.1 Resolution Order

For a given event, `$HORIZON_BIN/resolve_sound.py` checks in order:

1. `aios_sounds.conf` at the nearest ancestor of cwd (walking up, stopping at `$HORIZON_ROOT`)
2. `$HORIZON_SYSTEM/harness_configs/<harness>/sounds.map` (if `--harness` is passed)
3. `$HORIZON_SOUNDS/sounds.map` (AIOS defaults)

First match wins. An empty value (`event_name =`) silences that event.

Before resolution, `resolve_sound.py` honors the `sounds_enabled` flag (see §10.6). If muted, it prints nothing and exits 0 — no event resolves.

### 10.2 File Locations

| File | Purpose |
|---|---|
| `$HORIZON_SOUNDS/aios_sounds.conf` | Master sound settings — the `sounds_enabled` kill switch |
| `$HORIZON_SOUNDS/sounds.map` | AIOS default event→sound mapping |
| `$HORIZON_SYSTEM/harness_configs/<harness>/sounds.map` | Harness-specific events and overrides |
| `$HORIZON_BIN/resolve_sound.py` | Resolver script — call from hooks |
| `$HORIZON_SYSTEM/templates/aios_sounds.conf` | Template for per-project overrides |
| `<project-root>/aios_sounds.conf` | Per-project override (copy from template) |

### 10.3 Event Taxonomy

Generic events (all harnesses):

| Event | Default sound |
|---|---|
| `task_complete` | `work_complete.wav` |
| `api_error` | `api_fail.wav` |
| `input_needed` | _(unmapped — set per harness or project)_ |
| `session_start` | _(unmapped)_ |
| `session_stop` | _(unmapped)_ |
| `notification` | _(unmapped)_ |

Harness-specific events use dot-prefix: `<harness>.<event>` (e.g., `claude.context_80`).

### 10.4 Hook Usage

```bash
sound=$(python "$HORIZON_BIN/resolve_sound.py" task_complete --harness claude_code)
[ -n "$sound" ] && bash "$HORIZON_SOUNDS/play_sound.sh" "$sound"
```

### 10.5 Per-Project Override

Copy `$HORIZON_SYSTEM/templates/aios_sounds.conf` to the project or brain root. Uncomment and set only the events to override. Unset events fall through to the harness and AIOS defaults.

Invariant: `aios_sounds.conf` is project-owned and committed to the project's own repo, not the OS repo. Add it to `$HORIZON_ROOT/.gitignore` if it should stay machine-local.

### 10.6 Master & Per-Project Mute (`sounds_enabled`)

A reserved `sounds_enabled` key (not an event→sound mapping) turns sounds off at two scopes. Accepted values: `true/false`, `1/0`, `yes/no`, `on/off`, `enabled/disabled`.

| Scope | File | Effect |
|---|---|---|
| Master | `$HORIZON_SOUNDS/aios_sounds.conf` | `sounds_enabled = false` silences **all** events everywhere |
| Per-project | nearest `aios_sounds.conf` (walk-up) | `sounds_enabled = false` silences that subtree |

Invariant: **the master switch is absolute.** When the master is `false`, no project-level `aios_sounds.conf` can re-enable sound. A per-project switch only takes effect when the master is enabled, and applies only to its own subtree. An absent or unrecognized value is treated as enabled (fail open).

---

## 11. Statusline Configuration

AIOS statusline scripts support per-project display and threshold configuration through the same walk-up discovery pattern as sounds.

### 11.1 Configuration Keys

| Key | Default | Description |
|---|---|---|
| `show_git` | `true` | Show git branch in statusline |
| `show_context_bar` | `true` | Show context usage bar |
| `bar_width` | `20` | Width of context bar in characters |
| `project_name` | _(cwd basename)_ | Override directory label shown in statusline |
| `context_thresholds` | `30,40,50,60,70,80,90` | Comma-separated context % values that trigger audio alerts |

### 11.2 Resolution Order

`statusline-context-alerts.ps1` walks up from the cwd supplied by the harness (JSON `cwd` field), checking each directory for `aios_statusline.conf`, stopping at `$HORIZON_ROOT`. First file found wins. If none found, all defaults apply.

### 11.3 Sound Integration

Context threshold sounds use `resolve_sound.py` — they resolve through `aios_sounds.conf` → harness sounds.map → AIOS defaults (see §10). Override threshold sounds by setting `claude.context_<N>` keys in the project's `aios_sounds.conf`.

### 11.4 Per-Project Usage

Copy `$HORIZON_SYSTEM/templates/aios_statusline.conf` to the project or brain root. Uncomment and set only the keys to override.

Invariant: `aios_statusline.conf` is project-owned. Add it to `$HORIZON_ROOT/.gitignore` if it should stay machine-local.
