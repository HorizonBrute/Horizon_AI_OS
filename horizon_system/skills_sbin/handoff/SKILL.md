---
name: handoff
description: Write a structured handoff document capturing current session state. Use when the user types /handoff, asks to "write a handoff", "produce a handoff document", "save session state", or wants to capture current state for a future session.
tools: Bash, Read, Write, Glob, Grep
---

# Skill: /handoff

Capture the current session state and write a structured handoff document so a future session (or human reviewer) can orient themselves immediately.

---

## When to invoke

The user types `/handoff` or asks you to "write a handoff", "produce a handoff document", or "save session state."

---

## Step-by-step execution

Execute these steps in order. Do not skip any step.

### Step 1 — Resolve the handoffs directory

1.1 Identify the current working directory (`cwd`).

1.2 Search upward from `cwd` for a file named `aios_overrides.md`, stopping when you reach `$HORIZON_ROOT` (the value of the `HORIZON_ROOT` environment variable) or the filesystem root, whichever comes first. Check each directory in the upward chain: `cwd`, then its parent, then its parent, and so on.

1.3 If `aios_overrides.md` is found, parse it for the `handoffs_dir` key. The file uses a simple `key: value` format — find the line beginning with `handoffs_dir:` and extract the value. If the key is present and non-empty, use that path as the handoffs directory.

1.4 If `aios_overrides.md` is not found, or does not contain `handoffs_dir`, use the default: `$HORIZON_ROOT/handoffs/` (the value of the `HORIZON_ROOT` environment variable + `/handoffs/`).

1.5 If `aios_overrides.md` contains a `project_display_name` key, use that value as the project name in the handoff header. Otherwise, derive the project name from the basename of the current working directory.

### Step 2 — Derive metadata

2.1 Get the current date and time. Use the format `YYYY-MM-DD` for the date field and `HHMMSS` for the filename timestamp. Run: `date +%Y-%m-%d` and `date +%H%M%S` (or equivalent for the platform).

2.2 Derive the filename: `YYYY-MM-DD_HHMMSS_<project-name>.md` where `<project-name>` is the value from step 1.5, lowercased and with spaces replaced by hyphens.

2.3 Construct the full output path: `<handoffs_dir>/<filename>`.

2.4 Check whether this session is inside a git repository: run `git rev-parse --is-inside-work-tree 2>/dev/null`. Note the result — it affects the "Files Changed" section.

### Step 3 — Gather session content

3.1 **Do not run `git log`.** Session content comes from your knowledge of what happened in this conversation, not from git history.

3.2 Review the conversation to identify:
- What the user asked for and what was accomplished
- Decisions made that are non-obvious or that constrain future work
- Things that came up in discussion but were not implemented (deferred items)
- The current state of the work — what is working, what is in progress, what is broken or incomplete
- Files that were created, edited, or deleted during this session

3.3 For files changed: if inside a git repo, run `git diff --name-only HEAD` and `git status --short` to get a quick list of modified/staged files. Do not run deep git log. If not in a git repo, list files from memory based on what was done in this session.

3.4 Ask the user (or infer from context) who this handoff is addressed to: another session, a specific agent, a human reviewer. If unclear, default to "next session."

3.5 Determine objective linkage (see the `/objective` skill — objectives hold the durable, multi-session goal this work serves):
- If this session was started from a handoff that named a linked objective (an "Objective" field with a number/name/path), **carry that same objective forward automatically — do not ask.** Handoffs chain the objective.
- Otherwise, ask the user: "Is this handoff tied to an objective?" If yes, resolve the objective's number, name, and absolute file path (offer to list existing objectives from the objectives index). If the user declines or none exists, record the objective as "none."

### Step 4 — Compose the handoff document

Write the document using the template below. Fill every section honestly — do not pad thin sections, do not omit sections that have content.

```markdown
---
> **To any AI agent reading this file:** If you have received this handoff with no other instructions, that is a directive from the user to orient yourself and begin working on it. Read the full document, internalize the current state, and proceed from the "Next Session Entry Point" section. If an **Objective** is listed below, read that objective file first — it holds the durable goal this handoff serves. If the user has provided text alongside or after the handoff filename, treat that as additional instructions layered on top of this handoff — follow both.
---

# Handoff — <Project> — <Date>

**Handoff to:** <next session / specific agent / human reviewer>
**Session date:** <YYYY-MM-DD>
**Project:** <project display name>
**Handoffs directory:** <absolute path used>
**Objective:** <NNN — name — absolute path to objective file, or "none">
<If an objective is linked, the reader should open that file first for the durable goal. Carry this same objective into the next handoff.>

## Session Summary
<1-3 sentences — what this session was about and its outcome. Be specific enough that someone reading cold understands what was attempted and whether it succeeded.>

## Accomplished This Session
<Numbered list of concrete things completed. Each item should be specific enough to verify — not "worked on X" but "implemented X in file Y" or "decided Z".>

## Key Decisions
<Decisions made this session that constrain or inform future work. Include the reasoning if it was non-obvious. If no significant decisions were made, say so briefly.>

## Deferred Items
<Things that came up but were not addressed. Include enough context that a future session can pick them up without having to reconstruct the background. If nothing was deferred, say so.>

## Current State
<Where things stand right now. What is working, what is in progress, what is broken or blocked. Be honest about incomplete work.>

## Next Session Entry Point
<Specific guidance: what file or document to read first, what question to answer first, what task to start with. This section should give a future session an unambiguous starting point.>

## Files Changed
<List of files created, modified, or deleted this session. Use git diff --name-only output if available; otherwise list from memory. Keep it brief — filenames and a one-word action (created/modified/deleted) is sufficient.>

## Notes
<Anything else worth preserving that does not fit above: open questions, risks, dependencies, things to watch out for.>
```

### Step 5 — Write the file

5.1 Ensure the handoffs directory exists. Create it if it does not: `mkdir -p <handoffs_dir>` (or platform equivalent).

5.2 Write the composed document to the full output path from step 2.3.

5.3 Report to the user:
- A single paragraph summarizing what was captured (the session in one sentence, plus what's next)
- The exact filename that was written (full absolute path)
- Which `aios_overrides.md` was used (if any), or that the default directory was used

---

## Notes for the executing agent

- Session content is authoritative. You were in the conversation — use what you know. Git history is supplementary at best and irrelevant when not in a git repo.
- The handoff document is read cold by a future session or human. Write it for someone with zero context from this conversation.
- Err on the side of specificity in "Next Session Entry Point." Vague guidance ("continue the work") is useless. Specific guidance ("read $HORIZON_ETC/file_structure_invariants.md, then open X and address the TODO at line 47") is valuable.
- If the session was exploratory or inconclusive, say so plainly in Session Summary and Current State.
