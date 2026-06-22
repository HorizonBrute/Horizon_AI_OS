# horizon_aios_monitor_runner.ps1
# Launches horizon_aios_monitor.py. For manual use or service wrapper.
# See $HORIZON_DOCS/security/audit_logging.md for service registration.
#
# Manual:   .\horizon_aios_monitor_runner.ps1
# With args: .\horizon_aios_monitor_runner.ps1 --watch C:\path\to\extra --log-dir C:\custom\logs

$scriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
python "$scriptDir\horizon_aios_monitor.py" @args
