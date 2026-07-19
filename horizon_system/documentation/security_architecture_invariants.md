# Security Invariants — Horizon AIOS

Hard constraints for all users, harnesses, and brain configurations.

> **Deployment prerequisite:** These invariants describe the security properties that Horizon AIOS establishes when correctly deployed. They are enforced by `bootstrap.ps1`/`bootstrap.sh` (which runs as Administrator/root) and `horizon_aios_harden.py`. On a machine where bootstrap has not been run, these properties do not yet hold.

---

## 0. Usage Model

Horizon AIOS operates under a three-tier principal model.

**Tier 1 — Administrative context:** The primary OS user account (or a dedicated admin account set up by the primary user) owns and manages $HORIZON_ROOT. This context installs and configures brains, provisions tools, sets filesystem permissions, and runs privileged scripts. All AIOS maintenance work happens at this tier.

**Tier 2 — Brain accounts:** Separate OS user accounts that run agentic workflows. Each brain is an expert system scoped to a specific task or set of tasks. Brain accounts start with zero access outside their own folder. Access to any additional resource is provisioned explicitly by the administrative context.

**Tier 3 — Docker (optional, per brain):** A brain may run its own Docker containers for isolated services. Docker adds network and process isolation on top of the OS account boundary, not instead of it.

### Why Dedicated Brain Accounts Exist

Running agentic workflows under a primary OS user account — the common default for most AI tooling — means the agent inherits everything that account can touch: the full filesystem, stored credentials, network resources, and any application the user can run. A misbehaving or compromised agent is operationally equivalent to a compromised user session. There is no containment boundary; blast radius equals the user's access.

Horizon AIOS addresses this by requiring that agentic workflows run as dedicated brain OS accounts with zero-default access. The brain's ACL boundary is enforced by the OS, not by harness instructions or agent promises — it cannot be overridden by anything the harness says or any prompt injection succeeds in getting the agent to attempt. The primary user retains full administrative control; the brain has only what it was explicitly given.

---

### Primary Threat Models

Two co-equal threat models drive every security decision:

**Threat 1 — Prompt Injection**
Malicious instructions embedded in data cause a brain to take unintended actions. Example: a document being summarized instructs the brain to exfiltrate its session context.

Mitigations: narrow tool access + audit trail (anomalous actions are detectable).

**Threat 2 — Credential and Data Containment**
A hallucinating, misconfigured, or compromised brain can only cause harm proportional to the credentials and data it holds. A brain with no API key cannot authenticate; a brain with no filesystem access outside its folder cannot read other brains' data.

Mitigations: OS-native credential storage (managed by `horizon_aios_brain_credential.py` in sbin) + zero-default access posture + least privilege on both tools and credentials.

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

**Single-user vs. multi-user access to brains and projects.** In a single-user installation, the installing user owns `$HORIZON_ROOT` and all its contents — they have full access to `$HORIZON_PROJECTS/` by default because they own the machine, and Read-Only access to `brains/` (below). This does not extend to multi-user, team, or enterprise deployments. In those environments, additional flesh-and-blood operators are real OS accounts that do not own the AIOS root; they are granted access by membership in the AIOS-managed **`horizon_humans`** group (below) or, for finer control, by direct OS ACL grants (`icacls` / `setfacl`) or organization-managed identity groups.

**`horizon_humans` — the AIOS-managed human-operator group (secure by onboarding).** Human operators *are* AIOS-managed objects. Onboarding (`bootstrap`) always creates the `horizon_humans` group and applies its ACLs via `horizon_aios_harden.py` — there is no separate "hardening step"; the security boundary is a property of onboarding. Members of `horizon_humans` receive **Full control of user space** (the AIOS tree *outside* `horizon_system/`) but are held **Read-Only on the install itself** — `$HORIZON_SYSTEM/` and the root-level canon files — and **Read-Only on `brains/`** (brain locations are for brains — to write into one a human elevates to admin or changes permissions). The install-wide config, canon, and tooling are admin-authored; humans extend the system via scope-local overrides that live outside `horizon_system/` (see §2). The group is created on *every* install, even with zero members: an empty group granted Full grants nobody, so a bare server reduces to "only owner + SYSTEM + Administrators write" with no separate code path. Onboarding asks whether the machine is a **server** (enroll no humans) or an **active-use workstation** (enroll the human operator accounts, by name or SID — cloud/AzureAD identities surface as SIDs). Enrollment is operator-supplied; after onboarding, the Administrator manages membership (`bootstrap --add-human <name|sid>`). The enrolled set is recorded in the gitignored `$HORIZON_ROOT/.horizon_aios_deployment.json`.

