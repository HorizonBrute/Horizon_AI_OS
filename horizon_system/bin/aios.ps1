# Thin wrapper — delegates to sbin/horizon_aios_switch.py
# Path-agnostic: derives sbin from this file's own location.
$sbin = Join-Path (Split-Path $PSScriptRoot) "sbin"
python "$sbin\horizon_aios_switch.py" @args
exit $LASTEXITCODE
