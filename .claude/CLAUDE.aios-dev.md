# AIOS Development Context — owner/maintainer only

Loaded only in the AIOS owner/maintainer session, via an import added to your
machine-local `~/.claude/CLAUDE.md` by bootstrap. **Brains never import this
file** — their `brain_CLAUDE.md.template` chains only the runtime config — so
AIOS-*development* rules stay out of every brain's runtime context.

Keep this file short: it loads every owner session (token economy still applies).
It holds proactive reminders only; the authoritative rules live in the invariants
and the consistency-check standard.

## Directives when developing the AIOS
- When you add, move, rename, or remove documentation, update
  `documentation/index.md` in the **same change**
  (`/horizon_aios_documentation_index_update`).
- Before calling AIOS work done, validate docs ↔ implementation against the
  standard: `/horizon_aios_dev_consistency_check`
  (spec: `documentation/development_tools/consistency_checks.md`).
