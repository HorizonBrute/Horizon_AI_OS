---
name: objective
description: Create and maintain durable, multi-session objectives that hold long-term context across sessions. Use when the user types /objective, asks to "create an objective", "make a new objective", "list objectives", "show objective N", or "update objective N". Complementary to /handoff — handoffs are point-in-time, objectives are the durable goal they chain back to.
tools: Read, Write, Edit, Glob, Bash
---

# Skill: /objective

Objectives are durable-but-ephemeral notepads for major goals spanning multiple sessions. They hold long-term context — the goal and why it matters — that a single handoff is too short-lived to carry.

A small set of primitives, **not** a task tracker. No status, no backup, no enforced lifecycle, no completion step. When the user stops referencing an objective it goes stale and is eventually pruned (see Notes). By design.

How context travels: a handoff tied to an objective writes the objective's number, name, and file path into the handoff. The next session reads the handoff, follows the pointer, and reads the objective back into context. Handoffs chain the objective forward; the objective itself just sits on disk.

---

## When to invoke

The user types `/objective ...` or asks to create, list, show, or update an objective.

---

## Step 1 — Resolve the objectives directory

1.1 Identify the current working directory (`cwd`).

1.2 Search upward from `cwd` for `aios_overrides.md`, stopping at `$HORIZON_ROOT` (the `HORIZON_ROOT` env var) or the filesystem root, whichever comes first.

1.3 If found, parse it for an `objectives_dir:` line (simple `key: value` format). If present and non-empty, use that path.

1.4 Otherwise use the default: `$HORIZON_ROOT/objectives/`.

1.5 The index file is always `<objectives_dir>/index.md`.

---

## Step 2 — Dispatch on the subcommand

Parse the user's input after `/objective`:

| Form | Action |
|---|---|
| `/objective <description>` | **create** with an auto-generated name |
| `/objective named "the_name" "description"` | **create** with an explicit name |
| `/objective list` | **list** |
| `/objective show <N\|name>` or `/objective <N>` (bare number) | **show** |
| `/objective update <N\|name> <note>` | **update** |

If ambiguous, ask the user which they meant. Then follow the matching section below.

---

## Create

C.1 Ensure `<objectives_dir>` exists; create if missing (`mkdir -p`). If `index.md` is absent, create it with this header:

```markdown
# Objectives Index

Durable, multi-session goals. Reference by number or name. Ephemeral by design —
objectives not updated within the retention window are pruned by maintain_logs.py
(AIOS_OBJECTIVES_MAX_DAYS). This is intentional; there is no task tracking here.

| # | Name | Created | Description |
|---|------|---------|-------------|
```

C.2 Determine the next number. Read `index.md` for the highest integer in the `#` column; also glob `<objectives_dir>/*.md` for `NNN_*.md` filenames. Next number is `max(all found) + 1`, or `1` if none exist. Zero-pad to three digits (`001`, `002`, ...).

C.3 Determine the name:
- **Explicit form** (`named "the_name" "description"`): use the given name verbatim, normalized — lowercase, spaces and hyphens to underscores, strip anything not `[a-z0-9_]`.
- **Description-only form**: generate a SHORT name — lowercase snake_case, **2 words target, 3 maximum**, drop filler words. E.g. "Build the syncable second-brain layer" → `second_brain`; "Migrate audit logging to structured JSON" → `audit_logging`.

C.4 Get today's date: `date +%Y-%m-%d`.

C.5 Create the objective file at `<objectives_dir>/NNN_<name>.md`:

```markdown
# Objective NNN — <name>

**Created:** YYYY-MM-DD
**Description:** <one-line description>

## Goal
<The durable goal and why it matters — the long-term context that should survive
across sessions. Write enough that a cold reader understands the destination, not
just the next step. Expand this with the user if the description is thin.>

## Log
- YYYY-MM-DD — created
```

C.6 Append a row to the index table:
```markdown
| N | <name> | YYYY-MM-DD | <one-line description> |
```

C.7 Report the number, name, and absolute file path. Tell the user they can reference it as `/objective show N` and tie handoffs to it.

---

## List

L.1 Read `<objectives_dir>/index.md` and print the table. If the directory or index is absent, tell the user there are no objectives yet.

---

## Show

S.1 Resolve the target: a bare number or `show N` → `NNN_*.md`; a name → the matching file. Glob `<objectives_dir>/*.md` to find it.

S.2 Read the file and present it into the conversation so its context is loaded. Do not modify it (show is read-only — reading does not refresh the retention clock; only `update` does).

S.3 If no match, list available objectives (run List) so the user can pick.

---

## Update

U.1 Resolve the target file as in Show.

U.2 Append a dated line to the `## Log` section: `- YYYY-MM-DD — <note>`. If the update materially changes the long-term goal, also edit `## Goal` with the user.

U.3 Writing the file refreshes its modification time, keeping it from being pruned. Confirm the appended note to the user.

---

## Notes for the executing agent

- Keep objective files tight and durable — loaded on demand, but bloat costs tokens every time they are shown or chained. Capture the goal, not a play-by-play.
- Never invent a status/done/close concept. There is none. The user retires an objective by ceasing to reference it.
- Retention is age-based, handled externally by `$HORIZON_SYSTEM/sbin/maintain_logs.py` (`AIOS_OBJECTIVES_MAX_DAYS`). `index.md`, `.gitkeep`, and `README.md` are never pruned. Do not implement pruning here.
- The objectives directory is machine-local and gitignored, like `handoffs/`.
- Number is the stable handle. Names can collide loosely across time; disambiguate by number when both are available.
