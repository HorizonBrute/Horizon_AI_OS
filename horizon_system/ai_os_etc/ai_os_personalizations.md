# AI OS Personalizations — Horizon AIOS

---

## 1. Settings Layer Ownership

Three-layer settings hierarchy (Claude Code is the reference implementation). Wrong layer → double-firing, override conflicts, or portability loss.

### Global (`~/.claude/settings.json`)

- `statusLine`, all hooks (`Stop`, `PermissionRequest`, `StopFailure`, etc.)
- UI preferences: `theme`, `verbose`, `effortLevel`, `autoUpdatesChannel`
- Base permissions that apply everywhere

### Devroot OS-layer (`$HORIZON_ROOT/.claude/settings.json`)

- `permissions.allow` and `permissions.defaultMode` only
- No hooks, no statusLine, no UI prefs — those belong to global

Committed to the OS repo; hooks and statusLine contain machine-specific paths and must stay out.

**Sync safety:** `horizon_aios_sync.py` does a `git merge --ff-only`, which updates this file if it changed upstream. This is intentional — the devroot settings file is OS-layer infrastructure, not personal config. Personal customizations do not belong here. Put them in `~/.claude/settings.json` (global layer), which lives outside the repo and is never touched by sync. Project-level permissions go in the project's own `.claude/settings.json`, also outside the OS repo.

### Project-level (`.claude/settings.json` inside a project folder)

- Additional `permissions.allow` entries scoped to the project
- May tighten or loosen `defaultMode`
- Must not own hooks or statusLine

---

## 2. CLAUDE.md Hierarchy

Stub-redirect pattern: canonical instructions stay in the OS repo; harness lookup is satisfied by pointer files.

### Global stub (`~/.claude/CLAUDE.md`)
Single `@` import only — no substantive instructions:
```
@$HORIZON_ROOT/.claude/CLAUDE.md
```
(@ imports require absolute paths)

### Canonical system-level (`$HORIZON_ROOT/.claude/CLAUDE.md`)
Thin entry point that imports `$HORIZON_ROOT/CLAUDE.md`. All system-level instructions live in the root CLAUDE.md and agents.md. Committed to OS repo; must not contain personal data.

### Project-level (`<project>/CLAUDE.md`)
Project-specific context: tech stack, conventions, anything the agent needs for that project. Owned by the project repo, not the OS repo.

---

## 3. How to Add a New AI Harness

1. Create a harness config directory at `$HORIZON_SYSTEM/harness_configs/<harness_name>/` (for runtime config: hooks, sounds map, harness-specific settings) and/or a template directory at `$HORIZON_SYSTEM/templates/<harness_name>/` (for setup templates copied at bootstrap).
2. Add a `settings.json` (or equivalent config file) template using placeholder strings (e.g., `AIOS_EXEC_WRAPPER`) instead of real paths. Document all placeholders in a `README.md` in the same directory.
3. If the harness supports event hooks (audio, alerts), wire them to sounds in `$HORIZON_SOUNDS/`. Use root-level generic sounds unless you have vendor-voiced audio, in which case create `$HORIZON_SOUNDS/<vendor>_event_sounds/`.
4. If the harness supports a status line or equivalent, add a status script to `$HORIZON_BIN/statusline/`.
5. Document the harness in `$HORIZON_DOCS/`.
6. Add harness-specific permissions or config conventions to this document under a new subsection.

The harness must not require any changes to `$HORIZON_ETC` invariant documents unless the invariants themselves need to evolve.

---

## 4. How to Create a Brain

Use `$HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py` to automate brain setup. Manual steps:

1. Create a new OS user account (`brain_researcher`, `brain_coder`, etc.). Windows: Settings > Accounts > Other users. Unix: `useradd`.
2. Create the brain's home directory under the brains path.
3. Set ACLs: brain user full access to its own folder; no access elsewhere, including $HORIZON_ROOT.
4. Grant brain user read+execute on `$HORIZON_BIN/` (excluding `sbin/` and `skills_sbin/` — see security_architecture_invariants.md §3).
5. Create `.claude/settings.json` inside the brain's folder scoped to the brain's permissions.
6. Create `CLAUDE.md` inside the brain's folder: persona, scope, behavioral rules.
7. Brain's CLAUDE.md may import `@$HORIZON_ROOT/CLAUDE.md` to inherit system-level instructions.

### What a brain inherits:
- Read+execute on `$HORIZON_BIN/` tools, sounds, skills_bin.
- System-level instructions from `$HORIZON_ROOT/CLAUDE.md` (if imported).
- No access to any other brain's folder or the primary user's data.

---

## 5. The Second Brain Model

Multiple isolated AI personas running concurrently on the same machine.

- Each brain is its own OS user — OS-level isolation, not application-level.
- Brains can use different harnesses, models, and memory systems.
- Project access is granted per-brain by adding the brain user to a project folder's ACL.
- Brains are ephemeral: delete the OS account and folder; no shared system state to clean up.
- Brains run interactively (switch user) or programmatically (scheduled tasks, automation).

---

## 6. How Community Contributions Fit In

Contributors may add:

- New harness templates in `$HORIZON_SYSTEM/templates/`.
- New sounds in `$HORIZON_SOUNDS/` (root for generic, vendor subdirectory for voiced audio).
- New status line scripts in `$HORIZON_BIN/statusline/`.
- Documentation in `$HORIZON_DOCS/`.
- Improvements to `$HORIZON_ETC` invariant documents (with community review).

Contributions must not:
- Hardcode real paths, usernames, or machine-specific values anywhere.
- Introduce dependencies on the primary user's personal setup.
- Break the existing three-layer settings hierarchy.
- Add files to `$HORIZON_SYSTEM/sbin/` — sbin is owner-managed and not community-contributed.
- Modify `$HORIZON_ROOT/.claude/CLAUDE.md` in ways that make it non-portable (no personal preferences, no project-specific instructions).

All contributed templates must use placeholder strings instead of real paths and document those placeholders in their `README.md`.

---

## 7. /handoff Skill

Generates a structured session handoff document. See `$HORIZON_SYSTEM/skills_sbin/handoff/SKILL.md`. The skill is live via the `~/.claude/skills/` symlink created by bootstrap — no manual copy needed.

---

## 8. aios_overrides.md

Optional per-project file that overrides handoff directory and display name. Place at the project root (not inside `.claude/`). See `$HORIZON_SYSTEM/templates/aios_overrides.md` for the template and available keys.
