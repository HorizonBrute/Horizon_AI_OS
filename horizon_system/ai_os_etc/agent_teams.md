# Agent Teams

When asked to spawn a named team, look it up below (local overrides win), spawn each role in
order on its model group chaining output; if no name matches, use **Full Team**. SAILL grammar
— flags, boxes `[ ]`, loops, `if fail`, `/skill` calls, `-context:<name>-` — is cataloged in
`$HORIZON_ETC/agent_team_flags.md`; full spec + complex examples in
`$HORIZON_DOCS/system/agent_teams.md`. Add/override teams in `local.agent_teams.md` (cascades
OS→project→brain→subfolder; same rules as model-prefs Scope Precedence).

## Teams

### Investigate & Fix
Diagnose a problem, then fix it.
1. Investigate (`#midcost`) — find root cause; hand the diagnosis to Fix.
2. Fix (`#lowcost`) — apply the change and verify.

### Full Team
Full lifecycle for a sizable or ambiguous task (the generic "send an agent team" default).
1. Orchestrator (`#highcap`) — break down and coordinate.
2. Log-reader (`#lowcost`, if needed) — gather runtime evidence.
3. Planner (`#highcap`) — design the approach.
4. Implementer (`#lowcost`) — write the code.
5. Validator (`#midcost`, if asked) — verify the work.
   **Loop:** to "Implementer" until clean or 3.

### Review & Fix
Audit a diff, then apply findings.
1. Reviewer (`#highcap`) — audit for correctness, security, regressions; hand findings to Fixer.
2. Fixer (`#lowcost`) — apply the findings and confirm each.

### Explore & Summarize
Fan out, then distill.
1. Explorer (`#investigate`) — gather evidence across files/sources.
2. Summarizer (`#lowcost`) — distill a tight, actionable report.
