---
name: model-prefs-test
description: Test which model the model-preference config actually resolves to per group, and (in live mode) spawn small test agents by group name to confirm the spawn honors it. Use when the user types /model-prefs-test, or says "test my model prefs", "check which model #lowcost uses", "validate model groups resolve", or "do the model-prefs reliability test".
tools: Read, Grep, Bash, Agent
---

# Skill: /model-prefs-test

**Model preference:** `#lowcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Reliability harness for the in-context model-preference layer. It answers the
question the spec flags as untested: *when I reference a group, does the right
model actually get used?* It has two modes — a cheap dry-run that shows how each
group resolves, and a `--live` mode that spawns small agents by group and has
them self-report which model ran.

Source of truth for the layer and member grammar:
`$HORIZON_ETC/horizon_aios_model_prefs.md` (+ the gitignored
`horizon_aios_model_prefs.local.md`). Read both before resolving anything.

---

## Quick Reference

- **Purpose:** verify group → model resolution for the model-preference config,
  and optionally prove a spawn honors it.
- **Triggers:** "test my model prefs", "check which model #lowcost uses",
  "validate model groups resolve", `/model-prefs-test`.
- **Modes:** dry-run (default, no spawns, free) · `--live` (spawns test agents,
  costs tokens).
- **Args:** `/model-prefs-test` · `/model-prefs-test --live` ·
  `/model-prefs-test --live #lowcost #highcap` (restrict to named groups).

---

## When to invoke

After editing the extend file, after `/model-catalog-refresh` changes members,
or any time you want to confirm a group resolves to what you expect in the
current runtime.

---

## What it tests

1. **Resolution** (both modes): for each group, which member is the first one
   runnable in the *current runtime*, and which members were skipped (wrong
   runtime / not available).
2. **Routing** (both modes): each task-class routing rule → its group → resolved
   model.
3. **Spawn honoring** (`--live` only): an agent actually spawned on the resolved
   model performs a tiny task and reports its own model identity, so you can see
   expected vs. spawned-as vs. self-reported.

---

## Procedure

### Step 1 — Load config and identify runtime
1.1 Read `$HORIZON_ETC/horizon_aios_model_prefs.md` and
    `$HORIZON_ETC/horizon_aios_model_prefs.local.md` (if the extend file is
    absent, say so — groups are empty and there is nothing to resolve).
1.2 Identify the current runtime — the harness you are executing in. For Claude
    Code: `claude:` members are runnable; `ollama:` members are skipped unless an
    Ollama bridge is configured. State which runtime you assumed.

### Step 2 — Resolve (dry-run; always done)
2.1 For each group, walk members top-to-bottom; the **resolved** model is the
    first member runnable in the current runtime. Strip the runtime prefix for
    the model name (`claude:haiku` → `haiku`). List skipped members and why.
2.2 Resolve each Task-Class Routing rule the same way (class → group → model).
2.3 Print the resolution table:

    | group | members (in order) | resolved (this runtime) | skipped |

    plus a routing table: | class | → group | resolved |

2.4 If not `--live`, stop here. This proves nothing about spawning — say so.

### Step 3 — Live test (`--live` only)
3.1 Choose the groups to exercise: the named ones if the user passed any, else a
    representative set — `#lowcost`, `#investigate`, `#highcap` (add `#fast` /
    `#debug` if the user wants broader coverage). Keep it to a few agents.
3.2 For each chosen group, spawn ONE agent with the **`model` parameter set to the
    resolved alias** from Step 2 (this is the mechanism under test — that group
    selection can drive spawn model). Give it the matching tiny task:
    - `#lowcost`, `#fast` → "Tell one short programming-related joke."
    - `#midcost`, `#investigate`, `#highcap` → "In 3 bullets, summarize the
      engineering values in `$HORIZON_DOCS/dev_values.md`."
    - `#debug` → "In 2 sentences, explain the bug in `for i in range(len(a)): a.pop(i)`."
    - Append to every task: "Then state, on its own line, `MODEL: <your model
      family/id as best you can identify it>`."
3.3 Collect each agent's final line and the model you spawned it with.

### Step 4 — Report
4.1 Print the live results table:

    | group | expected (config) | spawned-as (model param) | self-reported | match? |

4.2 Mark match `✓` (self-report agrees with spawned-as), `✗` (disagrees), or `?`
    (agent couldn't identify itself — common; not a failure of the config).
4.3 Summarize: did every group resolve? did every spawn accept the model param?
    any surprises (a group falling through to default, a routing class with no
    runnable member)?

---

## Interpreting results — caveats

- **Self-report is corroboration, not ground truth.** Models often can name their
  family (haiku/sonnet/opus/fable) but not the exact version, and may guess. A `?`
  or a vague answer is not a config failure. The reliable signal is that the
  spawn *accepted* the resolved model and ran.
- **The real pass/fail is resolution + spawn acceptance**, not the prose answer.
  The joke/summary just gives the agent something cheap to do.
- **Runtime matters.** In Claude Code, `ollama:` members are *expected* to be
  skipped — that is correct behavior, not a miss. Flag it as skipped, not failed.
- A group whose only runnable member is missing should fall through to the
  harness default; note when that happens.
- **Dry-run cannot detect access-suspension.** It resolves by runtime prefix
  only, so a `claude:` member that the provider has access-restricted (e.g. a
  suspended model) still shows as "resolved" in dry-run. Only `--live` reveals it
  — the spawn fails and resolution must fall through to the next member. Never
  trust a green dry-run for a model you know may be access-restricted; confirm
  with `--live`.

---

## Notes for the executing agent

- Dry-run is the default — never spawn agents unless `--live` is present.
- Spawn live test agents in parallel where the harness allows; keep tasks tiny to
  bound cost.
- This skill only reads config and the values doc and spawns short-lived agents;
  it writes nothing and touches no privileged paths — safe for brains.
- Resolve `$HORIZON_ETC` / `$HORIZON_DOCS` from the environment; never hardcode
  paths.