Establishing this group requires onboarding to break inheritance at `$HORIZON_ROOT` and re-grant only the known-good principals (owner + SYSTEM + Administrators + `horizon_humans`), which is what removes broad inherited write grants from the volume root (e.g. `Authenticated Users:Modify`, sandbox groups, stray cloud SIDs) that would otherwise reach the tree. Finer-grained, org-specific grants beyond `horizon_humans` remain a deployment decision implemented with whatever OS/identity tooling the organization operates.

---

## 2. Brain Isolation

Each "brain" is an isolated AI persona running as a separate OS user account, scoped to its own directory subtree.

- A brain's home directory is its scope boundary. It may not read or write outside that boundary by default.
- Brains do not share data with each other. There is no cross-brain readable path unless the primary user explicitly creates one.
- If a brain is compromised or misbehaves, the blast radius is limited to its own folder. The primary user's data and other brains are unaffected.

**Brains group:** All brain user accounts are members of a single OS-level group, conventionally named `brains`. Administrative convenience only — lets the admin grant or deny a path for all brains without enumerating accounts. Does not imply shared access. OS construct, not an AIOS construct.

**Default brains group filesystem permissions** — enforced on the AIOS layer by `$HORIZON_SYSTEM/sbin/horizon_aios_harden.py` (run from bootstrap, independent of any brain) and re-applied per brain by `horizon_aios_create_brain.py`:

