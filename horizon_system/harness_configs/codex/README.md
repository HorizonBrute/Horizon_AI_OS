# Codex Harness Config

Codex reads `agents.md` at the project root for agent instructions.
The AIOS `agents.md` at `$HORIZON_ROOT/agents.md` serves this role automatically.

## Per-project override

To customize instructions for a specific project under $HORIZON_ROOT, place an
`agents.md` in that project's root directory. Codex will use the nearest one.

## Configuration

Place any Codex-specific configuration (API settings, model selection, tool permissions)
in this directory. Use `HORIZON_SYSTEM_PATH` as a placeholder for the absolute path to
`horizon_system/` — bootstrap substitutes the real path.

## Status

Community contribution welcome. See `$HORIZON_DOCS/CONTRIBUTING.md`.
