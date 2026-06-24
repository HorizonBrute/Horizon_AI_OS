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
`~/.claude/skills/` is pointed at `skills_sbin/`, and symlinks are created
inside `skills_sbin/` for each `skills_bin/` skill so the owner sees the full
set flat. Brain users' `~/.claude/skills/` points directly at `skills_bin/`.

---

## Quick-scan table

| Slash command | Location | What it does |
|---|---|---|
| `/context-cost` | `skills_bin/` | Report KB, word count, and token estimates for all files the harness auto-loads above a given path |
| `/create-brain` | `skills_sbin/` | Provision a new brain OS user, groups, workspace, shell profile, and keystore credential (Admin/root) |
| `/doctor` | `skills_bin/` | Run the AIOS health check — env vars, skills symlink, hooks, registry, and privileged-dir Deny ACLs |
| `/handoff` | `skills_sbin/` | Write a structured session handoff document for the next session or a human reviewer |
| `/harden` | `skills_sbin/` | Apply the authoritative brains-group ACL model to the AIOS layer (Admin/root) |
| `/agent-teams` | `skills_sbin/` | List, create, or edit agent-team definitions in `local.agent_teams.md` at any scope; manage custom role flags |
| `/horizon_aios_dev_consistency_check` | `skills_sbin/` | Run an iterative docs/implementation consistency validation pass against the AIOS check standard |
| `/horizon_aios_documentation_index_update` | `skills_sbin/` | Rebuild `documentation/index.md` so every doc is registered with a stable path-based ID |
| `/horizon_aios_wiki_upkeep` | `skills_sbin/` | Run a consistency pass between the operational wiki and its source documentation; fix unambiguous drift, surface judgment calls |
| `/terseness-check` | `skills_sbin/` | Evaluate every file in the Terseness Contract Index for context overhead; report FAIL/ADVISORY findings with file:line evidence and cut suggestions |
| `/test-agent-teams` | `skills_sbin/` | End-to-end self-test of the Agent Teams system — walk every team, spawn each role to echo a nonce + role + model, report PASS/FAIL per team |
| `/model-catalog-refresh` | `skills_bin/` | Fetch live model+pricing data from Anthropic, OpenAI, Gemini, and Ollama; diff against the current model-preference config |
| `/userguides` | `skills_bin/` | Browse the operational wiki: no argument summarizes all sections via parallel Haiku agents; `/userguides N` displays section N in full |
| `/model-prefs` | `skills_sbin/` | Author or inspect model groups, per-session slots, and task-class routing rules in the gitignored extend file |
| `/model-prefs-assign` | `skills_sbin/` | Audit skills for model-preference group callouts and assign or refresh them; keep indexes in sync |
| `/model-prefs-test` | `skills_bin/` | Test how each model group resolves in the current runtime (dry-run or live spawn) |
| `/monitor` | `skills_bin/` | Start the AIOS filesystem integrity monitor (watches system dirs, logs events as JSON lines; requires elevation) |
| `/objective` | `skills_sbin/` | Create, list, show, or update durable multi-session objectives that handoffs chain back to |
| `/pre-flight-tooling-validation` | `skills_sbin/` | Validate the repo ships full-lifecycle tooling per platform, then emit a ready-to-run test prompt per platform |
| `/remove-brain` | `skills_sbin/` | Deprovision a brain — remove its OS user, per-brain group, workspace, profile, and credential (Admin/root) |
| `/resync-user-skills` | `skills_sbin/` | Report skill inventory and rebuild symlinks so the owner view matches the filesystem |
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
`horizon_aios_model_prefs.local.md` is populated with valid, current ids
rather than training-cutoff guesses.
**Offboarding:** You lose the guided, multi-provider fetch. Provider docs remain
publicly accessible and can be read directly; the catalog format and fetch
strategy are documented in the skill's `SKILL.md`.

---

### /model-prefs

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** None — Claude reads and writes the extend file directly

