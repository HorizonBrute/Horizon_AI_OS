---
name: horizon_aios_documentation_index_update
description: Create or update the Horizon AIOS per-folder documentation indexes so every document is registered and referenceable by a stable DOC-NNNN serial. Use when asked to index the docs, update/rebuild the documentation index, or after adding/moving/removing documentation (supports CC-G4 in the consistency-check standard).
tools: Read, Grep, Glob, Bash, Edit, Write
---

# Skill: /horizon_aios_documentation_index_update

Maintain the documentation index tree under `$HORIZON_DOCS/` so that every
document is registered with a stable `DOC-NNNN` serial and can be located via
the root index. This is the tool that satisfies **CC-G4** in
`$HORIZON_DOCS/development_tools/consistency_checks.md`.

---

## When to invoke

- "index the docs", "update/rebuild the documentation index", "register this doc".
- After any doc is added, moved, renamed, or removed under `$HORIZON_DOCS/`.
- When a consistency pass reports CC-G4 as FAIL/PARTIAL.

---

## Index structure

The documentation index is a tree of per-folder files:

- **`$HORIZON_DOCS/documentation.index.md`** — root index; catalogs every root-level
  file and directory, then embeds a rollup table from each sub-directory index.
- **`$HORIZON_DOCS/<subdir>/<subdir>.index.md`** — one per subdirectory; catalogs
  only the files and directories directly inside that subdirectory.
- **Naming rule:** index file = `<relative-path-from-doc-root-with-/-replaced-by-nothing>.index.md`
  placed inside the directory it describes. Currently one level deep.

## Table format (all indexes)

```markdown
| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-NNNN | filename.md | subdir/filename.md | Short human-readable description | DOC-XXXX, DOC-YYYY | implementation | File |
| DOC-NNNN | subdir/ | subdir/ | Short description of directory | — | — | Directory |
```

**Columns:**
- **Serial** — `DOC-NNNN` assigned from the global running counter (see below).
- **Filename** — bare filename or `dirname/`.
- **Path (from doc root)** — path relative to `$HORIZON_DOCS/`; root-level files have no leading segment.
- **Description** — one short sentence; preserve existing curated text, only fill blank for new entries.
- **Cross-Refs** — comma-delimited `DOC-NNNN` list of directly related docs; `—` if none.
- **Status** — `canon` for constitutional/invariant docs, `implementation` for all others, `—` for index files and directories.
- **Type** — `File` or `Directory`.

**Serial counter:** scan all existing `*.index.md` files for the highest `DOC-NNNN` already assigned; next serial = max + 1. Serials are never reused.

## Status classification

- **`canon`** — the doc is a constitutional or invariant document: `philosophy.md`,
  `dev_values.md`, `build_decisions/architecture_decisions.md`, `development_pipeline.md`,
  `terseness_contract_index.md`, `branding_invariants.md`, `security_architecture_invariants.md`.
- **`implementation`** — everything else.
- **`—`** — index files (this file type) and directory entries.

---

## Run this as a subagent (do this first)

This skill reads every document in the repo, so running it inline bloats the
invoking session's context. **When invoked, delegate to a general-purpose subagent.**
Only run inline if subagents are unavailable.

How to delegate:
1. Spawn one general-purpose subagent. Give it enough scope and context to be self-sufficient.
2. Tell it to follow this SKILL.md and instruct: "report the index path, entry count
   by area, and any docs without a description; **do not commit**."
3. The subagent runs the Execution loop and returns a summary; the main session relays it.

---

## Execution

### A. Adding a new document

1. Identify which directory the file lands in.
2. Open that directory's `<subdir>.index.md` (create it if the directory is new — see §C).
3. Assign the next `DOC-NNNN` serial.
4. Add the new row in the correct alphabetical position in the table.
5. Open `documentation.index.md`. Either:
   - Add the file's row to the correct rollup section (if the file is in a subdir), or
   - Add the file's row to the "Files (root)" table (if at the doc root).
6. If a new directory was added, also add a row in the "Directories" table and a new rollup section in `documentation.index.md`.

### B. Removing or renaming a document

1. Remove the row from the relevant `<subdir>.index.md`.
2. Remove or update the row in the matching rollup section of `documentation.index.md`.
3. Serials belonging to the removed entry are retired — do not reuse.

### C. Creating an index for a new subdirectory

Create `<subdir>/<subdir>.index.md` with:
```markdown
# <subdir> — Documentation Index

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-NNNN | <subdir>.index.md | <subdir>/<subdir>.index.md | Index of this directory | — | — | File |
```
Then add the directory entry and rollup section to `documentation.index.md`.

### D. Full rebuild (when index is stale or missing)

1. **Glob** all `*.md` under `$HORIZON_DOCS/`, recursively. Exclude existing `*.index.md` files from the "documents to index" list (index files are themselves listed as entries but should not trigger recursive indexing).
2. **Walk** the directory structure; for each subdirectory, derive or rebuild its `<subdir>.index.md`.
3. **Assign serials** starting from the current max + 1 for any unregistered file; preserve existing serials.
4. **Rebuild** `documentation.index.md`: Files (root) table, Directories table, then one Rollup section per subdirectory embedding that subdirectory's full table.
5. **Preserve** curated descriptions — only fill blank descriptions for new entries.
6. **Report** added / removed / changed entries and the new total.

---

## Notes

- **Deterministic & idempotent:** re-running with no doc changes must produce no diff.
- If a doc has no clear title or purpose, **flag it** (may be CC-G1/CC-G3 finding).
- Do not index outside `$HORIZON_DOCS/`; do not invent serials out of sequence.
- Commit only if the user asks; a new/removed doc and its index entry land in the same commit.
