# Thin wrapper — delegates to sbin/aios_switch.py
# Path-agnostic: derives sbin from this file's own location.
$sbin = Join-Path (Split-Path $PSScriptRoot) "sbin"
python "$sbin\aios_switch.py" @args
exit $LASTEXITCODE
