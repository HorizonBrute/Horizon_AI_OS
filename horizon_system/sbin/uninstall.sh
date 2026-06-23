#!/usr/bin/env bash
# =============================================================================
# Horizon AIOS — Uninstall Script
# Undoes everything bootstrap.sh does on this machine.
# Safe to run multiple times (idempotent). Non-destructive on user content.
#
# Usage:
#   bash horizon_system/sbin/uninstall.sh --dry-run     # preview, no changes (no root)
#   sudo bash horizon_system/sbin/uninstall.sh          # interactive
#   sudo bash horizon_system/sbin/uninstall.sh --yes    # non-interactive
#   sudo bash horizon_system/sbin/uninstall.sh -y       # same as --yes
# Unknown arguments are rejected (exit 2) rather than silently ignored.
#
# Works on: macOS, Linux (and Git Bash on Windows as a fallback — prefer uninstall.ps1)
# Must be run as root (sudo) — same requirement as bootstrap.
#
# What this removes (mirrors bootstrap.sh section by section):
#   Section 2  — ~/.claude/CLAUDE.md redirect lines written by bootstrap
#   Section 3  — ~/.claude/skills/ symlink and user-skill symlinks in skills_sbin/
#   Section 4  — $HORIZON_ROOT/handoffs/ and objectives/ (only if empty)
#   Section 5  — ~/.horizon/ tree (registry, active_env, wrappers), ~/.claude/settings.json
#   Section 5b — ~/.claude/projects symlink (memory redirect); memory data left intact
#   Section 6  — .git/hooks/commit-msg, pre-commit; git core.hooksPath config
#   Section 7  — /etc/profile.d/horizon_aios.sh and /etc/paths.d/horizon-aios (macOS)
#   Section 8  — active_env line in the owner shell profile + the two global git
#                include.path entries `aios setup` writes (framework gitconfig and
#                the machine-local git_identity.local.gitconfig)
#   Section 9  — $HORIZON_ETC/aios_local.conf, $HORIZON_SYSTEM/logs/ (only if empty)
#   Section 10 — brains-group ACEs removed from $HORIZON_SYSTEM subtrees
#                Advisory: 'brains' OS group left in place (may have brain members)
#
# What this does NOT remove:
#   - Optional sync schedule / cron entries from horizon_aios_setup_sync_schedule.py (separate opt-in)
#   - 'brains' OS group (may have brain OS users as members)
#   - Brain OS user accounts and their data (use horizon_aios_create_brain.py remove flow)
#   - Python packages (watchdog, keyring) installed by the user
# =============================================================================

set -euo pipefail

# --- Parse flags (reject unknown args instead of silently dropping them) ---
usage() {
  echo ""
  echo "  Horizon AIOS uninstall — reverses the bootstrap footprint."
  echo ""
  echo "  Usage: sudo bash $0 [--dry-run] [--yes]"
  echo "    --dry-run     Preview every action; make no changes (no root needed)."
  echo "    --yes, -y     Non-interactive; accept all removals without prompting."
  echo "    --help, -h    Show this help and exit."
  echo ""
}

YES_ALL=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --yes|-y)  YES_ALL=true ;;
    --dry-run) DRY_RUN=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo ""; echo "  [ERR] Unknown argument: $arg"; usage; exit 2 ;;
  esac
done

# --- Root check (a dry-run only previews, so it needs no root) ---
if [ "$(id -u)" -ne 0 ] && [ "$DRY_RUN" != "true" ]; then
  echo ""
  echo "  [ERR] Uninstall must be run as root (ACL/permission removal requires root)."
  echo "  Re-run as:"
  echo "    sudo bash $0 $*"
  echo "  Or preview without root:  bash $0 --dry-run"
  echo ""
  exit 1
fi

