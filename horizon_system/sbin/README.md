# sbin — Privileged Scripts

`$HORIZON_SYSTEM/sbin/` is the privileged scripts directory for Horizon AIOS. It mirrors the role of `/sbin` on Unix systems: scripts here require primary-user authority to execute and must never be accessible to brain user accounts or any other secondary OS user.

---

## What Belongs Here

Scripts belong in sbin when they:

- Create, modify, or delete OS user accounts (brain provisioning and teardown).
- Modify ACLs or permissions on any path outside a brain's own folder.
- Write to $HORIZON_ROOT or $HORIZON_SYSTEM in ways that affect all users.
- Install or remove system-wide tools or dependencies.
- Perform any action that requires elevation (admin/root) or acts on behalf of the primary user.

Current sbin scripts follow the `horizon_aios_` naming convention (see `security_architecture_invariants.md §8`). Examples: `horizon_aios_create_brain.py`, `horizon_aios_remove_brain.py`, `horizon_aios_harden.py`. See `$HORIZON_DOCS/utilities.md` for the full catalog.

## What Does NOT Belong Here

If a script only reads from $HORIZON_BIN (status line, sounds, templates), it belongs in $HORIZON_BIN or an appropriate subdirectory — not sbin. Brain users need read-execute access to those scripts, and sbin must remain inaccessible to them.

---

## Security Boundary

The brains-group Deny ACL on `sbin/` is applied by `horizon_aios_harden.py` (run from bootstrap) and re-applied after each brain provisioning. Use that script rather than setting per-user ACEs manually — it enforces the correct model group-wide.

### Windows (NTFS ACLs)

sbin must have an explicit Deny ACL for the `brains` group covering all access. "No entry" is not sufficient — inherited permissions from $HORIZON_BIN may grant access unintentionally. An explicit Deny overrides any inherited Allow. Run `horizon_aios_harden.py` to apply the correct ACL.

### Unix (POSIX permissions)

sbin must be chmod 700 (rwx------), owned by the primary user, with no group or world bits set. `horizon_aios_harden.py` applies this.

```bash
chmod 700 $HORIZON_SYSTEM/sbin
chown $USER $HORIZON_SYSTEM/sbin
```

---

## Community Contributions

sbin is not open to community contributions. Scripts here are owner-managed and require elevation. If you are contributing to Horizon AIOS, your contribution goes into `$HORIZON_BIN` (unprivileged shared tooling), `$HORIZON_SYSTEM/harness_configs/<harness>/` (harness-specific config), or `$HORIZON_SYSTEM/templates/` (setup templates) — not sbin.
