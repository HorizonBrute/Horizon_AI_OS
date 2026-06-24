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

### 1.1 Example flows — natural language in, SAILL out

You speak plainly; the acting model maps it onto a team and its SAILL flags
(Section 8):

1. "Send an **investigate-and-fix** team at the flaky test in `auth/`."
   → Investigator (`#midcost`) diagnoses → Fixer (`#lowcost`) patches.
2. "Send a **full-team** to build the export feature, but **ask me before you start
   implementing**."
   → the Planner gates on `ask user` — presents the plan and waits for your approval
   before the Implementer runs.
3. "Run a **review-and-fix** over my current diff, but **only fix if I say so**."
   → Reviewer (`#highcap`) audits → Fixer (`#lowcost`, `if asked`) applies only on your
   go-ahead.
4. "**Explore-and-summarize** how sessions persist — fan out **three explorers in
   parallel** across the API, the DB, and the UI, then summarize."
   → three Explorers (`#investigate`, `parallel`) → Summarizer (`#lowcost`, `wait`) syncs
   on them and distills.
5. "Send a **full-team**, but **skip the log-reader** and **loop the validator up to 3
   times** until it's clean."
   → Log-reader (`if needed`) is skipped → Validator loops back to the Implementer until
   it passes or hits 3 iterations.

Each right-hand side is the SAILL the model resolves to; you never have to write it —
but it is the shareable, standard form behind the plain-English request.

### 1.2 Directing roles in plain language

A team is a scaffold, not a cage. At invocation you can also tell a role **what to do or
what to focus on**, ad hoc, and the model honors it on top of the team:

> "Send a **full-team** for the export bug; have the **Validator run `/security-review`**,
> and **Log-reader, scope to just the auth module**."

That works because two different things are in play:
1. **SAILL flags govern control flow** — *whether / when / how often / concurrently /
   ask-the-user* a role runs (`if needed`, `ask user`, `parallel`, `Loop`, …).
2. **A role's *work* is charter prose** — which tools or skills it uses, what to scope to,
   what it hands on. That lives in the role's charter (in the team definition) and can be
   set or overridden in plain language at invocation.

So "the Validator runs `/security-review`" or "the Log-reader focuses on auth" are **role
direction**, not flags — do not encode them as SAILL primitives. Keep SAILL to control
flow; put the work in the charter or your request. The two compose cleanly.

---

## 2. Shipped starter teams

Four teams ship with the OS layer and are defined in `$HORIZON_ROOT/agent_teams.md`.

| Team name | Roles (in order) | Model group | Charter |
|---|---|---|---|
| **Investigate & Fix** | Investigator | `#midcost` | Gathers evidence, isolates root cause |
| | Fixer | `#lowcost` | Applies the targeted fix |
| **Full Team** | Orchestrator | `#highcap` | Breaks down task, coordinates the rest |
| | Log-reader *(if needed)* | `#lowcost` | Gathers runtime evidence before planning |
| | Planner | `#highcap` | Designs the approach |
| | Implementer | `#lowcost` | Writes the code |
| | Validator | `#midcost` | Verifies the fix, checks for regressions |
| **Review & Fix** | Reviewer | `#highcap` | Audits code for correctness and quality |
| | Fixer | `#lowcost` | Applies the reviewer's findings |
| **Explore & Summarize** | Explorer | `#investigate` | Searches broadly across the target scope |
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

## 7. The `/agent-teams` management skill

The `/agent-teams` owner skill (`skills_sbin/`) manages agent teams without hand-editing
markdown. This is the supported, guided way to create and override teams; hand-editing
`local.agent_teams.md` remains valid but `/agent-teams` is the preferred path.

The skill:

1. **Lists loaded teams** (bare `/agent-teams`) — runs `resolve_agent_teams.py` and
   presents each source with its team names, then prompts to add or modify.
2. **Edits or scaffolds** `local.agent_teams.md` at whichever scope the user chooses
   (OS root, project root, brain root, or subfolder), creating the file from the shipped
   template if it does not yet exist.
3. **Guides team composition** — walks through the role chain, model-group preferences,
   and optional loop/retry constructs.
4. **Adds custom role flags** to `local.agent_team_flags.md` at the target scope.

The skill operates on gitignored `local.agent_teams.md` files only; it never modifies
the tracked `$HORIZON_ROOT/agent_teams.md`. See `$HORIZON_SYSTEM/skills_sbin/agent-teams/SKILL.md`
for the full invocation reference.

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
4. **Human-in-the-loop** — `ask user` (pause for the user's input, decision, or approval
   before continuing).

### SAILL primitives

Each flag is a **primitive** — one small, atomic, composable operation, not a recipe.
Like the closed-class control words of a programming language (`if`, `while`, `parallel`,
`await`), the set is intentionally small; expressive power comes from **composing**
primitives in a team definition, not from piling on bespoke flags. A primitive:

1. **Does exactly one thing** — a condition, a concurrency move, a sync point, an
   iteration. If a flag needs an "and", it is two primitives.
