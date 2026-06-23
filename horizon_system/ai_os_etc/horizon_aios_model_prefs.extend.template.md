# Model Preferences — Extension TEMPLATE (example; copy to remove the .template suffix)
#
# This is a tracked EXAMPLE. Your live config is `horizon_aios_model_prefs.extend.md`
# (same directory, gitignored, auto-loaded). To use this template:
#   1. Copy it to `horizon_aios_model_prefs.extend.md`.
#   2. Replace the example members below with current model ids/tags.
#   3. Get a current list any time by running the OS skill: /model-catalog-refresh
#      (fetches live models + pricing from Anthropic, OpenAI, Gemini, Ollama and
#       can diff this config for stale members).
#
# Member grammar: bare `model-id`/alias (any runtime) OR `runtime:model-id`
# (e.g. claude:haiku, ollama:llama3.2). A runtime silently skips members it can't
# run, so one file can list Anthropic + local models side by side. Members are
# tried top-to-bottom; first runnable one wins. Prefer Anthropic aliases
# (haiku/sonnet/opus/fable) over pinned full ids unless you want a specific version.
# Lines starting with `#` are comments. The example values below are illustrative,
# NOT verified-current — confirm with /model-catalog-refresh before relying on them.

## Per-Session Slot Preferences

### Spawned Agent Model
Unset

### Sub-Agent Override
Unset

## Model Groups

### #lowcost
# Minimize token cost. Cheapest acceptable model first.
- claude:haiku
- ollama:llama3.2

### #midcost
# Balanced cost vs. capability.
- claude:sonnet

### #highcap
# Maximum capability regardless of cost.
- claude:opus

### #investigate
# Research, exploration, open-ended analysis.
- claude:sonnet

### #debug
# Step-by-step debugging; favor strong coding models.
- claude:sonnet
- ollama:qwen2.5-coder:7b

### #fast
# Latency over depth; small/fast models.
- claude:haiku
- ollama:llama3.2

## Task-Class Routing
# Give a kind of work a default group so cheap work stops landing on expensive
# models. A prompt directive ("use #X") always overrides these.
- documentation, formatting, mechanical edits -> #lowcost
- research, exploration                       -> #investigate
- architecture, security-sensitive changes    -> #highcap
- step-by-step debugging                      -> #debug
