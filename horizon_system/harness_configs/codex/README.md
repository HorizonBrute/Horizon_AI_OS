# Codex Harness Config

Codex reads `agents.md` at the project root for agent instructions.
The AIOS `agents.md` at `$HORIZON_ROOT/agents.md` serves this role automatically.

## Per-project override

To customize instructions for a specific project under $HORIZON_ROOT, place an
`agents.md` in that project's root directory. Codex will use the nearest one.

## Configuration

Place any Codex-specific configuration (API settings, model selection, tool permissions)
in this directory. Reference `$HORIZON_SYSTEM` (the runtime env var) for the absolute path to
`horizon_system/` — the harness expands this at runtime, not at bootstrap.

## Status

Community contribution welcome. See `horizon_system/license/CONTRIBUTING.md`.