2. **Is orthogonal** — it combines cleanly with the others (`(`#group`, if asked, parallel)`)
   with no special cases.
3. **Has a single registry-defined meaning** — identical everywhere it appears.
4. **Is context-light** — rich meaning in one or two words, so a whole loop fits in a
   glance and a small prompt.

Compose existing primitives before inventing a compound flag. Add a new primitive only
for a genuinely new control-flow idea (a new kind of branch, gate, or synchronization) —
never to encode one team's specifics, which belong in that role's charter prose.

### Naming a SAILL primitive

Names are the interface; choose them so the notation stays terse and self-translating:

1. **Reads as English in place.** Slotted into a role it should parse naturally —
   `Validator (`#midcost`, if asked)`, `Crawler (`#investigate`, parallel)`.
2. **One or two words.** Lowercase for inline conditions/modifiers (`if needed`,
   `parallel`, `wait`); Capitalized for an annotation primitive that introduces its own
   clause (`Loop`, and any future `Gate` / `Branch`).
3. **Names the behavior, not the mechanism** — what happens, never how it is implemented.
4. **Self-translating** — a human should render it to plain English without opening the
   registry. If it needs a footnote to be understood, rename it.
5. **Stable and distinct** — never collide with another primitive or a `#model-group`
   name, and pick a name you will not have to rename (renames ripple through every team
   definition that uses it).

### Sub-teams and nesting — boxes

SAILL composes beyond a flat role list. A **box** `[ … ]` bundles one or more roles (or
other boxes) into a single node that runs as a unit; the brackets set the order of
operations. Name a box to declare an inline, **ephemeral sub-team** — `Recon[ … ]`. A
sub-agent is just a named role inside a box; a named box is a throwaway team of them. Inside
a box you use the ordinary role syntax and the existing flags — **no new operators**:
concurrency via `parallel` + `wait`, iteration via a `**Loop:**` annotation, gating via
`if needed` / `if asked` / `ask user`.

A box is itself a node: sequence it, flag it, and — the point — **nest boxes inside boxes,
without limit.** Depth is a user choice; turtles all the way down. Order of operations is the
bracket nesting, so one line carries parallelism, loops, and delegation to named sub-agents
at once. Examples:

1. Parallel recon, then plan:
   `Orchestrator (`#highcap`) -> Recon[ APICrawler (`#investigate`, parallel), DBReader (`#investigate`, parallel) ] (wait) -> Planner (`#highcap`)`
2. Gated build with an implement/validate loop:
   `Planner (`#highcap`, ask user) -> [ Implementer (`#lowcost`), Validator (`#midcost`) **Loop:** to "Implementer" until pass or 3 ]`
3. Nested — two sub-teams looping in parallel, then integrate (turtles):
   `[ Frontend[ Impl (`#lowcost`), Val (`#midcost`) **Loop:** to "Impl" until pass or 3 ] (parallel), Backend[ Impl (`#lowcost`), Val (`#midcost`) **Loop:** to "Impl" until pass or 3 ] (parallel) ] (wait) -> Integrator (`#midcost`)`

**Tooling note.** `resolve_agent_teams.py` lists flat team definitions today; it does not yet
expand nested boxes — the acting model interprets them from this spec. Box-aware resolution
is a planned extension.

### Values from context (`-context-`)

Wherever a SAILL parameter would take a literal — a loop's pass condition or cap, a scope, a
target — you can instead write **`-context-`** to mean *"resolve this from context"*: the
user's invocation, the conversation, or runtime state. Qualify it with the delimited form
**`-context:<name>-`**, where `<name>` may be multi-word — `-context:pass criteria-`,
`-context:cap-`, `-context:source data-`, `-context:findings-`. It keeps a team definition
generic and reusable: the structure is fixed; the specifics arrive at run time. It is the
explicit hook for "a team is a scaffold you parameterize in plain language" (§1.2). Examples:

1. Loop until a context-defined pass, capped at a literal 3:
   `[ Implementer (`#lowcost`), Validator (`#midcost`) **Loop:** to "Implementer" until -context:pass criteria- or 3 ]`
2. Both the pass and the cap from context:
   `… **Loop:** to "Implementer" until -context:pass- or -context:cap-`
3. Scope a role from context:
   `Investigator (`#midcost`) — audit -context:source data-` (its charter pulls the target from your request)

### Failure handling, skill calls, and compound loop exits

Three further pieces let a flow react and reach out:
1. **`if fail <action>`** — a failure handler on a role or box: if it fails (or a loop hits its
   cap unmet), run `<action>` instead of stopping silently. The action is usually a skill —
   `Build[ … ] if fail /build_fail_triage_report` — or a fallback role/box.
2. **Skill calls** — a role's charter (or an `if fail` action) may invoke a named skill by its
   slash name: `Ship (`#lowcost`, ask user) — present the result; wait for approval before
   /deploy`. The skill is the role's *work* (charter), not a control-flow flag (§1.2).
3. **Compound loop exits** — a `**Loop:**` may list several `or`-separated exit conditions: a
   pass (`-context:pass criteria-` or literal), `ask user` (the user can approve/stop early),
   and a cap (`3` or `-context:cap-`). Example:
   `Security-Reviewer (`#highcap`) — audit -context:source data-; on -context:findings- **Loop:** to "Build" until clean or ask user or -context:cap-`

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