# --- Resolve paths (same logic as bootstrap.sh) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HORIZON_SYSTEM="$(cd "$SCRIPT_DIR/.." && pwd)"
HORIZON_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HORIZON_BIN="$HORIZON_SYSTEM/bin"
HORIZON_SBIN="$HORIZON_SYSTEM/sbin"
HORIZON_ETC="$HORIZON_SYSTEM/ai_os_etc"
HORIZON_LOGS="$HORIZON_SYSTEM/logs"

# The owner is whichever user invoked sudo. Fall back through $USER to `id -un`
# so this stays defined under `set -u` even when neither var is exported
# (e.g. Git Bash, or a minimal non-login shell).
OWNER="${SUDO_USER:-${USER:-$(id -un)}}"
OWNER_HOME="$(eval echo ~"$OWNER")"

# --- Helpers ---
banner() {
  echo ""
  echo "============================================================"
  echo "  $1"
  echo "============================================================"
}

ok()       { echo "  [OK]      $1"; }
warn()     { echo "  [WARN]    $1"; }
info()     { echo "  [INFO]    $1"; }
advisory() { echo "  [MANUAL]  $1"; }
skip()     { echo "  [SKIP]    $1"; }
dry()      { echo "  [DRY]     would $1"; }

confirm() {
  local prompt="$1"
  if [ "$YES_ALL" = "true" ]; then return 0; fi
  printf "  %s [y/N] " "$prompt"
  read -r answer </dev/tty
  [ "$answer" = "y" ] || [ "$answer" = "Y" ]
}

if [ "$DRY_RUN" = "true" ]; then
  echo ""
  echo "  [DRY-RUN] Previewing actions only — no changes will be made."
  if [ "$(id -u)" -ne 0 ]; then
    echo "  [DRY-RUN] Not root; a real uninstall must be run with sudo."
  fi
fi

# =============================================================================
# SECTION 2: ~/.claude/CLAUDE.md — remove lines written by bootstrap
# Bootstrap writes the @ redirect line and the @ CLAUDE.aios-dev.md import line.
# We strip only those two lines; any content the user added is preserved.
# If the file becomes empty after stripping, offer to delete it.
# =============================================================================
banner "SECTION 2: ~/.claude/CLAUDE.md cleanup"

CLAUDE_MD="$OWNER_HOME/.claude/CLAUDE.md"

if [ -f "$CLAUDE_MD" ]; then
  # Strip lines that reference our CLAUDE.md redirect or the aios-dev import
  # Use a temp file to avoid in-place sed portability issues across macOS/Linux
  TMPFILE="$(mktemp)"
  grep -v -F "$HORIZON_ROOT/.claude/CLAUDE.md" "$CLAUDE_MD" \
    | grep -v "CLAUDE.aios-dev.md" \
    > "$TMPFILE" || true

  # Strip trailing/leading blank lines
  CONTENT="$(sed '/^[[:space:]]*$/d' "$TMPFILE")"
  rm -f "$TMPFILE"

  if [ -z "$CONTENT" ]; then
    if [ "$DRY_RUN" = "true" ]; then
      dry "delete ~/.claude/CLAUDE.md (would be empty after removing bootstrap lines)."
    elif confirm "~/.claude/CLAUDE.md will be empty after removing bootstrap lines — delete it?"; then
      rm -f "$CLAUDE_MD"
      ok "Deleted ~/.claude/CLAUDE.md (was only bootstrap content)."
    else
      : > "$CLAUDE_MD"
      ok "Cleared bootstrap lines from ~/.claude/CLAUDE.md (file kept, now empty)."
    fi
  elif [ "$DRY_RUN" = "true" ]; then
    dry "strip bootstrap redirect lines from ~/.claude/CLAUDE.md (user content preserved)."
  else
    echo "$CONTENT" > "$CLAUDE_MD"
    ok "Removed bootstrap redirect lines from ~/.claude/CLAUDE.md (user content preserved)."
  fi
else
  skip "~/.claude/CLAUDE.md not found — nothing to remove."
fi

info "The active_env line in your shell profile is removed in Section 8 below."

