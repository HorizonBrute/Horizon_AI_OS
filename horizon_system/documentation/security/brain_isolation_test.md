# Horizon AIOS — Brain Isolation Test (Criterion #5)

`horizon_aios_verify_isolation.py` (`$HORIZON_SYSTEM/sbin/`) proves the central
AIOS security claim: a **brain OS account can read `$HORIZON_BIN` but is denied
`$HORIZON_SYSTEM/sbin`**. This is verification **criterion #5** in
`tested_configurations.md` — the one guarantee that, unlike the others, can only
be fully proven by a *real, separate-identity process being refused*.

It is the in-repo, version-controlled home for what began as an out-of-tree
scratch harness — promoted so the owner and any contributor can re-validate the
isolation model on demand.

---

## Two modes

| Mode | Flag | Touches accounts? | Elevation | What it proves |
|---|---|---|---|---|
| **Safe (default)** | *(none)* | No | No | The *static* ACL posture is correct. |
| **Live** | `--live` | Yes (creates + deletes a throwaway brain) | Yes | A real brain process is *empirically* denied `sbin`. |

The account-touching, UAC/elevation behaviour is **opt-in** — it lives entirely
behind `--live`. Running with no flag never creates or deletes a user, so it is
safe to run anywhere, including the owner's primary machine.

### Safe mode (default)

```bash
python $HORIZON_SYSTEM/sbin/horizon_aios_verify_isolation.py
```

Confirms an explicit, non-inherited `brains` **Deny** on `sbin`, `skills_sbin`,
and `logs` — on Windows via `Get-Acl` (the same authoritative check
`horizon_aios_doctor.py` makes), on Unix via owner-only mode `0o700`. Non-destructive,
no elevation. Exit 0 if the posture holds, 1 if a Deny/permission is missing
(run `horizon_aios_harden.py`).

This is the static proxy for isolation: it verifies the *lock is configured*. It
does not prove a brain is *actually* refused — that is what `--live` is for.

### Live mode (`--live`) — opt-in, elevated, destructive

```bash
# Elevated (Administrator / root). On a test machine, not the owner box if avoidable.
python $HORIZON_SYSTEM/sbin/horizon_aios_verify_isolation.py --live
```

Steps: provision a throwaway brain (`aios_isotest` by default) → log on **as**
that brain → attempt to read `bin` (expect `BIN=READABLE`) and `sbin` (expect
`SBIN=DENIED`) → remove the brain. Expected pass line:

```
BIN=READABLE  SBIN=DENIED
[PASS] brain reads bin but is denied sbin (criterion #5)
```

On Windows the probe uses the brain's keystore password to launch a process under
its credentials (this needs the account's "Log on as a batch job" right — which a
plain brain has on most systems; if the probe reports *no result file*, grant it
via `--automation scheduled` at provision time or local security policy). On
Unix, root runs the read test as the brain via `runuser`/`su`/`sudo -u`.

It refuses to run if an account with the target name already exists (so it can
never clobber a real brain); pass `--brain-name` to pick a free name.

---

## Flags

- *(none)* — safe ACL check (non-destructive, no elevation)
- `--live` — opt-in full provision → probe → teardown (requires elevation)
- `--brain-name NAME` — throwaway account name for `--live` (default `aios_isotest`)
- `--keep` — `--live`: leave the brain provisioned afterwards (for inspection)
- `--yes` / `-y` — skip the `--live` confirmation prompt
- `--dry-run` — print what `--live` would do, change nothing
- `--horizon-root PATH` — explicit root; otherwise derived from script location

---

## Platform status

- **Windows** — both modes implemented and **verified** end-to-end.
- **Linux / macOS** — safe mode (mode `0o700`) implemented; the `--live` probe is
  a working **framework** (`runuser`/`su`/`sudo -u`) but has **not** been validated
  on real hardware. Tracked in `development_pipeline.md` (Known Gaps — Code) and
  reflected by the Linux **Partial** / macOS **Untested** rows in
  `tested_configurations.md`.

---

## See also

- `getting_started/lifecycle_test.md` — the broader operator lifecycle runbook;
  the isolation test is an optional step there.
- `tested_configurations.md` — the six verification criteria; this tool proves #5.
- `deployment/brain_automation.md` — the logon-right tiers (a brain's batch-logon
  right is what lets the Windows live probe run as the brain).
- `security/audit_logging.md` — the complementary runtime integrity monitor.
