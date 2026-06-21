# monitor_aios_runner.ps1
# Launches monitor_aios.py. For manual use or service wrapper.
# See $HORIZON_DOCS/security/audit_logging.md for service registration.
#
# Manual:   .\monitor_aios_runner.ps1
# With args: .\monitor_aios_runner.ps1 --watch C:\path\to\extra --log-dir C:\custom\logs

$scriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
python "$scriptDir\monitor_aios.py" @args
