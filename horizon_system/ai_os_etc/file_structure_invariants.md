# File Structure Invariants — Horizon AIOS

---

## 1. Environment Variables

Hardcoded paths are forbidden in committed files. Use these variables exclusively:

| Variable | Points To | Purpose |
|---|---|---|
| `$HORIZON_ROOT` | The repo root (e.g., `C:\devroot`) | Anchor for all other paths |
| `$HORIZON_SYSTEM` | `$HORIZON_ROOT\horizon_system` | OS system directory — all AIOS assets and tooling |
| `$HORIZON_BIN` | `$HORIZON_ROOT\horizon_system\bin` | User-callable executables; brains have R+X here |
| `$HORIZON_ETC` | `$HORIZON_ROOT\horizon_system\ai_os_etc` | OS configuration documents and invariants |
| `$HORIZON_DOCS` | `$HORIZON_ROOT\horizon_system\documentation` | User-facing documentation |
| `$HORIZON_SOUNDS` | `$HORIZON_SYSTEM\sounds` | Sound files, maps, and vendor audio |
| `$HORIZON_LOGS` | `$HORIZON_ROOT\logs` | Centralized audit and operational logs |
| `$HORIZON_USRBIN` | `$HORIZON_ROOT\usrbin` | Common application installs shared across brains and projects |
| `$HORIZON_PROJECTS` | `$HORIZON_ROOT\Projects` | Primary user's personal project workspace |
| `$HORIZON_KEYS` | `$HORIZON_ROOT\keys` | Designated location for brain-accessible credential files |

Rules:
- Scripts resolve these variables at startup; never hardcode paths.
- Templates use placeholder strings (e.g., `HORIZON_BIN_PATH`) substituted at setup time in local, non-committed copies.
- $HORIZON_ROOT is the only machine-specific variable; all others derive from it.

---

## 2. Directory Tree

