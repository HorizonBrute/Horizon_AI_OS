# Model Preferences — Reference

Full reference for the in-context model-preference layer. For the directive spec (what the acting model follows), see `$HORIZON_ETC/horizon_aios_model_prefs.md`. For setup workflow, see `$HORIZON_DOCS/system/model_preferences.md`.

**Full specification (member grammar, slot descriptions, group purposes, task-class routing format, scope precedence and merge rules, reliability framing):**
→ https://github.com/HorizonBrute/Standardized_AI_Looping_Language-SAILL

---

## Files

| File | Tracked | Purpose |
|------|---------|---------|
| `$HORIZON_ETC/horizon_aios_model_prefs.md` | Yes | Directive spec (context-loaded every session) |
| `$HORIZON_ETC/horizon_aios_model_prefs.local.md` | No (gitignored) | User choices: group members and routing rules |

The base file ships structure and defaults; the local file holds your members and routing rules. They combine on load: slots — local wins if set; groups — membership combined.

---

## Model groups (seeded names)

Members are BYO; configure in the local extend file.

| Group | Intended use |
|-------|--------------|
| `#lowcost` | Minimize token cost |
| `#midcost` | Balanced cost vs. capability |
| `#highcap` | Maximum capability regardless of cost |
| `#investigate` | Research, exploration, open-ended analysis |
| `#debug` | Step-by-step debugging |
| `#fast` | Latency over depth |
