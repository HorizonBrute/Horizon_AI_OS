#!/usr/bin/env bash
# =============================================================================
# Horizon AIOS — Bootstrap Script
# Sets up a new machine with all required Horizon AIOS configuration.
# Safe to run multiple times (idempotent). Non-destructive by default.
#
# Usage:
#   bash /path/to/horizon_bin/bootstrap.sh
#
# Works on: Windows (Git Bash), macOS, Linux
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Parse --yes / -y flag
# -----------------------------------------------------------------------------
YES_ALL=false
for arg in "$@"; do
  case "$arg" in
    --yes|-y) YES_ALL=true ;;
  esac
done

# -----------------------------------------------------------------------------
# Resolve HORIZON_ROOT from script location (works regardless of CWD)
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HORIZON_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HORIZON_BIN="$HORIZON_ROOT/horizon_bin"
HORIZON_ETC="$HORIZON_BIN/ai_os_etc"
HORIZON_DOCS="$HORIZON_BIN/documentation"

export HORIZON_ROOT HORIZON_BIN HORIZON_ETC HORIZON_DOCS

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
PASS=0
FAIL=0

banner() {
  echo ""
  echo "============================================================"
  echo "  $1"
  echo "============================================================"
}

ok()   { echo "  [OK]   $1"; }
warn() { echo "  [WARN] $1"; }
info() { echo "  [INFO] $1"; }
err()  { echo "  [ERR]  $1"; }

