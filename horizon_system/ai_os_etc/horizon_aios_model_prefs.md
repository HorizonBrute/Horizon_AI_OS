# Model Preferences — Horizon AIOS

These preferences are advisory. Harnesses read this file at session start (via
@-import in `agents.md`) and apply the values in good faith when tools support
explicit model selection. When a preference cannot be honored — unsupported tool,
unavailable model, provider constraint — skip it silently and fall through to the
next level or the harness default.

Model identifiers are provider-specific and change over time. This file carries no
classification or tiering; set what you want and the harness attempts it.

---

## Preferences

### Spawned Agent Model

Unset

Preferred model for any agent or sub-agent the session spawns (Agent tool `model`
parameter, workflow `agent()` `model` option, or equivalent on other harnesses). When
set, supply this value wherever a model can be specified on agent spawn. When "Unset",
the harness or provider selects the model.

### Sub-Agent Override

Unset

Preferred model for sub-agents spawned by an already-running agent (one recursion
level deeper than the main session spawn). When "Unset", inherits the Spawned Agent
Model preference above.

---

## Fallback Order

Sub-Agent Override -> Spawned Agent Model -> harness / provider default.

---

## Editing

Replace the word "Unset" immediately following a preference heading with a model
identifier string. To clear a preference, restore that line to exactly "Unset".

Example:

    ### Spawned Agent Model
    claude-sonnet-4-6