# =============================================================================
# SECTION 3: ~/.claude/skills/ symlink and user-skill symlinks in skills_sbin/
# =============================================================================
banner "SECTION 3: Skills symlink and user-skill symlinks"

SKILLS_DST="$OWNER_HOME/.claude/skills"
SKILLS_SBIN="$HORIZON_SYSTEM/skills_sbin"

# Remove user-skill symlinks from skills_sbin/ (created by horizon_aios_register_user_skills.py)
if [ -d "$SKILLS_SBIN" ]; then
  while IFS= read -r -d '' link; do
    target="$(readlink "$link" 2>/dev/null || true)"
    if echo "$target" | grep -q "usr_skills\|usrbin"; then
      if [ "$DRY_RUN" = "true" ]; then
        dry "remove user-skill symlink: $(basename "$link")"
      else
        rm -f "$link"
        ok "Removed user-skill symlink: $(basename "$link")"
      fi
    fi
  done < <(find "$SKILLS_SBIN" -maxdepth 1 -type l -print0 2>/dev/null)
fi

# Remove the ~/.claude/skills/ symlink itself
if [ -L "$SKILLS_DST" ]; then
  if [ "$DRY_RUN" = "true" ]; then
    dry "remove ~/.claude/skills/ symlink."
  else
    rm -f "$SKILLS_DST"
    ok "Removed ~/.claude/skills/ symlink."
  fi
elif [ -d "$SKILLS_DST" ]; then
  warn "~/.claude/skills/ is a real directory (not a symlink) — skipping removal."
  warn "  If it was not created by bootstrap, manage it manually."
else
  skip "~/.claude/skills/ not found — nothing to remove."
fi

# =============================================================================
# SECTION 4: handoffs/ and objectives/ directories (only if empty)
# =============================================================================
banner "SECTION 4: Handoffs and objectives directories"

for dirName in handoffs objectives; do
  dirPath="$HORIZON_ROOT/$dirName"
  if [ -d "$dirPath" ]; then
    if [ -z "$(ls -A "$dirPath" 2>/dev/null)" ]; then
      if [ "$DRY_RUN" = "true" ]; then
        dry "remove empty directory: $dirPath"
      else
        rmdir "$dirPath"
        ok "Removed empty directory: $dirPath"
      fi
    else
      warn "$dirPath is not empty — not removed."
      advisory "Review and remove $dirPath manually if no longer needed."
    fi
  else
    skip "$dirPath not found — nothing to remove."
  fi
done

# =============================================================================
# SECTION 5: ~/.horizon/ tree and ~/.claude/settings.json
# Bootstrap creates (via horizon_aios_switch.py init):
#   ~/.horizon/aios_registry.json
#   ~/.horizon/active_env.sh  (or active_env.ps1 on Windows Git Bash)
#   ~/.horizon/bin/aios-exec.sh  (and .ps1 on Windows)
# And optionally:
#   ~/.claude/settings.json
# =============================================================================
banner "SECTION 5: ~/.horizon/ tree and ~/.claude/settings.json"

HORIZON_DIR="$OWNER_HOME/.horizon"

if [ -d "$HORIZON_DIR" ]; then
  if [ "$DRY_RUN" = "true" ]; then
    dry "remove entire ~/.horizon/ directory (registry, active_env, wrappers)."
  elif confirm "Remove entire ~/.horizon/ directory (registry, active_env, wrappers)?"; then
    rm -rf "$HORIZON_DIR"
    ok "Removed ~/.horizon/."
  else
    skip "Skipping ~/.horizon/ removal."
  fi
else
  skip "~/.horizon/ not found — nothing to remove."
fi

