# Security Invariants — Horizon AIOS

These invariants define the non-negotiable security boundaries of Horizon AIOS. They apply to all users, all AI harnesses, and all brain configurations. AI agents operating within this OS must treat these as hard constraints, not guidelines.

---

## 1. User Ownership Model

The primary OS user (the human who installed Horizon AIOS) owns $HORIZON_ROOT and all its contents. This ownership is absolute.

- All files and directories under $HORIZON_ROOT are created and maintained by the primary user.
- No brain user account may write to $HORIZON_ROOT itself or any path outside its own designated brain folder.
- The primary user may read, write, delete, or restructure any path in the OS at any time.
- Ownership is enforced at the OS level (NTFS ACLs on Windows, POSIX permissions on Unix). Horizon AIOS does not implement its own access control layer — it relies on the underlying OS.

---

## 2. Brain Isolation

Each "brain" is an isolated AI persona running as a separate OS user account, scoped to its own directory subtree.

- A brain's home directory is its scope boundary. It may not read or write outside that boundary by default.
- Brains do not share data with each other. There is no cross-brain readable path unless the primary user explicitly creates one.
- A brain's configuration, memory, session data, and any files it generates live inside its own folder.
- If a brain is compromised or misbehaves, the blast radius is limited to its own folder. The primary user's data and other brains are unaffected.
- The primary user is responsible for creating and scoping brain user accounts. Horizon AIOS provides conventions; enforcement is the primary user's responsibility.

---

## 3. The bin/sbin Boundary

$HORIZON_BIN mirrors the Unix /bin and /sbin distinction:

- `$HORIZON_BIN/` (bin) — group-readable. All brain user accounts may read and execute scripts and assets here. This is where shared tooling, sounds, templates, and status scripts live.
- `$HORIZON_BIN/sbin/` — owner-only. Brain user accounts must never have read or execute access to this directory. This is where privileged scripts live: scripts that manage brain accounts, modify OS-level config, or act on behalf of the primary user.

On Windows: sbin must have an explicit ACL denying all brain user accounts (Deny: Read, Write, Execute). The default "no entry" posture is insufficient because inherited permissions may grant access. An explicit Deny takes precedence.

On Unix: sbin must be chmod 700 (rwx------), owned by the primary user, with no group or world bits set.

AI agents must never place privileged logic in $HORIZON_BIN root or subdirectories other than sbin. If a script requires primary-user authority to run correctly, it belongs in sbin.

---

## 4. External Tool Provisioning for Brains

When a brain needs access to an external tool (CLI, MCP server, API key), the primary user provisions it explicitly.

- Tools provisioned for a brain are installed in or scoped to the brain's folder, or granted as read-execute only from $HORIZON_BIN.
- API keys and secrets are never stored in $HORIZON_ROOT committed files. They are stored in environment variables, OS credential stores, or brain-local config that is gitignored.
- The primary user audits what each brain has access to before provisioning. Least privilege applies (see Section 5).
- A brain must never self-provision new tools or escalate its own permissions. Any such capability must be wired through sbin scripts controlled by the primary user.

---

## 5. Principle of Least Privilege

Every component of Horizon AIOS — scripts, brain users, AI harnesses, hooks — operates with the minimum permissions necessary to do its job.

- Hooks that play sounds need read access to $HORIZON_BIN/sounds/ only.
- Status line scripts need read access to session metadata only.
- Brain users need write access to their own folder only.
- No script in $HORIZON_BIN should require or request elevated (admin/root) privileges at runtime. If elevation is needed, it belongs in sbin and must be invoked explicitly by the primary user.

When in doubt, grant less access and expand as needed. Never grant access speculatively.

---

## 6. No Sensitive Data in Committed Files

The Horizon AIOS git repository is designed for community release. This means:

- No real usernames, real paths, hostnames, or machine-specific identifiers may appear in committed files.
- No API keys, tokens, passwords, or credentials of any kind may be committed, even in comments or example values.
- Templates use placeholder strings (e.g., `HORIZON_BIN_PATH`) in place of real paths. Users substitute real values at setup time in their local, gitignored copies.
- `.gitignore` must exclude: local settings overrides, brain folders, credential files, session data, and any file that contains a real path or secret.
- The `.claude/settings.json` at $HORIZON_ROOT is committed because it contains only devroot-scoped permissions and no personal data. If it ever acquires personal data, it must be moved to a gitignored local override.
- AI agents operating in this repo must refuse to commit files containing hardcoded personal paths or credentials. If such content is detected, the agent must flag it and halt.
