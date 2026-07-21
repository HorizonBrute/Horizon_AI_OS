# Horizon AIOS bin/ Index

Common utilities for all AIOS users (brain-readable, OS-tier). See `$HORIZON_SYSTEM/sbin/README.md` for the privilege/boundary model.

| Utility | Description |
|---------|-------------|
| [context_cost.py](./context_cost.py) | Measure Claude Code harness context overhead (CLAUDE.md / agents.md / @-imports) for a path |
| [monitor_status.py](./monitor_status.py) | Check whether horizon_aios_monitor.py is running; prints 'running' or 'stopped' |
| [options_package_readiness.py](./options_package_readiness.py) | Static readiness checker: point at a repo path or git URL to verify it meets the Options Package Readiness Standard (PKG-* rules) before deploying it as an AIOS Options Package |
| [resolve_agent_teams.py](./resolve_agent_teams.py) | Resolve the Agent Teams in effect for a given path, walking scope cascade from cwd to AIOS root |
| [resolve_sound.py](./resolve_sound.py) | Resolve an AIOS event name to a sound file path per mute config and resolution order |
| [statusline/statusline.sh](./statusline/statusline.sh) | Horizon AIOS cross-platform statusline dispatcher; routes Claude Code JSON to platform-appropriate script |
| [statusline/statusline-command.sh](./statusline/statusline-command.sh) | Claude Code status line script showing directory, git, model, context usage, and cost (Linux/macOS) |
| [statusline/statusline-context-alerts.ps1](./statusline/statusline-context-alerts.ps1) | Claude Code status line script showing context alerts and cost (Windows PowerShell) |
