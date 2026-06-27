# Security Invariants — Horizon AIOS (Quick Reference)

Operational checklist. **Full specification:** `$HORIZON_DOCS/security_architecture_invariants.md`

Do not add new rules here — add them to the full spec and update these summary lines if warranted.

---

1. **Three-tier model.** Owner (Tier 1) owns `$HORIZON_ROOT`. Brains (Tier 2) are separate OS accounts scoped to their own folder. Docker (Tier 3) is optional per brain.

2. **Brain isolation.** `sbin/`, `skills_sbin/`, `logs/`: explicit **DENY** to the `brains` group. `bin/`, `skills_bin/`: read + execute. No write anywhere in `$HORIZON_SYSTEM`. No cross-brain readable path unless explicitly provisioned by the owner.

3. **No secrets in committed files.** No real paths, usernames, hostnames, API keys, or credentials in any committed file. Use placeholder strings in templates; substitute at setup time in gitignored local copies.
