# Horizon AIOS — Development Values

These values govern how development sessions on the AIOS operating-system layer
should be conducted. They apply to both human contributors and AI agents working
on this repository.

---

## 1. Agent-First Architecture

**Do as much work as possible in agents; keep the main session context minimal.**

The main session is an orchestrator. It decomposes tasks, spawns agents, and
synthesizes results. It does not read files, write code, or run commands inline
unless the work is trivial. Every file read, every tool call, every search that
happens in the main session consumes context tokens that persist for the life of
the conversation. Offload to agents aggressively.

See `agents.md` for the canonical orchestration pattern and agent team structure.

---

## 2. Token Economy

**Brevity is a first-class concern. Every byte in context costs money.**

- Context-loaded files (CLAUDE.md, invariants, @ imports) must be short and
  direct. Verbose context multiplies cost every session.
- Prefer CLI tools (`grep`, `Select-String`, `mv`) over file-content tools
  (`Read`, `Write`) for mechanical operations.
- Documentation files should communicate their point in the fewest words
  possible without sacrificing clarity.
- Do not add comments that restate what the code already says.
- Configuration files should be terse to the point of minimal. Comments in
  config files explain the non-obvious (a security warning, a known gotcha);
  they do not narrate the obvious. If a setting name already communicates its
  purpose, no comment is needed. Aim for configuration files that are read
  in seconds, not minutes.

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

- When a new feature, script, or convention is added, its documentation is part
  of the same unit of work.
- Significant additions and architectural decisions are recorded in
  `architecture_decisions.md` with a unique sequential entry number. This is
  the "serial number" for decisions — it makes reasoning traceable across time.
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

No part of the AIOS core layer should be readable only by one AI harness or
executable only on one model. Cross-harness conventions (`agents.md`, the
hook taxonomy, the log schema, the sound naming tier) are designed so that:

- A Codex agent and a Claude Code agent can read the same instruction file.
- An Ollama-backed brain and a Claude-backed brain share the same bootstrap,
  the same log structure, and the same sbin boundary.
- The choice of model is a deployment decision, not an architectural one.

Harness-specific configuration lives in `$HORIZON_BIN/harness_configs/<vendor>/`
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
- `horizon_bin/harness_configs/git/` (hooks, gitconfig)
- `horizon_bin/sbin/` (any script)
- `horizon_bin/bootstrap.ps1` / `bootstrap.sh`
- `brains/.aioscommon/` templates
- `~/.claude/settings.json` (hooks, permissions)
- Any file that references a path, credential, or user account

---

## 9. Portable Paths

**Hardcoded paths are forbidden in committed files.**

Every script, template, hook, and document that references a Horizon path must
use `$HORIZON_ROOT`, `$HORIZON_BIN`, `$HORIZON_ETC`, or `$HORIZON_DOCS`. No
exceptions. Machine-specific values live in `aios_local.conf` (gitignored) or
in environment variables set at shell startup.
