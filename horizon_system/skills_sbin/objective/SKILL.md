---
name: objective
description: Create and maintain durable, multi-session objectives that hold long-term context across sessions. Use when the user types /objective, asks to "create an objective", "make a new objective", "list objectives", "show objective N", or "update objective N". A bare /objective (no args) surfaces the conversation's active objective (from a handoff or an earlier mention), else lists existing ones, else offers to create one. Complementary to /handoff — handoffs are point-in-time, objectives are the durable goal they chain back to.
tools: Read, Write, Edit, Glob, Bash
---

# Skill: /objective

**Model preference:** `#lowcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

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
| `/objective` (no arguments) | **default** — surface the conversation's active objective, else list, else offer to create (see Default) |
| `/objective <description>` | **create** with an auto-generated title |
| `/objective named "The Title" "description"` | **create** with an explicit title |
| `/objective list` | **list** |
| `/objective show <N\|name>` or `/objective <N>` (bare number) | **show** |
| `/objective update <N\|name> <note>` | **update** |

Check the **no-arguments** case first: empty input is the Default, not a create with an empty description. If ambiguous beyond that, ask the user which they meant. Then follow the matching section below.

---

## Default (bare `/objective`, no arguments)

A raw `/objective` orients the user on what they are working toward: surface the
**active objective** if this conversation has one, otherwise list, otherwise offer
to create. It never silently creates an empty objective.

D.1 **Identify the objective associated with this conversation**, in priority order:
   1. A handoff read into this session that names an objective — the handoff's
      `Objective:` field carries the number, name, and/or file path. If it points
      to a real objective (not "none"/empty), that is the active one.
   2. An objective the user referenced earlier in this conversation — one they
      created, showed, updated, or named explicitly.
   If exactly one is identified, treat it as the **active objective**. If two or
   more compete, list those and ask which to focus.

D.2 **Resolve and read the index** (Step 1), and glob `<objectives_dir>/*.md` to
   know what exists on disk.

D.3 Branch:
   - **Active objective found** → run **Show** on it (load it, give the 2–4 line
     orientation). If other objectives also exist, add a one-line
     `other open objectives: N, M` pointer so they are discoverable.
   - **No active objective, but objectives exist** → run **List**, then ask whether
     to continue one (`/objective show N` / `/objective update N <note>`) or start a
     new one.
   - **No objectives at all** → there is nothing to show; **seek to create one**.
     Ask the user for the goal in one line — what they are working toward and why it
     matters — then follow **Create**. Do not invent the goal: if the user has not
     stated one and the conversation has no clear durable goal, ask first.

D.4 The no-echo rule applies — never paste objective bodies into chat (see Notes).

---

## Create

C.1 Ensure `<objectives_dir>` exists; create if missing (`mkdir -p`). If `index.md` is absent, create it with this header:

```markdown
# Objectives Index

Durable, multi-session goals. Reference by number or name. Ephemeral by design —
objectives not updated within the retention window are pruned by horizon_aios_maintain_logs.py
(AIOS_OBJECTIVES_MAX_DAYS). This is intentional; there is no task tracking here.

| # | Name | Created | Description |
|---|------|---------|-------------|
```

C.2 Determine the number. Read `index.md` for the highest integer in the `#` column; also glob `<objectives_dir>/*.md` for `NNN_*.md` filenames. Next number is `max(all found) + 1`, or `1` if none exist. Zero-pad to three digits (`001`, `002`, ...).

C.3 Determine the **title** and **slug** — every objective has both:

- **Title** — the human-readable display name, shown in the file heading and the index `Name` column. Title Case, **2–5 words**, specific and readable. E.g. "Getting Horizon.AIOS Shippable", "Second-Brain Layer", "Audit Logging". This is the "nice" name the user reads.
- **Slug** — the title normalized for the filename only: lowercase, spaces → hyphens, drop anything not `[a-z0-9-]`, collapse repeated hyphens. E.g. "Getting Horizon.AIOS Shippable" → `getting-horizon-aios-shippable`.

Resolve the title by form:
- **Explicit** (`named "The Title" "description"`): use the given title verbatim as the Title; derive the slug from it.
- **Description-only**: generate a short, readable Title (Title Case, 2–4 words, drop filler) from the description, then derive the slug. E.g. "Build the syncable second-brain layer" → Title "Second-Brain Layer", slug `second-brain-layer`.

C.4 Get today's date: `date +%Y-%m-%d`.

C.5 Create the objective file at `<objectives_dir>/NNN_<slug>.md` using this template. Fill the sections you have signal for; leave a one-line placeholder in the rest rather than padding. There is **no status field** — objectives are ephemeral and retire by going stale, never by being closed.

```markdown
# Objective NNN — <Title>

**Created:** YYYY-MM-DD
**Description:** <one-line description>

## Goal
<The durable goal AND why it matters — the long-term context that should survive
across sessions. Write enough that a cold reader understands the destination and
the stakes, not just the next step. Expand this with the user if the description
is thin.>

## Success criteria
<- [ ] concrete, verifiable outcomes that define "done enough". Use checkboxes so
progress is visible across sessions. Omit this section if the goal is open-ended.>

## Current state
<Where things stand now — what is in place, what remains. The living section;
refreshed on update. One short paragraph or a tight bullet list.>

## Linked handoffs
<- relative paths to the handoffs that advanced this objective, appended as they
land. Empty at creation.>

## Log
- YYYY-MM-DD — created
```

C.6 Append a row to the index table:
```markdown
| N | <Title> | YYYY-MM-DD | <one-line description> |
```

C.7 Report the number, title, and absolute file path — three lines, nothing more. Tell the user they can reference it as `/objective show N` and tie handoffs to it. **Do not echo the template or the file body into chat.**

---

## List

L.1 Read `<objectives_dir>/index.md` and print the table. If the directory or index is absent, tell the user there are no objectives yet.

---

## Show

S.1 Resolve the target: a bare number or `show N` → `NNN_*.md`; a name → the matching file. Glob `<objectives_dir>/*.md` to find it.

S.2 Read the file so its content enters your working context. **Do not echo the file body into chat** — reading it is what loads the context; pasting it back is redundant and buries the signal. Instead give the user a tight orientation (≈2–4 lines): the title, the one-line description, where it stands now (from Current state), and any open success criteria. The full text is on disk if they want it verbatim. Do not modify the file (show is read-only — reading does not refresh the retention clock; only `update` does).

S.3 If no match, list available objectives (run List) so the user can pick.

---

## Update

U.1 Resolve the target file as in Show.

U.2 Append a dated line to the `## Log` section: `- YYYY-MM-DD — <note>`. If the update materially changes the long-term goal or where things stand, also edit `## Goal` / `## Current state` with the user.

U.3 Writing the file refreshes its modification time, keeping it from being pruned. Confirm the appended note to the user in one line — do not reprint the file.

---

## Notes for the executing agent

- **Never echo a full objective (or the template) into chat.** Reading the file loads it into your context; a 2–4 line summary is the user-facing deliverable, the file on disk is the source of truth. This mirrors the `/handoff` no-echo rule and exists for the same reason: dumping the body bloats context and buries the useful signal.
- Title vs. slug vs. number: the **number** is the stable handle (use it to disambiguate). The **title** is the human-readable display name. The **slug** exists only to form the filename. Names can collide loosely across time; numbers do not.
- Keep objective files tight and durable — loaded on demand, but bloat costs tokens every time they are shown or chained. The richer template is a frame, not a quota: capture the goal and current state, not a play-by-play.
- There is **no status/done/close concept** — none. Do not add a Status field to files or the index. The user retires an objective by ceasing to reference it; retention is age-based.
- Retention is handled externally by `$HORIZON_SYSTEM/sbin/horizon_aios_maintain_logs.py` (`AIOS_OBJECTIVES_MAX_DAYS`). `index.md`, `.gitkeep`, and `README.md` are never pruned. Do not implement pruning here.
- The objectives directory is machine-local and gitignored, like `handoffs/`.
