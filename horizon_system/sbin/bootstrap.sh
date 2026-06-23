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
# Require root — horizon_aios_harden.py (run below) needs root privileges to set
# filesystem ACLs.  Fail fast rather than let the user discover this mid-run
# at Section 9.
# -----------------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
  echo ""
  echo "  [ERR] Bootstrap must be run with sudo (root privileges required for ACL hardening)."
  echo "  Re-run as:"
  echo "    sudo bash $0 $*"
  echo ""
  exit 1
fi

# -----------------------------------------------------------------------------
# Resolve HORIZON_ROOT from script location (works regardless of CWD)
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HORIZON_SYSTEM="$(cd "$SCRIPT_DIR/.." && pwd)"
HORIZON_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HORIZON_BIN="$HORIZON_SYSTEM/bin"
HORIZON_SBIN="$HORIZON_SYSTEM/sbin"
HORIZON_ETC="$HORIZON_SYSTEM/ai_os_etc"
HORIZON_DOCS="$HORIZON_SYSTEM/documentation"
HORIZON_SOUNDS="$HORIZON_SYSTEM/sounds"
HORIZON_LOGS="$HORIZON_SYSTEM/logs"
HORIZON_USRBIN="$HORIZON_ROOT/usrbin"
HORIZON_PROJECTS="$HORIZON_ROOT/Projects"

export HORIZON_SYSTEM HORIZON_ROOT HORIZON_BIN HORIZON_SBIN HORIZON_ETC HORIZON_DOCS HORIZON_SOUNDS HORIZON_LOGS HORIZON_USRBIN HORIZON_PROJECTS

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
  echo "Add ONE line to your shell profile (~/.bashrc, ~/.zshrc, or ~/.bash_profile)"
  echo "to load whichever AIOS is active (Section 5 generates this file; the AIOS"
  echo "switcher regenerates it on switch):"
  echo ""
  echo "    . \"\$HOME/.horizon/active_env.sh\""
  echo ""
  echo "  This sets HORIZON_ROOT + all derived vars for the active AIOS, so"
  echo "  'aios switch <name>' repoints your shell without editing your profile."
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

# Owner-only AIOS development context: import the dev directives into the owner
# stub. Brains never import this (their brain_CLAUDE.md.template omits it), so
# AIOS-development rules stay out of brain/runtime context.
DEV_CONTEXT_IMPORT="@$HORIZON_ROOT/.claude/CLAUDE.aios-dev.md"
if ! grep -qF "CLAUDE.aios-dev.md" "$CLAUDE_MD" 2>/dev/null; then
  printf '\n%s\n' "$DEV_CONTEXT_IMPORT" >> "$CLAUDE_MD"
  ok "Added owner-only AIOS development context import to ~/.claude/CLAUDE.md."
else
  ok "~/.claude/CLAUDE.md already imports AIOS development context."
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

# Register machine-local user skills (usrbin/usr_skills -> skills_sbin symlinks).
# Best-effort: never abort bootstrap if python is missing or no user skills exist.
REG_SCRIPT="$HORIZON_SYSTEM/sbin/horizon_aios_register_user_skills.py"
if [ -f "$REG_SCRIPT" ]; then
  if command -v python3 >/dev/null 2>&1; then
    if python3 "$REG_SCRIPT"; then
      ok "Registered machine-local user skills."
    else
      warn "horizon_aios_register_user_skills.py exited non-zero."
    fi
  else
    warn "python3 not found — skipping user-skill registration. Run later: python3 $REG_SCRIPT"
  fi
fi

# -----------------------------------------------------------------------------
# SECTION 4: Create handoffs and objectives directories
# -----------------------------------------------------------------------------
banner "SECTION 4: Handoffs and objectives directories"

HANDOFFS_DIR="$HORIZON_ROOT/handoffs"

if [ -d "$HANDOFFS_DIR" ]; then
  ok "Handoffs directory already exists: $HANDOFFS_DIR"
