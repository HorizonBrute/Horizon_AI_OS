# Model Preferences — Horizon AIOS

Governs the model used for spawned agents and delegated tasks. Apply in this order:

1. Named group from the prompt — first runnable member.
2. Task-Class Routing match — first runnable member of the mapped group.
3. Sub-Agent Override (sub-agents only, if set).
4. Spawned Agent Model (if set).
5. Harness / provider default.

Member resolution: try members in listed order; skip any not runnable in the current runtime; never surface errors about unreachable models.

---

## Per-Session Slot Preferences

### Spawned Agent Model
Unset

### Sub-Agent Override
Unset

---

## Model Groups

Members defined in `horizon_aios_model_prefs.local.md`.

### #lowcost
### #midcost
### #highcap
### #investigate
### #debug
### #fast

---

## Task-Class Routing

Defined in `horizon_aios_model_prefs.local.md`.

---

## Merge Rules

When local and base files both load:
- Slots: local wins if not "Unset".
- Groups: membership combined.
- Routing: local rules apply; more specific class wins on conflict.

Scope cascade (OS-global < project < brain < subfolder): same merge rules, most specific scope wins.
Override files @-imported from `agents.md`; never routed through `CLAUDE.md`.