pass_check() { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
fail_check() { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }

# -----------------------------------------------------------------------------
# SECTION 1: Environment Variables
# -----------------------------------------------------------------------------
banner "SECTION 1: Environment Variables"

echo ""
echo "Resolved paths:"
echo "  HORIZON_ROOT  = $HORIZON_ROOT"
echo "  HORIZON_BIN   = $HORIZON_BIN"
echo "  HORIZON_ETC   = $HORIZON_ETC"
echo "  HORIZON_DOCS  = $HORIZON_DOCS"

echo ""
echo "Add the following to your shell profile (~/.bashrc, ~/.zshrc, or ~/.bash_profile):"
echo "  (Replace the HORIZON_ROOT value with your actual path if different)"
echo ""
echo "    export HORIZON_ROOT=\"$HORIZON_ROOT\""
echo "    export HORIZON_BIN=\"\$HORIZON_ROOT/horizon_bin\""
echo "    export HORIZON_ETC=\"\$HORIZON_BIN/ai_os_etc\""
echo "    export HORIZON_DOCS=\"\$HORIZON_BIN/documentation\""
echo ""
echo "  Then run: source ~/.bashrc  (or open a new terminal)"

# -----------------------------------------------------------------------------
# SECTION 2: ~/.claude/CLAUDE.md stub
# -----------------------------------------------------------------------------
banner "SECTION 2: ~/.claude/CLAUDE.md stub"

CLAUDE_HOME_DIR="$HOME/.claude"
CLAUDE_MD="$CLAUDE_HOME_DIR/CLAUDE.md"
EXPECTED_REDIRECT="@$HORIZON_ROOT/.claude/CLAUDE.md"

mkdir -p "$CLAUDE_HOME_DIR"

if [ -f "$CLAUDE_MD" ]; then
  if grep -qF "@" "$CLAUDE_MD" && grep -qF ".claude/CLAUDE.md" "$CLAUDE_MD"; then
    ok "~/.claude/CLAUDE.md already contains an @ redirect — skipping."
    current_content="$(cat "$CLAUDE_MD")"
    if [ "$current_content" != "$EXPECTED_REDIRECT" ]; then
      warn "Existing redirect points somewhere else:"
      warn "  Current:  $current_content"
      warn "  Expected: $EXPECTED_REDIRECT"
      warn "If this is wrong, update ~/.claude/CLAUDE.md manually."
    fi
  else
    warn "~/.claude/CLAUDE.md exists but does not contain an @ redirect."
    warn "  Current content: $(cat "$CLAUDE_MD")"
    warn "  Expected:        $EXPECTED_REDIRECT"
    warn "Not overwriting — update manually if needed."
  fi
else
  echo "$EXPECTED_REDIRECT" > "$CLAUDE_MD"
  ok "Created ~/.claude/CLAUDE.md with @ redirect to repo CLAUDE.md."
fi

# -----------------------------------------------------------------------------
# SECTION 3: Deploy skills
# -----------------------------------------------------------------------------
banner "SECTION 3: Deploy skills"

SKILLS_SRC="$HORIZON_BIN/skills"
SKILLS_DST="$HOME/.claude/skills"

if [ ! -d "$SKILLS_SRC" ]; then
  warn "Skills source directory not found: $SKILLS_SRC"
  warn "Skipping skills deploy."
else
  mkdir -p "$SKILLS_DST"
  skill_count=0
  skipped_count=0

  for src_file in "$SKILLS_SRC"/*.md; do
    [ -f "$src_file" ] || continue
    filename="$(basename "$src_file")"
    dst_file="$SKILLS_DST/$filename"

    if [ -f "$dst_file" ]; then
      # Compare content
      if diff -q "$src_file" "$dst_file" > /dev/null 2>&1; then
        ok "  $filename — already up to date, skipping."
        skipped_count=$((skipped_count + 1))
      else
        warn "  $filename — destination differs from source."
        echo "    Diff summary (source vs deployed):"
        diff --unified=2 "$dst_file" "$src_file" | head -20 | sed 's/^/      /'
        if [ "$YES_ALL" = "true" ]; then
          answer=y
        else
          echo -n "    Overwrite $dst_file? [y/N] "
          read -r answer </dev/tty
        fi
        if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
          cp "$src_file" "$dst_file"
          ok "  $filename — overwritten."
          skill_count=$((skill_count + 1))
        else
          warn "  $filename — skipped (keeping existing)."
          skipped_count=$((skipped_count + 1))
        fi
      fi
    else
      cp "$src_file" "$dst_file"
      ok "  $filename — copied."
      skill_count=$((skill_count + 1))
    fi
  done

  info "Skills deploy complete: $skill_count copied, $skipped_count skipped."
fi

# -----------------------------------------------------------------------------
# SECTION 4: Create handoffs directory
# -----------------------------------------------------------------------------
banner "SECTION 4: Handoffs directory"

HANDOFFS_DIR="$HORIZON_ROOT/handoffs"

if [ -d "$HANDOFFS_DIR" ]; then
  ok "Handoffs directory already exists: $HANDOFFS_DIR"
else
  mkdir -p "$HANDOFFS_DIR"
  ok "Created handoffs directory: $HANDOFFS_DIR"
fi

# -----------------------------------------------------------------------------
# SECTION 5: ~/.claude/settings.json
# -----------------------------------------------------------------------------
banner "SECTION 5: ~/.claude/settings.json"

SETTINGS_DST="$HOME/.claude/settings.json"
SETTINGS_TEMPLATE="$HORIZON_BIN/templates/claude_code/settings.json"

if [ -f "$SETTINGS_DST" ]; then
  info "~/.claude/settings.json already exists."
  info "Review $SETTINGS_TEMPLATE and merge any new entries manually."
  info "See $HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md Step 8 for the hard-link approach."
else
  if [ -f "$SETTINGS_TEMPLATE" ]; then
    echo ""
    echo "  No ~/.claude/settings.json found."
    echo "  The template is at: $SETTINGS_TEMPLATE"
    if [ "$YES_ALL" = "true" ]; then
      answer=y
    else
      echo -n "  Copy template to ~/.claude/settings.json? [y/N] "
      read -r answer </dev/tty
    fi
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
      # Substitute HORIZON_BIN_PATH placeholder with actual path
      sed "s|HORIZON_BIN_PATH|$HORIZON_BIN|g" "$SETTINGS_TEMPLATE" > "$SETTINGS_DST"
      ok "Copied template to ~/.claude/settings.json (HORIZON_BIN_PATH substituted)."
      warn "Review ~/.claude/settings.json — some paths may still need manual adjustment."
      warn "See $HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md Step 8 for path substitution details."
    else
      info "Skipping settings.json — create it manually from the template."
    fi
  else
    warn "Template not found: $SETTINGS_TEMPLATE"
    warn "Create ~/.claude/settings.json manually. See $HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md Step 8."
  fi
fi

# -----------------------------------------------------------------------------
# SECTION 6: Git hooks path
# -----------------------------------------------------------------------------
banner "SECTION 6: Git hooks"

GIT_DIR="$HORIZON_ROOT/.git"
HOOKS_PATH="./horizon_bin/harness_configs/git/hooks"

if [ -d "$GIT_DIR" ]; then
  git -C "$HORIZON_ROOT" config core.hooksPath "$HOOKS_PATH"
  ok "Set git core.hooksPath to: $HOOKS_PATH"

  # Install commit-msg hook (DCO sign-off enforcement)
  cp "$HORIZON_BIN/harness_configs/git/hooks/commit-msg" "$HORIZON_ROOT/.git/hooks/commit-msg"
  chmod +x "$HORIZON_ROOT/.git/hooks/commit-msg"
  ok "Installed commit-msg hook (DCO sign-off enforcement)."
else
  info "$HORIZON_ROOT is not a git repository — skipping git hooks config."
fi

# -----------------------------------------------------------------------------
# SECTION 7: Verification
# -----------------------------------------------------------------------------
banner "SECTION 7: Verification"

echo ""

# Check 1: ~/.claude/CLAUDE.md contains @ redirect
if [ -f "$HOME/.claude/CLAUDE.md" ] && grep -qF "@" "$HOME/.claude/CLAUDE.md" && grep -qF ".claude/CLAUDE.md" "$HOME/.claude/CLAUDE.md"; then
  pass_check "~/.claude/CLAUDE.md contains @ redirect"
else
  fail_check "~/.claude/CLAUDE.md is missing or does not contain @ redirect"
fi

# Check 2: handoff.md deployed
if [ -f "$HOME/.claude/skills/handoff.md" ]; then
  pass_check "~/.claude/skills/handoff.md exists"
else
  fail_check "~/.claude/skills/handoff.md not found"
fi

# Check 3: handoffs directory exists
if [ -d "$HORIZON_ROOT/handoffs" ]; then
  pass_check "\$HORIZON_ROOT/handoffs/ exists"
else
  fail_check "\$HORIZON_ROOT/handoffs/ not found"
fi

echo ""
echo "------------------------------------------------------------"
echo "  Bootstrap complete: $PASS passed, $FAIL failed"
echo "------------------------------------------------------------"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  warn "Some checks failed. Review the output above and resolve manually."
  warn "See $HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md for step-by-step instructions."
  exit 1
fi

echo ""
ok "All checks passed. Horizon AIOS is bootstrapped on this machine."
echo ""

# -----------------------------------------------------------------------------
# SECTION 8: Local Config and Sync Schedule
# -----------------------------------------------------------------------------
banner "SECTION 8: Local Config and Sync Schedule"

echo ""
echo "=== Section 8: Local Config and Sync Schedule ==="

LOCAL_CONF="$HORIZON_ETC/aios_local.conf"
CONF_TEMPLATE="$HORIZON_BIN/templates/aios_local.conf.template"

if [ ! -f "$LOCAL_CONF" ]; then
    echo "aios_local.conf not found."
    if [ "$YES_ALL" = "true" ]; then
        copy_conf=y
    else
        printf "Copy template to aios_local.conf? [y/N] "
        read -r copy_conf
    fi
    if echo "$copy_conf" | grep -qi "^y"; then
        cp "$CONF_TEMPLATE" "$LOCAL_CONF"
        echo "Created $LOCAL_CONF from template. Edit it to customize your settings."
    else
        echo "Skipped. Run manually: cp $CONF_TEMPLATE $LOCAL_CONF"
    fi
else
    echo "aios_local.conf already exists — skipping template copy."
fi

mkdir -p "$HORIZON_ROOT/logs"

if [ "$YES_ALL" = "true" ]; then
    setup_sched=y
else
    printf "Set up daily auto-sync from upstream? [y/N] "
    read -r setup_sched
fi
if echo "$setup_sched" | grep -qi "^y"; then
    python3 "$HORIZON_BIN/setup_sync_schedule.py" $([ "$YES_ALL" = "true" ] && echo "--yes")
else
    echo "Skipped. Run later: python3 $HORIZON_BIN/setup_sync_schedule.py"
fi