else
  mkdir -p "$HANDOFFS_DIR"
  ok "Created handoffs directory: $HANDOFFS_DIR"
fi

OBJECTIVES_DIR="$HORIZON_ROOT/objectives"

if [ -d "$OBJECTIVES_DIR" ]; then
  ok "Objectives directory already exists: $OBJECTIVES_DIR"
else
  mkdir -p "$OBJECTIVES_DIR"
  ok "Created objectives directory: $OBJECTIVES_DIR"
fi

# -----------------------------------------------------------------------------
# SECTION 5: settings.json + AIOS indirection layer
# Initializes the machine-local AIOS registry (~/.horizon/) and generates the
# active_env snippet + aios-exec wrappers, then wires settings.json at the
# stable wrapper so switching AIOS never rewrites settings.json. See
# horizon_aios_switch.py and $HORIZON_DOCS/system/aios_switching.md.
# -----------------------------------------------------------------------------
banner "SECTION 5: settings.json + AIOS indirection layer"

# 5a: AIOS registry + active_env + wrappers (idempotent; self-heals registry).
SWITCH_SCRIPT="$HORIZON_SYSTEM/sbin/horizon_aios_switch.py"
if [ -f "$SWITCH_SCRIPT" ]; then
  if command -v python3 >/dev/null 2>&1; then
    if python3 "$SWITCH_SCRIPT" init; then
      ok "AIOS registry + indirection layer initialized."
    else
      warn "horizon_aios_switch.py init exited non-zero."
    fi
  else
    warn "python3 not found - skipping AIOS registry init. Run later: python3 $SWITCH_SCRIPT init"
  fi
else
  warn "horizon_aios_switch.py not found at $SWITCH_SCRIPT - skipping AIOS registry init."
fi

# 5b: settings.json points at the stable, AIOS-independent wrapper.
AIOS_EXEC_WRAPPER="$HOME/.horizon/bin/aios-exec.sh"
SETTINGS_DST="$HOME/.claude/settings.json"
# Select template based on OS: Windows (Git Bash) uses PowerShell hooks; Linux/macOS use bash hooks.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    SETTINGS_TEMPLATE="$HORIZON_SYSTEM/templates/claude_code/settings.json"
    AIOS_EXEC_WRAPPER="$HOME/.horizon/bin/aios-exec.ps1" ;;
  *) SETTINGS_TEMPLATE="$HORIZON_SYSTEM/templates/claude_code/settings_unix.json" ;;
esac

if [ -f "$SETTINGS_DST" ]; then
  info "~/.claude/settings.json already exists."
  info "To use the AIOS switcher, point statusLine + hooks at the wrapper:"
  info "  $AIOS_EXEC_WRAPPER  (actions: statusline, hook-stop, hook-permission, hook-stopfailure)"
  info "Compare with $SETTINGS_TEMPLATE and merge manually."
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
      # Point settings.json at the stable, AIOS-independent wrapper.
      sed "s|AIOS_EXEC_WRAPPER|$AIOS_EXEC_WRAPPER|g" "$SETTINGS_TEMPLATE" > "$SETTINGS_DST"
      ok "Copied template to ~/.claude/settings.json (pointed at aios-exec wrapper)."
      info "settings.json now resolves the active AIOS at run time - switching never rewrites it."
    else
      info "Skipping settings.json — create it manually from the template."
    fi
  else
    warn "Template not found: $SETTINGS_TEMPLATE"
    warn "Create ~/.claude/settings.json manually. See $HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md Step 8."
  fi
fi

