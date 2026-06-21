#!/usr/bin/env bash
# Horizon AIOS — Cross-platform statusline dispatcher
# Reads Claude Code JSON from stdin, routes to the platform-appropriate script.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
input=$(cat)

case "$(uname -s)" in
    MINGW*|CYGWIN*|MSYS*)
        echo "$input" | powershell.exe -NonInteractive -File "$SCRIPT_DIR/statusline-context-alerts.ps1"
        ;;
    Darwin*|Linux*)
        echo "$input" | bash "$SCRIPT_DIR/statusline-command.sh"
        ;;
esac
