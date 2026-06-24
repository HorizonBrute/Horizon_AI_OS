# Model Preferences — Reference

Full reference for the in-context model-preference layer. For the directive spec (what the acting model follows), see `$HORIZON_ETC/horizon_aios_model_prefs.md`. For setup workflow, see `horizon_system/documentation/system/model_preferences.md`.

---

## What this layer is

In-context, bring-your-own-model override. Loaded into context via `agents.md`; the acting model reads it and honors it by direct instruction. There is no enforcement engine, env-var wiring, or resolver script — reliability comes from the model following context, the same channel it follows any other instruction.

This layer governs the model used for **spawned agents and delegated tasks**. Your interactive session model is set by the harness/provider at launch, not here.

User choices belong in `horizon_aios_model_prefs.local.md` (gitignored, same directory, auto-loaded). The base file ships structure and defaults; the local file holds your members and routing rules.

---

## Member grammar

A member is a bare model id/alias (any runtime) or a runtime-qualified `runtime:model-id`:

    - claude:haiku
    - claude:sonnet
    - ollama:llama3.2
    - ollama:qwen2.5-coder:7b

A Claude Code session skips `ollama:*` and lands on a `claude:` member; an Ollama session skips `claude:*` and lands on a local member. One file, every runtime. Prefer Anthropic short aliases (`haiku`, `sonnet`, `opus`, `fable`) over pinned full model ids — aliases survive model refreshes.

---

## Per-Session Slot Preferences

**Spawned Agent Model** — model for any agent/sub-agent this session spawns. "Unset" → harness/provider selects, or a named group / routing rule applies.

**Sub-Agent Override** — model for sub-agents spawned by an already-running agent. "Unset" → inherits Spawned Agent Model.

---

## Model Groups

Named sets of models considered equivalent for a purpose, referenced by hashtag in prompts ("use #lowcost", "run on #investigate"). Members tried in listed order; first runnable wins; unreachable members skipped silently.

| Group | Purpose |
|---|---|
| `#lowcost` | Minimize token cost |
| `#midcost` | Balanced cost vs. capability |
| `#highcap` | Maximum capability regardless of cost |
| `#investigate` | Research, exploration, open-ended analysis |
| `#debug` | Step-by-step debugging |
| `#fast` | Latency over depth |

No members are pre-configured in the base file; define them in the local file.

---

## Task-Class Routing

Optional map from a kind of work to a group, so common work gets a sensible default model without naming one each time. Define rules in the local file with `->`:

    documentation, formatting, mechanical edits -> #lowcost
    research, exploration, open-ended analysis  -> #investigate
    architecture, security-sensitive changes    -> #highcap

A named group in the prompt always overrides routing.

---

## Scope Precedence

The base → local cascade generalizes to an N-scope cascade. Most specific scope wins:

1. OS-global (`$HORIZON_ETC` base + local)
2. project-root
3. brain-root
4. subfolder

Merge rules are the same at every scope boundary: slots — more-specific wins if not "Unset"; groups — membership combined; routing — more-specific scope wins on conflict, then more-specific class within a scope.

Override convention: drop a `horizon_aios_model_prefs.local.md` in the scope's directory and @-import it from that scope's `agents.md`. Never route through `CLAUDE.md`.

Loading reliability: OS-global and project/brain-root files load reliably at session start. Subfolder overrides are lazy-loaded (only when the session touches files in that subtree) and are best-effort.

---

## Reliability

Best-effort, not a guarantee. Whether a preference takes effect depends on the acting model following context and the harness's model-selection support. No enforcement engine exists — the mechanism is the same in-context instruction channel as every other AIOS behavior.
