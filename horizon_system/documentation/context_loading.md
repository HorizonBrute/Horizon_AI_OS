# Context Loading — Horizon AIOS

At the start of every Claude Code session, the harness assembles a system prompt from files on disk. That assembled content is what Claude knows before the user types anything. Context loading is the process that determines which files go in, in what order, and how large that pre-loaded payload is.

This is a fixed-cost tax: every byte in the auto-loaded files is paid on every session, even if Claude never acts on it. Understanding and controlling that cost is part of maintaining a healthy AIOS install.

---

## The loading layers

Claude Code loads all `CLAUDE.md` files from `~/.claude/` down to the current working directory — not just the nearest one. They stack. Outermost (most global) first, innermost last.

| Layer | File | Location | Scope |
|---|---|---|---|
| User-global | `CLAUDE.md` | `~/.claude/CLAUDE.md` | All projects for this OS user |
| Project harness | `CLAUDE.md` | `$HORIZON_ROOT/.claude/CLAUDE.md` | Thin entry point; imports the project root file |
| Project root | `CLAUDE.md` | `$HORIZON_ROOT/CLAUDE.md` | AIOS-wide rules; imports `agents.md` |
| Cross-harness | `agents.md` | `$HORIZON_ROOT/agents.md` | Harness-agnostic agent instructions |
| Subdirectory | `CLAUDE.md` | Any directory between root and CWD | Active when CWD is inside that directory |
| Brain | `CLAUDE.md` | Brain home directory | Applies when a session runs as that brain |
| Local override | `CLAUDE.local.md` | Same locations as `CLAUDE.md` | Machine-local; gitignored; loaded when present |

`CLAUDE.local.md` files are loaded alongside their matching `CLAUDE.md` at the same level. They are machine-local overrides (paths, API keys, local conventions) that must not be committed.

---

## @-imports

The `@file` syntax in `CLAUDE.md` is a **harness directive**, not a runtime instruction to Claude. The harness resolves `@`-imports before any conversation starts and inlines the referenced file's bytes directly into the system prompt.

Key properties:

- Inlining is unconditional. There is no lazy loading and no conditional loading. Any language on the same line as the `@` directive — including "only load if needed" — becomes part of the already-loaded content. The harness does not interpret it as a condition.
- Only `CLAUDE.md` and `CLAUDE.local.md` trigger harness `@`-import resolution. `agents.md` may contain lines starting with `@` but those are passed to Claude as plain text; the harness does not inline the referenced files.
- `@`-imports are recursive. If `CLAUDE.md` imports a file, and that file contains `@`-references, the harness continues resolving them — because the resolution context started from a `CLAUDE.md`. The harness does not re-enter `@`-import resolution on `agents.md` files it encounters as standalone auto-loads.

**The right pattern for optional content:** If you want a file available only when Claude explicitly needs it, do not `@`-import it. Instead, tell Claude where to find it in prose:

> "If you need X, read `$HORIZON_ETC/foo.md`."

That line costs a handful of tokens in the always-loaded context. The file itself costs nothing until Claude reads it mid-conversation.

---

## What is loaded in a standard AIOS session

The following is the actual load order for a session started at `$HORIZON_ROOT`. Numbers are measured by `context_cost.py`.

| File | How loaded | ~Tokens |
|---|---|---|
| `~/.claude/CLAUDE.md` | Auto (user-global) | 28 |
| `$HORIZON_ROOT/.claude/CLAUDE.md` | @-import from above | 7 |
| `$HORIZON_ROOT/CLAUDE.md` | @-import from above | 47 |
| `$HORIZON_ROOT/agents.md` | @-import from `CLAUDE.md` | 7 |
| `$HORIZON_SYSTEM/ai_os_etc/horizon_aios_agents.md` | @-import from `agents.md`* | 606 |
| `$HORIZON_ROOT/.claude/CLAUDE.aios-dev.md` | @-import from `~/.claude/CLAUDE.md` | 153 |
| **Total** | | **848** |

*Note: `agents.md` itself does not trigger harness @-import inlining (it is not a `CLAUDE.md`). However, `$HORIZON_ROOT/CLAUDE.md` imports `agents.md`, and because `CLAUDE.md` is the import-resolving file, the harness follows its imports recursively — including `agents.md`'s own `@`-references. The net effect is that `horizon_aios_agents.md` is inlined. `context_cost.py` reflects the same rule: it recurses into files imported by `CLAUDE.md`/`CLAUDE.local.md` but not into files imported by `agents.md` directly.

