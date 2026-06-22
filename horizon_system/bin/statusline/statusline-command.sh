#!/usr/bin/env bash
# Claude Code status line script
# Shows: current directory | git branch/repo | model | context usage | cost

input=$(cat)

# --- Current directory ---
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')

# --- Git branch and repo ---
repo=$(echo "$input" | jq -r '.workspace.repo | if . then .owner + "/" + .name else empty end')
branch=$(echo "$input" | jq -r '.workspace.git_worktree // empty')
# Try to get branch from git directly (skip locks for safety)
if [ -z "$branch" ] && [ -n "$cwd" ]; then
  branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null)
fi

# --- Model ---
model=$(echo "$input" | jq -r '.model.display_name // empty')

# --- Session ID (for threshold audio state tracking) ---
session_id=$(echo "$input" | jq -r '.session_id // empty')

# --- Context usage ---
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
total_input=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_output=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')

# --- Approximate auto-compact trigger point (not exposed in statusline JSON; defaults to ~80%) ---
compact_threshold=80

# --- Threshold audio alerts (fires once per threshold per session) ---
if [ -n "$used_pct" ] && [ -n "$session_id" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  HORIZON_BIN="$(cd "$SCRIPT_DIR/.." && pwd)"
  HORIZON_SYSTEM="$(cd "$HORIZON_BIN/.." && pwd)"

  # Walk up from cwd to find aios_statusline.conf
  thresholds="30 40 50 60 70 80 90"
  if [ -n "$cwd" ]; then
    current="$cwd"
    while true; do
      candidate="$current/aios_statusline.conf"
      if [ -f "$candidate" ]; then
        raw=$(grep -E '^[[:space:]]*context_thresholds[[:space:]]*=' "$candidate" | tail -1 | sed 's/.*=[[:space:]]*//' | tr -d ' ')
        [ -n "$raw" ] && thresholds=$(echo "$raw" | tr ',' ' ')
        ct=$(grep -E '^[[:space:]]*compact_threshold[[:space:]]*=' "$candidate" | tail -1 | sed 's/.*=[[:space:]]*//' | tr -d ' ')
        [ -n "$ct" ] && compact_threshold=$ct
        break
      fi
      parent=$(dirname "$current")
      [ "$parent" = "$current" ] && break
      current="$parent"
    done
  fi

  state_file="${TMPDIR:-/tmp}/claude_ctx_${session_id}.txt"
  last_fired=0
  [ -f "$state_file" ] && last_fired=$(cat "$state_file" 2>/dev/null || echo 0)
  pct_int=$(printf "%.0f" "$used_pct")
  new_threshold=0
  for t in $thresholds; do
    if [ "$pct_int" -ge "$t" ] && [ "$last_fired" -lt "$t" ]; then
      new_threshold=$t
    fi
  done
  if [ "$new_threshold" -gt 0 ]; then
    resolve_script="$HORIZON_BIN/resolve_sound.py"
    sound=$(python3 "$resolve_script" "claude.context_${new_threshold}" --harness claude_code --cwd "${cwd:-$PWD}" 2>/dev/null)
    if [ -n "$sound" ] && [ -f "$sound" ]; then
      bash "$HORIZON_SYSTEM/sounds/play_sound.sh" "$sound" &
    fi
    echo "$new_threshold" > "$state_file"
  fi
fi

# --- Cost estimation (approximate, based on Sonnet 4 pricing) ---
# Input: $3.00/MTok, Output: $15.00/MTok (ballpark for claude-sonnet class)
cost=""
if [ -n "$total_input" ] && [ "$total_input" -gt 0 ] 2>/dev/null; then
  cost=$(echo "$total_input $total_output" | awk '{
    input_cost  = $1 / 1000000 * 3.00
    output_cost = $2 / 1000000 * 15.00
    total = input_cost + output_cost
    printf "$%.4f", total
  }')
fi

# --- Assemble output ---
parts=()

# Directory (shorten home dir to ~)
if [ -n "$cwd" ]; then
  home_dir="$HOME"
  display_cwd="${cwd/#$home_dir/~}"
  parts+=("$(printf '\033[1;34m%s\033[0m' "$display_cwd")")
fi

# Repo and branch
git_part=""
if [ -n "$repo" ] && [ -n "$branch" ]; then
  git_part="$repo ($branch)"
elif [ -n "$repo" ]; then
  git_part="$repo"
elif [ -n "$branch" ]; then
  git_part="$branch"
fi
[ -n "$git_part" ] && parts+=("$(printf '\033[1;32m%s\033[0m' "$git_part")")

# Model
[ -n "$model" ] && parts+=("$(printf '\033[1;36m%s\033[0m' "$model")")

# Context usage
if [ -n "$used_pct" ]; then
  ctx_str=$(printf "Context Window: %.0f%%" "$used_pct")
  # Color: green < 50%, yellow 50-80%, red > 80%
  color=32
  pct_int=$(printf "%.0f" "$used_pct")
  [ "$pct_int" -ge 50 ] && color=33
  [ "$pct_int" -ge 80 ] && color=31
  parts+=("$(printf "\033[1;${color}m%s\033[0m" "$ctx_str")")

  # % To Compact (remaining headroom before approximate auto-compact point)
  to_compact=$(awk -v t="$compact_threshold" -v u="$pct_int" 'BEGIN { d = t - u; if (d < 0) d = 0; print d }')
  parts+=("$(printf '\033[1;35m%s\033[0m' "Estimated % To Compact: ${to_compact}%")")
fi

# Cost
[ -n "$cost" ] && [ "$cost" != '$0.0000' ] && parts+=("$(printf '\033[0;33m%s\033[0m' "$cost")")

# Join parts with separator
printf "%s" "$(IFS='  |  '; echo "${parts[*]}")"