# 5c: Redirect ~/.claude/projects into $HORIZON_ROOT/memory (owner harness memory).
# Migrates the Claude harness's per-project state into the AIOS so memory is
# owned by the OS layer. The script junctions ~/.claude/projects → $HORIZON_ROOT/
# memory, backing up any existing real directory first. Idempotent: re-running
# no-ops if already redirected, so it is safe to always call.
# NOTE: Have Claude Code closed when bootstrap runs — the script moves the live
# projects directory (it leaves a backup if one was present).
REDIRECT_MEMORY_SCRIPT="$HORIZON_SYSTEM/sbin/horizon_aios_redirect_memory.py"
if [ -f "$REDIRECT_MEMORY_SCRIPT" ]; then
  if command -v python3 >/dev/null 2>&1; then
    if python3 "$REDIRECT_MEMORY_SCRIPT"; then
      ok "~/.claude/projects redirected to \$HORIZON_ROOT/memory."
    else
      warn "horizon_aios_redirect_memory.py exited non-zero."
    fi
  else
    warn "python3 not found - skipping memory redirect. Run later: python3 $REDIRECT_MEMORY_SCRIPT"
  fi
else
  warn "horizon_aios_redirect_memory.py not found at $REDIRECT_MEMORY_SCRIPT - skipping memory redirect."
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

# 6b: .gitignore.user — the pre-commit hook syncs this file into
# .git/info/exclude. Seed it from the template so a fresh install is
# doctor-clean (horizon_aios_doctor.py checks $HORIZON_ROOT/.gitignore.user).
# Idempotent: never overwrite an existing file (it holds user-local patterns).
GITIGNORE_USER="$HORIZON_ROOT/.gitignore.user"
GITIGNORE_TEMPLATE="$HORIZON_ROOT/.gitignore.user.template"
if [ -f "$GITIGNORE_USER" ]; then
  info ".gitignore.user already exists — skipping template copy."
elif [ -f "$GITIGNORE_TEMPLATE" ]; then
  cp "$GITIGNORE_TEMPLATE" "$GITIGNORE_USER"
  ok "Created .gitignore.user from template."
else
  warn "Template not found: $GITIGNORE_TEMPLATE — create .gitignore.user manually."
fi

# -----------------------------------------------------------------------------
# SECTION 7: System PATH
# Adds $HORIZON_BIN to the system PATH via /etc/profile.d/horizon_aios.sh so
# brain accounts and new login shells can run AIOS commands without manually
# editing PATH. Removes stale horizon_system/bin entries first (AIOS switching).
# On macOS, also writes to /etc/paths.d/horizon-aios for zsh via path_helper.
# -----------------------------------------------------------------------------
banner "SECTION 7: System PATH"

PROFILE_D_FILE="/etc/profile.d/horizon_aios.sh"
EXPANDED_BIN="$HORIZON_BIN"

# Remove any stale horizon_system/bin line from /etc/profile.d/horizon_aios.sh
if [ -f "$PROFILE_D_FILE" ]; then
  # Strip lines that export PATH with a horizon_system/bin component
  sed -i '/horizon_system\/bin/d' "$PROFILE_D_FILE"
  ok "Removed stale horizon_system/bin entry from $PROFILE_D_FILE (if any)."
fi

# Append the current HORIZON_BIN to PATH in /etc/profile.d/horizon_aios.sh
# Use the expanded path — /etc/profile.d/ files are sourced before HORIZON_BIN
# is in scope, so variable references would not resolve correctly.
mkdir -p /etc/profile.d
{
  echo "# Horizon AIOS — managed by bootstrap.sh (do not edit manually)"
  echo "export PATH=\"$EXPANDED_BIN:\$PATH\""
} >> "$PROFILE_D_FILE"
chmod 644 "$PROFILE_D_FILE"
ok "Added $EXPANDED_BIN to system PATH via $PROFILE_D_FILE"

# macOS: also write to /etc/paths.d/ for zsh (path_helper reads this)
case "$(uname -s)" in
  Darwin)
    PATHS_D_FILE="/etc/paths.d/horizon-aios"
    # Remove stale horizon_system/bin entries
    if [ -f "$PATHS_D_FILE" ]; then
      sed -i '' '/horizon_system\/bin/d' "$PATHS_D_FILE"
    fi
    echo "$EXPANDED_BIN" >> "$PATHS_D_FILE"
    chmod 644 "$PATHS_D_FILE"
    ok "Added $EXPANDED_BIN to /etc/paths.d/horizon-aios (macOS zsh path_helper)"
    ;;
