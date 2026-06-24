# Harness Memory and Per-Project State

The Claude Code harness stores per-project state — conversation **transcripts**
and the file-based **memory** the agent writes — under `~/.claude/projects/`.
By default that lives outside the AIOS, ungoverned by its gitignore,
sync-exclusion, audit-logging, and hardening rules. Horizon AIOS redirects this
state into the AIOS so it is governable and available to any harness the
operator points at the tree.

## Where memories live

The redirect points `~/.claude/projects/` at `$HORIZON_ROOT/memory/`:

```
~/.claude/projects/   ->   $HORIZON_ROOT/memory/     (symlink)
```

Inside `memory/`, the harness keeps one directory per project, named by a hash
of the project's working directory. Each per-project hash dir holds that
project's conversation transcripts plus a `memory/` subdir — the durable,
cross-session memory the agent reads and writes for that project.

`memory/` is **gitignored** — never committed, shipped, or synced. A fresh
install ships the *mechanism*, never any memory *content*.

## How the redirect works

**Owner** — `$HORIZON_SYSTEM/sbin/horizon_aios_redirect_memory.py` creates the symlink. It is
backup-first, idempotent, and supports `--dry-run`:

- It **moves** any existing content out of `~/.claude/projects/` into the memory
  root (merging), after taking a backup, then replaces `~/.claude/projects/`
  with the symlink.
- It is idempotent: if the symlink is already in place pointing at the memory
  root, it does nothing.
- Before moving, it leaves a safety copy at `~/.claude/projects.backup-<timestamp>`.

> **Run with Claude Code CLOSED.** The active session holds its own project dir
> open. Close Claude Code, run `horizon_aios_redirect_memory.py`, then restart Claude.

**Brains** — handled separately and already redirected. `horizon_aios_create_brain.py`
symlinks each brain's home `~/.claude` to its workspace `brains/<name>/.claude/`,
so a brain's `projects/` (transcripts + memory) lives inside its OWN isolated,
group-owned brain folder (accessed via the `<brain>_group` Windows group /
`<brain>` Unix account). Brains never see the owner's memory or each other's —
the same isolation boundary described in `security_invariants.md §2`.

## Why centralize it

Centralizing per-project state in the AIOS makes it:

- **Governable** — covered by the AIOS gitignore and sync-exclusion rules, so
  sensitive transcripts never leak into git or a synced cloud folder.
- **Auditable** — `$HORIZON_ROOT/.claude` and the tree around `memory/` fall
  under the filesystem monitor's watch (see `security/audit_logging.md`).
- **Cross-harness** — any harness the operator points at the AIOS reads and
  writes the same memory root, which is the bring-your-own-harness/model enabler.

## Removing the AIOS destroys the memories — back them up first

**This is the user's responsibility. The AIOS documents it; it does not
auto-rescue it.**

Memory CONTENT lives only inside `$HORIZON_ROOT/memory/`. It is gitignored, so it
exists in exactly one place on disk with no tracked or synced copy. Therefore:

- **Deleting, moving, or uninstalling the AIOS deletes the memories** along with
  the rest of the tree, unless you have copied `$HORIZON_ROOT/memory/`
  elsewhere first.
- Uninstall scripts and `horizon_aios_switch.py uninstall` remove the *machine-local
  configuration footprint* (symlinks, wrappers, registry) — they do **not**
  preserve or relocate memory content for you.
- If you want to keep your transcripts and agent memory across an uninstall,
  reinstall, or machine migration, **back up `$HORIZON_ROOT/memory/` yourself
  before removing the AIOS.** The owner redirect's
  `~/.claude/projects.backup-<timestamp>` is only a one-time pre-migration safety
  copy of whatever was there *before* the first redirect — it is not an ongoing
  backup of accumulated memory.

When in doubt, copy `$HORIZON_ROOT/memory/` to safe storage before any
destructive AIOS operation.
