---
name: doctor
description: Run the Horizon AIOS health check — verifies env vars, the skills junction, git hooks, local config, the AIOS registry, and privileged-dir Deny ACLs, then reports passed/warnings/failures. Use when the user types /doctor, asks to "run the doctor", "health check the AIOS", "check the install", or diagnoses why the AIOS is misbehaving.
tools: Bash, Read
---

# Skill: /doctor

**Model preference:** `#lowcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Run the read-only Horizon AIOS health check and surface its results. Use this after bootstrap, after an upstream sync that touches bootstrapping, or whenever something behaves unexpectedly and you need a quick status read.

---

## When to invoke

The user types `/doctor`, or asks you to "run the doctor", "health-check the AIOS", "check the install", or diagnose a broken/misbehaving AIOS.

---

## Step-by-step execution

### Step 1 — Run the check

```
python "$HORIZON_SYSTEM/sbin/horizon_aios_doctor.py"
```

Read-only — no elevation required. It takes no arguments and runs every check unconditionally.

### Step 2 — Report the result

2.1 Relay the summary line (`N checks passed, M warnings, K failures`).

2.2 For each `[FAIL]` and `[WARN]`, surface the line and its remediation hint (the script prints the fix inline, e.g. "run bootstrap", "run horizon_aios_harden.py", "run horizon_aios_switch.py init"). Do not invent fixes — quote the script's own guidance.

2.3 Exit code is `1` if any check failed, `0` if only warnings or clean. Report success/failure accordingly.

---

## Post-setup mode (`--post-setup`)

Right after an install, bootstrap, or `/harden`, run the post-setup mode to
confirm the user-facing plumbing actually works:

```
python "$HORIZON_SYSTEM/sbin/horizon_aios_doctor.py" --post-setup
```

This runs all the standard checks plus three post-install verifications: a test
sound through the canonical sound chokepoint, statusline command resolution, and
git `commit.gpgsign`. A muted sound config reports a clean `[SKIP]` (not a
failure), and the summary then includes a skipped count. Exit-code semantics are
unchanged — exit 1 only if a check FAILs; SKIP and WARN do not fail the run.

---

## Notes for the executing agent

- `$HORIZON_SYSTEM` must be set. If it is not, report that the AIOS environment is not active and the user should source their profile or run the AIOS switcher.
- This skill is purely diagnostic — it changes nothing. A stopped monitor is a WARN, not a FAIL (the monitor is optional).
- Do not reimplement any check — the script is the single source of truth. Run it and format its output.
