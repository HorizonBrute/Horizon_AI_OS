---
name: create-brain
description: Provision a new Horizon AIOS brain — creates the OS user account, the shared brains group and a per-brain group, the workspace folder, a login shell profile, and stores an auto-generated password in the OS keystore. Use when the user types /create-brain, asks to "create a brain", "provision a brain account", "stand up a new brain", or "add a brain user".
tools: Bash, Read
---

# Skill: /create-brain

**Model preference:** `#highcap` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Provision a new isolated AI brain with `horizon_aios_create_brain.py`: an OS user account, the shared `brains` group, a per-brain group, the workspace at `$HORIZON_ROOT/brains/<brain-name>/`, a login shell profile, and an auto-generated 64-char password stored in the OS native keystore. The `sbin/skills_sbin/logs` Deny ACEs are re-applied after all grants per the security invariants.

---

## When to invoke

The user types `/create-brain`, or asks to "create a brain", "provision a brain account", "stand up a new brain", or "add a brain user".

---

## Arguments

`/create-brain <brain-name> [--automation none|scheduled|daemon] [--horizon-root PATH] [--dry-run]`

- `<brain-name>` — **required** positional; must match `^[a-z][a-z0-9_]{1,31}$` (start with a lowercase letter, then 1–31 lowercase letters/digits/underscores). If the user did not supply one, ask before running.
- `--automation` — opt-in logon-rights tier (default `none`). `scheduled` grants "Log on as a batch job" (Windows) / enables systemd lingering (Linux); `daemon` grants "Log on as a service" (Windows) / prints system-service guidance.
- `--horizon-root PATH` — explicit root; otherwise derived from the script location.
- `--dry-run` — print every action without making changes.

---

## Step-by-step execution

### Step 1 — Check elevation

This **hard-requires** the administrative context — the script exits with an error if not run as Administrator (Windows) or root (Unix). If the session is not elevated and the user did NOT pass `--dry-run`, do not run it: tell the user to re-run from an elevated terminal (or with `sudo`) and stop. `--dry-run` still calls the same privilege check, so a real preview also needs elevation; if blocked, surface the script's own message.

### Step 2 — Run

```
python "$HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py" <brain-name>
```

Append `--automation` / `--horizon-root` / `--dry-run` as requested.

### Step 3 — Report

3.1 Relay the Phase 4 verification checks (`[PASS]`/`[FAIL]`) and the Summary.

3.2 Surface the "Next steps" the script prints — notably retrieving the account password: `python "$HORIZON_SYSTEM/sbin/horizon_aios_brain_credential.py" get <brain-name> --show`. The password is never printed by provisioning; it lives in the OS keystore.

3.3 If verification reported failures, relay the script's cleanup instructions (it points at `horizon_aios_remove_brain.py <name> --yes`).

---

## Notes for the executing agent

- The generated password is stored in the OS native keystore via `horizon_aios_brain_credential.py` and is NEVER echoed. Do not attempt to print or log it.
- If the user already exists, the script reports "Nothing to do" and exits 0 — that is not a failure.
- Per-brain group naming: `<brain-name>_group` on Windows (shared user/group namespace), `<brain-name>` on Linux/macOS.
- Deny ACEs on `sbin/skills_sbin/logs` are always (re)applied AFTER all brains grants — do not reorder; just run the script.