`CLAUDE.aios-dev.md` is owner/maintainer-specific. Brains do not load it — their `brain_CLAUDE.md.template` chains only the runtime config.

If CWD is inside a brain's home directory, the brain's `CLAUDE.md` is added on top of the above, at the innermost level.

---

## Configuring each layer

**`~/.claude/CLAUDE.md` (user-global)**
User-specific preferences that apply across all projects. Should be minimal — it is loaded in every session, including sessions in unrelated projects. Keep content here only if it genuinely applies everywhere.

**`$HORIZON_ROOT/.claude/CLAUDE.md` (project harness entry point)**
A thin file. Its sole job is to import `$HORIZON_ROOT/CLAUDE.md`. Do not add content here; extend `CLAUDE.md` instead.

**`$HORIZON_ROOT/CLAUDE.md` (project root)**
AIOS-wide rules, `@`-import of `agents.md`, and prose pointers to the invariant documents. This is the right place for rules Claude must have in every AIOS session. The invariant documents (`security_invariants.md`, `file_structure_invariants.md`, `ai_os_personalizations.md`) are referenced as prose pointers (not `@`-imported) because Claude can read them on demand; loading them unconditionally would add significant tokens per session.

**`$HORIZON_ROOT/agents.md` (cross-harness)**
Harness-agnostic agent instructions: orchestration model, session-start checklist, skills conventions, commit rules. This file is consumed by Claude Code and other harnesses (Codex, OpenHands). It `@`-imports its sibling `local.agents.md` last — the machine-local override seam (see §12.6 of `$HORIZON_ETC/file_structure_invariants.md`). `local.agents.md` is gitignored, materialized by `aios setup`, and is the right place for owner/machine-specific instructions that must not ship. Do not put `@`-imports here with the intent that they will be inlined — they will not be. If you need a file inlined, `@`-import it from a `CLAUDE.md`.

**Brain `CLAUDE.md`**
Brain-specific persona, memory conventions, scope restrictions, and any tools or context the brain needs at session start. Brains load the AIOS base layers above plus this file. Keep it short: token economy applies to brain sessions too. See `$HORIZON_ETC/security_invariants.md §2` for why brain sessions are isolated from the owner's config.

**`CLAUDE.local.md` (any level)**
Machine-local overrides: paths that differ by machine, API keys, local-only conventions. Must not be committed. Add to `.gitignore`. This is the right way to override an AIOS config without touching committed files.

---

## Token economy

Every byte in the auto-loaded files costs tokens on every session. It is a fixed tax that runs before the user types anything.

The current baseline overhead for this AIOS install is **~848 tokens / 4.9 KB** (measured at `$HORIZON_ROOT`).

Rules:
- Keep the always-loaded total under 1000 tokens if possible.
- At 2000 tokens, review and trim before adding more.
- The terseness invariant: context-loaded files (anything `@`-imported, the invariants, `CLAUDE.md` itself) must be as short as the content allows. Every sentence that can be removed without losing a rule should be removed.
- Do not put lengthy explanations, examples, or reference material in auto-loaded files. Put them in files Claude can read on demand, and point to them in prose.

---

## Measuring and managing overhead

**`context_cost.py`** — `$HORIZON_SYSTEM/bin/context_cost.py`

Walks the ancestor chain from a target path to the filesystem root, collecting every `CLAUDE.md`, `CLAUDE.local.md`, and `agents.md` the harness would load, plus all `@`-imports. Reports KB, words, and estimated token count per file and as a total.

```
python "$HORIZON_SYSTEM/bin/context_cost.py" [path]
python "$HORIZON_SYSTEM/bin/context_cost.py" [path] --json
```

`path` defaults to CWD. `--json` emits machine-readable output.

**`/context-cost` skill** — invoke inside a Claude Code session for an instant overhead report. It runs `context_cost.py --json`, formats the output as a table, and flags thresholds:
- >= 1000 tokens: `[NOTE] Moderate context load`
- >= 2000 tokens: `[WARN] High context load`

**Workflow:** Run `context_cost.py` after adding or modifying any `CLAUDE.md` or `@`-import. Confirm the overhead stayed in budget before committing.

---

## Related documents

| Document | Purpose |
|---|---|
| `documentation/authoring/claude_md_authoring.md` | Detailed authoring rules and the @-import unconditional-load clarification |
| `documentation/utilities.md` | Full utility reference including `context_cost.py` |
| `$HORIZON_ETC/security_invariants.md` | Why brain `CLAUDE.md` files are scoped — brain isolation model |
| `$HORIZON_ETC/file_structure_invariants.md` | Canonical file locations for every AIOS path |
