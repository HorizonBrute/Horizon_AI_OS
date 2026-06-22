# Architecture Decisions — Horizon AIOS

This document memorializes the "why" behind structural decisions made as Horizon AIOS is built. It is a living document — new decisions are appended as they are made. Existing entries are never deleted or revised; if a decision is superseded, a new entry records the reversal and its rationale.

**How to use this document:** When making a structural or design decision, append a new entry to the Architectural Decisions Log (Section 3) with the current date, a short title, what was decided, why, and any implications for future work.

---

## 1. Purpose

Architecture decisions accumulate silently. Six months into a project it becomes impossible to reconstruct why a particular structure was chosen, and the team (human or AI) makes decisions that unknowingly conflict with prior constraints. This document prevents that.

Every time a non-obvious structural choice is made — about file placement, sync strategy, naming convention, permission model, or anything else that affects how the system fits together — an entry is added here. The "why" is more important than the "what"; the what is visible in the files themselves.

---

## 2. File Synchronization Manifest

This section is the authoritative reference for which files have a source-of-truth location, which have a deployed/machine-local copy, and how they are kept in sync.

### 2.1 Synced Pairs (source → deployed copy)

| File / Directory | Source (in repo) | Deployed / Machine-Local | Sync Mechanism | In Git Repo |
|---|---|---|---|---|
| CLAUDE.md instructions | `$HORIZON_ROOT/.claude/CLAUDE.md` | `~/.claude/CLAUDE.md` | One-time stub creation (@ redirect, not a copy) | Source only — stub is machine-local |
| settings.json template | `$HORIZON_SYSTEM/templates/claude_code/settings.json` | `~/.claude/settings.json` | Manual review and hard link / copy at setup time | Template only — local copy is NOT committed |

**Note on settings.json:** The deployed `~/.claude/settings.json` is not a simple copy of the template. It contains machine-specific paths (embedded in hook commands and statusLine). The bootstrap script offers to copy the template as a starting point; the user must substitute real paths. See `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md` Step 8.

**Note on skills:** Skills are no longer synced via copy. `~/.claude/skills/` is a junction (Windows) or symlink (Unix) pointing directly to `$HORIZON_SYSTEM/skills_sbin/` for the primary user, and to `$HORIZON_SYSTEM/skills_bin/` for brain users. Changes to skills in the repo are live immediately — only a Claude Code session restart is needed. See the 2026-06-21 ADR entry for the junction redirect decision.

### 2.2 Local-Only Files (not in repo, not synced)

These files exist only on the local machine. Anyone who clones the repo will not have them — they must be created during setup.

| File | Location | Why Local-Only |
|---|---|---|
| Global Claude settings | `~/.claude/settings.json` | Contains machine-specific paths; configured from template at setup time |
| CLAUDE.md stub redirect | `~/.claude/CLAUDE.md` | One-line `@` pointer to repo CLAUDE.md; machine-local bootstrap artifact |
| Local git config | `$HORIZON_ROOT/.git/config` | Git-managed, machine-local (e.g., `core.hooksPath` setting) |
| Brain-specific configs | `$HORIZON_ROOT/brains/<brain_name>/` | Per-brain, scoped to brain user; sensitive; gitignored |
| Handoff documents | `$HORIZON_ROOT/handoffs/` | Session-specific artifacts; machine-local continuity; gitignored |

### 2.3 Repo-Tracked Files (synced via git clone/pull)

These files are committed to the OS repo and present on every machine after cloning.