esac

# -----------------------------------------------------------------------------
# SECTION 8: Verification
# -----------------------------------------------------------------------------
banner "SECTION 8: Verification"

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

# Check 4: objectives directory exists
if [ -d "$HORIZON_ROOT/objectives" ]; then
  pass_check "\$HORIZON_ROOT/objectives/ exists"
else
  fail_check "\$HORIZON_ROOT/objectives/ not found"
fi

# Check 5: git user.name and user.email set (required for DCO sign-off)
_git_name="$(git config user.name 2>/dev/null || true)"
_git_email="$(git config user.email 2>/dev/null || true)"
if [ -z "$_git_name" ] || [ -z "$_git_email" ]; then
  warn "git user.name or user.email not set — DCO sign-off lines will be malformed."
  warn "  Fix: git config --global user.name \"Your Name\""
  warn "       git config --global user.email \"you@example.com\""
else
  pass_check "git user.name and user.email are set"
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
# SECTION 9: Local Config and Sync Schedule
# -----------------------------------------------------------------------------
banner "SECTION 9: Local Config and Sync Schedule"

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

mkdir -p "$HORIZON_SYSTEM/logs"

if [ "${AIOS_DEPLOY_MODE:-}" = "docker" ]; then
    info "Docker mode: skipping sync schedule setup (refresh via image rebuild or pull)."
elif [ "$YES_ALL" = "true" ]; then
    setup_sched=y
    echo "$setup_sched" | grep -qi "^y" && python3 "$HORIZON_SYSTEM/sbin/horizon_aios_setup_sync_schedule.py" --yes
else
    printf "Set up daily auto-sync from upstream? [y/N] "
    read -r setup_sched
    if echo "$setup_sched" | grep -qi "^y"; then
        python3 "$HORIZON_SYSTEM/sbin/horizon_aios_setup_sync_schedule.py"
    else
        echo "Skipped. Run later: python3 $HORIZON_SYSTEM/sbin/horizon_aios_setup_sync_schedule.py"
    fi
fi

# -----------------------------------------------------------------------------
# SECTION 10: Harden AIOS layer ACLs (brains group)
# Enforces security_invariants.md §2/§3/§5 — brains denied on sbin/skills_sbin/
# logs, granted rx on bin/skills_bin, no write elsewhere in $HORIZON_SYSTEM.
# FATAL: horizon_aios_harden.py failure exits bootstrap non-zero — ACL hardening is a
# security requirement, not a best-effort step.
# -----------------------------------------------------------------------------
banner "SECTION 10: Harden AIOS layer ACLs"

HARDEN_SCRIPT="$HORIZON_SYSTEM/sbin/horizon_aios_harden.py"
if [ "${AIOS_SKIP_HARDEN:-}" = "1" ]; then
  ok "Hardening skipped (AIOS_SKIP_HARDEN=1) — already applied as root before this step."
elif [ -f "$HARDEN_SCRIPT" ]; then
  if command -v python3 >/dev/null 2>&1; then
    if python3 "$HARDEN_SCRIPT"; then
      ok "AIOS layer hardened (brains-group ACLs applied)."
    else
      err "horizon_aios_harden.py exited non-zero — ACL hardening FAILED. The system is NOT secured."
      err "Review horizon_aios_harden.py output above and re-run bootstrap with sudo before using this installation."
      exit 1
    fi
  else
    err "python3 not found — cannot run horizon_aios_harden.py. ACL hardening FAILED. The system is NOT secured."
    err "Install Python 3.6+ and re-run: sudo python3 $HARDEN_SCRIPT"
    exit 1
  fi
else
  err "horizon_aios_harden.py not found at $HARDEN_SCRIPT — ACL hardening FAILED. The system is NOT secured."
  exit 1
fi
