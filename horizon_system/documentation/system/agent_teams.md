# Horizon AIOS — Agent Teams

Agent Teams are named, reusable multi-agent workflows you invoke in-session by
name. Instead of manually spawning and sequencing agents, you say:

> "Send the **investigate-and-fix** agent team to look at problems 2, 3, and 4."

The acting model looks up the named team, spawns its roles in order — each on
its assigned model group — and chains their outputs through to a result.

The authoritative spec lives at `$HORIZON_ROOT/agent_teams.md`; the structural
rules (override file pattern, cascade precedence, gitignore rules) are in
`$HORIZON_ETC/file_structure_invariants.md` §12.

---

## 1. Invocation

Call a team by name in any session instruction. The acting model resolves the
name against the loaded team definitions and executes the role sequence. You can
scope the work at invocation time:

> "Send the **full-team** agent team to investigate and fix the auth regression."
> "Send the **explore-and-summarize** agent team across all three failing modules."

No slash command — it is a natural-language invocation pattern, not a skill.

---

## 2. Shipped starter teams

Four teams ship with the OS layer and are defined in `$HORIZON_ROOT/agent_teams.md`.

| Team name | Roles (in order) | Model group | Charter |
|---|---|---|---|
| **investigate-and-fix** | Investigator | `#midcost` | Gathers evidence, isolates root cause |
| | Fixer | `#lowcost` | Applies the targeted fix |
| **full-team** | Orchestrator | `#highcap` | Breaks down task, coordinates the rest |
| | Log-reader *(if needed)* | `#lowcost` | Gathers runtime evidence before planning |
| | Planner | `#highcap` | Designs the approach |
| | Implementer | `#lowcost` | Writes the code |
| | Validator | `#midcost` | Verifies the fix, checks for regressions |
| **review-and-fix** | Reviewer | `#highcap` | Audits code for correctness and quality |
| | Fixer | `#lowcost` | Applies the reviewer's findings |
| **explore-and-summarize** | Explorer | `#investigate` | Searches broadly across the target scope |
| | Summarizer | `#lowcost` | Distills findings into a concise report |

`full-team` is the formalized version of the hard-coded "send an agent team"
flow described in `$HORIZON_ETC/horizon_aios_agents.md`. Use it for large,
multi-phase tasks; use `investigate-and-fix` for focused debugging.

Model group names (`#midcost`, `#lowcost`, `#highcap`, `#investigate`) are
defined in `$HORIZON_ETC/horizon_aios_model_prefs.md` and configured via the
gitignored extend file. See `$HORIZON_DOCS/system/model_preferences.md` for
setup steps.

---

## 3. Defining and overriding teams

### 3.1 Where definitions live

1. `$HORIZON_ROOT/agent_teams.md` — OS-level starter teams shipped with the
   repo. Overwritten on upstream sync; do not put personal teams here.
2. `local.agent_teams.md` — machine-local override, gitignored, never clobbered
   by sync. This is the git-safe seam, identical in role to `local.agents.md`
   (see `$HORIZON_ETC/file_structure_invariants.md` §12.6).

### 3.2 The cascade

Team definitions cascade from least to most specific; the most-specific
definition of a given team name wins:

```
OS root (agent_teams.md)
  → project-root (local.agent_teams.md)
    → brain-root (local.agent_teams.md)
      → subfolder (local.agent_teams.md)
```

