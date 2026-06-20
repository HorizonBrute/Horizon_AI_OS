# File Structure Invariants — Horizon AIOS

These invariants define how Horizon AIOS is laid out on disk, what each directory means, and the rules all scripts, templates, and AI agents must follow when referencing paths. Deviating from these conventions breaks portability and community shareability.

---

## 1. Environment Variables

All scripts, templates, hooks, and AI agent instructions must reference Horizon AIOS paths exclusively through these environment variables. Hardcoded paths are forbidden in committed files.

| Variable | Points To | Purpose |
|---|---|---|
| `$HORIZON_ROOT` | The repo root (e.g., `C:\devroot`) | Anchor for all other paths |
| `$HORIZON_BIN` | `$HORIZON_ROOT\horizon_bin` | Tooling, scripts, sounds, templates, assets |
| `$HORIZON_ETC` | `$HORIZON_ROOT\horizon_bin\ai_os_etc` | OS configuration documents and invariants |
| `$HORIZON_DOCS` | `$HORIZON_ROOT\horizon_bin\documentation` | User-facing documentation |

Rules:
- Every script that references a Horizon path must source or resolve these variables at startup, not hardcode the paths they currently point to.
- Templates use placeholder strings (e.g., `HORIZON_BIN_PATH`) that are substituted with real values at setup time in local, non-committed copies.
- $HORIZON_ROOT is the only variable whose value is machine-specific. All other variables derive from it.

---

## 2. Directory Tree

```
$HORIZON_ROOT/                          # OS repo root; primary user owns everything
├── agents.md                           # Cross-harness canonical agent instructions (Codex, OpenHands, etc.)
├── .claude/
│   ├── CLAUDE.md                       # Claude Code entry point; imports agents.md via @ syntax
│   └── settings.json                   # Devroot-scoped permissions (no hooks, no statusLine)
├── handoffs/                           # Default output directory for /handoff skill (see Section 7)
├── horizon_bin/                        # $HORIZON_BIN — all OS tooling and assets
│   ├── ai_os_etc/                      # $HORIZON_ETC — invariant OS documents (this file lives here)
│   │   ├── security_invariants.md
│   │   ├── file_structure_invariants.md
│   │   └── ai_os_personalizations.md
│   ├── documentation/                  # $HORIZON_DOCS — user-facing docs
│   ├── skills/                         # AIOS skill definitions — source of truth (see Section 7)
│   │   └── handoff/                    # /handoff skill (directory containing SKILL.md)
│   │       └── SKILL.md
│   ├── sounds/                         # Audio assets for event hooks
│   │   ├── *.wav                       # Generic, vendor-agnostic sounds
│   │   └── <vendor>_event_sounds/      # Vendor-specific voiced audio (see Section 3)
│   ├── statusline/                     # Status line scripts for harness UI
│   ├── templates/                      # Setup templates for harnesses and brains
│   │   ├── claude_code/                # Claude Code-specific templates
│   │   └── aios_overrides.md           # Template for project-level AIOS config overrides
│   └── sbin/                           # Owner-only privileged scripts (see security_invariants.md)
└── [project folders]/                  # Individual projects; each may be its own git repo
    └── aios_overrides.md               # Optional — project-level AIOS config overrides (see Section 7)
```

Each node's purpose is fixed. Adding new categories of content requires updating this document and the directory tree simultaneously.

---

## 3. Sounds Directory Convention

The sounds directory uses a two-tier structure that separates generic audio from vendor-voiced audio:

**Tier 1 — Root (`$HORIZON_BIN/sounds/*.wav`):**
- Generic sounds with no vendor-specific voice or branding.
- Any AI harness integration may use these sounds.
- Examples: `WorkComplete_ork.wav` (generic completion sound), `APIFail.wav` (generic failure sound).
- New sounds added here must be usable without referencing a specific AI product by voice or name.

**Tier 2 — Vendor subdirectories (`$HORIZON_BIN/sounds/<vendor>_event_sounds/`):**
- Audio that contains voiced references to a specific AI product or vendor (e.g., "Claude Code is waiting for your input").
- Named using the pattern `<vendor>_event_sounds/` where `<vendor>` matches the harness vendor name in lowercase (e.g., `claude_event_sounds/`, `ollama_event_sounds/`).
- These sounds are only appropriate for use with the matching harness.
- Community contributors adding support for a new harness should create a new vendor subdirectory if they have vendor-voiced audio to contribute.

