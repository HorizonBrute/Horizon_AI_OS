# Model Preferences — Horizon AIOS

> **Reliability notice.** Best-effort infrastructure, not a guarantee. Whether a
> harness honors these preferences depends on: the session model (which may not
> follow instructions about its own selection), harness tool support for explicit
> model selection, named model availability in the current provider session, and
> whether the session model acts on this file when it reads it. All outside AIOS
> control -- treat these as directional signals, not enforcement.
>
> **Reliability testing has not yet been performed.** Testing slot preferences and
> group resolution across harnesses and session models is planned; until then,
> actual reliability is unknown.

Harnesses apply preferences silently; skip anything unresolvable and fall through
to the next level or harness default.

Tracked by the AIOS repo; may change with system updates. Put user customizations
and group membership in `horizon_aios_model_prefs.extend.md` (gitignored, same
directory) -- see Extension File below.

---

## Per-Session Slot Preferences

### Spawned Agent Model

Unset

Model for any agent or sub-agent this session spawns. When "Unset", the harness
or provider selects (or a named group applies).

### Sub-Agent Override

Unset

Model for sub-agents spawned by an already-running agent. When "Unset", inherits
Spawned Agent Model.

---

## Model Groups

Named sets of models the user considers equivalent for a purpose. Reference by
hashtag in prompts (e.g. "use #lowcost", "run on #investigate"). The harness
tries members in order, uses the first available, and falls through to the
per-session slots or harness default if none resolve.

The harness must not surface errors about models it cannot access while resolving
a group -- skip unavailable members silently.

No members are pre-configured; define them in `horizon_aios_model_prefs.extend.md`.

### #lowcost
No members. Minimize token cost.

### #midcost
No members. Balanced cost vs. capability.

### #highcap
No members. Maximum capability regardless of cost.

### #investigate
No members. Research, exploration, open-ended analysis.

### #debug
No members. Step-by-step debugging.

### #fast
No members. Latency over depth.

---

## Fallback Order

1. Named group from the prompt -- first available member.
2. Sub-Agent Override (sub-agents only, if set).
3. Spawned Agent Model (if set).
4. Harness / provider default.

---

## Extension File

`horizon_aios_model_prefs.extend.md` (same directory, gitignored, auto-loaded).
Same heading format; members one per line with `-`:

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
- Slot preferences: extend file wins if not "Unset".
- Group membership: combined.
