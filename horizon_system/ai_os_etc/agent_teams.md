# Agent Teams — Horizon AIOS

---

When asked to spawn a named team, look it up below (local overrides win), then spawn each role in order on its model group, chaining output. If no name matches, use **Full Team**.

---
## Loops
**Loop:** on `<cond>`, return to `"<role>"`; until `<pass>` or `<max>` iterations, then `<cap action>`.
- `<cond>` — failure trigger. `<role>` — re-entry point (prefer name over number). `<max>` — required hard cap. `<cap action>` — what to do when cap hits without passing (report failures; don't proceed silently).
## Conditional roles
- `(#group, if needed)` — skip if role adds no value for this task.
- `(#group, if asked)` — skip unless user explicitly requests it.
Conditions compose with loops; a conditional loop only iterates on runs where it executes.
## Sub-teams (boxes)
`[ … ]` = one node. `Name[ … ]` = inline ephemeral sub-team. Nest freely. No new operators — use role flags for concurrency/iteration inside boxes.
## Role flags & values
Full vocabulary in `$HORIZON_ETC/agent_team_flags.md`. Key flags: `if needed`, `if asked`, `ask user`, `parallel`, `wait`, `if fail <action>`, `/skill-name`.
Use `-context:<name>-` anywhere a value comes from context rather than a literal (e.g. `-context:pass criteria-`, `-context:cap-`).

---

## Teams

### Investigate & Fix
Diagnose a problem then apply the fix.
1. Investigate (`#midcost`) — diagnoses root cause across the relevant files/logs; hands
   a precise diagnosis and proposed change to the Fix role.
2. Fix (`#lowcost`) — applies the change described by Investigate and verifies it resolves
   the issue.

### Full Team
Full lifecycle for a sizable or ambiguous task. This is the default that the generic
phrase "send an agent team" resolves to.
1. Orchestrator (`#highcap`) — breaks the task down and coordinates the rest.
2. Log-reader (`#lowcost`, if needed) — gathers runtime evidence before planning.
3. Planner (`#highcap`) — designs the approach.
4. Implementer (`#lowcost`) — writes the code.
5. Validator (`#midcost`, if asked) — verifies the Implementer's work and checks for regressions.
   **Loop:** on failure, return specific feedback to the Implementer and re-run from "Implementer";
   repeat until the Validator passes clean or 3 iterations, then stop and report any
   outstanding failures.

### Review & Fix
Audit a diff then apply findings.
1. Reviewer (`#highcap`) — audits the diff for correctness, security, and regressions;
   hands a findings list to the Fixer.
2. Fixer (`#lowcost`) — applies the reviewer's findings and confirms each is resolved.

### Explore & Summarize
Fan out across a codebase or question then distill.
1. Explorer (`#investigate`) — fans out across files/sources to gather evidence.
2. Summarizer (`#lowcost`) — distills the findings into a tight, actionable report.

---
