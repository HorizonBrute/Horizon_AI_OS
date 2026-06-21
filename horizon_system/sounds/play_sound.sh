#!/usr/bin/env bash
# Horizon AIOS — Cross-platform audio player
# Usage: play_sound.sh <wav_file>
# Detects OS and uses the appropriate audio player.
# Fails silently if the file is missing or no suitable player is found.

SOUND_FILE="$1"

[ -z "$SOUND_FILE" ] && exit 0
[ ! -f "$SOUND_FILE" ] && exit 0

case "$(uname -s)" in
    MINGW*|CYGWIN*|MSYS*)
        powershell.exe -Command "(New-Object Media.SoundPlayer '$SOUND_FILE').PlaySync()" 2>/dev/null
        ;;
    Darwin*)
        afplay "$SOUND_FILE" 2>/dev/null
        ;;
    Linux*)
        if command -v paplay >/dev/null 2>&1; then
            paplay "$SOUND_FILE" 2>/dev/null
        elif command -v aplay >/dev/null 2>&1; then
            aplay -q "$SOUND_FILE" 2>/dev/null
        elif command -v ffplay >/dev/null 2>&1; then
            ffplay -nodisp -autoexit -loglevel quiet "$SOUND_FILE" 2>/dev/null
        elif command -v mpg123 >/dev/null 2>&1; then
            mpg123 -q "$SOUND_FILE" 2>/dev/null
        fi
        ;;
esac

exit 0
