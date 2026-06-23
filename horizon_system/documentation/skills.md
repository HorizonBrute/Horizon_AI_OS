# Horizon AIOS — Skills Reference

AIOS skills are slash commands exposed in the Claude Code harness UI. Each skill
is a `SKILL.md` file that tells Claude how to drive a task: what steps to take,
what scripts to call, and what to surface to the user. They are distinct from
Claude Code marketplace plugins (code-review, update-config, verify, etc.), which
are installed separately from Anthropic's marketplace and are not part of this
repo.

Skills live in one of two OS-level directories:

- `$HORIZON_SYSTEM/skills_bin/` — available to all users, including brain accounts
- `$HORIZON_SYSTEM/skills_sbin/` — owner only; brain accounts have an explicit
  Deny ACL on this directory

At bootstrap (or when `/resync-user-skills` is run), the owner's
`~/.claude/skills/` is pointed at `skills_sbin/`, and junctions are created
inside `skills_sbin/` for each `skills_bin/` skill so the owner sees the full
set flat. Brain users' `~/.claude/skills/` points directly at `skills_bin/`.

---

## Quick-scan table

| Slash command | Location | What it does |
|---|---|---|
| `/context-cost` | `skills_bin/` | Report KB, word count, and token estimates for all files the harness auto-loads above a given path |
| `/handoff` | `skills_sbin/` | Write a structured session handoff document for the next session or a human reviewer |
| `/model-catalog-refresh` | `skills_bin/` | Fetch live model+pricing data from Anthropic, OpenAI, Gemini, and Ollama; diff against the current model-preference config |
| `/model-prefs` | `skills_sbin/` | Author or inspect model groups, per-session slots, and task-class routing rules in the gitignored extend file |
| `/horizon_aios_dev_consistency_check` | `skills_sbin/` | Run an iterative docs/implementation consistency validation pass against the AIOS check standard |
| `/horizon_aios_documentation_index_update` | `skills_sbin/` | Rebuild `documentation/index.md` so every doc is registered with a stable path-based ID |
| `/objective` | `skills_sbin/` | Create, list, show, or update durable multi-session objectives that handoffs chain back to |
| `/resync-user-skills` | `skills_sbin/` | Report skill inventory and rebuild junctions so the owner view matches the filesystem |
| `/skill-creation` | `skills_sbin/` | Scaffold a new AIOS skill with correct structure, frontmatter, and index registration |

---

## Per-skill entries

### /context-cost

**Location:** `skills_bin/` (available to all users including brains)
**Underlying tool:** `$HORIZON_SYSTEM/bin/context_cost.py`

Reports the Claude Code harness context overhead for a given path — how many KB,
words, and estimated tokens will be loaded into every session that starts under
that directory. It walks the ancestor chain collecting every `CLAUDE.md`,
`CLAUDE.local.md`, `agents.md`, and `@`-import file the harness would pull in, and
flags totals above 1,000 tokens as worth reviewing.

**Onboarding:** Gives immediate visibility into how much context overhead any
directory imposes, enabling the token economy discipline described in `dev_values.md`.
**Offboarding:** You lose the integrated harness-aware report format. The underlying
`context_cost.py` script remains at `$HORIZON_SYSTEM/bin/` and can be run directly:
`python context_cost.py [path] [--json]`.

---

### /handoff

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** None — Claude drives the session from conversation memory

Captures the current session state and writes a structured handoff document
(summary, decisions, deferred items, next-session entry point) to the handoffs
directory. The directory defaults to `$HORIZON_ROOT/handoffs/` and can be
overridden per project via `aios_overrides.md`. Supports objective linkage so
handoffs chain a durable goal forward across sessions.

**Onboarding:** Provides a consistent handoff format and path convention across all
sessions, making session continuity reliable rather than ad hoc.
**Offboarding:** You lose the structured format and automatic directory routing.
Handoff documents are plain Markdown and remain readable; future sessions can still
read them directly. The skill is the entry point — no underlying script.

---

### /horizon_aios_dev_consistency_check

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** `$HORIZON_DOCS/development_tools/consistency_checks.md` (the
check definitions); delegates to a general-purpose subagent for file-heavy work

Runs the AIOS consistency validation protocol (check IDs `CC-*`) over the repo or
a defined scope. Fixes unambiguous drift in place (stale paths, missing index
entries, one-sided platform implementations), surfaces judgment calls for user
input, and re-runs until 100% clean or blocked. The check definitions file — not
this skill — is the source of truth for what is checked.

**Onboarding:** Provides a single, repeatable entry point for the consistency
standard, ensuring docs and implementation stay synchronized after every change.
**Offboarding:** You lose the automated iteration loop. The check definitions remain
in `$HORIZON_DOCS/development_tools/consistency_checks.md` and can be followed
manually; the underlying standard is not a skill.

---

### /horizon_aios_documentation_index_update

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** None — Claude reads and writes `documentation/index.md` directly

Rebuilds `$HORIZON_DOCS/index.md` by globbing all in-scope docs, deriving each
entry's title and one-line purpose, and writing a grouped, path-keyed catalog.
Add/remove/rename operations are reflected deterministically. Satisfies the CC-G4
consistency check requirement that every doc has a stable index entry. Delegates
to a subagent to avoid bloating the main session's context.

**Onboarding:** Keeps the documentation index accurate without manual upkeep; a
new doc added without running this skill will be flagged by the CC-G4 consistency
check.
**Offboarding:** You lose the automated rebuild. The index file remains at
`documentation/index.md` and can be maintained by hand; the format is documented
in the skill and in the index file's own header.