| File / Directory | Path | Notes |
|---|---|---|
| Canonical AI instructions | `$HORIZON_ROOT/.claude/CLAUDE.md` | System-level instructions for all Claude sessions |
| Devroot permissions | `$HORIZON_ROOT/.claude/settings.json` | Devroot-scoped tool permissions only (no hooks, no statusLine) |
| Skills (primary user) | `$HORIZON_SYSTEM/skills_sbin/` | Live via junction at `~/.claude/skills/` → no copy needed |
| Skills (brain users) | `$HORIZON_SYSTEM/skills_bin/` | Live via junction at brain `~/.claude/skills/` → no copy needed |
| Sounds (generic) | `$HORIZON_SYSTEM/sounds/*.wav` | Vendor-agnostic event audio |
| Sounds (vendor-voiced) | `$HORIZON_SYSTEM/sounds/<vendor>_event_sounds/` | Vendor-specific voiced audio |
| Statusline scripts | `$HORIZON_BIN/statusline/` | Terminal statusline scripts for Claude Code |
| Harness configs | `$HORIZON_SYSTEM/harness_configs/` | Per-harness config templates (git hooks, etc.) |
| Config templates | `$HORIZON_SYSTEM/templates/` | Setup templates; contain placeholders, not real paths |
| Invariant documents | `$HORIZON_ETC/` | File structure, security, and personalization invariants |
| Documentation | `$HORIZON_DOCS/` | User-facing docs including this file |
| Privileged scripts | `$HORIZON_SYSTEM/sbin/` | Owner-only; brain users may not access |
| Gitignore | `$HORIZON_ROOT/.gitignore` | Repo-wide ignore rules |

---

## 3. Architectural Decisions Log

Entries are in reverse-chronological order at the top (newest first). Each entry is immutable once added.

---

### 2026-06-21 — Skills redirect via junction/symlink supersedes copy-based deploy

**Decision:** Supersedes "2026-06-20 — Skills have dual location: source and deployed copy." `~/.claude/skills/` is now a directory junction (Windows) or symlink (Unix/macOS) pointing directly to `$HORIZON_SYSTEM/skills_sbin/` for the primary user, and to `$HORIZON_SYSTEM/skills_bin/` for brain users. No copy step exists; skills are live on disk as soon as they are written to the repo directory.

**Rationale:** The copy-based model required a manual deploy step after every skill change, with no way to detect drift between source and deployed copies. Per-skill symlinks inside `~/.claude/skills/` were considered but rejected as inelegant (one symlink per skill, all pointing into the same source tree). Redirecting the entire directory via a single junction/symlink is simpler, drift-proof, and consistent with how other AIOS config files are managed (the CLAUDE.md stub uses the same pattern). Windows directory junctions require no administrator rights, keeping the bootstrap friction-free.

**Implications:** Skills are split across two source directories mirroring the bin/sbin security model: `skills_sbin/` (primary user only) and `skills_bin/` (brain-readable). Bootstrap creates the primary user junction to `skills_sbin/`; `create_brain.py` creates the brain junction to `skills_bin/`. A session restart is the only action needed after adding or editing a skill. The "deployed copy" concept no longer applies to skills.

---

### 2026-06-21 — Docker deployment model: brain isolation via containers, not OS users

**Decision:** Added Docker deployment templates (`horizon_system/templates/docker/`): Dockerfile, docker-compose.yml, .dockerignore. Added `bootstrap_docker.sh` to `sbin/` as a thin wrapper around `bootstrap.sh` that sets `AIOS_DEPLOY_MODE=docker` (suppresses shell profile instructions and sync schedule setup). Added `documentation/deployment/docker.md` and `documentation/tested_configurations.md`.

In the Docker deployment model, brain isolation is container-level rather than OS-user-level. Each brain runs as a separate Docker container. The AIOS OS layer runs in the primary `horizon-aios` container; brains are defined as additional services in `docker-compose.yml` with per-brain volume mounts for their directories and keys. The audit log volume is not mounted into brain containers.

**Rationale:** IaC/containerization compatibility is a first-class design goal (see `philosophy.md §5`). The native OS user model and the Docker container model are isomorphic at the security boundary level — both use OS-enforced isolation with explicit provisioning of tools and credentials per brain. Docker adds network isolation and makes deployment reproducible and portable. The two models coexist: the Docker templates wrap the native AIOS layer without modifying it.

**Implications:** `create_brain.py` is not yet Docker-aware — it provisions OS accounts, not containers. Brain container provisioning in Docker is currently manual (duplicate the compose service template). This is tracked as a gap in `tested_configurations.md`. The Dockerfile is harness-agnostic except for Claude Code CLI installation; the BYOH principle is documented in the Dockerfile and `docker.md`.

