---
name: handoff
description: Write a structured handoff document capturing current session state. Use when the user types /handoff, asks to "write a handoff", "produce a handoff document", "save session state", or wants to capture current state for a future session.
tools: Bash, Read, Write, Glob, Grep
---

# Skill: /handoff

**Model preference:** `#midcost`

---

## Execution

### 1 — Resolve handoffs directory

- Search upward from `cwd` for `aios_overrides.md` (stop at `$HORIZON_ROOT` or filesystem root).
- If found and contains `handoffs_dir: <path>` → use that path.
- Otherwise → use `$HORIZON_ROOT/handoffs/`.
- If `aios_overrides.md` contains `project_display_name` → use it; otherwise use `basename(cwd)`.

### 2 — Derive metadata

- Date: `YYYY-MM-DD`. Time: `HHMMSS`.
- Filename: `YYYY-MM-DD_HHMMSS_<project-name>.md` (project-name lowercased, spaces → hyphens).
- Full path: `<handoffs_dir>/<filename>`.
- Check git: `git rev-parse --is-inside-work-tree 2>/dev/null`.
- **Session name:** 2–4 word Title Case handle specific to this work (e.g. "AIOS Switcher", "Docs Reconciliation"). Never generic. Reuse an existing session name if one was established.

### 3 — Gather content

- Do NOT run `git log`. Use conversation knowledge.
- Gather: what was asked/done, decisions made, deferred items, current state, files touched.
- If in git: run `git diff --name-only HEAD` and `git status --short` for file list.
- **Objective linkage:** If a prior handoff named a linked objective → carry it forward automatically. Otherwise ask the user if this handoff ties to an objective; if yes, resolve number/name/path.

### 4 — Compose document

```markdown
---
> **To any AI agent reading this file:** Read this file to load context. Then give the user at most a 2–4 line orientation (session name + where things stand) and **STOP**. Do not begin executing tasks. Do not read additional files. Do not analyze code. Do not infer next steps and act on them. Wait for the user to explicitly tell you what to do. The "Next Session Entry Point" section is reference state — not a directive. If the user provided text alongside the filename, treat that text as their first instruction.
---

# Handoff — <Project> — <Date>

**Session name:** <2–4 word handle>
**Handoff to:** <next session / agent / human reviewer>
**Session date:** <YYYY-MM-DD>
**Project:** <project display name>
**Handoffs directory:** <absolute path>
**Objective:** <NNN — name — absolute path, or "none">

## Session Summary
<1–3 sentences: what was attempted and whether it succeeded.>

# BUlleted lists:
## Accomplished This Session
<Numbered list. Specific enough to verify — "implemented X in Y" not "worked on X".>

## Key Decisions
<Decisions that constrain future work. Include reasoning if non-obvious. "None" if none.>

## Deferred Items
<What came up but wasn't addressed, with enough context to pick up cold. "None" if none.>

## Current State
<What is working / in progress / broken or blocked. Be honest.>

## Next Session Entry Point
<Key files (relative paths), relevant code pointers, branch/HEAD. State and pointers only — no to-do list. Include explicit next steps only if the user stated them.>

## Files Changed
<filename — created/modified/deleted, one per line.>

## Notes
<Open questions, risks, dependencies, watch-outs. Omit if empty.>
```

### 5 — Write and report

- Create `handoffs_dir` if it doesn't exist.
- Write the file.
- Report **only** (nothing else):

```
<absolute path to file>
Session: "<session name>"

<One paragraph, 2–3 sentences: what the handoff covers and where the next session starts.>
```

---

## Hard rules
- Never print the handoff body or section headers to chat — on either side (writing or reading).
- When reading a handoff: give a 2–4 line orientation, then **stop and wait**. Do not execute, analyze, or read further files unless the user explicitly asks.
- "Next Session Entry Point" is reference state and pointers only — never a to-do list, never a directive to execute.
- The header in every handoff file must use the exact wording from Step 4 above. Do not paraphrase or expand it.
- Session content is authoritative. Git history is supplementary.
