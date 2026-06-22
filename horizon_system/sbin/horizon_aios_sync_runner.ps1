# Thin launcher for Windows Task Scheduler.
# Resolves Python and delegates to horizon_aios_sync.py.
# Lives in sbin alongside horizon_aios_sync.py.

$ScriptDir = $PSScriptRoot
$PythonScript = Join-Path $ScriptDir "horizon_aios_sync.py"

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $python) {
    Write-Error "Python not found on PATH. Install Python 3 and ensure it is on PATH."
    exit 1
}

& $python $PythonScript
exit $LASTEXITCODE