---

### 2026-06-21 — Formalized Brain vs. AIOS vocabulary; created philosophy.md

**Decision:** The conceptual distinction between a "Brain" (an atomic expert system — an App) and an "AI Operating System" (the config, harness, security, and logging layer that Brains run on top of) is now formally documented in `$HORIZON_DOCS/philosophy.md`. The term "Brain" in all AIOS documentation refers specifically to a purpose-scoped agentic workflow running as an isolated OS user account. What the broader industry often calls an "AI OS" (a highly tuned expert system for a specific domain) maps to "Brain" in Horizon vocabulary.

**Rationale:** The vocabulary was implicit in the implementation but never stated. Contributors, auditors, and new AI sessions had to infer the distinction from context. The gap also meant the "blue team answerability" design goals — what is the agent doing, how is it doing it, how is it enforced, what data/tools does it have access to — were scattered across technical documents rather than stated as a unified design objective. `philosophy.md` also documents the IaC/containerization deployment model, the BYOH principle, and an evaluation of where the current implementation aligns with or falls short of these values.

**Implications:** Any document, skill, or AI instruction that introduces a new use of "brain," "AIOS," or "second brain" must be consistent with the vocabulary in `philosophy.md`. Architectural decisions that affect the Brain/AIOS boundary (e.g., adding capabilities to `sbin` vs. provisioning them to individual brains) should be evaluated against the conceptual separation documented there.

---

### 2026-06-20 — Two-group model per brain (brains common group + brain-specific group)

