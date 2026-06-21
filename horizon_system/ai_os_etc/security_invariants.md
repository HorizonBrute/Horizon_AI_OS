# Security Invariants — Horizon AIOS

Hard constraints for all users, harnesses, and brain configurations.

---

## 0. Usage Model

Horizon AIOS operates under a three-tier principal model.

**Tier 1 — Administrative context:** The primary OS user account (or a dedicated admin account set up by the primary user) owns and manages $HORIZON_ROOT. This context installs and configures brains, provisions tools, sets filesystem permissions, and runs privileged scripts. All AIOS maintenance work happens at this tier.

**Tier 2 — Brain accounts:** Separate OS user accounts that run agentic workflows. Each brain is an expert system scoped to a specific task or set of tasks. Brain accounts start with zero access outside their own folder. Access to any additional resource is provisioned explicitly by the administrative context.

**Tier 3 — Docker (optional, per brain):** A brain may run its own Docker containers for isolated services. Docker adds network and process isolation on top of the OS account boundary, not instead of it.

### Primary Threat Models

Two co-equal threat models drive every security decision:

**Threat 1 — Prompt Injection**
Malicious instructions embedded in data cause a brain to take unintended actions. Example: a document being summarized instructs the brain to exfiltrate its session context.

Mitigations: narrow tool access + audit trail (anomalous actions are detectable).

**Threat 2 — Credential and Data Containment**
A hallucinating, misconfigured, or compromised brain can only cause harm proportional to the credentials and data it holds. A brain with no API key cannot authenticate; a brain with no filesystem access outside its folder cannot read other brains' data.

Mitigations: OS-native credential storage (managed by `brain_credential.py` in sbin) + zero-default access posture + least privilege on both tools and credentials.

These two models are defense-in-depth layers: even if injection succeeds (Threat 1 fails), containment limits blast radius (Threat 2). Even if a brain has broad tool access (Threat 2 partially relaxed), the audit trail can detect and surface the injection (Threat 1 compensating control).

### Bring Tools to the Brain

Brains do not get default access to shared resources. The administrative context provisions specifically what each brain needs — not a shared directory the brain can browse.

### Audit Trail

The audit log must be stored where the brain cannot modify or delete it — enforced by filesystem permissions. It is the detection layer for prompt injection: unexpected tool calls, credential use, or anomalous output volume are the signals.

---

## 1. User Ownership Model

The primary OS user (the human who installed Horizon AIOS) owns $HORIZON_ROOT and all its contents. This ownership is absolute.

- No brain user account may write to $HORIZON_ROOT itself or any path outside its own designated brain folder.
- The primary user may read, write, delete, or restructure any path in the OS at any time.
- Access control is enforced entirely by OS filesystem permissions (NTFS ACLs on Windows, POSIX permissions on Unix). Horizon AIOS does not implement its own access control layer. All documentation, configuration, and agent instructions that reference access control are describing OS-level permissions to be set by the primary user, not an AIOS enforcement mechanism.

---

## 2. Brain Isolation

Each "brain" is an isolated AI persona running as a separate OS user account, scoped to its own directory subtree.

- A brain's home directory is its scope boundary. It may not read or write outside that boundary by default.
- Brains do not share data with each other. There is no cross-brain readable path unless the primary user explicitly creates one.
- If a brain is compromised or misbehaves, the blast radius is limited to its own folder. The primary user's data and other brains are unaffected.

**Brains group:** All brain user accounts are members of a single OS-level group, conventionally named `brains`. Administrative convenience only — lets the admin grant or deny a path for all brains without enumerating accounts. Does not imply shared access. OS construct, not an AIOS construct.

**Default brains group filesystem permissions** — set by `create_brain.py` and `bootstrap.ps1`:

| Path | Brains Group |
|---|---|
| `$HORIZON_BIN/` | Read + Execute |
| `$HORIZON_SYSTEM/sbin/` | **DENY** (explicit) |
| `$HORIZON_SYSTEM/skills_bin/` | Read + Execute (explicit grant — not inherited from `$HORIZON_BIN`) |
| `$HORIZON_SYSTEM/skills_sbin/` | **DENY** (explicit) |
| `$HORIZON_USRBIN/` | None (tools provisioned selectively per brain) |
| `$HORIZON_ROOT/logs/` | **DENY** (explicit — audit log must not be writable by brains) |
| `$HORIZON_PROJECTS/` | No default convention — per-project decision |
| `$HORIZON_ROOT/` | None |
| `brains/<brain-name>/` | That brain's account: full. All others: none. |

`create_brain.py` (`$HORIZON_SYSTEM/scripts/`) applies all of the above for each new brain. Run it as the administrative context. See `$HORIZON_DOCS/security/audit_logging.md` for the monitor setup and `$HORIZON_SYSTEM/sbin/bootstrap.ps1` for first-machine setup.

---

## 3. The bin/sbin Boundary

`$HORIZON_SYSTEM` mirrors the Unix `/usr` layout. `bin/` and `sbin/` are direct children.

- `$HORIZON_BIN/` (`horizon_system/bin/`) — brains group: read and execute. User-callable executables live here. Brains access skills, sound resolver, statusline, and status scripts through this path.
- `$HORIZON_SYSTEM/sbin/` — primary user only. Brains group must have no access. Privileged scripts that manage brain accounts, modify OS config, or act on behalf of the primary user.

**Windows:** `sbin` requires an explicit Deny ACE for the brains group via `icacls`. The default "no entry" posture is insufficient — inherited permissions may grant access. An explicit Deny takes precedence.

**Unix:** `sbin` must be `chmod 700` (rwx------), owned by the primary user, with no group or world bits set.

