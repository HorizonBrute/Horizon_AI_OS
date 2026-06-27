# Multi-Brain Deployment — Horizon AIOS

One Horizon AIOS install can host any number of brains on the same OS. This is the standard configuration — AIOS is designed from the ground up for it. Each brain is an isolated OS user account; the AIOS layer is shared infrastructure that no brain can modify.

---

## Deployment model

```
$HORIZON_ROOT/
  horizon_system/          ← shared AIOS layer (owner-writable, brains: read-only)
    bin/                   ← brains: read + execute
    sbin/                  ← brains: DENY
    skills_bin/            ← brains: read + execute
    skills_sbin/           ← brains: DENY
    logs/                  ← brains: DENY
  brains/
    researcher/            ← researcher's account: full; all others: none
    coder/                 ← coder's account: full; all others: none
    analyst/               ← analyst's account: full; all others: none
  memory/                  ← owner memory; brain memory is in brains/<name>/.claude/
  handoffs/                ← owner handoffs
  objectives/              ← owner objectives
```

Each brain gets:
- An OS user account (`researcher`, `coder`, etc.)
- A workspace at `$HORIZON_ROOT/brains/<brain-name>/` with full ownership
- A `~/.claude/skills/` symlink → `skills_bin/` (brain-accessible skills only)
- A login profile that exports `HORIZON_*` env vars

---

## Common patterns

### Parallel expert systems

Run multiple specialized brains simultaneously, each focused on a distinct domain:

| Brain | Expert function | Example provisioned tools |
|---|---|---|
| `researcher` | Deep research, web fetch, literature review | Browser, search tools |
| `coder` | Implementation, code review, debugging | Language runtimes, git |
| `analyst` | Data analysis, report generation | Python data stack, spreadsheet tools |
| `writer` | Prose, documentation, communications | Minimal — write-only access |

Each brain has its own session history, memory, and credential store. The owner coordinates by sharing output files or via handoffs in each brain's folder.

### Sequential pipeline

Brains hand off work to each other through the filesystem. The owner drops an input file into the receiving brain's folder; the brain processes it and writes output. The folder boundary is also the trust boundary — a brain cannot read another brain's working directory.

### Single-purpose automation brain

A brain provisioned with a single tool (e.g. a webhook listener) and an automation logon right (`SeBatchLogonRight`) runs unattended as a scheduled task. See `$HORIZON_DOCS/deployment/brain_automation.md`.

---

## Isolation tradeoff table

| What is shared | What is isolated per brain |
|---|---|
| The AIOS layer (`horizon_system/`) | Home directory (`brains/<name>/`) |
| `skills_bin/` skills (read-only) | `skills_sbin/` is DENIED to all brains |
| `bin/` utilities (read-only) | OS credential store entry |
| AIOS documentation (read-only) | Harness memory (`brains/<name>/.claude/`) |
| Sync schedule (owner-managed) | Provisioned tools |
| Monitor + audit log (owner-reads; brains DENIED write) | Session context and handoffs |

**Brains cannot see each other.** There is no cross-brain readable path by default. If two brains need to exchange data, the administrative context creates a shared location and grants both explicitly — this is a deliberate provisioning decision, not a default.

**The AIOS layer is read-only to all brains.** `horizon_aios_harden.py` enforces a no-write Deny across `$HORIZON_SYSTEM` for the `brains` group. A brain running compromised cannot alter the AIOS configuration, skills, or scripts that govern it.

---

## Provisioning a new brain

Use the `/create-brain` skill (owner session) or invoke `horizon_aios_create_brain.py` directly:

```
python "$HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py" <brain-name>
```

This creates the OS user, workspace, `brains` group membership, login profile, and stored credential in one step. The `/harden` skill re-applies ACLs across the full AIOS layer after provisioning if needed.

See `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md` for the full provisioning protocol, and `$HORIZON_DOCS/security_architecture_invariants.md §2` for the security model.

---

## Filesystem peer coordination

When brains need to share data, the administrative context creates a shared directory outside any brain's home folder and grants both brains read (and optionally write) access:

```
$HORIZON_ROOT/shared/<project-name>/    ← not a default; provisioned explicitly
```

The grant is additive and scoped: only the specific brains involved receive access, and only to the specific path. `horizon_aios_harden.py`'s broad no-write Deny does not apply to explicitly provisioned per-path grants — explicit Allow ACEs on a subdirectory are evaluated before the inherited Deny.

**Do not use `$HORIZON_PROJECTS/` as a shared drop-folder without deliberate scoping.** The security invariants impose no default convention on `$HORIZON_PROJECTS/`; that is a feature, not a gap. Decide access per project.

---

## Removing a brain

Use the `/remove-brain` skill or `horizon_aios_remove_brain.py`. This removes the OS user, per-brain group, workspace, login profile, and stored credential. The `brains` group is left intact.

```
python "$HORIZON_SYSTEM/sbin/horizon_aios_remove_brain.py" <brain-name>
```
