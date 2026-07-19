---
name: context-cost-tree
description: Map Claude Code harness context overhead across the ENTIRE AIOS as an ASCII tree — brute-forces every directory under $HORIZON_ROOT, attributes each auto-loaded CLAUDE.md / agents.md / @-import file to the directory it lives in, and reports per-directory, subtree, and grand-total context cost. Use when the user types /context-cost-tree, wants a whole-AIOS context map, or asks where context cost accrues across the tree (as opposed to /context-cost, which measures one path's upward load).
tools: Bash
---

# Skill: /context-cost-tree

**Model preference:** `#lowcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Show, as ASCII-tree art, where harness context overhead lives across the whole AIOS. Where `/context-cost` answers "what will a session started *here* load?" (an upward walk from one path), `/context-cost-tree` brute-forces the whole tree: it walks **down** from `$HORIZON_ROOT`, finds every auto-load file (`CLAUDE.md`, `CLAUDE.local.md`, `agents.md`) plus everything they `@`-import, de-duplicates, and attributes each file to the directory it physically lives in — so you can see at a glance which directories carry the context weight.

---

## Arguments

`/context-cost-tree [path]`

- `path` — optional; defaults to `$HORIZON_ROOT` (the whole AIOS). Pass a path to scope the map to a subtree.

---

## Step-by-step execution

### Step 1 — Run the mapper

1.1 Run (no path arg needed — it defaults to `$HORIZON_ROOT`):
```
python "$HORIZON_SYSTEM/bin/context_cost_tree.py"
```
To scope to a subtree, pass a path: `python "$HORIZON_SYSTEM/bin/context_cost_tree.py" <path>`.

1.2 The script prints the ASCII tree directly. Relay it to the user verbatim inside a code block — the tree art and alignment matter.

1.3 For programmatic use, add `--json` to get `{root, directories[], external, total_files, total_kb, total_tokens}` instead of the tree.

If the command fails (non-zero exit, missing script, `$HORIZON_ROOT` unset), report the error clearly and stop. An unset `$HORIZON_ROOT` means the AIOS environment is not active — tell the user to source their profile or run the AIOS switcher.

### Step 2 — Read the output

Each node shows the tokens/KB/file-count for auto-load files **physically in that directory**, plus a `[subtree: N tok]` roll-up for structural (pass-through) directories. Directories with no auto-load weight and no weighted descendants are pruned, so the tree highlights where context accrues rather than dumping every folder.

The grand total sums the de-duplicated auto-load fileset inside the root. A separate `External` line accounts for files pulled in from outside the tree (e.g. `~/.claude` imports).

### Step 3 — Flag heavy nodes (optional)

If any single directory dominates the total (e.g. a subtree carrying a large share of the tokens), point it out as the first place to trim `CLAUDE.md` / `agents.md` / `@`-imports.

---

## Notes for the executing agent

- `$HORIZON_SYSTEM` and `$HORIZON_ROOT` must be set. If not, report that the AIOS environment is not active.
- Measurement and `@`-import resolution are **reused** from `context_cost.py` (`/context-cost`'s engine) — it is the single source of truth for tokenization and import semantics. Do not reimplement counting; just run `context_cost_tree.py` and relay its output.
- A file `@`-imported by several `CLAUDE.md` files is counted once (de-duplicated) and attributed to where it physically lives — so the tree is a map of *where the bytes are*, not of every place they get pulled into.
- Token counts are estimates (chars ÷ 4), same convention as `/context-cost`.
