# Horizon AIOS — Model Preferences

The model-preference layer is a gitignored, BYO-model configuration that the
acting model reads and honors directly. There is no resolver script, env-var
wiring, or enforcement engine — the mechanism is in-context instruction, the
same channel that governs every other AIOS behavior.

This doc is the **practical workflow**: how to set up and maintain your config.
The **authoritative definition of the mechanism** — model groups, per-session
slots, task-class routing, member grammar, and fallback order — lives in the
spec, which is loaded into context every session via `agents.md`:

> `$HORIZON_ETC/horizon_aios_model_prefs.md`

Read it for the rules; read this for the steps. In short: the base spec is
OS-tracked and ships the structure; all your choices go in the gitignored extend
file (`$HORIZON_ETC/horizon_aios_model_prefs.extend.md`), auto-loaded alongside
it. The two combine — slots: extend wins if set; groups: membership combined.

---

## Set up the extend file

1.1 Copy the tracked template to the live extend file:

```bash
cp "$HORIZON_ETC/horizon_aios_model_prefs.extend.template.md" \
   "$HORIZON_ETC/horizon_aios_model_prefs.extend.md"
```

Windows (PowerShell):
```powershell
Copy-Item "$env:HORIZON_ETC\horizon_aios_model_prefs.extend.template.md" `
          "$env:HORIZON_ETC\horizon_aios_model_prefs.extend.md"
```

1.2 Get a current model+pricing catalog — run `/model-catalog-refresh`. It
fetches live data from Anthropic, OpenAI, Google Gemini, and Ollama (locally
available models + library top picks) and can diff your config for stale members.

1.3 Fill in group members with ids from the catalog, following the member grammar
in the spec (runtime-qualified `claude:` / `ollama:` members, or bare aliases for
Anthropic-only groups).

1.4 Add task-class routing rules if you want cheap work to stop landing on
expensive models — e.g. `documentation, formatting -> #lowcost`. See the spec's
Task-Class Routing section for the format and precedence.

1.5 Run `/model-prefs` any time to inspect, add, or change entries. It reads both
files, walks you through the change, and reports which member each group resolves
to in your current runtime.

---

## Skills reference

| Skill | Location | What it does |
|---|---|---|
| `/model-prefs` | `skills_sbin/` (owner only) | Author or inspect model groups, slots, and routing rules in the extend file |
| `/model-catalog-refresh` | `skills_bin/` (all users) | Fetch live model+pricing data from providers; diff against current config |

---

## Practical notes

- The extend file is gitignored and machine-local — nothing to commit after
  editing it. Never put choices in the OS-tracked base spec; a sync overwrites them.
- Prefer Anthropic aliases (`haiku`, `sonnet`, `opus`, `fable`) over pinned full
  model ids unless you need a specific version — aliases survive model refreshes.
- `ollama:` members that aren't pulled locally silently no-op until `ollama pull`;
  they're skipped entirely in Claude Code sessions regardless.
- Google model ids carry date suffixes — use the exact versioned string and
  validate with `/model-catalog-refresh` before relying on them.
- Reliability is best-effort: whether a harness/session model honors a preference
  depends on the acting model following context and the harness's model-selection
  support. No enforcement guarantee — see the spec's framing.
