# Agent Teams — Horizon AIOS

---

When asked to spawn a named team, look it up below (local overrides win), then spawn each role in order on its model group, chaining output. If no name matches, use **Full Team**.

---

## Loops (retry until pass)

A role may declare a **Loop** to re-run an earlier role with feedback until a pass
condition or an iteration cap. Declare it inline on the looping role:

> **Loop:** on `<condition>`, return feedback to `<role>` and re-run from `"<role name>"`
> (or from step `<N>`); repeat until `<pass condition>` or `<max>` iterations, then `<action at cap>`.

1. `<condition>` — what counts as a failure that triggers another pass (e.g. "validation fails").
2. re-run from `"<role name>"` (or step `<N>`) — the earlier role the loop feeds back into; that
   role and every role after it, up to the looping role, re-run each iteration. Prefer the named
   form so renumbering roles never breaks the target.
3. `<max>` iterations — a hard cap. Always set one: it bounds cost and prevents infinite loops.
4. `<action at cap>` — what to do if the cap is hit without passing (typically: stop and
   report the outstanding failures rather than proceeding silently).

---

## Conditional roles

A role may be marked **conditional**, inline in its model-group parenthetical:

1. `(`#group`, if needed)` — the acting model runs the role only if it judges the role
   adds value for the task at hand; otherwise it skips the role and continues.
2. `(`#group`, if asked)` — the role runs only when the user explicitly asks for it
   (e.g. "…and validate it"); it is skipped by default.

Conditions combine with loops: a conditional looping role loops only on the runs where it
actually executes.

`if needed`, `if asked`, and `ask user` (pause for the user's input/decision) are inline
**role flags**; `parallel` and `wait` (run adjacent roles concurrently, then sync) are others. The full vocabulary, with
meanings, is cataloged in `$HORIZON_ETC/agent_team_flags.md`; add your own in
`local.agent_team_flags.md` (gitignored) or via `/agent-teams`. List them any time with
`resolve_agent_teams.py --flags`.

---

## Sub-teams (boxes)

`[ … ]` bundles roles (or other boxes) into one **node** that runs as a unit; the brackets
set the order of operations. Name it for an inline, ephemeral sub-team: `Recon[ Crawler
(`#investigate`, parallel), DBReader (`#investigate`, parallel) ]`. Sub-agents are just named
roles inside a box. A box is itself a node — sequence it, flag it (`if asked`, `Loop`, …),
and **nest boxes inside boxes without limit** (depth is the user's call). No new operators:
concurrency/iteration/conditions use the role flags above. One line where it fits; the acting
model executes the nesting. (`resolve_agent_teams.py` lists flat teams; box expansion is a
planned extension.)

Write `-context-` (e.g. `-context-pass`, `-context-cap`, `-context-scope`) anywhere a value
comes from context rather than a literal — the explicit hook for run-time parameterization.

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

## Custom teams

Use `local.agent_teams.md` (gitignored). Same-name overrides this file; new names are unioned in.

---

## Scope Precedence

Same cascade and override-file rules as `horizon_aios_model_prefs.md § Scope Precedence`. No new semantics.
