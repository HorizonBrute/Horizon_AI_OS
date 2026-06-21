# Horizon AIOS

Horizon AIOS is a centralized, syncable AI OS configuration layer designed to be forked,
extended, and shared across machines and community members. It gives Claude Code a
consistent, version-controlled environment — hooks, sounds, statusline, permissions, and
AI instructions — reproducible on any supported machine with a single bootstrap.

## What's in This Repo

1. `.claude/` — Claude Code settings, permissions, and global AI instructions (CLAUDE.md)
2. `horizon_bin/sounds/` — audio feedback files for Claude lifecycle events
3. `horizon_bin/statusline/` — cross-platform statusline scripts with context alerts
4. `horizon_bin/harness_configs/` — portable git config and pre-commit hooks
5. `horizon_bin/scripts/` — brain provisioning and setup scripts
6. `horizon_bin/documentation/` — setup guides and system reference docs
7. `handoffs/` — session handoff documents

## Platform Support

- **Windows** — primary platform; full feature support (PowerShell statusline, sound via Media.SoundPlayer)
- **Linux** — community-targeted; sound via PulseAudio/ALSA/ffmpeg/mpg123, bash statusline
- **macOS** — community-targeted; sound via `afplay`, bash statusline

## Quick Start

1. Fork or clone this repo to your preferred root path (e.g. `C:\devroot` on Windows, `~/devroot` on Unix).
2. Run the bootstrap script:
   - **Windows:** `.\sbin\bootstrap.ps1`
   - **Linux/macOS:** `./sbin/bootstrap.sh`
3. Read the full setup guide before your first commit.

## Full Setup Guide

`horizon_bin/documentation/getting_started/ReadMeToSetupYourSystem.md`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Horizon AIOS is licensed under [AGPL-3.0](LICENSE). Forking or using this
project means operating under the terms of AGPL-3.0 — including the requirement
to release modifications under the same license if you distribute or serve them.

**Commercial use** (proprietary products, SaaS without open-sourcing modifications)
requires a separate license. See [LICENSE_COMMERCIAL.md](LICENSE_COMMERCIAL.md).
