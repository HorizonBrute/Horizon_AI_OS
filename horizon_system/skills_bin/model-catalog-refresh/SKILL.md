---
name: model-catalog-refresh
description: Fetch CURRENT model information from live provider docs (Anthropic, OpenAI, Google Gemini, Ollama) and return a structured catalog the user can use to populate or validate the Horizon AIOS model-preference config. Use when the user types /model-catalog-refresh, or says "refresh model catalog", "update model groups", "check current models", "what models are current", or "validate my model config".
tools: Read, Write, Edit, Bash, WebFetch, WebSearch
---

# Skill: /model-catalog-refresh

**Model preference:** `#investigate` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Fetch live model data from provider documentation and return a structured catalog
the user (or the `model-prefs` skill) uses to populate or validate
`horizon_aios_model_prefs.local.md`. This is a reference document — you, the
agent, perform the fetches and parsing at runtime with your web/bash access. Do
not rely on training-cutoff knowledge of model ids or prices; the entire point is
live data.

---

## Quick Reference

- **Purpose:** produce a dated, structured catalog of current models + pricing
  across Anthropic, OpenAI, Google Gemini, and Ollama, and diff it against an
  existing model-preference config.
- **Triggers:** "refresh model catalog", "update model groups", "check current
  models", "what models are current", "validate my model config", `/model-catalog-refresh`.
- **Companion:** `/model-prefs` consumes this output to edit the gitignored extend
  file. This skill fetches truth; that skill writes config.

---

## When to invoke

Whenever the user wants an up-to-date picture of available models to configure or
sanity-check their groups — e.g. before defining `#lowcost`/`#highcap`, after a
provider releases a new model, or to confirm a member id is still valid.

---

## Providers and fetch strategy

Fetch each provider's MODEL LISTING and PRICING separately — they are always two
different pages. Prefer an API/CLI when available over scraping.

### 1. Anthropic
- Models: https://platform.claude.com/docs/en/about-claude/models/overview
- Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Changelog / notices (for suspensions): check the docs changelog and any banner.
- Extract: full model id string, tier (haiku/sonnet/opus/fable), input & output
  $/MTok, context window, known aliases, deprecation or access-suspension notices.

### 2. OpenAI
- Preferred: if `OPENAI_API_KEY` is set, `GET https://api.openai.com/v1/models`
  and parse directly — more reliable than the docs page.
- Models (fallback): https://developers.openai.com/api/docs/models
- Pricing (scrape; no pricing API): https://openai.com/api/pricing
- Extract: model id, family (gpt-5.x / gpt-oss), open-weight flag, input/output
  $/MTok, context window, recommended-for notes.

### 3. Google Gemini
- Models: https://ai.google.dev/gemini-api/docs/models
- Changelog (deprecations): https://ai.google.dev/gemini-api/docs/changelog
- Extract: exact versioned model id (Google uses date suffixes — capture them),
  tier (flash-lite/flash/pro), pricing (note tiered-by-context-length), GA vs
  preview status, shutdown notices.

### 4. Ollama
- Preferred: if `ollama` is on PATH and running, `ollama list` for what is already
  pulled, then `ollama show <model>` per model for metadata.
- Fallback (no local ollama): fetch https://ollama.com/library and take the top
  models by pull count in each relevant category (coding, reasoning, fast/small).
- Extract: exact pull tag (e.g. `qwen2.5-coder:7b`), category, VRAM requirement,
  parameter count, notable capability notes.

---

## Output schema

Return a plain-text block (not JSON — this lands in config-adjacent context):

  ## Model Catalog — <YYYY-MM-DD fetched>

  ### Anthropic
  | model_id | alias | tier | input $/MTok | output $/MTok | ctx | status |

  ### OpenAI
  | model_id | family | open_weight | input $/MTok | output $/MTok | ctx | status |

  ### Google
  | model_id | tier | input $/MTok | output $/MTok | ctx | ga_or_preview | status |

  ### Ollama (local-available / library-top)
  | tag | category | vram | params | notes |

  ### Deprecation / Access Alerts
  List any model found suspended, sunset-announced, or access-restricted.

  ### Config Diff (only if a config was provided — see Diff behavior)
  Per group in the current config, flag:
    - member ids that no longer appear in provider docs
    - newer models that better fit the group's intent
    - pricing changes vs the member's prior cost

---

## Diff behavior

If the current Horizon AIOS `## Model Groups` block is already in context when
invoked, run the Config Diff automatically. If it is not, prompt once:
"Paste your current `## Model Groups` block to get a config diff." Do not invent a
config to diff against.

---

## Freshness

- Stamp the output with the fetch date.
- State, per provider, whether you got live data or fell back (scrape / cache /
  unavailable).
- If a page is unreachable, say so explicitly for that provider — never return
  stale data silently as if it were current.

---

## Populating the config

After presenting the catalog, offer to hand the relevant ids to `/model-prefs`
(or do it directly if the user asks) to update `horizon_aios_model_prefs.local.md`.
Use runtime-qualified members: `claude:<id|alias>` for Anthropic, `ollama:<tag>`
for local models. Prefer Anthropic aliases (haiku/sonnet/opus/fable) over pinned
full ids unless the user wants a specific version. Never write the base
`horizon_aios_model_prefs.md` — user choices go only in the extend file.

---

## Known Gotchas

- Ollama tags often omit the size suffix — always use the full tag (`:7b`, not
  `:latest`); `:latest` silently pulls whatever the registry defaults to.
- Google model ids frequently carry date suffixes — never store bare
  `gemini-3.5-flash` without verifying the exact stable string.
- OpenAI open-weight models (`gpt-oss-*`) run locally via Ollama/LM Studio AND are
  available via the OpenAI API — record both surfaces; they differ in price.
- Anthropic access suspensions (e.g. Fable 5, mid-2026) may not show on the models
  overview page — check the changelog and any banner before trusting availability.
- Pricing and model-listing pages are separate fetches for every provider — do
  both; a listing without prices is an incomplete catalog.

---

## What this skill must NOT do

- No executable code embedded as the mechanism — you fetch at runtime; the file is
  instruction.
- No hardcoded model ids or prices — live fetch only.
- No assumption about which runtime/harness you are in.

---

## Notes for the executing agent

- Run independent provider fetches in parallel where possible; one provider being
  down must not block the others.
- This skill is read-only toward provider sources and the base config; the only
  thing it may write is the gitignored extend file (and only when the user asks).
- Brains may invoke this — it touches public docs and the user's own extend file
  only; no privileged paths.
