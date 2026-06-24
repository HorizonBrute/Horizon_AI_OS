# Agent Team Flags — Standardized AI Loop Language (SAILL)

Role primitives for agent team definitions. Extend in `local.agent_team_flags.md`.

| Flag | Form | Means |
|------|------|-------|
| `if needed` | inline | Run only if it adds value; else skip. |
| `if asked` | inline | Run only when the user explicitly asks; else skip. |
| `ask user` | inline | Pause to ask the user (input / decision / approval) and wait for the answer before continuing. |
| `if fail` | inline | On the role/box failing (or a loop hitting its cap unmet), run the named action — often a skill, e.g. `if fail /triage` — instead of stopping silently. |
| `parallel` | inline | Run concurrently with adjacent `parallel` roles. |
| `wait` | inline | Wait for the preceding `parallel` group to finish (sync point). |
| `Loop` | annot | `**Loop:** on <cond>, return to "<role>"; until <pass> (or `ask user`, or `-context:cap-`), then <cap action / if fail>.` Re-run earlier role w/ feedback. Always bound it. |
| `[ … ]` | struct | Box roles into one node. `Name[ … ]` = inline ephemeral sub-team; nest freely. No new operators — concurrency/iteration use the flags above. |
| `/skill-name` | call | A role's charter (or an `if fail` / handler action) may invoke a named skill — e.g. `… before /security-review`, `if fail /triage`. The work is charter, not a flag. |
| `-context-` | value | Resolve from context where a literal would go; qualify `-context:<name>-` (multi-word ok), e.g. `-context:pass criteria-`, `-context:cap-`, `-context:source data-`. |
