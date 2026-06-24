---
name: convert-prompt-to-saill
description: Convert a natural-language prompt into a SAILL agent-team flow — roles with model groups, control-flow flags (parallel/wait/Loop/if needed/if asked/ask user), boxes for sub-teams and nesting, and -context- for run-time values. Use when the user types /convert-prompt-to-saill, says "turn this into SAILL", "convert my prompt to SAILL", or "express this as an agent team / SAILL flow".
tools: Read, Bash
---

# Skill: /convert-prompt-to-saill

**Model preference:** `#midcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Turn "here's my prompt" into its **SAILL** form — the standard, shareable agent-team notation
(roles + model groups + flags + boxes + loops + `-context-`). The deliverable is the compact,
portable representation behind a plain-English request, which the user can then run, save as a
team, or share. Authoritative grammar: `documentation/system/agent_teams.md` (SAILL, §8) and the
flag catalog `$HORIZON_ETC/agent_team_flags.md`.

---

## When to invoke

`/convert-prompt-to-saill <prompt>`, or the user asks to turn a prompt into SAILL / express
work as an agent team.

---

## Step 1 — Load the vocabulary (do not invent flags)

1.1 Recognized flags: `python $HORIZON_BIN/resolve_agent_teams.py --flags`.
1.2 Existing teams (reuse one if it fits): `python $HORIZON_BIN/resolve_agent_teams.py --json`.
Use only flags in the registry and `#groups` defined in `horizon_aios_model_prefs.md`.

---

## Step 2 — Analyze the prompt

Decompose the prompt into a flow:
1. **Roles** — the distinct units of work; for each, a short charter (what it does).
2. **Order** — sequential vs concurrent; mark concurrency with `parallel` + a following `wait`.
3. **Iteration** — "until it passes / retry" → a `**Loop:**` back to a named role, with a cap.
4. **Gates** — "ask me / approve first" → `ask user`; "only if needed" → `if needed`; "only if I ask" → `if asked`.
5. **Sub-agents / nesting** — group related roles in a box `[ … ]`; name it for an ephemeral sub-team `Name[ … ]`; nest as deep as the prompt implies.
6. **Context values** — anything left to runtime (a scope, a pass condition, a cap) → `-context-` / `-context-<name>`.

---

## Step 3 — Map to SAILL

3.1 If the prompt matches a shipped team (e.g. "investigate and fix X"), reuse it by name and
add only the prompt's specifics (scope, flags) — do not reinvent.

3.2 Otherwise compose roles. Assign each a `#group` by the kind of work (mirror
`horizon_aios_model_prefs.md` Task-Class Routing): security / architecture / review → `#highcap`;
research / exploration → `#investigate`; mechanical / edits / summarizing → `#lowcost`;
debugging / coding → `#debug`; otherwise → `#midcost`.

3.3 Apply the flags, boxes, loops, and `-context-` from Step 2. Prefer named loop targets and
the most one-line-readable form that stays faithful.

---

## Step 4 — Output

4.1 The **SAILL block** — either the `agent_teams.md` role format (`### Name` + numbered roles)
or a one-line box expression, whichever is clearer for this flow.

4.2 A short **gloss**: map each role / flag back to the phrase in the prompt it came from.

4.3 Call out any `-context-` placeholders and what fills them at run time.

---

## Step 5 — Offer next steps

Offer to **save** it as a reusable team (`/agent-teams`), **run** it ("send this team …"), or
**test** it (`/test-agent-teams <name>`). Do NOT execute the work here — this skill only converts.

---

## Notes for the executing agent

1. Use ONLY flags from the registry and `#groups` from model-prefs — never invent vocabulary.
   If the prompt needs a new one, offer `/agent-teams` (add a flag) or `/model-prefs` (add a group).
2. SAILL governs control flow; a role's *work* is charter prose (§1.2) — keep "run skill X" /
   "scope to Y" in the charter or as `-context-`, never as a flag.
3. Keep the output terse and human-readable — the value of SAILL is a compact, shareable form.
4. This converts only; it never runs the flow.
