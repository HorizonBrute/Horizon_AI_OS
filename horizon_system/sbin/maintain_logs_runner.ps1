$ScriptDir = $PSScriptRoot
$PythonScript = Join-Path $ScriptDir "maintain_logs.py"
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $python) { Write-Error "Python not found on PATH."; exit 1 }
& $python $PythonScript
exit $LASTEXITCODE
