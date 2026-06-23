---
name: agent-teams
description: Create or edit agent-team definitions in local.agent_teams.md at any scope (OS, project, brain, or subfolder) — define the agent chain, each role's model-group preference, and loop/retry constructs. Use when the user types /agent-teams, asks to "add an agent team", "define an agent team", "edit agent teams", or "create a team for this project/scope".
tools: Read, Write, Edit, Glob, Grep, Bash
---

# Skill: /agent-teams

**Model preference:** `#midcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Tooling to define and override **Agent Teams** without hand-editing markdown blind. Agent Teams are named, reusable multi-agent workflows (ordered roles, each on a model group, optionally with loops) that the user invokes in-session ("send an investigate-and-fix agent team to look at problems 2, 3, and 4").

Shipped OS defaults live in `$HORIZON_ROOT/agent_teams.md` (tracked — do NOT edit it here). User definitions and overrides live in `local.agent_teams.md` (machine-local, gitignored, never clobbered by sync), `@`-imported by that scope's `agents.md`. This skill always writes to a `local.agent_teams.md`, never to the shipped file. Authoritative spec: `agent_teams.md` and `file_structure_invariants.md` §13.

---

## When to invoke

The user types `/agent-teams ...`, or asks to add/define/edit an agent team, or to set up team definitions for a specific project/brain/subfolder scope.

**Dispatch.** A bare `/agent-teams` with NO arguments → run **Default (list loaded teams)** below, then stop — do not start creating or editing anything unless the user asks. Any request to add/define/edit/override/scope a team → go to Step 1 and the flow that follows.

---

## Default (bare `/agent-teams`, no arguments) — list loaded team sources

D.1 Run the resolver utility — it does the discovery; do NOT hand-glob or rely on
memory of what is "in context":

    python $HORIZON_BIN/resolve_agent_teams.py <cwd>          # human-readable
    python $HORIZON_BIN/resolve_agent_teams.py <cwd> --json   # structured

It walks the scope cascade from the path up to the OS root, reads the shipped
`$HORIZON_ROOT/agent_teams.md` plus every `local.agent_teams.md` override (excluding
any file merely named `agent_teams.md`, e.g. the doc under `documentation/`), and
reports each source with its team names — and, in `--json`, each team's roles, model
groups, and loop flag — plus the resolved set (most-specific scope wins; same-name
overrides shipped, new names unioned in).

D.2 Present its output to the user: the sources (path → team names, stubs noted as
"no custom teams") and the resolved teams in effect. Keep it tight.

D.3 Then ask whether they want to **add a custom team**, **modify/override** an
existing one, or **set up a project/brain scope** — and stop. Proceed to Step 1 and
the flow below only if they ask you to.

---

## Step 1 — Resolve the scope (which `local.agent_teams.md`)

1.1 Default scope is the OS root: `$HORIZON_ROOT/local.agent_teams.md`.

1.2 If the user names a different scope (a project, a brain folder, "here"/cwd, or a subfolder), target that directory's `local.agent_teams.md` instead. Teams cascade OS → project → brain → subfolder, most-specific wins (same semantics as model-prefs Scope Precedence).

1.3 Confirm the resolved absolute path with the user before writing.

---

## Step 2 — Ensure the override seam exists at that scope

2.1 The scope's directory must have an `agents.md` that `@`-imports its sibling `./local.agent_teams.md` (per §13 / §12 override-file anchoring). Check for it.

2.2 If the directory already ships the seam (OS root, `.claude/`, a brain `.claude/`), nothing to wire — proceed.

2.3 If creating a NEW scope (e.g. a project subfolder) that has no `agents.md`:
1. Create `agents.md` in that directory with the override line `@./local.agent_teams.md` (and, to inherit OS defaults, `@<relative-path>/agents.md` up to the nearest parent `agents.md`). Keep it a real `agents.md`, not a `CLAUDE.md` (§12: overrides anchor on `agents.md`).
2. If the directory also needs a `CLAUDE.md`, make it a thin pointer importing ONLY `./agents.md` (§12.3).

2.4 If `local.agent_teams.md` does not yet exist at the scope, materialize it: copy the nearest `local.agent_teams.md.template` if present, else create a short stub header. It is gitignored — never commit it.

---

## Step 3 — Define or edit the team

3.1 Gather, with the user:
1. **Team name** — the phrase they'll invoke ("Investigate & Fix").
2. **Roles, in order** — for each: a label, a **model group** (`#midcost`, `#lowcost`, `#highcap`, `#investigate`, … from model-prefs), an optional **condition** (`if needed` = model skips it unless it adds value; `if asked` = runs only when the user asks — see `agent_teams.md` → "Conditional roles"), and a 1–2 line charter (what it does + what it hands to the next role).
3. **Loops (optional)** — see Step 4.

3.2 Verify each referenced model group exists in `horizon_aios_model_prefs.md` (or its extend file). If a group is missing, tell the user and offer to add it via `/model-prefs`.

3.3 Write the team into the scope's `local.agent_teams.md`, matching the format in `agent_teams.md` (a `### <Team Name>` heading then a numbered role list). A same-named team overrides the shipped one; a new name is unioned in. Keep entries tight — the file loads into context every session.

3.4 To EDIT an existing team, read the scope's `local.agent_teams.md` (and the shipped `agent_teams.md` for reference), then modify the matching block in the local file only.

---

## Step 4 — Loops (retry until pass)

4.1 A role may loop back to an earlier role with feedback until a pass condition or an iteration cap. Express it inline on the looping role, per `agent_teams.md` → "Loops":

> **Loop:** on `<condition>`, return feedback to `<role>` and re-run from step `<N>`; repeat until `<pass condition>` or `<max>` iterations, then `<action at cap>`.

4.2 Always set an iteration cap (bounds cost, prevents infinite loops) and a cap action (typically: stop and report outstanding failures). Example (Full Team): "Validator → on fail, feedback to Implementer, re-run from step 4; repeat until clean or 3 iterations, then report."

---

## Notes for the executing agent

1. Never edit the shipped `$HORIZON_ROOT/agent_teams.md` from this skill — it holds OS defaults overwritable by sync. All user changes go in a `local.agent_teams.md`.
2. `local.agent_teams.md` files are gitignored and machine-local — do not commit them or echo their full contents back; confirm the change in one or two lines.
3. Keep team definitions short and durable. They load every session at their scope; bloat costs tokens each time.
4. Model groups must resolve in model-prefs. Do not invent group names — reuse the shipped set or have the user define one via `/model-prefs`.
5. Honor the §12/§13 invariants: overrides anchor on `agents.md`, never `CLAUDE.md`; `CLAUDE.md` stays a thin pointer to its sibling `agents.md`.