# Decide whether bootstrap created settings.json (safe to remove) or the user owns
# it (must preserve). Precedence:
#   (a) PROVENANCE STAMP (authoritative): bootstrap writes ~/.claude/.horizon-settings.stamp
#       containing the lowercase SHA-256 hex of the settings.json bytes it wrote.
#       Re-hash the current file; equal => bootstrap-created and untouched => REMOVE
#       (confirm-gated) and drop the stamp. Differs => user edited it post-bootstrap =>
#       PRESERVE; drop the now-stale stamp (it no longer describes the file).
#   (b) NO STAMP (older installs / pre-existing user settings.json): fall back to the
#       content-equality heuristic — reconstruct template+substitution and compare,
#       BOM-safe. Match => remove; else => preserve.
# Stamp contract (must match bootstrap.sh writer byte-for-byte):
#   path   : ~/.claude/.horizon-settings.stamp
#   format : one line, lowercase SHA-256 hex of settings.json's on-disk bytes,
#            no trailing newline
SETTINGS_JSON="$OWNER_HOME/.claude/settings.json"
SETTINGS_STAMP="$OWNER_HOME/.claude/.horizon-settings.stamp"

# hash_file <path> -> prints lowercase SHA-256 hex (sha256sum on Linux, shasum on macOS)
hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

if [ -f "$SETTINGS_JSON" ]; then
  decision=""   # "remove" or "preserve"

  if [ -f "$SETTINGS_STAMP" ]; then
    # (a) Stamp present — authoritative provenance check.
    stamped="$(tr -d '[:space:]' < "$SETTINGS_STAMP" | tr '[:upper:]' '[:lower:]')"
    current="$(hash_file "$SETTINGS_JSON")"
    if [ -n "$stamped" ] && [ "$stamped" = "$current" ]; then
      info "Provenance stamp matches current settings.json — bootstrap-created, unmodified."
      decision="remove"
    else
      skip "~/.claude/settings.json was modified after bootstrap (provenance stamp mismatch) — PRESERVING it."
      advisory "If you want it gone, remove ~/.claude/settings.json manually."
      decision="preserve"
      # The stamp no longer describes the file; drop it regardless.
      if [ "$DRY_RUN" = "true" ]; then
        dry "remove stale provenance stamp ~/.claude/.horizon-settings.stamp."
      else
        rm -f "$SETTINGS_STAMP"
        ok "Removed stale provenance stamp ~/.claude/.horizon-settings.stamp."
      fi
    fi
  else
    # (b) No stamp — older install or pre-existing user file. Fall back to the
    # content-equality heuristic. Mirror bootstrap.sh Section 5b template + wrapper
    # selection exactly.
    AIOS_EXEC_WRAPPER="$OWNER_HOME/.horizon/bin/aios-exec.sh"
    case "$(uname -s)" in
      MINGW*|MSYS*|CYGWIN*)
        SETTINGS_TEMPLATE="$HORIZON_SYSTEM/templates/claude_code/settings.json"
        AIOS_EXEC_WRAPPER="$OWNER_HOME/.horizon/bin/aios-exec.ps1" ;;
      *) SETTINGS_TEMPLATE="$HORIZON_SYSTEM/templates/claude_code/settings_unix.json" ;;
    esac

    is_bootstrap_default=false
    if [ -f "$SETTINGS_TEMPLATE" ]; then
      expected="$(sed "s|AIOS_EXEC_WRAPPER|$AIOS_EXEC_WRAPPER|g" "$SETTINGS_TEMPLATE")"
      # Strip a leading UTF-8 BOM (bytes EF BB BF) from the on-disk content so a
      # BOM-only difference doesn't block removal. Use a literal BOM (built via
      # printf) rather than sed \x escapes, which are GNU-only and silently no-op
      # under BSD/macOS sed. $(...) already strips trailing newlines.
      bom="$(printf '\357\273\277')"
      on_disk="$(cat "$SETTINGS_JSON")"
      on_disk="${on_disk#"$bom"}"
      if [ "$on_disk" = "$expected" ]; then
        is_bootstrap_default=true
      fi
    fi

    if [ "$is_bootstrap_default" = "true" ]; then
      info "No provenance stamp; content matches the freshly-bootstrapped default (fallback heuristic)."
      decision="remove"
    else
      skip "~/.claude/settings.json differs from the bootstrap default (user-customized or user-authored) — PRESERVING it."
      advisory "If you want it gone, remove ~/.claude/settings.json manually."
      decision="preserve"
    fi
  fi

  if [ "$decision" = "remove" ]; then
    if [ "$DRY_RUN" = "true" ]; then
      dry "remove ~/.claude/settings.json (bootstrap-created) and its provenance stamp."
    elif confirm "~/.claude/settings.json was created by bootstrap and is unmodified — remove it?"; then
      rm -f "$SETTINGS_JSON"
      ok "Removed ~/.claude/settings.json (was the unmodified bootstrap default)."
      # Full teardown: drop the stamp so no dangling provenance file remains.
      if [ -f "$SETTINGS_STAMP" ]; then
        rm -f "$SETTINGS_STAMP"
        ok "Removed provenance stamp ~/.claude/.horizon-settings.stamp."
      fi
    else
      skip "Keeping ~/.claude/settings.json — remove manually if needed."
    fi
  fi
