#!/usr/bin/env bash
# =============================================================================
# Horizon AIOS — Bootstrap Script
# Sets up a new machine with all required Horizon AIOS configuration.
# Safe to run multiple times (idempotent). Non-destructive by default.
#
# Usage:
#   bash /path/to/horizon_system/sbin/bootstrap.sh
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
HORIZON_SYSTEM="$(cd "$SCRIPT_DIR/.." && pwd)"
HORIZON_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HORIZON_BIN="$HORIZON_SYSTEM/bin"
HORIZON_ETC="$HORIZON_SYSTEM/ai_os_etc"
HORIZON_DOCS="$HORIZON_SYSTEM/documentation"
HORIZON_SOUNDS="$HORIZON_SYSTEM/sounds"
HORIZON_LOGS="$HORIZON_ROOT/logs"

export HORIZON_SYSTEM HORIZON_ROOT HORIZON_BIN HORIZON_ETC HORIZON_DOCS HORIZON_SOUNDS HORIZON_LOGS

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
echo "  HORIZON_ROOT   = $HORIZON_ROOT"
echo "  HORIZON_SYSTEM = $HORIZON_SYSTEM"
echo "  HORIZON_BIN    = $HORIZON_BIN"
echo "  HORIZON_ETC    = $HORIZON_ETC"
echo "  HORIZON_DOCS   = $HORIZON_DOCS"
echo "  HORIZON_SOUNDS = $HORIZON_SOUNDS"
echo "  HORIZON_LOGS   = $HORIZON_LOGS"

if [ "${AIOS_DEPLOY_MODE:-}" = "docker" ]; then
  info "Docker mode: HORIZON_* env vars (including HORIZON_SOUNDS, HORIZON_LOGS) are set in the Dockerfile — no shell profile changes needed."
else
  echo ""
  echo "Add the following to your shell profile (~/.bashrc, ~/.zshrc, or ~/.bash_profile):"
  echo "  (Replace the HORIZON_ROOT value with your actual path if different)"
  echo ""
  echo "    export HORIZON_ROOT=\"$HORIZON_ROOT\""
  echo "    export HORIZON_SYSTEM=\"\$HORIZON_ROOT/horizon_system\""
  echo "    export HORIZON_BIN=\"\$HORIZON_SYSTEM/bin\""
  echo "    export HORIZON_ETC=\"\$HORIZON_SYSTEM/ai_os_etc\""
  echo "    export HORIZON_DOCS=\"\$HORIZON_SYSTEM/documentation\""
  echo "    export HORIZON_SOUNDS=\"\$HORIZON_SYSTEM/sounds\""
  echo "    export HORIZON_LOGS=\"\$HORIZON_ROOT/logs\""
  echo ""
  echo "  Then run: source ~/.bashrc  (or open a new terminal)"
fi

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
# SECTION 3: Redirect ~/.claude/skills/ to skills_sbin/
# Primary user is AIOS root — all skills live in skills_sbin/.
# We redirect the directory itself (symlink) so changes are live immediately.
# -----------------------------------------------------------------------------
banner "SECTION 3: Skills redirect"

SKILLS_SRC="$HORIZON_SYSTEM/skills_sbin"
SKILLS_DST="$HOME/.claude/skills"

if [ ! -d "$SKILLS_SRC" ]; then
  warn "skills_sbin not found: $SKILLS_SRC — skipping skills redirect."
elif [ -L "$SKILLS_DST" ]; then
  current_target="$(readlink "$SKILLS_DST")"
  if [ "$current_target" = "$SKILLS_SRC" ]; then
    ok "~/.claude/skills/ already redirected to skills_sbin/ — OK."
  else
    warn "~/.claude/skills/ is a symlink pointing elsewhere: $current_target"
    if [ "$YES_ALL" = "true" ]; then answer=y; else
      echo -n "  Replace symlink? [y/N] "; read -r answer </dev/tty
    fi
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
      rm "$SKILLS_DST"
      ln -s "$SKILLS_SRC" "$SKILLS_DST"
      ok "Updated symlink: ~/.claude/skills/ → skills_sbin/"
    else
      warn "Skipping skills redirect."
    fi
  fi
elif [ -d "$SKILLS_DST" ]; then
  if [ -z "$(ls -A "$SKILLS_DST" 2>/dev/null)" ]; then
    rmdir "$SKILLS_DST"
    ln -s "$SKILLS_SRC" "$SKILLS_DST"
    ok "Created symlink: ~/.claude/skills/ → skills_sbin/"
  else
    warn "~/.claude/skills/ is a real directory with content."
    warn "Cannot auto-redirect. Manually empty or remove it, then re-run bootstrap."
  fi
else
  ln -s "$SKILLS_SRC" "$SKILLS_DST"
  ok "Created symlink: ~/.claude/skills/ → skills_sbin/"
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
# Select template based on OS: Windows (Git Bash) uses PowerShell hooks; Linux/macOS use bash hooks.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) SETTINGS_TEMPLATE="$HORIZON_SYSTEM/templates/claude_code/settings.json" ;;
  *) SETTINGS_TEMPLATE="$HORIZON_SYSTEM/templates/claude_code/settings_unix.json" ;;
esac

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
      # Substitute path placeholders
      sed "s|HORIZON_BIN_PATH|$HORIZON_BIN|g; s|HORIZON_SYSTEM_PATH|$HORIZON_SYSTEM|g" "$SETTINGS_TEMPLATE" > "$SETTINGS_DST"
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
HOOKS_PATH="./horizon_system/harness_configs/git/hooks"

if [ -d "$GIT_DIR" ]; then
  git -C "$HORIZON_ROOT" config core.hooksPath "$HOOKS_PATH"
  ok "Set git core.hooksPath to: $HOOKS_PATH"

  # Install commit-msg hook (DCO sign-off enforcement)
  cp "$HORIZON_SYSTEM/harness_configs/git/hooks/commit-msg" "$HORIZON_ROOT/.git/hooks/commit-msg"
  chmod +x "$HORIZON_ROOT/.git/hooks/commit-msg"
  ok "Installed commit-msg hook (DCO sign-off enforcement)."
  cp "$HORIZON_SYSTEM/harness_configs/git/hooks/pre-commit" "$HORIZON_ROOT/.git/hooks/pre-commit"
  chmod +x "$HORIZON_ROOT/.git/hooks/pre-commit"
  ok "Installed pre-commit hook."
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

# Check 2: ~/.claude/skills/ is a symlink to skills_sbin/
if [ -L "$HOME/.claude/skills" ]; then
  pass_check "~/.claude/skills/ redirected to skills_sbin/ (symlink)"
else
  fail_check "~/.claude/skills/ is not a symlink — skills redirect not set up"
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
CONF_TEMPLATE="$HORIZON_SYSTEM/templates/aios_local.conf.template"

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

if [ "${AIOS_DEPLOY_MODE:-}" = "docker" ]; then
    info "Docker mode: skipping sync schedule setup (refresh via image rebuild or pull)."
elif [ "$YES_ALL" = "true" ]; then
    setup_sched=y
    echo "$setup_sched" | grep -qi "^y" && python3 "$HORIZON_SYSTEM/sbin/setup_sync_schedule.py" --yes
else
    printf "Set up daily auto-sync from upstream? [y/N] "
    read -r setup_sched
    if echo "$setup_sched" | grep -qi "^y"; then
        python3 "$HORIZON_SYSTEM/sbin/setup_sync_schedule.py"
    else
        echo "Skipped. Run later: python3 $HORIZON_SYSTEM/sbin/setup_sync_schedule.py"
    fi
fi
