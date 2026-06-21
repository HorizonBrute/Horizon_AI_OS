# analyze_aios_monitor_runner.ps1
# Analyzes AIOS monitor logs and writes to security.log.
# Run periodically via Task Scheduler or cron.
# See $HORIZON_DOCS/security/audit_logging.md for scheduling instructions.
#
# Manual:         .\analyze_aios_monitor_runner.ps1
# With syslog:    .\analyze_aios_monitor_runner.ps1 --syslog
# Custom range:   .\analyze_aios_monitor_runner.ps1 --days 7

$scriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
python "$scriptDir\analyze_aios_monitor.py" @args
