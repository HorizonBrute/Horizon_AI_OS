#!/usr/bin/env bash
# Appends a structured line to $HORIZON_ROOT/logs/hooks/hook_events.log.
# Usage: log_hook_event.sh <Event>
EVENT="${1:?Usage: log_hook_event.sh <Event>}"
HORIZON_ROOT="${HORIZON_ROOT:-$(cd "$(dirname "$0")/../../../../.." && pwd)}"
LOG_DIR="$HORIZON_ROOT/logs/hooks"
mkdir -p "$LOG_DIR"
TS=$(date +"%Y-%m-%dT%H:%M:%S")
echo "[$TS] [$EVENT]" >> "$LOG_DIR/hook_events.log"
