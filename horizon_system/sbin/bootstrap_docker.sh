#!/usr/bin/env bash
# =============================================================================
# Horizon AIOS — Docker Bootstrap
#
# Runs the standard bootstrap in Docker mode:
#   - Non-interactive (all prompts auto-accepted)
#   - Skips shell profile instructions (env vars are set in the Dockerfile)
#   - Skips sync schedule setup (containers are refreshed by rebuild/pull)
#
# Executed automatically during `docker build` (see Dockerfile).
# Safe to run manually inside a running container.
#
# Usage (inside container):
#   bash /aios/horizon_system/sbin/bootstrap_docker.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export AIOS_DEPLOY_MODE=docker

exec bash "$SCRIPT_DIR/bootstrap.sh" --yes "$@"
