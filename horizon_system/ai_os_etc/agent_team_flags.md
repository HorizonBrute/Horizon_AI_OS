# Agent Team Flags — Standardized AI Loop Language (SAILL)

Role primitives for agent team definitions. Extend in `local.agent_team_flags.md`.

| Flag | Form | Means |
|------|------|-------|
| `if needed` | inline | Run only if it adds value; else skip. |
| `if asked` | inline | Run only when the user explicitly asks; else skip. |
| `ask user` | inline | Pause to ask the user (input / decision / approval) and wait for the answer before continuing. |
| `parallel` | inline | Run concurrently with adjacent `parallel` roles. |
| `wait` | inline | Wait for the preceding `parallel` group to finish (sync point). |
| `Loop` | annot | `**Loop:** on <cond>, return to "<role>" (or step N); until <pass> or <max>, then <cap action>.` Re-run earlier role w/ feedback until pass/cap. Always cap. |
| `[ … ]` | struct | Box roles into one node. `Name[ … ]` = inline ephemeral sub-team; nest freely. No new operators — concurrency/iteration use the flags above. |
| `-context-` | value | Resolve from context wherever a literal would go (e.g. `-context-pass`, `-context-cap`, `-context-scope`). |
