---
name: remove-brain
description: Deprovision a Horizon AIOS brain — removes its OS user account, per-brain group, workspace folder, profile config, and stored credential, leaving the shared brains group intact. Use when the user types /remove-brain, asks to "remove a brain", "delete a brain account", "deprovision a brain", or "tear down a brain user".
tools: Bash, Read
---

# Skill: /remove-brain

Deprovision a brain with `horizon_aios_remove_brain.py` — the counterpart to `horizon_aios_create_brain.py`. Removes the brain's OS user account, its per-brain group, its workspace folder, its user-profile config, and its stored credential. The shared `brains` group is left intact (other brains use it).

---

## When to invoke

The user types `/remove-brain`, or asks to "remove a brain", "delete a brain account", "deprovision a brain", or "tear down a brain user".

---

## Arguments

`/remove-brain <brain-name> [--yes] [--keep-credential] [--horizon-root PATH] [--dry-run]`

- `<brain-name>` — **required** positional; must match `^[a-z][a-z0-9_]{1,31}$`. The script refuses reserved names (`brains`, `root`, `administrator`, the invoking user, etc.).
- `--yes` / `-y` — skip the interactive confirmation prompt.
- `--keep-credential` — do not delete the stored OS-keystore credential.
- `--horizon-root PATH` — explicit root; otherwise derived from the script location.
- `--dry-run` — print what would be removed without changing anything.

---

## Step-by-step execution

### Step 1 — Check elevation

This **hard-requires** the administrative context — the script exits with an error if not run as Administrator (Windows) or root (Unix). (Privileges are checked only on a real run, not `--dry-run`.) If the session is not elevated and the user did NOT pass `--dry-run`, do not run it: tell the user to re-run from an elevated terminal (or with `sudo`) and stop.

### Step 2 — Confirmation

Without `--yes`, the script prompts interactively and requires the user to **type the brain name** to confirm. A non-interactive agent session cannot answer that prompt — if you intend to run it unattended and the user has clearly confirmed the destructive removal, pass `--yes`. Otherwise surface that confirmation is required.

### Step 3 — Run

```
python "$HORIZON_SYSTEM/sbin/horizon_aios_remove_brain.py" <brain-name>
```

Append `--yes` / `--keep-credential` / `--horizon-root` / `--dry-run` as requested.

### Step 4 — Report

Relay the removal output and the final "Verify removal" result. If anything is still present after removal (exit code 2), surface what remained so the user can clean it up.

---

## Notes for the executing agent

- Destructive and irreversible — it deletes the OS account, workspace, profile, and credential. Confirm intent before running with `--yes`.
- Links (home `~/.claude` → workspace, workspace `.claude/skills` → `skills_bin`) are removed as reparse points (rmdir/unlink) BEFORE any recursive delete, so `skills_bin` is never followed/destroyed — do not work around this; just run the script.
- The shared `brains` group is intentionally kept. Only the per-brain group is removed.
