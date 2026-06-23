# Appends a structured line to $HORIZON_SYSTEM/logs/hooks/hook_events.log.
# Usage: log_hook_event.ps1 -Event <name> [-SessionId <id>]
param(
    [Parameter(Mandatory)][string]$Event,
    [string]$SessionId = ""
)
# This script lives at $HORIZON_SYSTEM/harness_configs/claude_code/hooks/ -
# go up three levels to reach $HORIZON_SYSTEM.
$horizonSystem = if ($env:HORIZON_SYSTEM) { $env:HORIZON_SYSTEM } else {
    Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
}
$logDir = Join-Path $horizonSystem "logs\hooks"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir "hook_events.log"
$ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
$sessionPart = if ($SessionId) { " session=$SessionId" } else { "" }
Add-Content -Path $logFile -Value "[$ts] [$Event]$sessionPart"
