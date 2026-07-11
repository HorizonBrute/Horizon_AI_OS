# =============================================================================
# Horizon.AIOS Monitor Watchdog Runner
# Invoked hourly by the AIOSMonitorWatchdog scheduled task. If the filesystem
# monitor (horizon_aios_monitor.py) is not running, (re)start it via the
# AIOSMonitor task. Keeps audit logging alive between reboots after a crash.
# ASCII-only (PS 5.1 + non-BOM UTF-8 corrupts non-ASCII).
# =============================================================================

$ErrorActionPreference = "Stop"

$MonitorTask = "AIOSMonitor"

# Is a python process currently running horizon_aios_monitor.py?
$running = @(
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*horizon_aios_monitor.py*' }
).Count -gt 0

if ($running) {
    Write-Output "[OK] horizon_aios_monitor.py is running - no action."
    exit 0
}

Write-Output "[WARN] horizon_aios_monitor.py not running - starting task '$MonitorTask'."
& schtasks /Run /TN $MonitorTask | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Output "[OK] Started '$MonitorTask'."
    exit 0
} else {
    Write-Output "[ERR] Failed to start '$MonitorTask' (schtasks exit $LASTEXITCODE)."
    exit 1
}
