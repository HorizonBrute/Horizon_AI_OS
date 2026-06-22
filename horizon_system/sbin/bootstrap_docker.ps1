# =============================================================================
# Horizon AIOS - Docker Bootstrap (PowerShell)
#
# Runs the standard bootstrap in Docker mode:
#   - Non-interactive (all prompts auto-accepted)
#   - Skips shell profile instructions (env vars are set in the Dockerfile)
#   - Skips sync schedule setup (containers are refreshed by rebuild/pull)
#
# AIOS Docker images are Linux containers; this wrapper exists so a Windows
# host can drive the same container build/run path that bootstrap_docker.sh
# drives on Linux/macOS hosts. Mirrors bootstrap_docker.sh.
#
# Usage:
#   .\bootstrap_docker.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

$env:AIOS_DEPLOY_MODE = "docker"

& "$PSScriptRoot\bootstrap.ps1" --yes @args
exit $LASTEXITCODE