Authors or inspects the gitignored model-preference extend file
(`$HORIZON_ETC/horizon_aios_model_prefs.local.md`): model groups, per-session
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
rebuilding symlinks. Also compares the on-disk state to what is
loaded in the current session and advises on restarts. An upstream sync that
refreshes `skills_sbin/` can drop these links; running this skill or
`horizon_aios_register_user_skills.py --check` detects that.

**Onboarding:** Provides a single command to verify and repair the skill wiring
after any sync or new skill is added, without needing to understand the symlink
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
frontmatter `name:` field must all match. OS skills require a restart; the symlink
is live immediately.

**Onboarding:** Ensures every new skill is correctly structured, registered, and
git-tracked from the start — misstructured skills are silently ignored by Claude
Code.
**Offboarding:** You lose the guided scaffolding. Skills can be created by hand by
following the structure in any existing `SKILL.md`; the requirements are also
documented in `skill-creation/SKILL.md` and both tier index files.

---

### /agent-teams

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** `$HORIZON_SYSTEM/bin/resolve_agent_teams.py` (for discovery); writes `local.agent_teams.md` and `local.agent_team_flags.md` directly

Bare `/agent-teams` lists all resolved agent teams in effect at the current path by running `resolve_agent_teams.py`. With arguments, creates or edits team definitions and custom role flags in the scope-appropriate `local.agent_teams.md` (gitignored, never clobbered by sync). Never modifies the shipped `$HORIZON_ROOT/agent_teams.md`.

**Onboarding:** Provides a guided entry point for creating and managing multi-agent workflow definitions without hand-editing markdown; discovers teams at the correct scope automatically.
**Offboarding:** Edit `local.agent_teams.md` at the desired scope directly. See `$HORIZON_ROOT/agent_teams.md` for the team definition format and `$HORIZON_DOCS/system/agent_teams.md` for the full invocation and cascade reference.

---

### /horizon_aios_wiki_upkeep

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** None — delegates section checks to `#investigate` subagents, then edits the wiki directly

Runs a consistency pass between `$HORIZON_DOCS/user_guides/using_your_aios.md` and its source documents. Spawns one subagent per section to check for factual drift, stale paths, outdated examples, and coverage gaps. Applies unambiguous fixes; surfaces judgment calls for user decision. Re-runs until all sections are CLEAN or remaining issues are explicitly deferred.

**Onboarding:** Keeps the operational wiki accurate after source docs change, without requiring a full manual audit.
**Offboarding:** Audit sections manually by reading the wiki and source docs side-by-side. The source-doc mapping is in `$HORIZON_SYSTEM/skills_sbin/horizon_aios_wiki_upkeep/SKILL.md`.

---

### /terseness-check

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** None — Claude reads the Terseness Contract Index and evaluates each tracked file directly

Evaluates every file listed in `$HORIZON_DOCS/terseness_contract_index.md` against the seven terseness criteria defined there. Reports `FAIL` findings with `file:line` evidence and concrete cut suggestions. Gitignored / user-controlled files are evaluated but findings are `ADVISORY` only. Auto-fixes pure-removal `FAIL` findings (no new content written); surfaces everything else for confirmation. Also delegated by CC-T2 in the consistency check.

**Onboarding:** Ensures context-loaded files stay token-efficient; a single command confirms the Terseness Contract is met before pushing changes.
**Offboarding:** Apply the seven criteria from `$HORIZON_DOCS/terseness_contract_index.md` manually to each tracked file.

---

### /test-agent-teams

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** `$HORIZON_SYSTEM/bin/resolve_agent_teams.py` (team discovery); spawns real subagents per role

End-to-end integration test of the Agent Teams system. Runs `resolve_agent_teams.py --json` to enumerate all resolved teams, then spawns one real subagent per role across all teams. Each role subagent echoes a nonce, its role name, and the model it actually ran as. Verifies that every role spawned, the `#model-group` routed correctly, and the chain executed. This is a deliberate, potentially costly integration test — run to verify, not routinely.

**Onboarding:** Proves the full agent-team loop works end-to-end (resolution, model routing, nonce proof of execution) before relying on agent teams for real work.
**Offboarding:** Test teams manually by invoking a team and observing which roles spawn and on which models.

---

