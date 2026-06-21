# Horizon AIOS — Development Values

---

## 1. Agent-First Architecture

**Do as much work as possible in agents; keep the main session context minimal.**

The main session is an orchestrator. It decomposes tasks, spawns agents, and
synthesizes results. It does not read files, write code, or run commands inline
unless the work is trivial. Every file read, every tool call, every search that
happens in the main session consumes context tokens that persist for the life of
the conversation. Offload to agents aggressively.

---

## 2. Token Economy

**Brevity is a first-class concern. Every byte in context costs money.**

- Context-loaded files (CLAUDE.md, invariants, @ imports) must be short and direct.
- Prefer CLI tools (`grep`, `Select-String`, `mv`) over file-content tools
  (`Read`, `Write`) for mechanical operations.
- Documentation files should communicate their point in the fewest words
  possible without sacrificing clarity.
- Do not add comments that restate what the code already says.
- Config file comments explain non-obvious constraints only. If the setting name communicates its purpose, no comment is needed.

---

## 3. Security by Default

**Security is not an afterthought. Every configuration change is a security change.**

- All edits to configuration files, hooks, gitignore, permissions, and scripts
  must be evaluated through a security lens before committing.
- Flag misalignment with `security_invariants.md` immediately and loudly. Do not
  silently work around a security constraint.
- Prefer explicit Deny ACLs over relying on absence of permissions (especially
  for sbin on Windows, per security_invariants.md §3).
- No real paths, usernames, credentials, or machine-specific identifiers in any
  committed file. Templates use placeholders.
- The gitignore defaults to conservative. When in doubt, ignore the file type.

---

## 4. Documentation Parity

**Documentation is a deliverable, not an afterthought. Update it in the same
commit as the feature it describes.**

- **Terseness invariant:** All context-loaded documentation (invariants, agents.md, CLAUDE.md, @ imports) must be as short as the content allows. Every sentence that can be removed without losing a rule or invariant must be removed. Verbosity compounds cost every session.
- Significant additions and architectural decisions are recorded in
  `architecture_decisions.md`. Each entry is identified by its ISO date and
  a short title (`YYYY-MM-DD — Title`). The date + title combination is the
  identifier — it makes reasoning traceable across time.
- File structure changes require updating `file_structure_invariants.md`
  simultaneously.
- Setup changes require updating `ReadMeToSetupYourSystem.md` simultaneously.

---

## 5. Extensibility and Community Ownership

**Design for the contributor you have not met yet.**

- Prefer conventions that a first-time contributor can follow without reading
  internal history. Document the "why" not just the "what."
- Vendor-specific customization lives in `$HORIZON_BIN/harness_configs/<vendor>/`
  and never pollutes the cross-harness layer.
- New features should be additive. Avoid changes that break existing brain
  configurations or require coordinated migration.
- The AGPL v3 license is intentional: improvements to the OS layer flow back
  to the community.

---

## 6. Standardization Enables Coordination

**A standard AIOS layout is the precondition for multi-agent and multi-system work.**

The long-term vision is AIOS instances that can run as coordinated expert systems
— dedicated brains for different domains (red team, dev, research) operating on
the same machine, or distributed across machines and Docker environments, able to
collaborate through shared conventions.

This only works if every AIOS installation is predictably laid out:
- Same environment variable names.
- Same directory structure.
- Same agent instruction conventions (`agents.md`, CLAUDE.md).
- Same hook events and log taxonomy.

Deviations from standard layout should be made in `aios_overrides.md` at the
project level, not by restructuring `$HORIZON_BIN`. The standard layer must
remain stable for coordination to be possible.

**Harness independence is a design constraint, not a feature.**

No part of the AIOS core layer may be readable only by one harness or executable only on one model. Cross-harness conventions (`agents.md`, hook taxonomy, log schema, sound naming) are harness-agnostic; the choice of model is a deployment decision. Harness-specific configuration lives in `$HORIZON_BIN/harness_configs/<vendor>/`
and extends, but never replaces, the cross-harness core. Any feature that
requires a specific harness to function belongs in that vendor's config
directory, not in `agents.md` or the invariants.

---

## 7. Minimization

**The simplest implementation that correctly solves the problem is the right one.**

- Do not add abstractions for hypothetical future requirements.
- Do not add error handling for scenarios that cannot occur.
- Do not add options, flags, or modes that no current use case requires.
- Three similar lines of code is better than a premature abstraction.
- Fewer dependencies, shorter files, smaller footprint.

---

## 8. Security Alignment Review

When any of the following are changed, cross-check against `security_invariants.md`
before committing. Flag discrepancies; do not suppress them:

- `.gitignore` or `.gitignore.user.template`
- `horizon_system/harness_configs/git/` (hooks, gitconfig)
- `horizon_system/sbin/` (any script)
- `horizon_system/sbin/bootstrap.ps1` / `bootstrap.sh`
- `brains/.aioscommon/` templates
- `~/.claude/settings.json` (hooks, permissions)
- Any file that references a path, credential, or user account

---

## 9. Portable Paths

**Hardcoded paths are forbidden in committed files.**

Every script, template, hook, and document that references a Horizon path must
use one of the canonical environment variables. No exceptions. Machine-specific
values live in `aios_local.conf` (gitignored) or in environment variables set
at shell startup.

Canonical variables: `$HORIZON_ROOT`, `$HORIZON_SYSTEM`, `$HORIZON_BIN`,
`$HORIZON_ETC`, `$HORIZON_DOCS`, `$HORIZON_USRBIN`, `$HORIZON_PROJECTS`, `$HORIZON_KEYS`.

---

## 10. Brain Sandbox Integrity

**Brains are expert systems. Scope their tools, credentials, and data access to their function.**

AIOS security is built around two co-equal threat models:

**Prompt injection** — malicious instructions in data cause a brain to take unintended actions. Mitigations: narrow tool provisioning (brain cannot act outside its capabilities), audit trail (anomalies surface).

**Credential and data containment** — a hallucinating or compromised brain can only cause harm proportional to what credentials and data it holds. A brain with no key for a service cannot authenticate to it. Mitigations: per-brain credential provisioning via `$HORIZON_KEYS`, zero-default filesystem access, least-privilege key scoping.

These are defense-in-depth: both must hold for the model to be secure. When relaxing one (e.g., granting broader tool access), the other must compensate (e.g., tighter credential scoping, more aggressive audit).

Operational rules:
- Default brain access posture: zero — own folder only.
- Tools are brought to the brain. Credentials are provisioned to the brain. Neither is discovered by browsing shared directories.
- Every tool and every credential provisioned to a brain must be explainable in one sentence tied to that brain's expert function.
- Brains must not self-provision tools or escalate permissions. Any such action is a security event.
- The audit log is stored where the brain cannot modify it.
