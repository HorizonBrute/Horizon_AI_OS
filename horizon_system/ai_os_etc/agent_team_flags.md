# Agent Team Flags — Standardized AI Loop Language (SAILL)

Role primitives beyond label + model group (small, composable; compose, don't pile on). Loaded every session (keep terse); read by
`resolve_agent_teams.py`; extend in `local.agent_team_flags.md`. Forms: **inline** = token
in `(`#group`, <flag>)`; **annot** = `**Name:** …` line under the role.
Structure: `[ … ]` boxes roles into one node; `Name[ … ]` = inline ephemeral sub-team; nest freely — no new operators (concurrency/iteration use the flags below).
Values: `-context-` (or `-context-<name>`, e.g. `-context-pass`, `-context-cap`, `-context-scope`) = resolve from context wherever a literal would go.

| Flag | Form | Means |
|------|------|-------|
| `if needed` | inline | Run only if it adds value; else skip. |
| `if asked` | inline | Run only when the user explicitly asks; else skip. |
| `ask user` | inline | Pause to ask the user (input / decision / approval) and wait for the answer before continuing. |
| `parallel` | inline | Run concurrently with adjacent `parallel` roles. |
| `wait` | inline | Wait for the preceding `parallel` group to finish (sync point). |
| `Loop` | annot | `**Loop:** on <cond>, return to "<role>" (or step N); until <pass> or <max>, then <cap action>.` Re-run earlier role w/ feedback until pass/cap. Always cap. |
