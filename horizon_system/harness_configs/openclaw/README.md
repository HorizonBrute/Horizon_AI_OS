# OpenClaw Harness Config

OpenClaw is a self-hosted multi-channel gateway that routes messages from chat apps (WhatsApp, Slack, Discord, Telegram, etc.) to AI coding agents.

## How it reads AIOS instructions

OpenClaw does not use an instruction file like `agents.md` or `CLAUDE.md`. All agent behavior is configured through `~/.openclaw/openclaw.json` (JSON5 format). There is no project-level instruction file concept — per-agent behavior is shaped through the `agents.list` entries and the `skills` system in the central config.

To inject AIOS context into OpenClaw agents, embed the relevant system prompt content directly in the `agents` section of your config, or implement a custom skill that reads from `$HORIZON_ROOT`.

## Configuration

OpenClaw reads `~/.openclaw/openclaw.json` (JSON5 — supports comments and trailing commas). All fields are optional; safe defaults apply when omitted.

Place your OpenClaw-specific configuration in this directory as `openclaw.json` (or `openclaw.json5`). A template is provided at `HORIZON_BIN_PATH/harness_configs/openclaw/openclaw.json.template`.

Key top-level sections:

- `gateway` — server port, auth token, TLS
- `agents` — model selection, defaults, per-agent identity
- `channels` — per-provider credentials and allowlists
- `models` — provider definitions and model allowlists
- `mcp` — Model Context Protocol server definitions
- `skills` — skill loading and extra skill directories
- `hooks` — webhook integrations
- `cron` — background job scheduling
- `logging` — log level and file paths

## Status

Community contribution welcome. See `horizon_bin/license/CONTRIBUTING.md`.
