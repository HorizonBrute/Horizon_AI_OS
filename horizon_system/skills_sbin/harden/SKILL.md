---
name: harden
description: Apply the authoritative brains-group ACL model to the AIOS layer — grants brains Read+Execute on bin/skills_bin, a no-write Deny across $HORIZON_SYSTEM, and an explicit full Deny on sbin/skills_sbin/logs. Use when the user types /harden, asks to "harden the AIOS", "apply the ACL model", "lock down sbin", or after horizon_aios_doctor.py reports a missing Deny ACE.
tools: Bash, Read
---

# Skill: /harden

Apply the authoritative brains-group ACL model to the AIOS layer (`horizon_aios_harden.py`), enforcing security_invariants.md §2/§3/§5. Run at bootstrap, after adding/removing directories under `$HORIZON_SYSTEM`, or when `horizon_aios_doctor.py` reports a missing brains Deny ACE.

---

## When to invoke

The user types `/harden`, or asks to "harden the AIOS", "apply the ACL model", "lock down sbin/skills_sbin", or `/doctor` flagged a missing Deny ACE on a privileged dir.

---

## Arguments

`/harden [--strict] [--dry-run] [--horizon-root PATH]`

- `--strict` — additionally strip inherited ACEs (Windows `/inheritance:r`; Unix `chown -R` + mode bits) for a locked-down standalone install. Default (additive) preserves existing/infra ACLs and enforces the model by adding ACEs only.
- `--dry-run` — print every action without executing anything (needs no elevation).
- `--horizon-root PATH` — explicit root; otherwise derived from the script location.

---

## Step-by-step execution

### Step 1 — Check elevation

ACL changes require the **administrative context** (Administrator on Windows, root on Unix). If the session is not elevated and the user did NOT pass `--dry-run`, warn that ACL changes will fail and instruct them to re-run from an elevated terminal (or with `sudo`). Do not pretend it succeeded. `--dry-run` needs no elevation — run it directly to preview.

### Step 2 — Run

```
python "$HORIZON_SYSTEM/sbin/horizon_aios_harden.py"
```

Append `--strict` / `--dry-run` / `--horizon-root` as the user requested. The script warns and continues (rather than crashing) when not elevated, so failures are visible.

### Step 3 — Report

Relay the banner output and the final Summary block (the brains grant/deny model applied). If the script reports the `brains` group was unavailable, surface that only owner-side hardening ran and it must be re-run after the group exists.

---

## Notes for the executing agent

- Owner + SYSTEM + Administrators always retain Full control (Windows), regardless of mode — the script never strips them.
- All Deny ACEs are applied AFTER all brains grants, so an inherited permission can never reach a privileged dir. Do not reorder anything — just run the script.
- The model: `bin`/`skills_bin` → brains Read+Execute; `sbin`/`skills_sbin`/`logs` → brains DENY (full); rest of `$HORIZON_SYSTEM` → brains no-write.
- Never set `AIOS_SKIP_HARDEN=1` in native deployments — that bypasses the hardening (it exists only for the Docker root-context build step).
