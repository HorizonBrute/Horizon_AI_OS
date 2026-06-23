---
name: model-prefs
description: Configure or inspect the in-context model-preference layer — model groups (incl. local/BYO models), per-session slots, and task-class routing — by editing the gitignored extend file. Use when the user types /model-prefs, asks to "set up model groups", "define #lowcost", "route docs to a cheap model", "use a local/Ollama model for X", or asks which model a group resolves to.
tools: Read, Write, Edit
---

# Skill: /model-prefs

Configuration on-ramp for the in-context model-preference layer. The *mechanism*
lives in context — `$HORIZON_ETC/horizon_aios_model_prefs.md`, loaded every
session via `agents.md`, which the acting model reads and honors by direct
instruction. This skill only helps the owner author their private overrides in
the gitignored extend file. It writes **no executable code** and wires **no**
env vars; selection happens because the model follows context.

Read `$HORIZON_ETC/horizon_aios_model_prefs.md` first — it is the source of truth
for the grammar (member resolution, runtime-qualified members, fallback order).

---

## When to invoke

- "Set up model groups" / "define #lowcost" / "what's in #highcap?"
- "Route documentation (or formatting, mechanical edits) to a cheap model"
- "Use a local model / Ollama model for <kind of work>"
- "Which model does #investigate resolve to here?"
- The user types `/model-prefs`.

---

## Key facts to hold

1. Base file `horizon_aios_model_prefs.md` is **OS-tracked** — do not put user
   choices there. All user configuration goes in the **extend file**:
   `$HORIZON_ETC/horizon_aios_model_prefs.extend.md` (gitignored, auto-loaded).
2. Member grammar: bare `model-id` (any runtime) or `runtime:model-id`
   (e.g. `claude:haiku`, `ollama:llama3.2`). Local/third-party models the AIOS
   does not understand are first-class — list them freely; runtimes that can't
   run a member skip it silently.
3. Precedence when both files load: slots — extend wins if not "Unset"; groups —
   membership combined; routing — extend rules apply, more specific class wins.
4. Prompt directive ("use #X") overrides routing; routing overrides slots.

---

## Step-by-step

### Step 1 — Read current state
1.1 Read `$HORIZON_ETC/horizon_aios_model_prefs.md` (structure + group names).
1.2 Read `$HORIZON_ETC/horizon_aios_model_prefs.extend.md` if it exists. If it
    does not, you will create it in Step 3.

### Step 2 — Clarify intent
2.1 Determine which of these the user wants: define/edit a **group**, set a
    **per-session slot**, add a **task-class routing** rule, or just **inspect**
    what a group resolves to.
2.2 For new group members, confirm runtime qualification when ambiguous (is
    `llama3.2` meant for Ollama? then write `ollama:llama3.2`).

### Step 3 — Write the extend file
3.1 If absent, create `$HORIZON_ETC/horizon_aios_model_prefs.extend.md` with the
    headings from the base file's "Extension File" section.
3.2 Apply the change with Edit/Write. Use one `-` member per line under a
    `### #group`; one `class -> #group` rule per line under `## Task-Class Routing`.
3.3 Never edit the base file for user choices. Never add scripts or env vars.

### Step 4 — Confirm resolution
4.1 Tell the user, for their current runtime, which member each touched group
    resolves to (first runnable member; note any silently-skipped ones).
4.2 Remind: the extend file is gitignored and machine-local — nothing to commit.

---

## Notes for the executing agent

- This skill is purely contextual configuration. If the user asks for "automatic"
  enforcement, env-var wiring, or a resolver, explain that the design is
  deliberately in-context (security/control/openness/extensibility) and decline
  to add code — author the override instead.
- Do not invent model ids. Use what the user provides or aliases the base file
  already references. Unknown/local ids are fine — just record them verbatim.
- Inspect-only requests must not write anything; just report resolution.
