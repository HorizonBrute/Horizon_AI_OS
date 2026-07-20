---
name: post-update
description: Post-update reconciliation for a deployed Horizon AIOS install. After pulling a sizable AIOS update, diff what the update changed, classify changed files into inert-in-tree vs needs-reapply, print a prioritized reapply checklist, and drive the reapply steps by delegating to /doctor, /harden, /resync-user-skills, and the maintenance-schedule registration script. Invoke after a big update or periodically; it is a manual tool, not a scheduled job.
tools: Bash, Read, Grep, Glob
---

# Skill: /post-update

**Model preference:** `#midcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Reconcile a running Horizon AIOS install with an update that has just landed in the tree. A `git pull`/merge changes files on disk, but many changes do NOT take effect until a reapply step runs against the live install (ACLs, scheduled tasks, skill links, git hooks). This skill finds what changed, decides what must be reapplied, and drives those steps by delegating to the existing tools. It never re-implements them.

---

## When to invoke

- After pulling a sizable AIOS update (a version bump, a merged feature branch, a batch that touches hardening / posture / skills / hooks).
- Periodically as install hygiene (e.g. every few weeks) even without a known-big update.
- Any time you are unsure whether the running install still matches the tree.

This is a **manual deployer tool**. It is intentionally not scheduled — the deployer decides when to run it.

---

## What it does NOT do

- It does not re-implement `/doctor`, `/harden`, or `/resync-user-skills` — it calls them.
- It does not schedule itself or install a cron/Scheduled Task.
- It does not modify source; it reconciles the live install to the source already on disk.

---

## Step-by-step execution

### Step 1 — Identify the update range

1.1 Find the commit the install was at BEFORE the update and where it is now. Prefer the reflog:
```
git -C "$HORIZON_ROOT" reflog -20
```
Look for the most recent `pull`, `merge`, `reset`, or `checkout` entry. The commit just before it is the pre-update HEAD; current `HEAD` is post-update.

1.2 If the reflog is ambiguous, ask the deployer for the pre-update SHA/tag, or fall back to the last release tag: `git -C "$HORIZON_ROOT" describe --tags --abbrev=0`.

1.3 Capture the changed-file set:
```
git -C "$HORIZON_ROOT" diff --stat <pre>..<post>
git -C "$HORIZON_ROOT" diff --name-only <pre>..<post>
```

If there is no VCS history (a tarball deploy), fall back to running `/doctor` and skip to Step 4 — you can still reconcile posture even without a diff.

### Step 2 — Classify changed files

Sort the changed paths into two buckets:

- **Inert in tree** — takes effect just by being present; NO action. Docs, `.gitignore`, indexes, wiki, comments-only changes.
- **Needs reapply** — changing the file on disk does NOT change the running install until a step runs. Use the mapping in Step 3 to identify these.

### Step 3 — Map trigger files to reapply actions

For each changed path, match against this table (match by filename/dir, not full path). Collect the unique set of actions triggered.

| Changed file / pattern | Reapply action |
|---|---|
| `horizon_aios_harden.py`, `horizon_aios_acl_posture.py`, `file_acl_hardening.toml`, `*acl*hardening*` | Re-run `/harden` (run `/doctor` first to preview drift) |
| `horizon_aios_doctor.py` | Run `/doctor` (diagnostic; also the verifier for the harden step) |
| anything under `skills_bin/`, `skills_sbin/`, or `usr_skills/` (added/removed/renamed skill dirs) | Run `/resync-user-skills` |
| `horizon_aios_setup_maintenance_schedule.py`, `horizon_aios_nightly_maintenance.py` | Run `python "$HORIZON_SYSTEM/sbin/horizon_aios_setup_maintenance_schedule.py"` to (re)register the maintenance task |
| git hook sources (`hooks/`, `*pre-commit*`, `*pre-push*`) | Reinstall hooks per the repo's hook-install script |
| `templates/docker/*`, `Dockerfile` | Rebuild container images (only if containers are in use) |
| `bootstrap.*`, `horizon_aios_create_brain.py` | No action unless reprovisioning or creating a brain |
| onboarding / env scripts (`*onboard*`, `*_environment.config.json`) | Re-run the onboarding/env script to refresh resolved paths |

If a changed file plausibly needs reapply but matches nothing above, surface it in the report as **needs review** rather than silently classifying it inert.

### Step 4 — Print the prioritized checklist

Report, in this order:

1. The update range (pre → post SHA) and a one-line summary of the theme.
2. **Reapply actions**, ordered: read-only checks first (`/doctor`), then posture (`/harden`), then task/skill registration, then optional (Docker rebuild, deployer overrides).
3. For each action: the trigger file(s) that caused it and a one-line "why".
4. Any **needs review** files.
5. The inert set, collapsed to a count (e.g. "14 docs/index changes — no action").

### Step 5 — Drive the reapply (with confirmation)

5.1 Offer to run the actions in order. Run read-only steps (`/doctor`) freely.

5.2 **`/harden` changes real ACLs — confirm with the deployer before running it.** Show the `/doctor` drift first so they see what will change.

5.3 After registering the maintenance task, remind the deployer to record it in their automations registry if their deployment tracks one.

5.4 Re-run `/doctor` at the end to confirm the install is clean.

---

## Notes for the executing agent

- Use `$HORIZON_ROOT` / `$HORIZON_SYSTEM` env vars — never hardcode install paths.
- The value of this skill is the *mapping and ordering*, not the execution — always delegate execution to the owning skill/script so their own logic and model preferences apply.
- `/harden` is privileged and mutating; treat it as the one step that always needs explicit go-ahead.
- If the diff is empty but `/doctor` reports drift, trust `/doctor` — the install can drift without a code change (manual edits, a partial prior run).
- Keep the report tight; a deployer wants the action list, not a file-by-file dump.