---

### /model-catalog-refresh

**Location:** `skills_bin/` (available to all users including brains)
**Underlying tool:** Web/bash access — the agent fetches live data at runtime

Fetches current model ids and pricing from Anthropic, OpenAI, Google Gemini,
and Ollama. If the current `## Model Groups` block is already in context,
automatically diffs it against live data and flags stale member ids, newer
alternatives, and pricing changes. Companion to `/model-prefs`, which writes
the extend file.

**Onboarding:** Provides an up-to-date model+pricing reference so
`horizon_aios_model_prefs.extend.md` is populated with valid, current ids
rather than training-cutoff guesses.
**Offboarding:** You lose the guided, multi-provider fetch. Provider docs remain
publicly accessible and can be read directly; the catalog format and fetch
strategy are documented in the skill's `SKILL.md`.

---

### /model-prefs

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** None — Claude reads and writes the extend file directly

Authors or inspects the gitignored model-preference extend file
(`$HORIZON_ETC/horizon_aios_model_prefs.extend.md`): model groups, per-session
slot preferences, and task-class routing rules. The mechanism is in-context —
the acting model reads the file each session and honors it by direct
instruction; no scripts or env vars are wired. Writes nothing to the OS-tracked
base file.

**Onboarding:** Provides a guided entry point for configuring the model-preference
layer without needing to know the file grammar or fallback-order rules.
**Offboarding:** You lose the guided edit and resolution report. The extend file is
plain Markdown and can be edited directly; the grammar and fallback order are
documented in `$HORIZON_ETC/horizon_aios_model_prefs.md` and
`$HORIZON_DOCS/system/model_preferences.md`.

---

### /objective

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** None — Claude reads and writes objective files directly

Creates, lists, shows, and updates durable objective files (plain Markdown) in the
objectives directory (default: `$HORIZON_ROOT/objectives/`). Objectives hold the
long-term goal behind a stream of work — not a task tracker, but a durable
notepad that handoffs reference by number so the goal survives across sessions.
Pruning of stale objectives is handled externally by `horizon_aios_maintain_logs.py`.

**Onboarding:** Provides a lightweight, persistent goal-tracking layer that handoffs
can chain back to, preventing goal drift across many sessions.
**Offboarding:** You lose the structured create/list/show/update interface. Objective
files are plain Markdown in the objectives directory and remain fully readable;
they can be managed by hand. The pruning logic in `horizon_aios_maintain_logs.py` remains
independent of the skill.

---

### /resync-user-skills

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** `$HORIZON_SYSTEM/sbin/horizon_aios_register_user_skills.py`

Reports whether the owner's aggregated skill view (`skills_bin/` + `usr_skills/`
linked into `skills_sbin/`) matches the filesystem, then heals any drift by
rebuilding junctions or symlinks. Also compares the on-disk state to what is
loaded in the current session and advises on restarts. An upstream sync that
refreshes `skills_sbin/` can drop these links; running this skill or
`horizon_aios_register_user_skills.py --check` detects that.

**Onboarding:** Provides a single command to verify and repair the skill wiring
after any sync or new skill is added, without needing to understand the junction
mechanics.
**Offboarding:** You lose the check/heal UX. The underlying
`horizon_aios_register_user_skills.py` script remains at `$HORIZON_SYSTEM/sbin/` and can be
run directly with `--check` or without flags to rebuild.

---

### /skill-creation

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** None — Claude creates files and updates indexes directly

Scaffolds a new AIOS skill at the correct tier (`skills_bin/`, `skills_sbin/`, or
`usr_skills/`), writes a valid `SKILL.md` with required YAML frontmatter, updates
the tier's `index.md`, and for `skills_sbin/` skills also updates `.gitignore` to
whitelist the new directory. Enforces the invariant that name, directory, and
frontmatter `name:` field must all match. OS skills require a restart; the junction
is live immediately.

**Onboarding:** Ensures every new skill is correctly structured, registered, and
git-tracked from the start — misstructured skills are silently ignored by Claude
Code.
**Offboarding:** You lose the guided scaffolding. Skills can be created by hand by
following the structure in any existing `SKILL.md`; the requirements are also
documented in `skill-creation/SKILL.md` and both tier index files.

---

## Onboarding and offboarding summary

When AIOS skills are registered, an owner gains nine slash commands. Two
(`/context-cost` and `/resync-user-skills`) wrap underlying Python scripts and
expose them through a guided, harness-aware interface. `/model-catalog-refresh`
performs live web and CLI fetches at runtime. The remaining six
(`/handoff`, `/horizon_aios_dev_consistency_check`,
`/horizon_aios_documentation_index_update`, `/model-prefs`, `/objective`,
`/skill-creation`) have no separate script — Claude is the engine, and the
`SKILL.md` is the procedure it follows.

Unregistering the skills (by removing the `~/.claude/skills/` junction or clearing
the skills directories) does not delete any underlying data or scripts. Handoff
documents, objective files, the documentation index, and the model-preference
extend file remain on disk exactly as written. The Python scripts in
`$HORIZON_SYSTEM/bin/` and `$HORIZON_SYSTEM/sbin/` remain fully functional from
any shell. What is lost is convenience: the single slash command, the guided
step-by-step procedure, and the integration with the harness context. A user
offboarding from AIOS retains all artifacts produced by the skills; they lose only
the automated workflow that produced them.

Brain accounts see only `skills_bin/` (`/context-cost` and
`/model-catalog-refresh`) and gain no access to the owner-only skills. This is
by design and enforced at the ACL level.