Scripts that wire sounds to hooks must reference the appropriate tier. If a hook is shared across harnesses, it must use a root-level generic sound, not a vendor subdirectory sound.

---

## 4. Project Inheritance Model

Horizon AIOS uses filesystem hierarchy to model config inheritance for nested projects:

- $HORIZON_ROOT is the outermost scope. Config here applies OS-wide unless overridden.
- Project folders inside $HORIZON_ROOT may be independent git repositories with their own `.claude/` directories.
- A project's `.claude/settings.json` overrides or extends devroot settings for that project only.
- A project's `CLAUDE.md` adds project-specific instructions on top of the canonical `$HORIZON_ROOT/.claude/CLAUDE.md`.
- AI harnesses that support hierarchical config (e.g., Claude Code) load configs from innermost to outermost: project → devroot → global (~/.claude).

**Cross-harness instruction file:** `$HORIZON_ROOT/agents.md` is the canonical agent instruction file for harnesses that read `agents.md` (e.g., Codex, OpenHands). `$HORIZON_ROOT/.claude/CLAUDE.md` imports it via `@` syntax so Claude Code reads the same content. Harness-specific extensions live in `$HORIZON_BIN/harness_configs/<harness>/` and do not override agents.md — they supplement it.

Invariant: project-level config may restrict or extend permissions but must not own hooks or statusLine — those belong to global (~/.claude/settings.json). The devroot layer owns devroot-scoped permissions only.

---

## 5. What the OS Repo Tracks vs Ignores

The Horizon AIOS git repository tracks:

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

This convention applies to all vendor-scoped subdirectories in $HORIZON_BIN, not just sounds. If a new category of vendor-specific asset is added, the subdirectory name follows the same `<vendor>_<category>/` pattern.

---

## 7. Skills, Handoffs, and Project Overrides

### 7.1 Skills

AIOS skills define slash commands (e.g., `/handoff`) available in Claude Code sessions. Each skill is a **directory** (not a flat `.md` file) containing a `SKILL.md` with YAML frontmatter (`name:`, `description:`, optional `tools:`). Skills have two canonical locations:

| Location | Role |
|---|---|
| `$HORIZON_BIN/skills/<name>/SKILL.md` | Source of truth — versioned with AIOS, committed to the OS repo |
| `~/.claude/skills/<name>/SKILL.md` | Deployed copy — where Claude Code reads skills from |

Deploy by copying directories: `cp -r "$HORIZON_BIN/skills/"* ~/.claude/skills/`. See `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md` Step 7 for full commands.

Invariant: never edit skills directly in `~/.claude/skills/`. Always edit the source at `$HORIZON_BIN/skills/` and redeploy. The deployed copy is ephemeral — it is not committed.

### 7.2 Handoffs Directory

`$HORIZON_ROOT/handoffs/` is the default output directory for the `/handoff` skill. It is NOT tracked by the OS repo. It is gitignored. It is machine-local session continuity data. Each machine maintains its own handoffs history.

The `/handoff` skill searches upward from the current working directory for a project-level `aios_overrides.md` file to determine where to write handoff documents. If no override is found, it defaults to `$HORIZON_ROOT/handoffs/`.

### 7.3 `aios_overrides.md` — Project-Level Config Overrides

`aios_overrides.md` is an optional per-project configuration file that overrides AIOS defaults for that project. It is placed at the project root (not inside `.claude/`) and is project-owned (committed to the project's own repo, not the OS repo).

Key properties:
- Location: `<project-root>/aios_overrides.md` — never inside `.claude/`
- Format: simple `key: value` pairs, one per line, `#` comment lines ignored
- Discovery: AIOS skills walk upward from the current working directory to find it, stopping at `$HORIZON_ROOT`
- Template: `$HORIZON_BIN/templates/aios_overrides.md` — copy to project root and configure

Currently supported keys:
- `handoffs_dir` — override the handoffs output directory for this project
- `project_display_name` — friendly name for handoff doc headers (defaults to directory basename)

The template file is fully annotated. New override keys are added to the template as AIOS gains new configurable behaviors.
