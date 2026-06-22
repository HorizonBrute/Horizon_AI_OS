---
name: horizon_aios_documentation_index_update
description: Create or rebuild the Horizon AIOS documentation index so every document is registered and referenceable by a stable index entry. Use when asked to index the docs, update/rebuild the documentation index, or after adding/moving/removing documentation (supports CC-G4 in the consistency-check standard).
tools: Read, Grep, Glob, Bash, Edit, Write
---

# Skill: /horizon_aios_documentation_index_update

Maintain the documentation index at `$HORIZON_DOCS/index.md` so that every
document is registered and can be referenced by a stable index entry. This is the
tool that satisfies **CC-G4** in
`$HORIZON_DOCS/development_tools/consistency_checks.md`.

---

## When to invoke

- "index the docs", "update/rebuild the documentation index", "register this doc".
- After any doc is added, moved, renamed, or removed.
- When a consistency pass reports CC-G4 (indexed & referenceable) as FAIL/PARTIAL.

## Run this as a subagent (do this first)

This skill reads every document in the repo, so running it inline bloats the
invoking session's context. **When invoked, delegate the work to a general-purpose
subagent** instead of doing it in the main session (this follows the agent
delegation model in `agents.md` — the main session orchestrates, subagents do the
file-heavy work). Only run inline if subagents are unavailable.

How to delegate:
1. Spawn one general-purpose subagent (the harness's Agent/Task tool,
   `subagent_type: general-purpose`). Subagents start cold — give it enough scope
   and context to be self-sufficient.
2. Tell it to follow this SKILL.md, pass it the **Scope** and **Index format**
   below, and instruct: "report the index path, entry count by area, and any
   docs flagged as missing a title/purpose; **do not commit**."
3. The subagent runs the Execution loop and returns a summary; the main session
   relays it.

For a very large doc tree you may fan out one subagent per area and have the main
session merge their entries into a single `index.md`.

## Scope (what gets indexed)

- Every `*.md` under `$HORIZON_DOCS/` (`horizon_system/documentation/`), recursively.
- The authority + invariant docs that govern the project:
  `documentation/philosophy.md`, `documentation/dev_values.md`,
  `documentation/build_decisions/architecture_decisions.md`, and the invariant
  docs under `horizon_system/ai_os_etc/` (`security_invariants.md`,
  `file_structure_invariants.md`, `ai_os_personalizations.md`).
- **Exclude:** the index file itself, skills' own `index.md` files, and any
  non-documentation file.

## Index format

`$HORIZON_DOCS/index.md` is a Markdown catalog grouped by area (top-level
directory), entries sorted by path. The **index entry / reference ID is the
repo-relative path** — stable, unique, and needs no renumbering when docs are
added or removed.

```markdown
# Horizon AIOS — Documentation Index

Reference a document by its path (the ID column). Regenerate with
`/horizon_aios_documentation_index_update`.

## <area> (e.g. getting_started)
| ID (path) | Title | Purpose |
|---|---|---|
| `documentation/getting_started/ReadMeToSetupYourSystem.md` | Setup guide | One-line purpose |
```

## Execution

1. **Glob** all in-scope docs.
2. For each doc, derive its **Title** (first `#` heading) and a one-line
   **Purpose**. If the doc already has an index entry with a curated purpose,
   **preserve it**; only fill in purposes for new docs (from the doc's intro).
3. Read the existing `index.md` if present.
4. **Rebuild** the index: one row per in-scope doc, grouped by area, sorted by
   path. **Add** rows for new docs, **remove** rows whose files no longer exist.
5. Write `index.md`. Keep purposes short — the index is referenced often, so it
   is itself subject to token economy (CC-G5).
6. **Report** added / removed / changed entries and the new total.

## Notes for the executing agent

- **Deterministic & idempotent:** re-running with no doc changes must produce no
  diff.
- If a doc has no clear title or purpose, **flag it** (it may itself be a CC-G1/
  CC-G3 finding) rather than inventing a description.
- Do not index outside the defined scope; do not invent IDs other than the path.
- Commit only if the user asks (DCO sign-off per repo rules); a new/removed doc
  and its index entry should land in the same commit.
