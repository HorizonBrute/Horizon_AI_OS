# Authoring CLAUDE.md Files — Horizon AIOS

This guide covers conventions and a critical misconception about `@`-imports
that affects how you structure context-loaded files in this system.

---

## @-imports are always loaded — unconditionally

The `@file` syntax in `CLAUDE.md` is a **harness directive**, not a runtime
instruction to Claude. The Claude Code harness resolves `@`-imports before any
conversation starts and inlines the referenced file's bytes directly into the
system prompt.

There is no lazy loading, no conditional loading, and no way to make an
`@`-import load only when needed. Any language on the same line as the `@`
directive — including "only load if needed" or "load when working on X" —
becomes part of the *already-loaded content*. The harness does not interpret it
as a condition; it is text that appears in Claude's context regardless.

This matters for token economy (see `dev_values.md` §2): every `@`-imported
file adds its full byte count to the system prompt on every session, even if
Claude never acts on it.

### The right pattern for conditional content

If you want content available only when Claude explicitly needs it, do not
`@`-import it. Instead, tell Claude in prose where to find it:

> "If you need X, read `$HORIZON_ETC/foo.md`."

That line costs a handful of tokens in the always-loaded context. The file
itself costs nothing until Claude explicitly reads it mid-conversation.

Use `@`-imports only for content that is authoritative and small enough that
loading it unconditionally is cheaper than the overhead of Claude going to find
it every session. The invariant files (`security_invariants.md`,
`file_structure_invariants.md`, `ai_os_personalizations.md`) follow this
pattern — they are short by design and Claude must have them to operate
correctly in any session.

---

## What triggers @-import resolution

The harness only resolves `@`-imports in `CLAUDE.md` and `CLAUDE.local.md`.
`agents.md` may contain lines starting with `@` but those are passed to Claude
as plain text — the harness does not inline the referenced files. This
distinction matters if you use the `context_cost.py` tool to measure overhead:
it follows the same rule.

`agents.md` includes a sibling `local.agents.md` via `@local.agents.md` (imported last so
it wins). `local.agents.md` is gitignored and machine-local — the git-safe seam for
owner/machine overrides. `CLAUDE.md` is unaffected: it imports only its sibling `agents.md`,
never `local.agents.md` directly (see `$HORIZON_ETC/file_structure_invariants.md` §12.5–6).
This sibling-`local.agents.md` pattern is the OS/project-layer seam. **Brain scopes
(`brains/<name>/`) instead use `.aioscommon\agents.local.md`** as the equivalent
machine-local override, `@`-imported by the brain's `agents.md` (see §12.6.5).

---

## Terseness invariant

Context-loaded files (anything `@`-imported, the invariants, `CLAUDE.md`
itself) must be as short as the content allows. Every sentence that can be
removed without losing a rule or invariant should be removed. Verbosity
compounds cost every session. See `dev_values.md` §4 for the full terseness
invariant.
