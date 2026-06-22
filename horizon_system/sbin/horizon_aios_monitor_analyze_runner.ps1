# horizon_aios_monitor_analyze_runner.ps1
# Analyzes AIOS monitor logs and writes to horizon_aios_security.log.
# Run periodically via Task Scheduler or cron.
# See $HORIZON_DOCS/security/audit_logging.md for scheduling instructions.
#
# Manual:         .\horizon_aios_monitor_analyze_runner.ps1
# With syslog:    .\horizon_aios_monitor_analyze_runner.ps1 --syslog
# Custom range:   .\horizon_aios_monitor_analyze_runner.ps1 --days 7

$scriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
python "$scriptDir\horizon_aios_monitor_analyze.py" @args