### /userguides

**Location:** `skills_bin/` (available to all users including brains)
**Underlying tool:** None — Claude reads the wiki file and optionally spawns Haiku summarizer agents

Bare `/userguides` reads `$HORIZON_DOCS/user_guides/using_your_aios.md`, discovers all numbered sections dynamically, spawns one `#lowcost` (Haiku) agent per section in parallel to write a 3–5 sentence summary, and presents summaries in section order. `/userguides N` displays the full text of section N. The section map in the SKILL.md is informational; the live file read is authoritative.

**Onboarding:** Provides a one-command overview of the full operational wiki without reading thousands of words; section N access gives targeted reference lookup.
**Offboarding:** Read `$HORIZON_DOCS/user_guides/using_your_aios.md` directly.

---

### /create-brain

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** `$HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py`

Provisions a new brain: creates the OS user account, the shared `brains` group
and a per-brain group, the workspace folder at `$HORIZON_ROOT/brains/<name>/`,
a login shell profile, and stores an auto-generated 64-char password in the OS
native keystore. Requires Administrator/root; delegates to `horizon_aios_create_brain.py`.

**Onboarding:** Provides a single guided entry point for brain provisioning that
handles all OS-level steps and surfaces the post-provisioning checklist.
**Offboarding:** Run `horizon_aios_create_brain.py` directly; see the "Adding a Brain"
section of `getting_started/ReadMeToSetupYourSystem.md`.

---

### /remove-brain

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** `$HORIZON_SYSTEM/sbin/horizon_aios_remove_brain.py`

Deprovisions a brain by removing its OS user account, per-brain group, workspace
folder, profile config (including the skills symlink), and stored credential.
The shared `brains` group is left intact. Requires Administrator/root.

**Onboarding:** Provides a safe, guided teardown path that mirrors provisioning.
**Offboarding:** Run `horizon_aios_remove_brain.py` directly (see `utilities.md`).

---

### /harden

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** `$HORIZON_SYSTEM/sbin/horizon_aios_harden.py`

Applies the authoritative brains-group ACL model to the AIOS layer: grants the
`brains` group Read+Execute on `bin/` and `skills_bin/`, applies a no-write Deny
across `$HORIZON_SYSTEM`, and adds an explicit full Deny on `sbin/`, `skills_sbin/`,
and `logs/`. Run after `horizon_aios_doctor.py` reports a missing Deny ACE, or after
structural changes to `$HORIZON_SYSTEM`. Requires Administrator/root.

**Onboarding:** Provides a single command to re-establish the security invariants
without needing to recall the `icacls`/`chmod` commands manually.
**Offboarding:** Run `horizon_aios_harden.py` directly (see `utilities.md`).

---

### /doctor

**Location:** `skills_bin/` (available to all users including brains)
**Underlying tool:** `$HORIZON_SYSTEM/sbin/horizon_aios_doctor.py`

Runs the AIOS health check: verifies env vars, the `~/.claude/skills/` symlink,
git hooks, local config (`aios_local.conf`), the AIOS registry, and that `sbin/`,
`skills_sbin/`, and `logs/` have an explicit Deny ACE for the `brains` group.
Reports PASS / WARN / FAIL for each check. Optional `--post-setup` flag adds
sound, statusline, and GPG signing checks.

**Onboarding:** Provides immediate post-install verification and ongoing health
checks without needing to know which files to inspect.
**Offboarding:** Run `horizon_aios_doctor.py` directly (see `utilities.md`).

---

### /monitor

**Location:** `skills_bin/` (available to all users including brains)
**Underlying tool:** `$HORIZON_SYSTEM/sbin/horizon_aios_monitor.py`

Starts (or explains) the AIOS filesystem integrity monitor, which watches the
AIOS system directories for create, modify, delete, and move events and appends
each as a JSON-line audit record to `$HORIZON_SYSTEM/logs/horizon_aios_monitor/`.
Requires elevation because writing to `logs/` is an admin-only action.