else
  skip "~/.claude/settings.json not found — nothing to remove."
  # Guard against a dangling stamp left after the file was removed by other means.
  if [ -f "$SETTINGS_STAMP" ]; then
    if [ "$DRY_RUN" = "true" ]; then
      dry "remove orphaned provenance stamp ~/.claude/.horizon-settings.stamp (settings.json already gone)."
    else
      rm -f "$SETTINGS_STAMP"
      ok "Removed orphaned provenance stamp ~/.claude/.horizon-settings.stamp."
    fi
  fi
fi

# =============================================================================
# SECTION 5b: ~/.claude/projects memory redirect (reverses bootstrap 5c)
# Bootstrap links ~/.claude/projects -> $HORIZON_ROOT/memory via horizon_aios_redirect_memory.py
# so the harness's per-project memory lives in the AIOS. We remove only the LINK —
# never the memory target's contents (that data lives in $HORIZON_ROOT/memory,
# part of the repo). Mirrors the Section 3 skills-symlink removal.
# =============================================================================
banner "SECTION 5b: ~/.claude/projects memory redirect"

PROJECTS_LINK="$OWNER_HOME/.claude/projects"
if [ -L "$PROJECTS_LINK" ]; then
  if [ "$DRY_RUN" = "true" ]; then
    dry "remove ~/.claude/projects symlink (memory redirect); memory data in \$HORIZON_ROOT/memory left intact."
  else
    rm -f "$PROJECTS_LINK"
    ok "Removed ~/.claude/projects symlink (memory redirect) — memory data left intact."
  fi
elif [ -d "$PROJECTS_LINK" ]; then
  warn "~/.claude/projects is a real directory (not a symlink) — leaving as-is."
  warn "  If bootstrap created it, manage it manually."
else
  skip "~/.claude/projects not found — nothing to remove."
fi

# Advise about any pre-redirect backup horizon_aios_redirect_memory.py left behind
found_proj_backup=false
for backup in "$OWNER_HOME/.claude/"projects.backup-*; do
  [ -e "$backup" ] || continue
  advisory "A pre-redirect harness-memory backup remains: $backup"
  found_proj_backup=true
done
if [ "$found_proj_backup" = "true" ]; then
  advisory "  To restore it: with the symlink removed (above), rename a backup back to ~/.claude/projects."
fi

# =============================================================================
# SECTION 6: Git hooks and core.hooksPath
# Bootstrap copies .git/hooks/commit-msg and .git/hooks/pre-commit,
# and sets git config core.hooksPath for the OS repo.
# =============================================================================
banner "SECTION 6: Git hooks and core.hooksPath"

GIT_DIR="$HORIZON_ROOT/.git"

