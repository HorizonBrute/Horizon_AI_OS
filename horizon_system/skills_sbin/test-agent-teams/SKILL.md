---
name: test-agent-teams
description: End-to-end self-test of the Agent Teams system — walk every defined team, run an example natural-language flow, and spawn each role so it echoes a nonce, its role, and the model it actually ran as. Use when the user types /test-agent-teams, says "test the agent teams", "run the agent-team self-test", or wants to verify team resolution + model routing works.
tools: Read, Bash, Task
---

# Skill: /test-agent-teams

**Model preference:** `#midcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

End-to-end verification that Agent Teams actually resolve and spawn each role on its
intended model. Every spawned role echoes a **nonce**, its **role**, **what it was told to
do** (its charter, from the resolver), and the **model it actually ran as** — a nonce the
orchestrator cannot fake, so a correct echo proves the role really spawned, the
`#model-group` routed, and the chain executed. This SPAWNS real agents (one per role across
all teams) — a deliberate, possibly costly integration test; run it to verify, not routinely.

---

## When to invoke

`/test-agent-teams [nonce]`, or the user asks to test / self-test the agent teams.

---

## Step 1 — Nonce

1.1 Use the nonce the user supplied. If none, generate a short random one (e.g. 8 hex
chars) and state it up front. The SAME nonce is passed to every role spawned this run.

---

## Step 2 — Enumerate the teams (use the tooling, do not hand-list)

2.1 Run `python $HORIZON_BIN/resolve_agent_teams.py --json`. It returns every resolved
team with its roles, model groups, and flags (and the loop target/cap). Use that.

---

## Step 3 — For each team, run an example flow

3.1 Compose a one-line natural-language example flow that exercises the team's roles and
flags (mirror `documentation/system/agent_teams.md` §1.1 style). State it before spawning.

3.2 For each role, in order, **spawn a sub-agent** (Task/Agent tool) on that role's model
group: resolve `#group` → a concrete model via `horizon_aios_model_prefs.md` (+ its local
file); if a group has no runnable member, note it and fall back to the harness default.
Record the model you spawned it as (the **expected** model). Honor flags for the test:
1. `if needed` / `if asked` — still spawn (note the flag) so every part is exercised.
2. `parallel` — spawn the adjacent `parallel` roles concurrently.
3. `ask user` — note it and continue; do not block the test.
4. `Loop` — spawn the looping role once (note the loop + cap + target); do NOT actually iterate.

3.3 Each role sub-agent gets this prompt (fill in the placeholders; `<CHARTER>` is the
role's `charter` from the resolver JSON — its real job in the team):

> You are the "<ROLE>" role of the "<TEAM>" agent team (model group `<GROUP>`).
> Your job in the team: <CHARTER>.
> This is a wiring test — do NOT carry the job out. Reply with EXACTLY four lines, nothing else:
>   nonce: <NONCE>
>   role: <ROLE>
>   told: <CHARTER>
>   model: <the model you are actually running as — your real model id/name>

---

## Step 4 — Collect and verify

4.1 Gather each role's four-line reply. Build one report table per team:

    | Team | Role | Told to do (charter) | Model group | Expected model | Reported model | Nonce OK |

4.2 Flag: a missing/incorrect nonce (the role did not really run, or the chain broke); a
reported model whose tier does not match the group (a routing problem); or a role that
failed to spawn.

---

## Step 5 — Report

5.1 Print the table(s) and a PASS/FAIL summary: **PASS** when every spawned role echoed the
nonce and ran on a model consistent with its `#group`. List every mismatch explicitly.

---

## Notes for the executing agent

1. The nonce is the proof of execution — NEVER fill it in yourself on a role's behalf; it
   must come back from the spawned agent or the test fails for that role.
2. Reuse `resolve_agent_teams.py` for discovery; never hand-parse `agent_teams.md`.
3. This is a real, fan-out spawn (≈ one agent per role across all teams). Tell the user the
   spawn count before a large run if they have many custom teams.
4. The point is to exercise EVERY part: every role, every model group, and a note for every
   flag — so the report doubles as a coverage check of the resolved team set.
