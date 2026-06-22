# Horizon AIOS — End-to-End Lifecycle Test

A runbook for proving the full install → switch → (provision/update/back up) →
uninstall → clean-reset lifecycle on a **dedicated clean machine**. Running it on
a throwaway box keeps that box a reusable test rig: the uninstall reverses the
entire bootstrap footprint, so you can re-run from a clean slate.

**Do not run this on your primary/owner machine** — bootstrap rewrites the live
`~/.claude` (skills + memory redirect) and local security policy (ACLs/logon
rights). `dev-env == build-target` is exactly the tension this test isolates.

This runbook is Windows-first (matches the verified platform). Linux/macOS use the
`uninstall.sh`/`bootstrap.sh` equivalents; the structure is identical.

**Scope vs. `system/uninstall.md`:** that doc is the **authoritative** uninstall
procedure and post-uninstall verification checklist. This runbook is the broader
*operator lifecycle* — it adds the parts the uninstall doc doesn't cover (the
**AIOS-switch** test and optional brain provisioning / sync / backup) and defers
to `system/uninstall.md` for the removal + verification detail rather than
repeating it.

---

## Prerequisites

- A clean Windows machine with your AI harness (e.g. Claude Code) installed.
- Admin rights (bootstrap/uninstall set ACLs and need elevation).
- Python on PATH, git configured for DCO sign-off (`user.name` + `user.email`).
- A scratch remote you own for the backup step (never the public upstream).

---

## Runbook

Run in an **elevated PowerShell**. AIOS switching needs a **second AIOS root**, so
this uses two clones.

```powershell
# ── 1. Baseline (nothing installed yet) ─────────────────────────────
git clone <your-remote> C:\devroot ; cd C:\devroot
.\horizon_system\sbin\uninstall.ps1 --dry-run      # should report ~nothing to remove

# ── 2. Install AIOS #1 ──────────────────────────────────────────────
.\horizon_system\sbin\bootstrap.ps1 --yes
aios list                                           # note the auto-registered name + (*) active
aios current                                        # confirm root = C:\devroot

# ── 3. AIOS switching test (needs a 2nd root) ──────────────────────
git clone <your-remote> C:\horizon-home             # second valid AIOS root
aios register home C:\horizon-home
aios list                                           # both shown; #1 still (*)
aios switch home --dry-run                          # preview pointer rewrites, no change
aios switch home
aios current                                         # root now C:\horizon-home
Get-Content $HOME\.horizon\active_env.ps1 | Select-String HORIZON_ROOT   # regenerated to new root
#   → open a NEW shell, check $env:HORIZON_ROOT == C:\horizon-home (env changes don't reach live shells)
aios switch <name-from-step-2>                      # switch back to #1
aios current                                         # root back to C:\devroot
aios unregister home                                # (optional) drop the 2nd registration; files untouched

# ── 4. Optional: exercise the rest of the lifecycle ────────────────
#   python horizon_system\sbin\create_brain.py testbrain --automation scheduled
#   python horizon_system\sbin\sync_aios.py            # simulate FF upstream update
#   python horizon_system\sbin\backup_user_data.py     # to YOUR remote (never public upstream)

# ── 5. Reset to clean ──────────────────────────────────────────────
#   if you made a brain:  python horizon_system\sbin\remove_brain.py testbrain --yes
.\horizon_system\sbin\uninstall.ps1 --dry-run       # preview full reversal
.\horizon_system\sbin\uninstall.ps1 --yes
#   then on C:\horizon-home if you bootstrapped it too:
#   cd C:\horizon-home ; .\horizon_system\sbin\uninstall.ps1 --yes
```

If `aios` isn't found right after bootstrap (PATH not refreshed in that shell),
open a fresh elevated shell or use the long form
`python horizon_system\sbin\aios_switch.py ...`.

---

## What to verify

### AIOS switching (step 3)
- `aios switch home` moves the `(*)` in `aios list` and updates `aios current`.
- `~/.horizon/active_env.ps1` is **regenerated** to the new root — but
  `~/.claude/settings.json` is **unchanged** (it points at the stable
  `~/.horizon/bin/aios-exec.ps1` wrapper; that is the indirection layer that makes
  a switch a pointer write, not a re-stamp). See `system/aios_switching.md`.
- A **new** shell picks up the new `$env:HORIZON_ROOT`; already-open shells do not.
- `aios switch` is **operator-config only** — it does not touch brain users' own
  profiles/ACLs.

### Clean reset after uninstall (step 5)
Run the **post-uninstall verification checklist in `system/uninstall.md`** — it is
authoritative (doctor.py failures = success, skills/memory junctions gone with
targets intact, PATH cleaned, ACEs stripped, idempotent re-run).

One switch-test-specific note: the registry (`aios_registry.json`) lives under
`~/.horizon/`, which uninstall removes — so the `home` registration from step 3
is cleaned up automatically (no manual `aios unregister` needed before teardown).

---

## See also
- `system/uninstall.md` — authoritative uninstall procedure + verification checklist.
- `system/aios_switching.md` — the switching model, registry, and commands.
- `system/distribution_and_updates.md` — framework vs. user-space, FF update,
  and backup model.
- `getting_started/updating.md` — the upstream-update how-to.
- `deployment/desktop.md` — bootstrap footprint and how a brain's harness is
  wired to AIOS.