if [ -d "$GIT_DIR" ]; then
  for hook in commit-msg pre-commit; do
    hook_path="$HORIZON_ROOT/.git/hooks/$hook"
    if [ -f "$hook_path" ]; then
      if [ "$DRY_RUN" = "true" ]; then
        dry "remove .git/hooks/$hook."
      else
        rm -f "$hook_path"
        ok "Removed .git/hooks/$hook."
      fi
    else
      skip ".git/hooks/$hook not found."
    fi
  done

  current_hooks_path="$(git -C "$HORIZON_ROOT" config --local core.hooksPath 2>/dev/null || true)"
  if [ -n "$current_hooks_path" ]; then
    if [ "$DRY_RUN" = "true" ]; then
      dry "unset git config core.hooksPath (currently: $current_hooks_path)."
    else
      git -C "$HORIZON_ROOT" config --local --unset core.hooksPath
      ok "Unset git config core.hooksPath (was: $current_hooks_path)."
    fi
  else
    skip "git core.hooksPath not set in local config — nothing to unset."
  fi
else
  skip "$HORIZON_ROOT is not a git repository — skipping git hooks cleanup."
fi

info "Global git include.path entries written by 'aios setup' are removed in Section 8 below."

# =============================================================================
# SECTION 7: System PATH — remove /etc/profile.d/horizon_aios.sh and /etc/paths.d/
# Bootstrap writes the horizon_aios.sh file and (on macOS) /etc/paths.d/horizon-aios.
# We delete the whole file if it was created by bootstrap (contains our marker comment).
# =============================================================================
banner "SECTION 7: System PATH files"

PROFILE_D_FILE="/etc/profile.d/horizon_aios.sh"

if [ -f "$PROFILE_D_FILE" ]; then
  if [ "$DRY_RUN" = "true" ]; then
    if grep -q "Horizon AIOS" "$PROFILE_D_FILE" 2>/dev/null; then
      dry "remove $PROFILE_D_FILE."
    else
      dry "strip Horizon AIOS lines from $PROFILE_D_FILE (other content preserved)."
    fi
  elif grep -q "Horizon AIOS" "$PROFILE_D_FILE" 2>/dev/null; then
    rm -f "$PROFILE_D_FILE"
    ok "Removed $PROFILE_D_FILE."
  else
    # File exists but wasn't created by us — strip only our lines
    TMPFILE="$(mktemp)"
    grep -v "horizon_system/bin\|Horizon AIOS" "$PROFILE_D_FILE" > "$TMPFILE" || true
    if [ -s "$TMPFILE" ]; then
      cp "$TMPFILE" "$PROFILE_D_FILE"
      chmod 644 "$PROFILE_D_FILE"
      ok "Removed Horizon AIOS lines from $PROFILE_D_FILE (other content preserved)."
    else
      rm -f "$PROFILE_D_FILE"
      ok "Removed $PROFILE_D_FILE (was empty after stripping)."
    fi
    rm -f "$TMPFILE"
  fi
else
  skip "$PROFILE_D_FILE not found — nothing to remove."
fi

# macOS: remove /etc/paths.d/horizon-aios
case "$(uname -s)" in
  Darwin)
    PATHS_D_FILE="/etc/paths.d/horizon-aios"
    if [ -f "$PATHS_D_FILE" ]; then
      if [ "$DRY_RUN" = "true" ]; then
        dry "remove $PATHS_D_FILE (macOS path_helper entry)."
      else
        rm -f "$PATHS_D_FILE"
        ok "Removed $PATHS_D_FILE (macOS path_helper entry)."
      fi
    else
      skip "$PATHS_D_FILE not found."
    fi
    ;;
esac