```
$HORIZON_ROOT/                          # OS repo root; primary user owns everything
├── agents.md                           # Cross-harness canonical agent instructions (Codex, OpenHands, etc.)
├── CLAUDE.md                           # Claude Code counterpart to agents.md — imports it explicitly
├── .claude/
│   ├── CLAUDE.md                       # Thin Claude Code entry point; imports $HORIZON_ROOT/CLAUDE.md
│   └── settings.json                   # Devroot-scoped permissions (no hooks, no statusLine)
├── handoffs/                           # Default output directory for /handoff skill (see Section 7)
├── horizon_system/                     # $HORIZON_SYSTEM — OS system directory
│   ├── VERSION                         # Canonical version file (SemVer)
│   ├── bin/                            # $HORIZON_BIN — user-callable executables; brains: R+X
│   │   ├── resolve_sound.py            # Resolver: event name → absolute sound path (see Section 10)
│   │   ├── monitor_status.py           # One-word monitor status check (see agents.md Session Start)
│   │   └── statusline/                 # Status line scripts for harness UI (see Section 11)
│   ├── sbin/                           # Owner-only privileged scripts; brains: DENY
│   │   ├── bootstrap.ps1               # Windows bootstrap (PowerShell)
│   │   ├── bootstrap.sh                # Unix/Linux/macOS bootstrap
│   │   ├── bootstrap_docker.sh         # Docker bootstrap wrapper
│   │   ├── doctor.py                   # System health check
│   │   ├── monitor_aios.py             # Filesystem audit monitor
│   │   ├── maintain_logs.py            # Log pruning and rotation
│   │   ├── setup_sync_schedule.py      # Upstream sync scheduler
│   │   └── [other privileged scripts]
│   ├── skills_bin/                     # Group-readable AIOS skills; brains: R+X explicit (see Section 7)
│   │   └── index.md                    # Skills index — check this first; update when adding a skill
│   ├── skills_sbin/                    # Owner-only privileged skills; brains: DENY (see Section 7)
│   │   ├── index.md
│   │   ├── handoff/                    # /handoff skill (owner-only)
│   │   │   └── SKILL.md
│   │   └── skill-creation/             # /skill-creation skill (owner-only)
│   │       └── SKILL.md
│   ├── ai_os_etc/                      # $HORIZON_ETC — invariant OS documents (this file lives here)
│   │   ├── security_invariants.md
│   │   ├── file_structure_invariants.md
│   │   ├── ai_os_personalizations.md
│   │   └── horizon_aios_agents.md      # Agent instructions (harness-agnostic)
│   ├── documentation/                  # $HORIZON_DOCS — user-facing docs
│   │   ├── deployment/                 # Deployment guides by mode (desktop.md, docker.md, etc.)
│   │   ├── tested_configurations.md    # Verified harness/OS/deployment compatibility matrix
│   ├── sounds/                         # Audio assets for event hooks
│   │   ├── sounds.map                  # AIOS default event→sound mapping (see Section 10)
│   │   ├── *.wav                       # Generic, vendor-agnostic sounds
│   │   └── <vendor>_event_sounds/      # Vendor-specific voiced audio (see Section 3)
│   ├── templates/                      # Setup templates for harnesses and brains
│   │   ├── claude_code/                # Claude Code-specific templates
│   │   ├── docker/                     # Docker deployment templates (Dockerfile, docker-compose.yml, .dockerignore)
│   │   ├── aios_overrides.md           # Template for project-level AIOS config overrides
│   │   ├── aios_sounds.conf            # Template for per-project sound overrides (see Section 10)
│   │   └── aios_statusline.conf        # Template for per-project statusline config (see Section 11)
│   ├── harness_configs/                # Harness-specific config (sounds maps, etc.)
│   └── scripts/                        # Admin setup scripts (create_brain.py, etc.)
├── keys/                               # $HORIZON_KEYS — credential store; per-brain subdirs with OS filesystem permissions (see Section 9)
│   └── <brain-name>/                   # Admin: full access. Named brain account: read. All other brains: none.
├── usrbin/                             # $HORIZON_USRBIN — tool repository; admin draws from here to provision brains (see Section 8)
│   └── [installed tools and apps]/     # Admin: full access. Brains: no default access — provisioned selectively per brain.
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
- Session data, conversation logs, cache directories.
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

---

## 7. Skills, Handoffs, and Project Overrides

### 7.1 Skills

AIOS skills define slash commands (e.g., `/handoff`) available in Claude Code sessions. Each skill is a **directory** (not a flat `.md` file) containing a `SKILL.md` with YAML frontmatter (`name:`, `description:`, optional `tools:`).

Skills are split across two source directories mirroring the bin/sbin security model:

| Directory | Access | Purpose |
|---|---|---|
| `$HORIZON_SYSTEM/skills_bin/<name>/SKILL.md` | Group-readable — all brains may execute | Standard skills |
| `$HORIZON_SYSTEM/skills_sbin/<name>/SKILL.md` | Owner-only — brain users denied access | Privileged skills |

Each directory contains an `index.md` listing all skills it holds. **Always check `index.md` first** before searching individual skill files. **When adding a skill, update the index in the same commit.**

`~/.claude/skills/` is a junction (Windows) or symlink (Unix/macOS) pointing to `$HORIZON_SYSTEM/skills_sbin/` for the primary user, and to `$HORIZON_SYSTEM/skills_bin/` for brain users. Skills are live on disk with no copy step — only a Claude Code session restart is needed after adding or editing a skill. Bootstrap creates the primary user junction; `create_brain.py` creates the brain junction.

Invariant: never edit skills directly in `~/.claude/skills/`. Always edit at the source in the repo. There is no deployed copy — the junction points directly to the source.

### 7.2 Handoffs Directory

`$HORIZON_ROOT/handoffs/` is the default output directory for the `/handoff` skill. Gitignored; machine-local; not tracked by the OS repo.

The `/handoff` skill searches upward from the current working directory for a project-level `aios_overrides.md` file to determine where to write handoff documents. If no override is found, it defaults to `$HORIZON_ROOT/handoffs/`.

### 7.3 `aios_overrides.md` — Project-Level Config Overrides

Optional per-project file that overrides AIOS defaults. Project-owned (committed to the project repo, not the OS repo).

Key properties:
- Location: `<project-root>/aios_overrides.md` — never inside `.claude/`
- Format: simple `key: value` pairs, one per line, `#` comment lines ignored
- Discovery: AIOS skills walk upward from the current working directory to find it, stopping at `$HORIZON_ROOT`
- Template: `$HORIZON_SYSTEM/templates/aios_overrides.md` — copy to project root and configure

Currently supported keys:
- `handoffs_dir` — override the handoffs output directory for this project
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

## 9. keys — Credential Store (`$HORIZON_KEYS`)

`$HORIZON_ROOT/keys/` is the canonical location for credential material brains may read.

**Structure:** Organize by brain name (or by service, then brain). Each subdirectory holds the credentials for one brain.

```
keys/
├── <brain-name>/          # one directory per brain that needs credentials
│   ├── api_key            # plain text or env-file format
│   └── service_account.json
└── <another-brain>/
    └── ...
```

**Filesystem permissions (set by the administrative context using OS tools):**
- Administrative context: full access to `keys/` and all subdirectories
- Each `keys/<brain-name>/`: that brain's OS account gets read-only; all other accounts denied

**Git:** The `keys/` directory scaffold is tracked. All key content is gitignored. Never commit credentials. See `.gitignore` for the pattern.

**Threat model:** See `security_invariants.md §0` (Credential and Data Containment). Keys provisioned here must be scoped to the brain's minimum functional requirements.

---

## 10. Sound Configuration

AIOS maps named events to sound files through a three-layer resolution chain. Hook scripts call `resolve_sound.py` rather than hardcoding paths.

### 10.1 Resolution Order

For a given event, `$HORIZON_BIN/resolve_sound.py` checks in order:

1. `aios_sounds.conf` at the nearest ancestor of cwd (walking up, stopping at `$HORIZON_ROOT`)
2. `$HORIZON_SYSTEM/harness_configs/<harness>/sounds.map` (if `--harness` is passed)
3. `$HORIZON_SOUNDS/sounds.map` (AIOS defaults)

First match wins. An empty value (`event_name =`) silences that event.

### 10.2 File Locations

| File | Purpose |
|---|---|
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
