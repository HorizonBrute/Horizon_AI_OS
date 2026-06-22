#!/usr/bin/env bash
# Appends a structured line to $HORIZON_SYSTEM/logs/hooks/hook_events.log.
# Usage: log_hook_event.sh <Event>
# This script lives at $HORIZON_SYSTEM/harness_configs/claude_code/hooks/ —
# go up three levels to reach $HORIZON_SYSTEM.
EVENT="${1:?Usage: log_hook_event.sh <Event>}"
HORIZON_SYSTEM="${HORIZON_SYSTEM:-$(cd "$(dirname "$0")/../../.." && pwd)}"
LOG_DIR="$HORIZON_SYSTEM/logs/hooks"
mkdir -p "$LOG_DIR"
TS=$(date +"%Y-%m-%dT%H:%M:%S")
echo "[$TS] [$EVENT]" >> "$LOG_DIR/hook_events.log"