# =============================================================================
# SECTION 8: Shell profile line + global git include.path entries
# `aios setup` (horizon_aios_switch.py) actively writes machine-wide pointers that
# persist after the repo is gone and must be reversed here (older bootstrap only
# PRINTED advisories): (a) the active_env source line in the owner's shell profile,
# (b) the global git include.path -> harness_configs/git/gitconfig (framework), and
# (c) the global git include.path -> ai_os_etc/git_identity.local.gitconfig. The
# identity FILE lives under $HORIZON_ROOT and dies with the repo; only its global
# include.path entry is removed here. Git config is the OWNER's, so we act as $OWNER.
# =============================================================================
banner "SECTION 8: Shell profile line and global git include.path"

# (a) Strip the active_env source line from the owner's shell profile(s).
PROFILE_STRIPPED=false
for prof in "$OWNER_HOME/.bashrc" "$OWNER_HOME/.zshrc"; do
  [ -f "$prof" ] || continue
  grep -q "active_env.sh" "$prof" 2>/dev/null || continue
  if [ "$DRY_RUN" = "true" ]; then
    dry "strip active_env source line from $prof."
  else
    TMPFILE="$(mktemp)"
    grep -v "active_env.sh" "$prof" > "$TMPFILE" || true
    cat "$TMPFILE" > "$prof"
    rm -f "$TMPFILE"
    ok "Stripped active_env source line from $prof."
  fi
  PROFILE_STRIPPED=true
done
[ "$PROFILE_STRIPPED" = "false" ] && skip "No active_env source line found in owner shell profiles."

# (b)+(c) Unset ONLY the two global git include.path entries aios setup added,
# matched against the literal stored value, acting as the owner (ownership-safe).
owner_git() {
  if command -v sudo >/dev/null 2>&1 && [ "$OWNER" != "root" ]; then
    sudo -u "$OWNER" git "$@"
  else
    HOME="$OWNER_HOME" git "$@"
  fi
}
FRAMEWORK_GITCONFIG="$HORIZON_SYSTEM/harness_configs/git/gitconfig"
IDENTITY_GITCONFIG="$HORIZON_ETC/git_identity.local.gitconfig"
for target in "$FRAMEWORK_GITCONFIG" "$IDENTITY_GITCONFIG"; do
  if owner_git config --global --get-all include.path 2>/dev/null | grep -qxF "$target"; then
    if [ "$DRY_RUN" = "true" ]; then
      dry "git config --global --unset-all include.path (value: $target) for $OWNER."
    else
      esc="$(printf '%s' "$target" | sed 's/[^a-zA-Z0-9_/-]/\\&/g')"
      if owner_git config --global --unset-all include.path "^$esc$" 2>/dev/null; then
        ok "Removed global include.path -> $target"
      else
        warn "Could not unset include.path for $target — remove manually."
      fi
    fi
  else
    skip "Global include.path not set for $target — nothing to unset."
  fi
done

# =============================================================================
# SECTION 9: aios_local.conf and logs/ directory
# =============================================================================
banner "SECTION 9: aios_local.conf and logs/ directory"

LOCAL_CONF="$HORIZON_ETC/aios_local.conf"
if [ -f "$LOCAL_CONF" ]; then
  if [ "$DRY_RUN" = "true" ]; then
    dry "remove $LOCAL_CONF (machine-local config)."
  elif confirm "Remove $LOCAL_CONF (machine-local config)?"; then
    rm -f "$LOCAL_CONF"
    ok "Removed aios_local.conf."
  else
    skip "Keeping aios_local.conf — remove manually if needed."
  fi
else
  skip "aios_local.conf not found — nothing to remove."
fi

if [ -d "$HORIZON_LOGS" ]; then
  if [ -z "$(ls -A "$HORIZON_LOGS" 2>/dev/null)" ]; then
    if [ "$DRY_RUN" = "true" ]; then
      dry "remove empty logs/ directory ($HORIZON_LOGS)."
    else
      rmdir "$HORIZON_LOGS"
      ok "Removed empty logs/ directory."
    fi
  else
    warn "logs/ is not empty — not removed."
    advisory "Review and remove $HORIZON_LOGS manually if logs are no longer needed."
  fi
