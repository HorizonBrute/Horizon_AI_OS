## Per-Session Slot Preferences

### Default Spawned Agent Model:
claude:sonnet

### Sub-Agent Override
claude:sonnet

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
