# Model Preferences — Horizon AIOS

In-context, bring-your-own-model override. This file is loaded as context via
`agents.md`; the acting model reads it and honors it by direct instruction. There
is no enforcement engine, env-var wiring, or resolver script -- reliability comes
from the model following context, the same channel it follows any instruction in.

You own the configuration. Define groups, members, and routing in
`horizon_aios_model_prefs.extend.md` (gitignored, same directory, auto-loaded).
This base file ships the structure; the extend file holds your choices.

---

## How the acting model applies this

When you reference a group (e.g. "use #lowcost"), or a unit of work matches a
Task-Class Routing rule, or a per-session slot is set, the acting model selects
its model accordingly -- including the model it picks when spawning an agent or
sub-agent.

Mainly this governs the model used for **spawned agents and delegated tasks** --
your interactive session model is set by the harness/provider at launch, not here.
Local models (`ollama:` members) are supported for agent work, but which tasks
they suit is user-tuned, not prescribed.

**Member resolution.** Group members are tried in listed order. Use the first
member runnable in the current runtime; silently skip members tagged for another
runtime or not currently available; if none are runnable, fall through to the
next level in Fallback Order. Never surface errors about models you cannot reach.

**Member grammar.** A member is a bare model id/alias (any runtime) or a
runtime-qualified `runtime:model-id`. Members may name models this layer does not
understand -- locally hosted or third-party models are first-class. Example:

    - claude:haiku
    - ollama:llama3.2
    - ollama:qwen2.5-coder:7b
    - <any-model-id-your-runtime-can-launch>

A Claude Code session skips `ollama:*` and lands on a `claude:` member; an Ollama
session skips `claude:*` and lands on a local member. One file, every runtime.

---

## Per-Session Slot Preferences

### Spawned Agent Model
Unset

Model for any agent/sub-agent this session spawns. "Unset" -> harness/provider
selects, or a named group / routing rule applies.

### Sub-Agent Override
Unset

Model for sub-agents spawned by an already-running agent. "Unset" -> inherits
Spawned Agent Model.

---

## Model Groups

Named sets of models you consider equivalent for a purpose, referenced by hashtag
in prompts ("use #lowcost", "run on #investigate"). Members follow the grammar
above. No members are pre-configured; define them in the extend file.

### #lowcost
Minimize token cost.

### #midcost
Balanced cost vs. capability.

### #highcap
Maximum capability regardless of cost.

### #investigate
Research, exploration, open-ended analysis.

### #debug
Step-by-step debugging.

### #fast
Latency over depth.

---

## Task-Class Routing

Optional, user-owned map from a kind of work to a group, so common work gets a
sensible default model without you naming one each time. Define rules in the
extend file. The acting model: before spawning an agent or starting a sizable
unit of work, if it matches a routing class, select from that group -- unless the
prompt named a different group, which always wins.

Example (define real rules in the extend file):

    documentation, formatting, mechanical edits -> #lowcost
    research, exploration                       -> #investigate
    architecture, security-sensitive changes    -> #highcap

---

## Fallback Order

1. Named group from the prompt -- first runnable member.
2. Task-Class Routing match -- first runnable member of the mapped group.
3. Sub-Agent Override (sub-agents only, if set).
4. Spawned Agent Model (if set).
5. Harness / provider default.

---

## Extension File

`horizon_aios_model_prefs.extend.md` (same directory, gitignored, auto-loaded).
Copy `horizon_aios_model_prefs.extend.template.md` to start; run `/model-catalog-refresh`
for a current model + pricing list to fill in. Same headings; group members one
per line with `-`, routing rules with `->`:

    ## Per-Session Slot Preferences
    ### Spawned Agent Model
    Unset

    ## Model Groups
    ### #lowcost
    - claude:haiku
    - ollama:llama3.2
    ### #investigate
    - claude:sonnet

    ## Task-Class Routing
    - documentation, formatting -> #lowcost
    - architecture              -> #highcap

When both files load:
- Slots: extend wins if not "Unset".
- Groups: membership combined.
- Routing: extend rules apply; on conflict, the more specific class wins.

---

## Scope Precedence

The base -> extend cascade above generalizes to an N-scope cascade, so config can
be overridden from the OS layer all the way down to a single subfolder. Most
specific scope wins:

1. OS-global (this spec + its extend, `$HORIZON_ETC`)
2. project-root
3. brain-root
4. subfolder

A brain runs as an isolated OS user scoped to its own folder, so a brain's root
*is* its project root; (2) and (3) are the same loading tier, listed separately
only for clarity.

**Merge across scopes reuses the per-file rules above — no new semantics.** Walk
scopes least- to most-specific and merge each as if it were an extend file over
what is already resolved: slots — a more-specific scope wins if not "Unset";
groups — membership combined across scopes; routing — more-specific scope's rules
apply, and on conflict the more-specific *scope* wins (then, within a scope, the
more-specific *class*).

**Override-file convention — anchored on `agents.md`, never `CLAUDE.md`.** A scope
that wants an override drops a `horizon_aios_model_prefs.extend.md` in its own
directory, and that scope's `agents.md` @-imports it. `CLAUDE.md` is only a thin
Claude-Code shim pointing at the sibling `agents.md`; no override is ever routed
through it.

**Loading-tier reality (be honest about reliability).** OS-global and
project/brain-root files are loaded reliably at session start (memory files walked
from cwd up to root) — these are first-class, fully-supported override scopes.
Subfolder/nested overrides are lazy-loaded (pulled in only when the session
touches files in that subtree) and are therefore best-effort, consistent with this
layer's "reliability comes from the model following context" framing. Do not
expect deterministic subfolder behavior.
