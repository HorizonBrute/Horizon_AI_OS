---
name: context-cost
description: Report harness context overhead (KB, words, estimated tokens) for a given path by walking the directory tree and collecting all CLAUDE.md, agents.md, and @-import files the Claude Code harness auto-loads. Use when the user types /context-cost or /ctx-cost, asks how much context overhead a directory has, or wants to know what files the harness is auto-loading.
tools: Bash
---

# Skill: /context-cost

Report how much context overhead the Claude Code harness will auto-load for a given path — walking up the directory tree and collecting every `CLAUDE.md`, `CLAUDE.local.md`, `agents.md`, and `@`-import file it will pull in at session start.

---

## Arguments

`/context-cost [path]`

- `path` — optional; defaults to the current working directory if omitted.

---

## Step-by-step execution

### Step 1 — Resolve the target path

1.1 If the user provided a path argument, use it. Otherwise use the current working directory.

1.2 Run:
```
python "$HORIZON_SYSTEM/sbin/context_cost.py" <path> --json
```

Capture the JSON output. If the command fails (non-zero exit, missing script, bad path), report the error clearly and stop.

### Step 2 — Parse and format the output

The JSON structure is:
```json
{
  "path": "...",
  "files": [
    {"level": N, "path": "...", "kb": N, "words": N, "tokens": N, "imported_by": "..." or null}
  ],
  "total_kb": N,
  "total_words": N,
  "total_tokens": N
}
```

### Step 3 — Present the report

3.1 Print a header line: `Context overhead for: <path>`

3.2 Print a table of the collected files, sorted by `level` (outermost first):

```
Level  File                              KB     Words   ~Tokens
-----  --------------------------------  -----  ------  -------
  0    /path/to/CLAUDE.md                1.2    210     280
  1    /path/to/agents.md                3.4    580     775
       (imported by CLAUDE.md)
```

- Show `(imported by <basename>)` on a sub-line when `imported_by` is non-null.
- Round KB to one decimal place; tokens and words are integers.

3.3 Print a totals line:
```
Total: N files — X.X KB — Y words — ~Z tokens
```

3.4 Threshold flags (after totals):
- If `total_tokens` >= 2000: print a warning: `[WARN] High context load: ~Z tokens. Consider trimming CLAUDE.md files or @-imports above this path.`
- Else if `total_tokens` >= 1000: print a notice: `[NOTE] Moderate context load: ~Z tokens. Worth reviewing if sessions feel slow.`
- Otherwise: no flag.

---

## Notes for the executing agent

- `$HORIZON_SYSTEM` must be set in the environment. If it is not, report that the AIOS environment is not active and the user should source their profile or run the AIOS switcher.
- The script walks upward from the given path to `$HORIZON_ROOT`, collecting files at each level. Level 0 is the given path; higher numbers are ancestor directories.
- Imported files (via `@`-imports in CLAUDE.md) are included in the table and counted in totals. The `imported_by` field names the file that referenced them.
- Do not reimplement the walk logic — the script is the single source of truth. Just run it and format its output.
