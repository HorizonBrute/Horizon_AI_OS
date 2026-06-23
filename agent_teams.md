# Agent Teams — Horizon AIOS

Named, reusable multi-agent workflows. This file is loaded as context via `agents.md`;
the acting model reads it and honors it by direct instruction — no enforcement engine,
same channel as any instruction. Model groups (`#midcost`, `#lowcost`, `#highcap`,
`#investigate`, …) are defined in `horizon_aios_model_prefs.md`.

---

## How the acting model resolves a team

When the user says "send/spawn the '<name>' agent team" (or similar), the acting model
looks up that team here (local overrides win — see `local.agent_teams.md`), then spawns
each role in listed order, each on its specified model group (resolved via model-prefs),
chaining each role's output into the next role's input. If a role is marked "(if needed)"
the model may skip it. The model picks the team whose name best matches; if none match,
it falls back to **Full Team**.

---

## Loops (retry until pass)

A role may declare a **Loop** to re-run an earlier role with feedback until a pass
condition or an iteration cap. Declare it inline on the looping role:

> **Loop:** on `<condition>`, return feedback to `<role>` and re-run from step `<N>`;
> repeat until `<pass condition>` or `<max>` iterations, then `<action at cap>`.

1. `<condition>` — what counts as a failure that triggers another pass (e.g. "validation fails").
2. re-run from step `<N>` — the earlier role the loop feeds back into; that role and every
   role after it, up to the looping role, re-run each iteration.
3. `<max>` iterations — a hard cap. Always set one: it bounds cost and prevents infinite loops.
4. `<action at cap>` — what to do if the cap is hit without passing (typically: stop and
   report the outstanding failures rather than proceeding silently).

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
5. Validator (`#midcost`) — verifies the Implementer's work and checks for regressions.
   **Loop:** on failure, return specific feedback to the Implementer and re-run from step 4;
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

## Define your own

Add custom teams in `local.agent_teams.md` (machine-local, gitignored, scope-cascading).
A same-named team in the local file overrides the shipped definition here; team names not
present here are unioned in. Agent Teams are a prime area for community-contributed
workflows — share yours upstream.

---

## Scope Precedence

Teams cascade OS(root) → project-root → brain-root → subfolder; most-specific wins.
Semantics are identical to `horizon_aios_model_prefs.md` "Scope Precedence" — no new
rules. On a same-named team, the more-specific scope's definition wins; otherwise team
sets are unioned.

**Override-file convention — anchored on `agents.md`, never `CLAUDE.md`.** A scope that
wants an override drops a `local.agent_teams.md` in its own directory, and that scope's
`agents.md` @-imports it. Mirror of the model-prefs override-file convention.
