# Horizon AIOS — Model Preferences

The model-preference layer is a gitignored, BYO-model configuration that the acting model reads and honors directly. It governs the model used for **spawned agents and delegated tasks**; your interactive session model is set by the harness/provider at launch, not here.

**Full specification (member grammar, slot descriptions, group purposes, task-class routing, scope precedence, reliability framing):**
→ https://github.com/HorizonBrute/Standardized_AI_Looping_Language-SAILL

---

## File locations

| File | Tracked | Purpose |
|------|---------|---------|
| `$HORIZON_ETC/horizon_aios_model_prefs.md` | Yes | Directive spec: fallback order, slot names, group names; loaded every session |
| `$HORIZON_ETC/horizon_aios_model_prefs.local.md` | No (gitignored) | Your group members and routing rules; never clobbered by sync |
| `$HORIZON_ETC/horizon_aios_model_prefs.local.template.md` | Yes | Template; copy to create the extend file |

Config cascades OS-global → project-root → brain-root → subfolder; most-specific scope wins. Extend files are @-imported from `agents.md` at each scope (never via `CLAUDE.md`).

---

## Setup

1. Copy the template: `cp "$HORIZON_ETC/horizon_aios_model_prefs.local.template.md" "$HORIZON_ETC/horizon_aios_model_prefs.local.md"`
2. Run `/model-catalog-refresh` to fetch a current model+pricing catalog.
3. Fill in group members. Prefer Anthropic short aliases (`haiku`, `sonnet`, `opus`, `fable`) over pinned model ids.
4. Add task-class routing rules if needed (e.g. `documentation, formatting -> #lowcost`).
5. Run `/model-prefs` to inspect or modify.

---

## Skills

| Skill | Location | What it does |
|---|---|---|
| `/model-prefs` | `skills_sbin/` | Author or inspect groups, slots, and routing in the extend file |
| `/model-catalog-refresh` | `skills_bin/` | Fetch live model+pricing data; diff against current config |
| `/model-prefs-assign` | `skills_sbin/` | Audit and refresh model-group assignments across skills |

---

## Notes

- Extend file is gitignored and machine-local — nothing to commit after editing.
- `ollama:` members not pulled locally are silently skipped; irrelevant in Claude Code sessions.
- Reliability is best-effort: honoring depends on the acting model following context and the harness supporting model selection. No enforcement guarantee.