This bin/sbin pattern extends to `skills_bin`/`skills_sbin` in `$HORIZON_SYSTEM`:
- `$HORIZON_SYSTEM/skills_bin/` — brains group: read and execute (**explicit grant required** — not inherited from `$HORIZON_BIN`)
- `$HORIZON_SYSTEM/skills_sbin/` — primary user only; same filesystem permission rules as sbin

AI agents must never place privileged logic in `$HORIZON_BIN` or any `*_bin` directory. Anything requiring primary-user authority belongs in the matching `*_sbin` directory.

---

## 4. Tool Provisioning — Bring Tools to the Brain

When a brain needs a tool, the administrative context provisions it explicitly. Brains do not have default access to $HORIZON_USRBIN or any shared tool directory.

Provisioning methods (in order of preference by isolation strength):
1. Install the tool inside the brain's own folder — the brain owns it, nobody else can use it
2. Symlink or copy a specific binary from $HORIZON_USRBIN into the brain's folder
3. Grant read+execute on a specific path in $HORIZON_USRBIN using OS filesystem permissions — only as a last resort when installation in the brain folder is impractical

- API keys and secrets are stored in environment variables, OS credential stores, or brain-local config — never in committed files.
- The administrative context audits what each brain has access to before provisioning. Each tool grant should have a documented reason tied to the brain's expert function.
- A brain must never self-provision new tools or escalate its own permissions. Any such capability must be wired through sbin scripts controlled by the administrative context.
- $HORIZON_USRBIN is a tool repository for the administrative context to draw from — not a shared mount that brains can browse.

---

## 5. Principle of Least Privilege

Every component of Horizon AIOS — scripts, brain users, AI harnesses, hooks — operates with the minimum permissions necessary to do its job.

- **Brain default posture: zero.** A brain account has full access to its own folder and no access to anything else unless explicitly provisioned. This is the starting point, not a goal to work toward.
- Hooks that play sounds need read access to $HORIZON_BIN/sounds/ only.
- Status line scripts need read access to session metadata only.
- No script in $HORIZON_BIN should require or request elevated (admin/root) privileges at runtime. If elevation is needed, it belongs in sbin and must be invoked explicitly by the administrative context.

When in doubt, grant less and expand as needed. Never grant access speculatively. Tool access should map directly to the brain's stated expert function — if you cannot explain why a brain needs a tool in one sentence, do not provision it.

### The Harness Cannot Modify Its Own Constraints

The AI harness (Claude Code, Ollama, or any other) runs as the brain OS user. Because the brain OS user has no write access to `$HORIZON_SYSTEM` and is explicitly denied `sbin/`, the harness has **no capacity to modify the AIOS-level protections that govern it** — not even its own security constraints.

This is an OS-enforced property, not an application-enforced one. It holds regardless of what the harness does or is instructed to do:

- A prompt injection attack that achieves arbitrary code execution as the brain user is still trapped inside the brain's folder with whatever tools were provisioned to it.
- The harness cannot write to `$HORIZON_SYSTEM`, cannot access `sbin/`, cannot reach the admin account's credential store, and cannot modify its own ACLs or permission grants.
- The harness cannot escalate to the administrative context through any path that AIOS controls — escalation requires OS-level credentials that the brain account does not hold.

This is stronger than application-layer deny lists (such as Claude Code's `deny` array in `settings.json`). Those are defense-in-depth reinforcement. The OS ACL is the enforcement layer — it operates independently of the application and cannot be bypassed by the application.

**Implication for threat modeling:** A fully compromised brain (Threat 1 — prompt injection succeeding completely) still cannot compromise the AIOS layer or other brains. Blast radius is bounded by what that brain's OS account can reach, which is bounded by what the administrative context provisioned to it.

---

## 6. No Sensitive Data in Committed Files

The Horizon AIOS git repository is designed for community release. This means:

- No real usernames, real paths, hostnames, or machine-specific identifiers may appear in committed files.
- No API keys, tokens, passwords, or credentials of any kind may be committed, even in comments or example values.
- Templates use placeholder strings (e.g., `HORIZON_BIN_PATH`) in place of real paths. Users substitute real values at setup time in their local, gitignored copies.
- `.gitignore` must exclude: local settings overrides, brain folders, credential files, session data, and any file that contains a real path or secret.
- The `.claude/settings.json` at $HORIZON_ROOT is committed because it contains only devroot-scoped permissions and no personal data. If it ever acquires personal data, it must be moved to a gitignored local override.
- AI agents operating in this repo must refuse to commit files containing hardcoded personal paths or credentials. If such content is detected, the agent must flag it and halt.

---

## 7. Audit Trail

Audit logging is a first-class security requirement.

**Properties the audit trail must have:**
- Stored in a location the brain cannot modify or delete — enforced by OS filesystem permissions
- Append-only from the brain's perspective (if any write access is needed at all)
- Controlled exclusively by the administrative context

**Implemented audit coverage:** `$HORIZON_SYSTEM/sbin/monitor_aios.py` watches `$HORIZON_SYSTEM` for file *write* events (creates, modifies, deletes, moves) using the `watchdog` library. It logs JSON-line events to `$HORIZON_ROOT/logs/aios_monitor/`. Run as the administrative context; brain accounts must not have write access to the log directory.

**OS-level audit extensions (not implemented by AIOS):** Tool invocations, file reads, network calls made, and events inside brain folders require OS-level audit: `auditd` with `IN_ACCESS` on Linux, or Windows Security Audit / Object Access Auditing. Enabling these is optional and documented as an extension in `$HORIZON_DOCS/security/audit_logging.md`.

See `$HORIZON_DOCS/security/audit_logging.md` for setup, service registration, Docker usage, and how to extend monitoring to additional paths.

**Log location convention:** `$HORIZON_ROOT/logs/` — owned by the administrative context, not brain accounts.
