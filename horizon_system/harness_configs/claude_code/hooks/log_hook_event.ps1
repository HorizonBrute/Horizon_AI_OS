# Appends a structured line to $HORIZON_ROOT/logs/hooks/hook_events.log.
# Usage: log_hook_event.ps1 -Event <name> [-SessionId <id>]
param(
    [Parameter(Mandatory)][string]$Event,
    [string]$SessionId = ""
)
$horizonRoot = if ($env:HORIZON_ROOT) { $env:HORIZON_ROOT } else {
    Split-Path (Split-Path (Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent) -Parent) -Parent
}
$logDir = Join-Path $horizonRoot "logs\hooks"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logFile = Join-Path $logDir "hook_events.log"
$ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
$sessionPart = if ($SessionId) { " session=$SessionId" } else { "" }
Add-Content -Path $logFile -Value "[$ts] [$Event]$sessionPart"
