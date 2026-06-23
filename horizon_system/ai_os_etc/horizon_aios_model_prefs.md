# Model Preferences — Horizon AIOS

> **Reliability notice.** This is best-effort infrastructure, not a guarantee.
> Whether a harness honors these preferences depends on: the model powering the
> session (which may not follow instructions about its own model selection), whether
> the harness tool or API supports explicit model selection at all, whether named
> models are available in the current provider session, and whether the session
> model chooses to act on these instructions when it reads them. All of these are
> outside the control of the AIOS. Set preferences here and the harness will attempt
> to apply them in good faith -- treat them as directional signals, not enforcement.

Harnesses read this file at session start (via @-import) and apply preferences
silently. When a preference cannot be honored, skip it and fall through to the
next level or the harness default.

This file is tracked by the AIOS repo and may be updated by system updates.
User customizations and group membership belong in
`horizon_aios_model_prefs.extend.md` (gitignored, in the same directory) so
they are never overwritten. See the Extension File section below.

---

## Per-Session Slot Preferences

### Spawned Agent Model

Unset

Preferred model for any agent or sub-agent this session spawns (Agent tool `model`
parameter, workflow `agent()` option, or equivalent on other harnesses). When set,
supply this value wherever a model can be specified on agent spawn. When "Unset",
the harness or provider selects, unless a named group preference applies.

### Sub-Agent Override

Unset

Override for sub-agents spawned by an already-running agent (one recursion level
deeper than the main session spawn). When "Unset", inherits Spawned Agent Model.

---

## Model Groups

Named sets of models the user considers equivalent for a given purpose. A prompt
can reference a group by its hashtag (e.g. "use a #lowcost model for this",
"route this sub-agent to #investigate"). The harness resolves the group by trying
each listed member in order and using the first available model it can pass to the
spawn tool. If no member is available or the group has no members, fall through to
the per-session slots or the harness default.

**The harness must not surface errors or commentary about models it cannot access
while resolving a group.** Skip unavailable members silently; warn or fall through
only if the entire group resolves to nothing.

Groups here are seed names only -- no members are pre-configured. Define members
in `horizon_aios_model_prefs.extend.md` so they survive AIOS updates.

### #lowcost

No members configured.

For tasks where minimizing token cost is the primary constraint.

### #midcost

No members configured.

For balanced cost-vs-capability tasks.

### #highcap

No members configured.

For tasks requiring maximum capability regardless of cost.

### #investigate

No members configured.

For research, exploration, and open-ended analysis requiring depth.

### #debug

No members configured.

For debugging sessions requiring careful, step-by-step reasoning.

### #fast

No members configured.

For tasks where response latency matters more than depth.

---

## Fallback Order

When resolving the model for a spawned agent or sub-agent:
1. Named group from the prompt (#lowcost, #investigate, etc.) -- first available member.
2. Sub-Agent Override slot (sub-agents only, if set).
3. Spawned Agent Model slot (if set).
4. Harness / provider default.

---

## Extension File

`horizon_aios_model_prefs.extend.md` in this directory is gitignored and never
overwritten by AIOS updates. It is loaded alongside this file via a separate
@-import in `agents.md`. Use it to set slot preferences and define group membership.

Follow the same heading format. Members are listed one per line with a leading `-`:

    ## Per-Session Slot Preferences

    ### Spawned Agent Model
    Unset

    ## Model Groups

    ### #lowcost
    - <model-id-1>
    - <model-id-2>

    ### #investigate
    - <model-id-1>

When both files are loaded:
- Slot preferences: the extend file's value takes precedence if not "Unset".
- Group membership: the member lists from both files are combined.