**Decision:** Each brain belongs to two groups: `brains` (common AIOS group, grants read+execute on `$HORIZON_BIN`) and `<brain-name>` (brain-specific group, grants full control on the brain's own folder). The invoking primary user is added to the brain-specific group for oversight but is not added to every brain's group.

**Rationale:** Separates two distinct privileges into two distinct groups. The `brains` group answers "can this account use shared AIOS tooling?" The `<brain-name>` group answers "who owns this brain's data?" Adding the primary user to the brain-specific group enables oversight (read/write to the brain folder) without placing the primary user in a catch-all group that spans all brains. This keeps group membership semantics clean and least-privilege.

**Implications:** The `brains` group ACL on `$HORIZON_BIN` must never cascade to `$HORIZON_BIN/sbin`. The `sbin` ACL must be explicitly set and verified *after* any `$HORIZON_BIN` group change — this is enforced structurally in `create_brain.py` (Phase 3 always re-locks `sbin` last). On Windows, `sbin` requires an explicit `/inheritance:r` ACE reset, not just absence of a grant, because inherited permissions take precedence over "no entry."

---

### 2026-06-20 — Brain provisioning via Python script (`create_brain.py`)

**Decision:** OS-level provisioning of new brains (user account, groups, folder, permissions) is performed by a single Python script at `$HORIZON_SYSTEM/scripts/create_brain.py`, invoked by the primary user with admin/root privileges.

**Rationale:** Python is cross-platform. A shell script would require separate `.sh` and `.ps1` variants to handle Linux/macOS and Windows, leading to two codebases that can drift. A single Python script with platform branches (`platform.system()`) keeps provisioning logic in one place, makes cross-platform divergences explicit and auditable, and is readable by any contributor without needing to know both Bash and PowerShell. Python 3.6+ is a reasonable dependency for a developer tooling system.

**Implications:** Python 3.6+ is a documented dependency for brain provisioning (added to the "Adding a Brain" section of `ReadMeToSetupYourSystem.md`). The script must be run as Administrator/root — it is placed in `$HORIZON_SYSTEM/scripts/`, not `$HORIZON_SYSTEM/sbin/`, because the primary user invokes it explicitly and intentionally, not as a privileged daemon. No automatic rollback is implemented by design: partial state is preserved and cleanup instructions are printed so the primary user retains full control over what gets undone.

---

### 2026-06-20 — Project overrides via `aios_overrides.md` at project root

**Decision:** Projects that need to override AIOS defaults (e.g., handoffs output directory, display name) do so via a file named `aios_overrides.md` placed at the project root directory — not inside `.claude/`.

**Rationale:** Placing the override file at the project root (not in `.claude/`) makes it easy to discover, not specific to Claude Code, and extensible to other harnesses or tooling that reads the same file. The `/handoff` skill and other AIOS skills walk upward from the working directory to find it before falling back to AIOS defaults.

**Implications:** Any AIOS skill that has configurable behavior must check for `aios_overrides.md` before acting. The template at `$HORIZON_SYSTEM/templates/aios_overrides.md` is the canonical reference for supported keys.

---

### 2026-06-20 — Self-activating handoff document header

**Decision:** Every handoff document produced by the `/handoff` skill begins with a block instructing any AI agent reading it to treat it as a directive to begin work, with any accompanying user text as additional instructions.

**Rationale:** Handoff files need to be directly usable as session starters — paste the file path or its contents and work begins without additional prompting. The self-activating header eliminates the intermediate "explain what to do with this" step. This is a UX property of the artifact, not a technical constraint.

**Implications:** The `/handoff` skill template must include the activation header. Agents should be designed to honor it when reading a handoff.

---

### 2026-06-20 — Handoffs are session artifacts, gitignored

**Decision:** `$HORIZON_ROOT/handoffs/` is gitignored. Handoff documents are not committed to the OS repo.

**Rationale:** Handoffs contain session-specific state and potentially sensitive context (partial code, personal workflow notes, in-progress work). They serve as machine-local continuity between sessions, not as version history. Committing them would pollute the repo with ephemeral content and risk exposing session-sensitive information if the repo is shared.

**Implications:** Handoffs do not survive a fresh clone. Anyone setting up a new machine starts fresh. If cross-machine continuity is needed in the future, it must be implemented as an explicit export/import mechanism, not via git.

---

### 2026-06-20 — bin/sbin boundary for brain isolation

**Decision:** `$HORIZON_BIN/` (bin) is group-readable — brain user accounts may read and execute scripts and assets there. `$HORIZON_BIN/sbin/` is owner-only — brain user accounts must never have access.

**Rationale:** Mirrors the Unix `/bin` and `/sbin` filesystem convention. Brains need access to shared tooling (sounds, templates, status scripts) without needing elevated authority. Privileged scripts that manage brain accounts or modify OS-level config require primary-user authority. The explicit directory boundary enforces this without needing per-file permission management.

**Implications:** Any script that requires primary-user authority must be placed in `sbin/`. Scripts placed in `$HORIZON_BIN/` root or subdirectories other than `sbin/` must not assume elevated privileges. On Windows, `sbin/` requires an explicit Deny ACL for brain users (not just absence of a grant) because inherited permissions can otherwise leak access.

---

### 2026-06-20 — `~/.claude/CLAUDE.md` is a stub redirect, not a copy

**Decision:** The machine-local `~/.claude/CLAUDE.md` contains a single line: `@$HORIZON_ROOT/.claude/CLAUDE.md`. It is not a copy of the repo's CLAUDE.md.

**Rationale:** A single source of truth for AI instructions. If `~/.claude/CLAUDE.md` were a copy, updates to the canonical instructions would require a manual copy step and would introduce drift risk. The `@` import syntax in Claude Code resolves the redirect at load time, so the deployed stub never needs updating when instructions change.

**Implications:** New machines only need the stub created once during bootstrap. The stub itself is machine-local and not committed. The canonical instructions live entirely in `$HORIZON_ROOT/.claude/CLAUDE.md` and are versioned with the repo.

---

### 2026-06-20 — Skills have dual location: source and deployed copy

> **SUPERSEDED by 2026-06-21 — Skills redirect via junction/symlink.** The copy-based model below is no longer in use. `~/.claude/skills/` is now a directory junction/symlink pointing directly at the source. No deploy step exists.

**Decision:** AIOS skills (markdown files defining slash commands) are stored in two locations: `$HORIZON_BIN/skills/` (source of truth, committed to repo) and `~/.claude/skills/` (deployed copy, where Claude Code reads them).

**Rationale:** Claude Code reads skills exclusively from `~/.claude/skills/` — it cannot read them from an arbitrary path. The repo must track the canonical versions for community sharing and version history. Therefore, a deploy step is required. The bootstrap script handles initial deployment; subsequent skill updates require a manual re-copy or re-run of bootstrap.

**Implications:** The deployed copy is ephemeral and not committed. Editing skills directly in `~/.claude/skills/` creates invisible local changes that will be lost on the next deploy. All skill edits must happen at the source location. A future improvement would be a file-watch daemon or symlinks (where OS supports them) to eliminate the manual sync step.

---

### 2026-06-20 — Two-tier sounds directory structure

**Decision:** `$HORIZON_BIN/sounds/` uses a two-tier structure. Generic sounds (usable by any harness) live at the root. Vendor-voiced sounds (containing AI product names or branded audio) live in subdirectories named `<vendor>_event_sounds/`.

**Rationale:** Generic sounds allow a hook to play audio without locking to a specific vendor. When a new harness is added, community contributors can add a vendor subdirectory with appropriate voiced audio without touching or conflicting with the generic tier. The naming convention (`<vendor>_event_sounds/`) is explicit and consistent.

**Implications:** Hooks that are shared across harnesses must use root-level generic sounds. Per-harness hooks may use the appropriate vendor subdirectory. No vendor sound should ever be placed at the root tier — it would break harness-agnosticism.

---

### 2026-06-20 — Global settings own hooks and statusLine; devroot settings own devroot permissions only

**Decision:** Event hooks (sounds on WorkComplete, InputNeeded, etc.) and the statusLine configuration live in `~/.claude/settings.json` (the global Claude Code settings). The devroot-scoped `$HORIZON_ROOT/.claude/settings.json` owns only devroot-specific tool permissions.

**Rationale:** Hooks and the statusline are system-level behaviors that should fire in every Claude Code session, regardless of which directory Claude is launched from. If they were configured in the devroot settings, they would only be active when Claude is run from inside `$HORIZON_ROOT`. The global settings layer is the correct scope for OS-level behaviors.

**Implications:** When updating hooks or statusline config, edit `~/.claude/settings.json` (the global file, not committed to the repo). The template at `$HORIZON_SYSTEM/templates/claude_code/settings.json` is the reference for what the global settings should contain. The devroot `.claude/settings.json` must never acquire hook or statusLine entries — if it does, those hooks will be double-fired when in devroot and silent elsewhere.

---

## 4. Files That Need Ongoing Synchronization

These pairs are the most likely to drift and require attention after any update.

### 4.1 Skills: `$HORIZON_SYSTEM/skills_sbin/` (live via junction)

Skills no longer require a copy/sync step. `~/.claude/skills/` is a junction (Windows) or symlink (Unix/macOS) pointing directly to `$HORIZON_SYSTEM/skills_sbin/`. Changes to skill files in the repo are live on disk immediately.

The only action needed after adding or editing a skill: **restart the Claude Code session** so it re-reads `~/.claude/skills/`.

Signs of a problem: a skill change in the repo has no effect after session restart. Verify that `~/.claude/skills/` is a junction/symlink (not a real directory) and that its target is `$HORIZON_SYSTEM/skills_sbin/`. Re-run bootstrap if the junction is missing.

### 4.2 Template-derived settings: `$HORIZON_SYSTEM/templates/claude_code/settings.json` → `~/.claude/settings.json`

The template is the reference for what global settings should contain. When the template is updated (new hooks, new sounds, statusline changes), review whether your local `~/.claude/settings.json` needs the same update.

The local file is NOT automatically updated — it is machine-local and may have machine-specific path substitutions. Review the diff manually and merge changes.

Signs of drift: a new sound or hook that works on another machine does not work on yours. Compare your `~/.claude/settings.json` against the template.

---

## 5. What Is NOT In the Repo (Local-Only)

Anyone who clones the Horizon AIOS repo will not have these. They must be created during setup (the bootstrap script handles most of them).

1. `~/.claude/settings.json` — Global Claude Code settings with machine-specific paths, hooks, and statusLine config. Created from the template at `$HORIZON_SYSTEM/templates/claude_code/settings.json`.

2. `~/.claude/CLAUDE.md` — Machine-local stub containing a single `@` redirect to the repo's CLAUDE.md. Created during bootstrap (one line, never changes).

3. `~/.claude/skills/` — A junction (Windows) or symlink (Unix/macOS) created by bootstrap pointing to `$HORIZON_SYSTEM/skills_sbin/`. Not a deployed copy — skills are live on disk. The junction itself is machine-local; the skills it points to are in the repo.

4. `$HORIZON_ROOT/.git/config` — Local git configuration, including `core.hooksPath` which wires the pre-commit hook. Set by bootstrap via `git config core.hooksPath`.

5. `$HORIZON_ROOT/handoffs/` — Handoff documents from Claude Code sessions. Directory created by bootstrap; contents are session-local and not committed.

6. Brain folders and their contents — `$HORIZON_ROOT/brains/<brain_name>/` and everything inside. Brain configurations are per-machine and per-user; they are never committed to the shared repo.

7. Any `*.local.json` files — Machine-specific config overrides. Gitignored by convention.

---

### 2026-06-20 — Centralized logging taxonomy

**Decision:** _(Path superseded — see Update below; canonical root is now `$HORIZON_SYSTEM/logs/`.)_ All AIOS operational logs are centralized under `$HORIZON_ROOT/logs/` with subdirectories: `bootstrap/`, `brain_provisioning/`, `agents_output/`, `hooks/`, `brains/`. Log behavior is configurable via `aios_local.conf` (`AIOS_LOG_MAX_DAYS`, `AIOS_LOG_MAX_SIZE_MB`, `AIOS_LOG_MAX_ROTATIONS`). Weekly `maintain_logs.py` in `sbin/` handles pruning and rotation. The `logs/` directory content is gitignored; a `.gitkeep` scaffold is tracked.

**Rationale:** Scattered log files make debugging cross-component issues difficult. A single root with a defined taxonomy makes logs discoverable and allows a single maintenance script to handle all log hygiene. Configurable retention keeps logs useful without unbounded disk growth. Gitignoring content but tracking `.gitkeep` ensures the directory structure is reproducible from a fresh clone without committing machine-specific log data.

**Implications:** Any new component that emits logs must write under `$HORIZON_SYSTEM/logs/<subdirectory>/`. The log directory is not created by the repo — bootstrap or the writing script must create it on first run (`mkdir -p`). `maintain_logs.py` must be kept in sync with the taxonomy if new subdirectories are added.

> **Update (2026-06-21):** The canonical log root moved from `$HORIZON_ROOT/logs/` to `$HORIZON_SYSTEM/logs/` so the audit log lives inside the AIOS layer that `harden_aios.py` locks down (explicit brains-group Deny). All writers and `$HORIZON_LOGS` now resolve to `$HORIZON_SYSTEM/logs/`. The subdirectory taxonomy is unchanged.

---

### 2026-06-20 — Token economy for context-loaded files

**Decision:** All files regularly loaded into Claude context (CLAUDE.md files, invariant docs, `@` import chain) must be short, direct, and token-efficient. Verbose documentation belongs in `$HORIZON_DOCS`, not in context-loaded config.

**Rationale:** Every token in a context-loaded file costs tokens on every session that loads it. A verbose invariant document read hundreds of times per week accumulates significant token overhead. Documentation that provides background, rationale, and examples is valuable — but it belongs in files that are read by humans on demand, not in files that are injected into every AI context window automatically.

**Implications:** When adding to CLAUDE.md files or invariant documents, write for density: one sentence per concept, no illustrative examples, no repeated caveats. If elaboration is needed, put it in `$HORIZON_DOCS` and link to it. Review context-loaded files periodically and trim any content that is not load-bearing for AI behavior.
