# Horizon AIOS — Agent Teams

Agent Teams are named, reusable multi-agent workflows invoked by name in plain language. The acting model looks up the team, spawns each role in order on its assigned model group, and chains their outputs to a result — no slash command required.

**Full specification (SAILL flags, loop constructs, primitives, nesting, context values):**
→ https://github.com/HorizonBrute/Standardized_AI_Looping_Language-SAILL

---

## Invocation

> "Send the **investigate-and-fix** agent team to look at problems 2, 3, and 4."

The acting model resolves the name, spawns roles in order, and chains output. Scope or direct roles at invocation time in plain language.

---

## Shipped starter teams

Defined in `$HORIZON_ROOT/agent_teams.md`.

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

---

## File locations

| File | Tracked | Purpose |
|------|---------|---------|
| `$HORIZON_ROOT/agent_teams.md` | Yes | OS-level starter teams; overwritten on sync — do not put personal teams here |
| `$HORIZON_ROOT/local.agent_teams.md` | No (gitignored) | Machine-local overrides; never clobbered by sync |
| `local.agent_teams.md.template` | Yes | Template; materialized to `local.agent_teams.md` by `aios setup` if absent |

Definitions cascade OS-global → project-root → brain-root → subfolder; most-specific definition of a given team name wins. See `$HORIZON_ETC/file_structure_invariants.md` §12 for the structural invariant governing this family.

Extend via `local.agent_team_flags.md` (gitignored) for custom SAILL flag additions.

---

## `/agent-teams` skill

`skills_sbin/` owner skill — lists loaded teams, scaffolds and edits `local.agent_teams.md` at any scope, guides team composition and loop constructs.