else
  skip "logs/ directory not found — nothing to remove."
fi

advisory "If you set up a cron sync schedule with horizon_aios_setup_sync_schedule.py, remove the cron entries manually:"
advisory "  crontab -e   # remove lines between the Horizon AIOS marker comments"

# =============================================================================
# SECTION 10: Remove brains-group ACEs from $HORIZON_SYSTEM subtrees
# horizon_aios_harden.py added these ACEs; we strip the brains group from each dir.
# We do NOT remove the 'brains' group itself — it may have brain OS user members.
# =============================================================================
banner "SECTION 10: Remove brains-group ACEs"

BRAINS_GROUP="brains"

DIRS_TO_CLEAN=(
  "$HORIZON_SYSTEM"
  "$HORIZON_BIN"
  "$HORIZON_SYSTEM/skills_bin"
  "$HORIZON_SBIN"
  "$HORIZON_SYSTEM/skills_sbin"
  "$HORIZON_LOGS"
)

OS="$(uname -s)"

group_exists() {
  case "$OS" in
    Darwin) dscl . -read /Groups/"$1" >/dev/null 2>&1 ;;
    *)      getent group "$1" >/dev/null 2>&1 ;;
  esac
}

if group_exists "$BRAINS_GROUP"; then
  for dir in "${DIRS_TO_CLEAN[@]}"; do
    if [ -d "$dir" ]; then
      if [ "$DRY_RUN" = "true" ]; then
        dry "remove brains-group ACL entries from: $dir"
      else
      case "$OS" in
        Linux)
          if command -v setfacl >/dev/null 2>&1; then
            setfacl -R -x "g:$BRAINS_GROUP" "$dir" 2>/dev/null || true
            setfacl -R -x "d:g:$BRAINS_GROUP" "$dir" 2>/dev/null || true
            ok "Removed brains-group ACL entries from: $dir"
          else
            # No setfacl — remove group write permission (conservative)
            chmod -R g-w "$dir" 2>/dev/null || true
            warn "setfacl not available; ran chmod g-w on $dir (ACL entries may remain)."
            advisory "Install 'acl' package and re-run, or manually verify ACLs on $dir."
          fi
          ;;
        Darwin)
          # macOS: chmod was the mechanism horizon_aios_harden.py used (no setfacl)
          chmod -R g+w "$dir" 2>/dev/null || true
          ok "Restored group-write permission on: $dir"
          ;;
        MINGW*|MSYS*|CYGWIN*)
          warn "Running under Git Bash on Windows — use uninstall.ps1 for icacls ACL removal."
          advisory "Run: icacls '$dir' /remove brains /T /C /Q   (/remove, not /remove:g, so deny ACEs go too)"
          ;;
      esac
      fi
    else
      skip "$dir not found — skipping ACE removal."
    fi
  done
  advisory "The 'brains' OS group was left in place — it may have brain OS user members."
  case "$OS" in
    Linux)  advisory "  To remove it: groupdel brains" ;;
    Darwin) advisory "  To remove it: dseditgroup -o delete -t group brains" ;;
  esac
  advisory "  Only do this after removing all brain OS user accounts."
else
  skip "brains group does not exist — no ACEs to remove."
fi

# =============================================================================
# SUMMARY
# =============================================================================
if [ "$DRY_RUN" = "true" ]; then
  banner "Dry run complete — no changes were made"
  echo ""
  echo "  Re-run without --dry-run (as root) to apply these actions."
  echo ""
  exit 0
fi

banner "Uninstall complete"
echo ""
echo "  Horizon AIOS bootstrap footprint removed from this machine."
echo ""
echo "  Manual steps still required (see [MANUAL] advisories above):"
echo "    1. Remove cron sync entries (if you set them up)"
echo "    2. Remove the 'brains' OS group (if no brain accounts remain)"
echo "    3. Remove any brain OS user accounts (use horizon_aios_create_brain.py remove flow)"
echo ""