| Path | Brains Group |
|---|---|
| `$HORIZON_BIN/` | Read + Execute |
| `$HORIZON_SYSTEM/sbin/` | **DENY** (explicit) |
| `$HORIZON_SYSTEM/skills_bin/` | Read + Execute (explicit grant — not inherited from `$HORIZON_BIN`) |
| `$HORIZON_SYSTEM/skills_sbin/` | **DENY** (explicit) |
| `$HORIZON_USRBIN/` | None (tools provisioned selectively per brain) |
| `$HORIZON_SYSTEM/logs/` | **DENY** (explicit — audit log must not be writable by brains) |
| `$HORIZON_PROJECTS/` | No default convention — per-project decision |
| `$HORIZON_ROOT/` | None |
| `$HORIZON_SYSTEM/` (everything else: `ai_os_etc`, `templates`, `harness_configs`, `documentation`, …) | No write anywhere (read permitted) |
| `brains/<brain-name>/` | That brain's account: full. All others: none (see `horizon_humans` row for human read access). |
| OS system directories (`/etc/`, `/etc/passwd`, `/etc/shadow`, `C:\Windows\System32\`, Windows Registry, etc.) | No access — enforced by the OS, not by AIOS. Brain accounts are standard non-privileged OS user accounts. They have no special access to OS system paths; those paths are protected by the OS's own permission model exactly as they are for any other non-elevated account. AIOS does not need to explicitly deny these paths. |

**This table covers brain account permissions only.** It does not describe what flesh-and-blood operator accounts can access. Human operators are not in the `brains` group and are not subject to the *brains* Deny ACEs above — they are owners, Administrators, or members of the AIOS-managed `horizon_humans` group. The one deliberate Deny that *does* apply to `horizon_humans` is the brains carve-out below.

**`horizon_humans` group (flesh-and-blood human operators) — AIOS-managed, applied by `horizon_aios_harden.py` on every install:**

| Path | horizon_humans Group |
|---|---|
| `$HORIZON_ROOT/` — user space *outside* `horizon_system/` (`$HORIZON_PROJECTS/`, `objectives/`, `handoffs/`, scope-local `local.*` overrides, …) | **Full control** |
| `$HORIZON_SYSTEM/` (the install itself: `bin`, `skills_bin`, `sounds`, `ai_os_etc`, `documentation`, templates, …) | **Read-Only** (read + execute, **no write**) |
| Root-level canon: `agents.md`, `CLAUDE.md`, `.claude/agents.md`, `.claude/CLAUDE.md` | **Read-Only** (`r--` ACL **plus the sticky bit on the parent dir**, so the file cannot be unlink+recreated around the ACL) |
| `$HORIZON_ROOT/sbin`, `skills_sbin`, `logs` (under `horizon_system/`) | **No access** (owner-only `0o700` / full Deny — privileged tooling + audit log) |
| `$HORIZON_ROOT/brains/` and `brains/<name>/` | **Read-Only** (explicit Deny-Write; to write, elevate to admin or change permissions) |

**Why humans are Read-Only on the install, not co-admins.** `horizon_humans` are trusted local operators, but the install itself is admin-authored: install-wide config/canon (`ai_os_etc`, the root canon files) and install-wide code (`bin`/`skills_bin`) are governed by the owner. Humans extend the system through **scope-local** overrides and project-specific skills that live *outside* `horizon_system/` (repo root, `.claude/`, project dirs), where they retain Full control. Keeping `bin`/`skills_bin` read-only for humans deliberately closes a privilege-escalation path — a human-writable executable dir whose tools are later run by root or a brain. Adding an install-wide tool/skill is therefore an admin action.

An **empty** `horizon_humans` grants nobody, so on a server profile the model reduces to owner + SYSTEM + Administrators writing. In a single-user install the owner is also an `Administrators` member (and on Unix, root bypasses ACLs), so they can always write anywhere by elevating; day-to-day the owner reads `brains/` and has full access to `$HORIZON_PROJECTS/`. See §1 (User Ownership Model) for the group's lifecycle (onboarding creates it; profile gates enrollment; Administrator manages membership afterward).

**Provisioning model.** AIOS hardening is an administrative/root action — hence bootstrap and `horizon_aios_harden.py` require elevation. The model is expressed entirely through two kinds of principal: the **owner + SYSTEM + Administrators**, who must always retain Full control (they are never stripped, and are re-granted by SID so this is locale-independent on Windows), and the **`brains` group**, which is restricted as above. *Human* operators are never granted access by AIOS — they are owners or members of Administrators, whatever the OS/infra already made them. On a single-user home workstation the operator is simultaneously owner and Administrator, so the model applies unchanged.

**Controlled root ACL (secure-by-onboarding baseline).** `horizon_aios_harden.py` always establishes a controlled ACL at `$HORIZON_ROOT`: it breaks inheritance (`/inheritance:r`) and re-grants only the known-good principals (owner + SYSTEM + Administrators, then `horizon_humans` Full on user space with an inheritable Read-Only carve-out over `horizon_system/` and the root canon). This is what removes broad inherited write grants from the volume root — `Authenticated Users:Modify`, sandbox groups, stray cloud SIDs — that additive-only hardening cannot revoke (you cannot suppress an inherited Allow without breaking inheritance, and a Deny on "Authenticated Users" would also catch the human owner/admins, who are themselves authenticated). owner + SYSTEM + Administrators are re-granted by well-known SID, so this is locale-independent and they are never collateral.

**Two modes for the `$HORIZON_SYSTEM` subtree (`horizon_aios_harden.py`).** *Additive* (default) preserves the system subtree's existing/inherited ACLs — including GPO/SCCM/Intune pushes — and enforces the brains model by *adding* ACEs only: an inheritable brains Deny-Write across `$HORIZON_SYSTEM` (an explicit/inherited Deny beats any Allow) plus full Deny on the privileged dirs. *`--strict`* additionally drops inherited ACEs (`/inheritance:r`) on the system dir and each privileged dir, re-establishing owner + SYSTEM + Administrators first — for locked-down standalone installs. Neither mode ever drops SYSTEM/Administrators.

`horizon_aios_harden.py` (`$HORIZON_SYSTEM/sbin/`) applies all of the above to the AIOS layer at bootstrap, so the machine is protected before any brain exists; `horizon_aios_create_brain.py` (`$HORIZON_SYSTEM/sbin/`) re-applies the per-brain grants/denies for each new brain (additively, so it agrees with `horizon_aios_harden.py`'s default and never re-strips the shared dirs). Run both as the administrative context. See `$HORIZON_DOCS/security/audit_logging.md` for the monitor setup and `$HORIZON_SYSTEM/sbin/bootstrap.ps1` for first-machine setup.

**Brain automation logon rights (opt-in).** To run a brain unattended (scheduled task / service), the account needs an OS logon right. These are **opt-in per brain** (default tier `none`), **least-privilege** (exactly one LSA right per tier — `SeBatchLogonRight` for `scheduled`, `SeServiceLogonRight` for `daemon`), granted **additively** (a single right via `horizon_aios_brain_logon_rights.py`, touching nothing else in local security policy), and **revoked on teardown** by `horizon_aios_remove_brain.py` before account deletion. A logon right governs *how the account may log on*, **not what it can read or write** — the Deny on `sbin`/`skills_sbin`/`logs` and the read-only `bin`/`skills_bin` grants above are untouched. See `$HORIZON_DOCS/deployment/brain_automation.md`.

**`AIOS_SKIP_HARDEN=1` — Docker-only escape hatch.** The environment variable `AIOS_SKIP_HARDEN=1` instructs `bootstrap.sh` to skip the `horizon_aios_harden.py` invocation. This is used exclusively in Docker builds where `horizon_aios_harden.py` is run as a separate root-context `RUN` step before the `USER aios` switch. Do not set this variable in native (non-Docker) deployments — doing so bypasses the ACL hardening that enforces brain isolation.

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
- Hooks that play sounds need read access to $HORIZON_SOUNDS/ only.
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

### When the Model Is Not Followed — The Elevated Account Risk

The security properties above are only valid when the deployment prerequisite is met: **AI harnesses must run as brain OS accounts, not as the operator's account.**

Running an AI harness under a developer's own account — particularly on a workstation where that account holds local Administrator rights — is functionally equivalent to running Linux as `root`: the harness inherits everything the account can touch, including OS system directories, credential stores, other users' files, and installed software. There is no OS-level containment boundary, because the account is the containment boundary, and it has not been applied.

**UAC is not a containment boundary.** Windows User Account Control governs interactive elevation prompts. It does not prevent a process running under an admin-group account from accessing most of the filesystem. It can be bypassed by misconfigured auto-elevation settings, COM object abuse, or developer-applied elevation grants. A harness with broad tool permissions may operate with effectively unrestricted access regardless of UAC.

**No AIOS configuration compensates for a missing OS account boundary.** The `settings.json` deny array, `agents.md` instructions, and harness-level permission lists are defense-in-depth — they reinforce the OS account boundary, they do not replace it. If the harness runs as an administrator or as the owner account, these controls are advisory. The OS enforces nothing against the account that owns the AIOS layer.

**An improperly installed AIOS short-circuits the security model it was designed to provide.** The user retains all the configuration overhead with none of the structural security properties. This risk is not a flaw in the model — it is the consequence of not applying the model's foundational prerequisite.

The correct deployment is: a separate administrative account manages AIOS; brain OS accounts run harnesses. See `$HORIZON_DOCS/philosophy.md §3` (Improper Installation Risk) for the full treatment.

---

## 6. No Sensitive Data in Committed Files

The Horizon AIOS git repository is designed for community release. This means:

- No real usernames, real paths, hostnames, or machine-specific identifiers may appear in committed files.
- No API keys, tokens, passwords, or credentials of any kind may be committed, even in comments or example values.
- Templates use placeholder strings (e.g., `AIOS_EXEC_WRAPPER` in the Claude Code settings template) in place of real paths. Users substitute real values at setup time in their local, gitignored copies.
- `.gitignore` must exclude: local settings overrides, brain folders, credential files, session data, and any file that contains a real path or secret.
- The `.claude/settings.json` at $HORIZON_ROOT is committed because it contains only devroot-scoped permissions and no personal data. If it ever acquires personal data, it must be moved to a gitignored local override.
- AI agents operating in this repo must refuse to commit files containing hardcoded personal paths or credentials. If such content is detected, the agent must flag it and halt.
- `$HORIZON_ROOT/memory/` holds redirected per-project harness state — conversation **transcripts** (sensitive) and agent memory. It is gitignored and must never be committed or synced. Brain memory is isolated per-brain by group: each brain's `~/.claude` redirects into its own group-owned `brains/<name>/.claude/`, so no brain sees the owner's or another brain's memory (see §2). See `$HORIZON_DOCS/system/memory.md`.

---

## 7. Audit Trail

Audit logging is a first-class security requirement.

**Properties the audit trail must have:**
- Stored in a location the brain cannot modify or delete — enforced by OS filesystem permissions
- Append-only from the brain's perspective (if any write access is needed at all)
- Controlled exclusively by the administrative context

**Implemented audit coverage:** `$HORIZON_SYSTEM/sbin/horizon_aios_monitor.py` watches the AIOS **system directories** for file *write* events (creates, modifies, deletes, moves) using the `watchdog` library: `$HORIZON_SYSTEM`, `$HORIZON_USRBIN`, `$HORIZON_ROOT/.claude`, the top-level OS files at `$HORIZON_ROOT`, and the `brains/` root (non-recursive — structural changes to the brain folders themselves). The `brains/` root is treated as a system folder; AIOS makes no presumption about brain *internals* (out of scope by default — opt in with `--brain-dirs`). It logs JSON-line events — each stamped with `source: Horizon.AIOS` and the originating `horizon_root` — to `$HORIZON_SYSTEM/logs/horizon_aios_monitor/`. Run as the administrative context; brain accounts must not have write access to the log directory (enforced by `horizon_aios_harden.py`, which sets an explicit Deny on `$HORIZON_SYSTEM/logs/`).

**OS-level audit extensions (not implemented by AIOS):** Tool invocations, file reads, network calls, and events inside brain folders require OS-level audit integration. AIOS provides the boundary and log location; the integration is the operator's responsibility. Platform guidance: Linux `auditd` (`IN_ACCESS`/`IN_EXEC`), macOS BSM/OpenBSM (`audit(8)`), Windows Security Audit Object Access, Docker logging drivers. See `$HORIZON_DOCS/philosophy.md §3` for per-platform recommendations and `$HORIZON_DOCS/security/audit_logging.md` for setup details.

See `$HORIZON_DOCS/security/audit_logging.md` for setup, service registration, Docker usage, how to extend monitoring to additional paths (CLI / env / `aios_monitor.conf`), and how administrators consume the logs (JSON-lines on disk; SIEM/forwarder integration).

**Log location convention:** `$HORIZON_SYSTEM/logs/` (canonical) — owned by the administrative context, not brain accounts. Explicit brains-group Deny set by `horizon_aios_harden.py`.

---

## 8. Branding & Identification

Attribution is a security property. Every artifact Horizon AIOS creates that a blue team, IT administrator, or auditor could encounter **must self-identify as Horizon AIOS without external context** — a running process, an OS account or group, a scheduled task/service, a log file, a log record, or an OS event-log/syslog entry. An investigator must be able to tell what an object is and what created it from the object alone.

**Standard brand tokens:**
- Human-readable text (OS-object descriptions, log fields, event sources): **`Horizon.AIOS`**.
- Filenames and machine identifiers: **`horizon_aios_`** prefix — lowercase, underscores.

**Required — these MUST self-identify:**
- **Audit/log records** — every record carries `source: Horizon.AIOS` and the originating `horizon_root` (see §7).
- **Log files / directories** — `horizon_aios_` prefix (`horizon_aios_security.log`, `horizon_aios_sync.log`, `horizon_aios_monitor/`).
- **OS principals** — brain/group `Description` / Linux `--comment` / Windows `FullName` / macOS `RealName` begin with `Horizon.AIOS` (e.g. `Horizon.AIOS brain account`, `Horizon.AIOS group: <name>`, and the human-operator group `horizon_humans` described `Horizon.AIOS Actual Humans`). Set by `horizon_aios_create_brain.py` and `horizon_aios_harden.py`.
- **OS log channels** — Windows Event source `Horizon.AIOS Monitor`; syslog logger under `horizon_aios.*`.
- **Privileged utility scripts** — `$HORIZON_SYSTEM/sbin/horizon_aios_*.{py,ps1}`, so process listings (`ps`, Task Manager, scheduled-task `/TR` targets) self-identify.

**Deliberately exempt — stable functional identifiers.** These are interface/compatibility contracts; renaming them breaks existing deployments, so they keep their established (already `AIOS`/`HorizonAIOS`-recognizable) names rather than the `horizon_aios_` form:
- Public entry points: `bootstrap.{ps1,sh}`, `uninstall.{ps1,sh}`, and the `aios` command wrapper.
- The `brains` OS group; the scheduled-task names `HorizonAIOS_Sync` / `HorizonAIOS_MaintainLogs` and their cron markers.
- Config filenames (`aios_*.conf`) and `AIOS_*` environment variables.

**On change:** any new admin-visible artifact (log, OS object, scheduled task/service, privileged script, event channel) adopts this invariant at creation — the `Horizon.AIOS` / `horizon_aios_` form is not optional for them. Renaming an exempt functional identifier is a breaking change requiring an ADR. The filename side of this convention is restated in `file_structure_invariants.md §6`.