This is the same scope precedence as model-prefs. (See
`$HORIZON_DOCS/system/model_preferences.md` §1.4 — "Config cascades across
scopes".)

Each `agents.md` throughout the filesystem can `@`-import its sibling
`local.agent_teams.md`, so you can scope overrides at the OS level, a specific
project, a specific brain, or even a subfolder. The OS-level `agents.md` at
`$HORIZON_ROOT` @-imports `$HORIZON_ROOT/agent_teams.md` and
`$HORIZON_ROOT/local.agent_teams.md`; project- and brain-scoped `agents.md`
files follow the same pattern.

### 3.3 Creating your own teams

Add team definitions to `local.agent_teams.md` at the scope where you want them
active. The file ships as `local.agent_teams.md.template` (tracked) and is
materialized to `local.agent_teams.md` by `aios setup` if absent, so the
import never dangles.

A minimal custom team entry (exact format defined in
`$HORIZON_ROOT/agent_teams.md`):

```
## my-team-name
1. Role A — #midcost — one-line charter
2. Role B — #lowcost — one-line charter
```

Refer to `$HORIZON_ROOT/agent_teams.md` for the authoritative format and any
additional fields (charter blocks, conditional roles, etc.).

---

## 4. Relationship to model-prefs and local.agents.md

The `#group` names in team role definitions (`#midcost`, `#highcap`, etc.) are
resolved through the model-preference layer. Configure which models back each
group in `$HORIZON_ETC/horizon_aios_model_prefs.local.md`; see
`$HORIZON_DOCS/system/model_preferences.md` for the full setup workflow.

The `local.agent_teams.md` override file follows the same git-safe, gitignored,
template-materialized pattern as `local.agents.md`. Both are @-imported last by
their sibling `agents.md` so their content takes precedence. See
`$HORIZON_ETC/file_structure_invariants.md` §12 for the invariant that governs
this family.

---

## 5. Contributing your workflows

`local.agent_teams.md` is a prime area for community-contributed agentic-loop
workflows. If you develop a team that generalizes well — a QA pipeline, a
security-review flow, a documentation pass — consider opening a PR against
`$HORIZON_ROOT/agent_teams.md` to add it to the OS-level starter set so
everyone benefits.

Contributions here follow the same quality bar as AIOS skills: clear role
charters, appropriate model-group assignments, and documented behavior. The
community-contributed team becomes part of the shipped defaults for all users
on the next sync.

---

## 6. Loop / retry constructs

A team role may declare a **loop**: if its exit condition is FAIL, it returns
structured feedback to a prior role and re-runs from that point. This continues
until either the pass condition is met or an iteration cap is reached.

### 6.1 What a looping role declares

A role that can loop specifies four things:

1. **Loop-back target** — which earlier role in the chain to re-run.
2. **Loop condition** — what constitutes FAIL (i.e., what triggers the loop).
3. **Max iterations** — the hard cap on how many times the loop may repeat.
4. **Cap behaviour** — what happens when the cap is reached without a clean
   pass: either `proceed` (continue to the next role with a caveat) or
   `report-failure` (stop and surface the outstanding failures to the user).

Authoritative source for exact markup: `$HORIZON_ROOT/agent_teams.md`.

### 6.2 Worked example — the Full Team

The `full-team` Validator (`#midcost`) checks the Implementer's (`#lowcost`)
output:

1. If the Validator passes clean, the team proceeds normally.
2. If the Validator fails, it returns specific, actionable feedback and loops
   back to the Implementer.
3. The Implementer revises and resubmits; the Validator re-checks.
4. This repeats until the Validator passes **OR** the iteration cap of 3 is
   reached.
5. At the cap without a clean pass, the team stops and reports the outstanding
   failures rather than proceeding with broken output.

### 6.3 Why caps matter

Without a cap, a loop between two roles is potentially infinite — unbounded
cost and no guarantee of termination. The iteration cap ensures every team
execution is cost-bounded and always terminates. Setting the cap behaviour to
`report-failure` (rather than `proceed`) is the safer default: it surfaces the
problem for the user rather than silently handing off broken work downstream.

### 6.4 Loops in custom teams

Loop constructs are first-class in the team-definition format. You can author
them in your own `local.agent_teams.md` at any scope (OS root, project, brain,
subfolder) using the same cascade rules as any other team definition. Refer to
`$HORIZON_ROOT/agent_teams.md` for authoritative syntax (authoritative source
pending finalisation).

---

## 7. The `/agent-teams` management skill (in progress)

An owner/sbin skill — `/agent-teams` — is being introduced to manage agent
teams without hand-editing markdown. This is the supported, guided way to
create and override teams; hand-editing `local.agent_teams.md` remains valid
but `/agent-teams` is the preferred path.

**Skill in progress** — exact invocation flags are not yet documented.

When available, the skill will:

1. **Edit or scaffold** `local.agent_teams.md` at whichever scope the user
   chooses (OS root, project root, brain root, or subfolder), creating the file
   from the shipped template if it does not yet exist.
2. **Guide team composition** — walk through defining the role chain, assigning
   a model-group preference (`#midcost`, `#lowcost`, etc.) to each role, and
   writing per-role charters.
3. **Guide loop/retry constructs** — help specify loop-back targets, pass/fail
   conditions, iteration caps, and cap behaviour without requiring the user to
   know the exact markup.

The skill operates on the gitignored `local.agent_teams.md` files only; it
never modifies the tracked `$HORIZON_ROOT/agent_teams.md` directly. It also adds
custom role flags (Section 8) to `local.agent_team_flags.md`.

## 8. Standardized AI Loop Language (SAILL)

The role flags and loop constructs above are an early sketch of what we call the
**Standardized AI Loop Language (SAILL)** — a small, terse, vendor-neutral vocabulary
for expressing *how* a team of agents runs, not just who is in it. One team definition
should read the same everywhere; a human, the acting model, and the
`resolve_agent_teams.py` tooling should all understand it identically.

**Why a language, not just prose.** A small, regular set of loop primitives prompts an
agent in very little context yet carries rich, unambiguous meaning, and stays extensible.
That lets you **write a loop in a standard form that is far more shareable than a
natural-language description** — portable across people, projects, and harnesses — while a
human can still read it back into plain English easily, without much context. SAILL is the
compact notation; natural language is always its lossless fallback translation.

Today SAILL covers:
1. **Conditional execution** — `if needed` (run only if it adds value), `if asked`
   (run only when the user explicitly asks).
2. **Concurrency** — `parallel` (run adjacent roles at once) and `wait` (sync on the
   preceding parallel group).
3. **Iteration** — `Loop` (re-run an earlier role with feedback `until <pass> or <cap>`,
   looping back to a named role so renumbering never breaks the target).

The vocabulary lives in `$HORIZON_ETC/agent_team_flags.md` (shipped) plus
`local.agent_team_flags.md` (your additions) — a deliberately dense, info-heavy block
loaded into context every session, so any agent grasps the flags without consulting a
deep reference. The resolver parses flags generically, so the language is open: a new
term works the moment it is used, and the registry gives it meaning. List the current
vocabulary with `resolve_agent_teams.py --flags`.

**This is a community frontier.** A shared, open language for agentic loops — adopted and
extended across harnesses and projects — is where SAILL gets valuable. Propose terms,
converge on meanings, and contribute them upstream; the goal is a common tongue for
agentic workflows, not a Horizon-only dialect.
