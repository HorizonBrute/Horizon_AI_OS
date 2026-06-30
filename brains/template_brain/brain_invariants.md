# template_brain Brain Invariants

Hard rules for every agent operating in this brain. These files load into every
context — keep them terse. Add brain-specific invariants below the defaults.

1. **Security invariants**: Never violate @'$HORIZON_ETC/security_invariants.md'.
2. **Stay in scope**: Operate only within this brain's working directories and the
   knowledge locations granted in `brain_core.md`. Do not seek access or data outside them.
3. **Context hygiene**: Files that load into every context (`agents.md`, `brain_core.md`,
   `local.agent_teams.md`) must stay terse. Do not add primitives or flags without a clear
   primitives-first justification.

<!-- TODO: Add brain-specific invariants (e.g. versioning discipline, branch protection,
     branding rules, hashing/integrity requirements). Delete this comment when done. -->