**Onboarding:** Provides a guided entry point for enabling filesystem audit
logging, including the watch set, log format, and service-registration options.
**Offboarding:** Run `horizon_aios_monitor.py` directly; see
`security/audit_logging.md` for full setup and SIEM integration guidance.

---

### /model-prefs-assign

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** None — Claude reads and edits skill files directly

Audits all skills in `skills_sbin/` and `skills_bin/` for a `Model preference:`
callout in the body. Adds the callout to skills that lack one (defaulting to
`#midcost`), updates it where a different group is more appropriate, and keeps
the `Model group` columns in both tier index files in sync with the actual skill
bodies.

**Onboarding:** Ensures every skill declares its model group so the
model-preference layer routes work correctly without per-invocation overrides.
**Offboarding:** Skills can be audited and updated by hand; the format is
documented in `system/skill_model_groups.md`.

---

### /model-prefs-test

**Location:** `skills_bin/` (available to all users including brains)
**Underlying tool:** None — Claude resolves and optionally spawns agents directly

Tests how each model group from the current model-preference config resolves
in this runtime: dry-run mode reports which member would be selected without
spawning anything; `--live` mode spawns a small agent per group to confirm the
harness actually honors the selection and has each agent self-report its model.

**Onboarding:** Provides confidence that the model-preference config is wired
correctly before relying on it for real work.
**Offboarding:** Test group resolution manually by reading the extend file and
checking which members are available in the current runtime.

---

### /pre-flight-tooling-validation

**Location:** `skills_sbin/` (owner only)
**Underlying tool:** None — Claude inspects repo contents directly

Validates that the AIOS repo ships every tool needed to run the full lifecycle
(install → create brain → create a second AIOS → switch → backup → delete) on
each supported platform (Windows, Linux, macOS), then emits a ready-to-run
admin/sudo test prompt per platform. Intended as a pre-test gate before handing
off a fresh clone to someone running a lifecycle test on a clean machine.

**Onboarding:** Catches missing or misnamed tooling before a test run so failures
are a tooling gap, not a test environment issue.
**Offboarding:** Check the tool list manually against `file_structure_invariants.md`
and `utilities.md`.

---

## Onboarding and offboarding summary

When AIOS skills are registered, an owner gains 22 slash commands across two
tiers. **skills_bin/** (available to brains): `/context-cost`, `/doctor`,
`/model-catalog-refresh`, `/model-prefs-test`, `/monitor`, `/userguides`.
**skills_sbin/** (owner only): `/agent-teams`, `/create-brain`, `/handoff`,
`/harden`, `/horizon_aios_dev_consistency_check`,
`/horizon_aios_documentation_index_update`, `/horizon_aios_wiki_upkeep`,
`/model-prefs`, `/model-prefs-assign`, `/objective`,
`/pre-flight-tooling-validation`, `/remove-brain`, `/resync-user-skills`,
`/skill-creation`, `/terseness-check`, `/test-agent-teams`.

Skills that wrap underlying scripts: `/context-cost`, `/doctor`, `/create-brain`,
`/harden`, `/monitor`, `/remove-brain`, `/resync-user-skills` (all delegate to a
`sbin/` or `bin/` Python script). `/model-catalog-refresh` and `/model-prefs-test`
perform live fetches or agent spawns at runtime. The remaining skills have no
separate script — Claude is the engine and the `SKILL.md` is the procedure.

Unregistering the skills (by removing the `~/.claude/skills/` symlink or clearing
the skills directories) does not delete any underlying data or scripts. Handoff
documents, objective files, the documentation index, and the model-preference
extend file remain on disk exactly as written. The Python scripts in
`$HORIZON_SYSTEM/bin/` and `$HORIZON_SYSTEM/sbin/` remain fully functional from
any shell. What is lost is convenience: the single slash command, the guided
step-by-step procedure, and the integration with the harness context. A user
offboarding from AIOS retains all artifacts produced by the skills; they lose only
the automated workflow that produced them.

Brain accounts see only `skills_bin/` (`/context-cost`, `/doctor`,
`/model-catalog-refresh`, `/model-prefs-test`, `/monitor`) and gain no access to
the owner-only skills. This is by design and enforced at the ACL level.
