# AI OS Personalizations — Horizon AIOS

This document defines the personalization model for Horizon AIOS: how configuration layers work, how to add harnesses, how to create and manage brains, and how community contributions fit into the system.

---

## 1. Settings Layer Ownership

Horizon AIOS uses a strict three-layer settings hierarchy for AI harnesses that support it (Claude Code is the reference implementation). Each layer has a defined ownership scope. Putting config in the wrong layer causes double-firing, override conflicts, or loss of portability.

### Global (`~/.claude/settings.json`)
Owns: everything that applies to the user across all sessions and all projects.

- `statusLine` — the harness status bar command.
- All hooks (`Stop`, `PermissionRequest`, `StopFailure`, etc.) — event-driven sounds and alerts.
- UI preferences: `theme`, `verbose`, `effortLevel`, `autoUpdatesChannel`.
- Base permissions that should apply everywhere.

### Devroot OS-layer (`$HORIZON_ROOT/.claude/settings.json`)
Owns: devroot-specific permissions only.

- `permissions.allow` — the list of tools and commands permitted within the devroot context.
- `permissions.defaultMode` — the default edit acceptance mode for devroot sessions.
- Nothing else. No hooks. No statusLine. No UI prefs. Those belong to global.

Rationale: the devroot settings file is committed to the OS git repo. Hooks and statusLine contain hardcoded paths that are machine-specific. Keeping them out of this file ensures the committed file stays portable and shareable.

### Project-level (`.claude/settings.json` inside a project folder)
Owns: project-specific permission overrides.

- Additional `permissions.allow` entries scoped to the project.
- May tighten or loosen defaultMode for the project.
- Must not own hooks or statusLine — those remain global.

---

## 2. CLAUDE.md Hierarchy

Horizon AIOS uses a stub-redirect pattern to keep the canonical instructions in the OS repo while satisfying harness lookup expectations.

### Global stub (`~/.claude/CLAUDE.md`)
Contains only a single `@` import directive pointing to the canonical file:

```
@$HORIZON_ROOT/.claude/CLAUDE.md
```
(substitute your actual absolute path — @ imports require absolute paths)

This file should not contain any substantive instructions. It is a pointer only.

### Canonical system-level (`$HORIZON_ROOT/.claude/CLAUDE.md`)
Contains all system-level instructions: agent usage preferences, list formatting rules, behavioral invariants, and references to the three `$HORIZON_ETC` invariant documents. This file is the single source of truth for how AI agents should behave in this OS environment. It is committed to the OS repo and is community-shareable (it must not contain personal data).

### Project-level (`<project>/CLAUDE.md`)
Contains project-specific context: what the project is, its tech stack, coding conventions, and anything the AI agent needs to know to work in that project. Project CLAUDE.md files are owned by the project, not by the OS, and are committed to the project's own git repo.

---

## 3. How to Add a New AI Harness

Horizon AIOS is designed to support multiple AI harnesses beyond Claude Code. To add support for a new harness:

1. Create a template directory at `$HORIZON_BIN/templates/<harness_name>/`.
2. Add a `settings.json` (or equivalent config file) template using `HORIZON_BIN_PATH` and other placeholders instead of real paths. Document all placeholders in a `README.md` in the same directory.
3. If the harness supports event hooks (audio, alerts), wire them to sounds in `$HORIZON_BIN/sounds/`. Use root-level generic sounds unless you have vendor-voiced audio, in which case create `$HORIZON_BIN/sounds/<vendor>_event_sounds/`.
4. If the harness supports a status line or equivalent, add a status script to `$HORIZON_BIN/statusline/`.
5. Document the harness in `$HORIZON_DOCS/`.
6. Add harness-specific permissions or config conventions to this document under a new subsection.

The harness must not require any changes to `$HORIZON_ETC` invariant documents unless the invariants themselves need to evolve.

---

## 4. How to Create a Brain

A brain is an isolated AI persona running as a separate OS user account.

### Setup steps:

1. Create a new OS user account (e.g., `brain_researcher`, `brain_coder`). On Windows: Settings > Accounts > Other users. On Unix: `useradd`.
2. Create the brain's home directory under a designated brains path (e.g., `C:\devroot\brains\<brain_name>\` or wherever the primary user designates).
3. Set ACLs so the brain user has full access to its own folder and no access to any other path, including $HORIZON_ROOT itself.
4. Grant the brain user read-and-execute access to `$HORIZON_BIN/` (excluding `$HORIZON_BIN/sbin/` — see security_invariants.md Section 3).
5. Inside the brain's folder, create a `.claude/` directory with a `settings.json` scoped to the brain's permissions. This is the brain's project-level config.
6. Create a `CLAUDE.md` inside the brain's folder defining the brain's persona, scope, and behavioral rules.
7. The brain's CLAUDE.md may reference `@$HORIZON_ROOT/.claude/CLAUDE.md` to inherit system-level instructions, then add persona-specific overrides below.

### What a brain inherits:
- Read-execute access to `$HORIZON_BIN/` tools and sounds.
- System-level instructions from `$HORIZON_ROOT/.claude/CLAUDE.md` (if the brain's CLAUDE.md imports it).
- No access to any other brain's folder or the primary user's data.

---

## 5. The Second Brain Model

The second brain model enables AI personas with different specializations, risk tolerances, or trust levels to run concurrently on the same machine without mutual interference.

Key properties:
- Each brain runs as its own OS user — OS-level isolation, not application-level.
- Brains can have different harnesses, different models, different memory systems.
- The primary user can provision a brain with access to a specific project by adding the brain user to a project folder's ACL explicitly.
- Brains are ephemeral by default — a brain can be deleted by removing its OS user account and its folder. No cleanup of shared system state is needed.
- The primary user may run a brain interactively (switch user) or programmatically (scheduled tasks, automation).

The second brain model is intentionally minimal at the OS layer. Horizon AIOS provides the isolation scaffold; the primary user builds the brain's personality and capabilities on top.

---

## 6. How Community Contributions Fit In

Horizon AIOS is designed for community release. Contributors may add:

- New harness templates in `$HORIZON_BIN/templates/`.
- New sounds in `$HORIZON_BIN/sounds/` (root for generic, vendor subdirectory for voiced audio).
- New status line scripts in `$HORIZON_BIN/statusline/`.
- Documentation in `$HORIZON_DOCS/`.
- Improvements to `$HORIZON_ETC` invariant documents (with community review).

Contributions must not:
- Hardcode real paths, usernames, or machine-specific values anywhere.
- Introduce dependencies on the primary user's personal setup.
- Break the existing three-layer settings hierarchy.
- Add files to `$HORIZON_BIN/sbin/` — sbin is owner-managed and not community-contributed.
- Modify `$HORIZON_ROOT/.claude/CLAUDE.md` in ways that make it non-portable (no personal preferences, no project-specific instructions).

All contributed templates must use the `HORIZON_BIN_PATH` placeholder pattern and document substitution steps in their `README.md`.

---

## 7. /handoff Skill

Generates a structured session handoff document. See `horizon_bin/skills/handoff.md` for the full implementation and template. Deploy the skill by copying it to `~/.claude/skills/handoff.md`.

---

## 8. aios_overrides.md

Optional per-project file that overrides handoff directory and display name. Place at the project root (not inside `.claude/`). See `horizon_bin/templates/aios_overrides.md` for the template and available keys.
