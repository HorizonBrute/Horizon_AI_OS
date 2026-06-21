# sbin — Privileged Scripts

`$HORIZON_BIN/sbin/` is the privileged scripts directory for Horizon AIOS. It mirrors the role of `/sbin` on Unix systems: scripts here require primary-user authority to execute and must never be accessible to brain user accounts or any other secondary OS user.

---

## What Belongs Here

Scripts belong in sbin when they:

- Create, modify, or delete OS user accounts (brain provisioning and teardown).
- Modify ACLs or permissions on any path outside a brain's own folder.
- Write to $HORIZON_ROOT or $HORIZON_BIN in ways that affect all users.
- Install or remove system-wide tools or dependencies.
- Perform any action that requires elevation (admin/root) or acts on behalf of the primary user.

Examples of sbin candidates:
- `provision_brain.ps1` — creates a brain OS user, home directory, and scoped ACLs.
- `teardown_brain.ps1` — removes a brain OS user account and archives or deletes its folder.
- `grant_project_access.ps1` — adds a brain user to a project folder's ACL.
- `audit_permissions.ps1` — reports ACL state of all brain folders and $HORIZON_BIN.

## What Does NOT Belong Here

If a script only reads from $HORIZON_BIN (status line, sounds, templates), it belongs in $HORIZON_BIN root or an appropriate subdirectory — not sbin. Brain users need read-execute access to those scripts, and sbin must remain inaccessible to them.

---

## Security Boundary

### Windows (NTFS ACLs)

sbin must have an explicit Deny ACL entry for all brain user accounts covering Read, Write, and Execute permissions. "No entry" is not sufficient — inherited permissions from $HORIZON_BIN may grant access unintentionally. An explicit Deny overrides any inherited Allow.

To deny access for a brain user on Windows (run as primary user or Administrator):

```powershell
$acl = Get-Acl "C:\devroot\horizon_bin\sbin"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "<brain_username>",
    "FullControl",
    "ContainerInherit,ObjectInherit",
    "None",
    "Deny"
)
$acl.AddAccessRule($rule)
Set-Acl "C:\devroot\horizon_bin\sbin" $acl
```

Repeat for each brain user account.

### Unix (POSIX permissions)

sbin must be chmod 700 (rwx------), owned by the primary user, with no group or world bits set:

```bash
chmod 700 $HORIZON_BIN/sbin
chown $USER $HORIZON_BIN/sbin
```

---

## Community Contributions

sbin is not open to community contributions. Scripts here are owner-managed and machine-specific. If you are contributing to Horizon AIOS, your contribution goes into $HORIZON_BIN (not sbin) or into $HORIZON_BIN/templates/ for setup automation.
