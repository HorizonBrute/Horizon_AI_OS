#!/usr/bin/env python3
"""Horizon AIOS - reverse all machine-level configuration written by bootstrap.

This is NOT a repo deletion tool.  It removes the machine-local *pointers* to
AIOS — the junction, the CLAUDE.md redirect, the active_env files, the
aios-exec wrappers, and the registry — without touching the AIOS repo itself,
brain accounts, or user data.

Usage:
    python uninstall_aios.py [--yes] [--dry-run] [--remove-path]

    --yes / -y      Skip interactive confirmations (still shows actions).
    --dry-run       Print every action without making any changes.
    --remove-path   Attempt to remove the system PATH entry (requires
                    admin/root); prints an advisory if it fails.

Default (no flags): shows a summary, asks for confirmation, then attempts
system PATH removal.

Env:
    AIOS_SWITCH_HOME   Override the home base (for testing). Defaults to ~.
"""

import argparse
import os
import platform
import subprocess
import sys


# --- Home-anchored paths (overridable for testing) ----------------------------
HOME = os.environ.get("AIOS_SWITCH_HOME") or os.path.expanduser("~")
HORIZON_HOME = os.path.join(HOME, ".horizon")
REGISTRY = os.path.join(HORIZON_HOME, "aios_registry.json")
ACTIVE_ENV_PS1 = os.path.join(HORIZON_HOME, "active_env.ps1")
ACTIVE_ENV_SH = os.path.join(HORIZON_HOME, "active_env.sh")
WRAPPER_DIR = os.path.join(HORIZON_HOME, "bin")
WRAPPER_PS1 = os.path.join(WRAPPER_DIR, "aios-exec.ps1")
WRAPPER_SH = os.path.join(WRAPPER_DIR, "aios-exec.sh")
CLAUDE_DIR = os.path.join(HOME, ".claude")
CLAUDE_MD = os.path.join(CLAUDE_DIR, "CLAUDE.md")
CLAUDE_SETTINGS = os.path.join(CLAUDE_DIR, "settings.json")
SKILLS_LINK = os.path.join(CLAUDE_DIR, "skills")


# --- small output helpers (mirror aios_switch.py) -----------------------------
def ok(msg):   print(f"  [OK]   {msg}")
def info(msg): print(f"  [INFO] {msg}")
def warn(msg): print(f"  [WARN] {msg}")
def err(msg):  print(f"  [ERR]  {msg}", file=sys.stderr)


def _confirm(prompt, yes):
    if yes:
        return True
    try:
        return input(f"  {prompt} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


# --- path helpers --------------------------------------------------------------
def _is_reparse(path):
    """Windows: True if path is a reparse point (junction/symlink)."""
    try:
        attrs = os.stat(path, follow_symlinks=False).st_file_attributes
        return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except (OSError, AttributeError):
        return False


def _is_junction_or_symlink(path):
    """True if path is a symlink or Windows junction (reparse point)."""
    if os.path.islink(path):
        return True
    if os.name == "nt" and os.path.isdir(path) and _is_reparse(path):
        return True
    return False


def _remove_link(path):
    """Remove a junction/symlink without following it into the target."""
    if os.name == "nt":
        # rmdir (without /s) removes the reparse point only — never recurses
        # into the target for a junction.
        subprocess.run(["cmd", "/c", "rmdir", path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        os.unlink(path)


def _remove_file(path, dry):
    """Remove a regular file if it exists."""
    if not os.path.exists(path) and not os.path.islink(path):
        info(f"not found (already removed?): {path}")
        return
    if dry:
        info(f"would remove {path}")
        return
    os.remove(path)
    ok(f"Removed {path}")


def _remove_dir_if_empty(path, dry):
    """Remove a directory only if it contains no entries."""
    if not os.path.isdir(path):
        return
    try:
        entries = os.listdir(path)
    except OSError:
        return
    if entries:
        info(f"Not removing {path} — still contains {len(entries)} item(s): "
             f"{', '.join(entries[:3])}{'...' if len(entries) > 3 else ''}")
        return
    if dry:
        info(f"would remove empty directory {path}")
        return
    try:
        os.rmdir(path)
        ok(f"Removed empty directory {path}")
    except OSError as exc:
        warn(f"Could not remove {path}: {exc}")


# --- individual removal steps -------------------------------------------------
def remove_skills_link(dry):
    """Remove ~/.claude/skills junction/symlink (without touching the target)."""
    if not os.path.exists(SKILLS_LINK) and not os.path.islink(SKILLS_LINK):
        info(f"~/.claude/skills not found — skipping.")
        return
    if not _is_junction_or_symlink(SKILLS_LINK):
        warn(f"~/.claude/skills is a real directory, not a junction/symlink — skipping. "
             "Remove manually if you no longer need it.")
        return
    if dry:
        info(f"would remove skills junction/symlink: {SKILLS_LINK}")
        return
    try:
        _remove_link(SKILLS_LINK)
        ok(f"Removed skills junction/symlink: {SKILLS_LINK}")
    except (OSError, subprocess.CalledProcessError) as exc:
        err(f"Failed to remove skills junction {SKILLS_LINK}: {exc}")


def remove_claude_md(dry):
    """Remove ~/.claude/CLAUDE.md (the AIOS @-redirect stub)."""
    if not os.path.isfile(CLAUDE_MD):
        info(f"~/.claude/CLAUDE.md not found — skipping.")
        return
    # Read content to confirm it's the AIOS redirect (don't clobber user edits)
    try:
        with open(CLAUDE_MD, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        content = ""
    if "@" not in content or "CLAUDE.md" not in content:
        warn(f"~/.claude/CLAUDE.md does not look like an AIOS @-redirect. "
             "Leaving it in place — remove manually if needed.")
        return
    _remove_file(CLAUDE_MD, dry)


def remove_active_env(dry):
    """Remove ~/.horizon/active_env.{ps1,sh}."""
    _remove_file(ACTIVE_ENV_PS1, dry)
    _remove_file(ACTIVE_ENV_SH, dry)


def remove_wrappers(dry):
    """Remove ~/.horizon/bin/aios-exec.{ps1,sh}."""
    _remove_file(WRAPPER_PS1, dry)
    _remove_file(WRAPPER_SH, dry)


def remove_registry(dry):
    """Remove ~/.horizon/aios_registry.json."""
    _remove_file(REGISTRY, dry)


def remove_horizon_dirs(dry):
    """Remove ~/.horizon/bin/ and ~/.horizon/ if now empty."""
    _remove_dir_if_empty(WRAPPER_DIR, dry)
    _remove_dir_if_empty(HORIZON_HOME, dry)


def handle_settings_json(yes, dry):
    """Advisory + optional removal of ~/.claude/settings.json."""
    if not os.path.isfile(CLAUDE_SETTINGS):
        info(f"~/.claude/settings.json not found — nothing to do.")
        return

    print()
    warn(f"{CLAUDE_SETTINGS} was written by AIOS.")
    warn("Delete it to let Claude Code regenerate defaults, or edit it manually "
         "to remove AIOS-specific hooks.")

    if dry:
        info(f"would ask to delete {CLAUDE_SETTINGS} (dry-run — no action taken)")
        return

    if _confirm(f"Delete {CLAUDE_SETTINGS} now?", yes):
        try:
            os.remove(CLAUDE_SETTINGS)
            ok(f"Removed {CLAUDE_SETTINGS}")
        except OSError as exc:
            err(f"Failed to remove {CLAUDE_SETTINGS}: {exc}")
    else:
        info(f"Left {CLAUDE_SETTINGS} in place.")


def remove_system_path(dry):
    """Attempt to remove $HORIZON_BIN from the system-level PATH.

    Mirrors the inverse of update_system_path() in aios_switch.py.
    Degrades gracefully with an advisory if not elevated.
    """
    _ADVISORY = (
        "Could not update system PATH (insufficient privileges). "
        "Re-run with --remove-path as Administrator / sudo, or remove the "
        "AIOS entry manually:\n"
        "  Windows: remove the horizon_system\\bin entry from the Machine-scope PATH "
        "(System Properties > Environment Variables > System variables > Path)\n"
        "  Linux/macOS: delete /etc/profile.d/horizon_aios.sh\n"
        "  macOS (additional): delete /etc/paths.d/horizon-aios"
    )

    if dry:
        info("would attempt to remove horizon_system/bin from system PATH")
        return

    if os.name == "nt":
        # Remove any entry ending in horizon_system\bin from Machine-scope PATH.
        ps_script = (
            "$mp = [System.Environment]::GetEnvironmentVariable('Path','Machine');"
            "$entries = $mp -split ';' | ForEach-Object { $_.TrimEnd('\\').TrimEnd('/') };"
            "$cleaned = $entries | Where-Object { $_ -notmatch '(?i)horizon_system[/\\\\]bin$' };"
            "$newPath = ($cleaned) -join ';';"
            "[System.Environment]::SetEnvironmentVariable('Path', $newPath, 'Machine')"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NonInteractive", "-Command", ps_script],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                warn(_ADVISORY)
                if result.stderr.strip():
                    info(f"Detail: {result.stderr.strip()[:200]}")
            else:
                ok("Removed horizon_system/bin from Machine-scope PATH")
        except OSError as exc:
            warn(_ADVISORY)
            info(f"Detail: {exc}")

    else:
        # Linux / macOS: remove /etc/profile.d/horizon_aios.sh
        profile_d = "/etc/profile.d/horizon_aios.sh"
        if os.path.isfile(profile_d):
            try:
                os.remove(profile_d)
                ok(f"Removed {profile_d}")
            except PermissionError:
                warn(_ADVISORY)
        else:
            info(f"{profile_d} not found — already removed or was never written.")

        # macOS: also remove /etc/paths.d/horizon-aios
        if platform.system() == "Darwin":
            paths_d = "/etc/paths.d/horizon-aios"
            if os.path.isfile(paths_d):
                try:
                    os.remove(paths_d)
                    ok(f"Removed {paths_d}")
                except PermissionError:
                    warn(_ADVISORY)
            else:
                info(f"{paths_d} not found — already removed or was never written.")


# --- advisories ---------------------------------------------------------------
def print_manual_steps():
    print()
    print("=" * 60)
    print("  Manual steps remaining")
    print("=" * 60)
    print()
    print("  Git config (cannot be safely automated):")
    print()
    print("    To remove the AIOS git hooks:")
    print("      git config --unset core.hooksPath")
    print("    (run from $HORIZON_ROOT, i.e., the AIOS repo directory)")
    print()
    print("    To remove the AIOS gitconfig include (if you added it):")
    print("      git config --global --unset include.path")
    print()
    print("  Shell profile:")
    print()
    print("    Remove the AIOS line from your shell profile")
    print("    (~/.bashrc, ~/.zshrc, or PowerShell $PROFILE).")
    print("    The line sources one of:")
    print("      ~/.horizon/active_env.sh   (bash/zsh)")
    print("      ~/.horizon/active_env.ps1  (PowerShell)")
    print()


def print_summary():
    """Print a header describing what will be removed."""
    print()
    print("=" * 60)
    print("  Horizon AIOS Uninstall")
    print("=" * 60)
    print()
    print("  This will remove the machine-local AIOS pointers:")
    print()
    print(f"    {SKILLS_LINK}")
    print(f"      (junction/symlink — target files are NOT deleted)")
    print(f"    {CLAUDE_MD}")
    print(f"    {ACTIVE_ENV_PS1}")
    print(f"    {ACTIVE_ENV_SH}")
    print(f"    {WRAPPER_PS1}")
    print(f"    {WRAPPER_SH}")
    print(f"    {REGISTRY}")
    print(f"    {WRAPPER_DIR}  (if empty after removal)")
    print(f"    {HORIZON_HOME}  (if empty after removal)")
    print(f"    {CLAUDE_SETTINGS}  (advisory + optional)")
    print()
    print("  The AIOS repo, brain accounts, handoffs, objectives, and")
    print("  logs are NOT touched.")
    print()


# --- main ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        prog="uninstall_aios",
        description="Reverse all machine-level Horizon AIOS bootstrap configuration.")
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip interactive confirmations (still shows what it's doing).")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print every action without making any changes.")
    parser.add_argument(
        "--remove-path", action="store_true",
        help="Attempt to remove the system PATH entry (requires admin/root; "
             "advisory if it fails). Enabled by default when running interactively.")
    args = parser.parse_args()

    dry = args.dry_run
    yes = args.yes

    if dry:
        print()
        info("DRY RUN — no changes will be made.")

    print_summary()

    if not yes and not dry:
        if not _confirm("Proceed with uninstall?", yes):
            info("Aborted — no changes made.")
            sys.exit(0)

    print()
    print("  Removing AIOS machine-local pointers ...")
    print()

    # Step 1: skills junction/symlink
    remove_skills_link(dry)

    # Step 2: ~/.claude/CLAUDE.md
    remove_claude_md(dry)

    # Step 3: active_env files
    remove_active_env(dry)

    # Step 4: aios-exec wrappers
    remove_wrappers(dry)

    # Step 5: registry
    remove_registry(dry)

    # Step 6-7: ~/.horizon/bin/ and ~/.horizon/ if now empty
    remove_horizon_dirs(dry)

    # settings.json: advisory + optional removal
    handle_settings_json(yes, dry)

    # System PATH: attempt removal (default yes; advisory on failure)
    # In interactive mode (no --yes, no --dry-run) always attempt.
    # With --yes we attempt as well; with --dry-run we describe what we'd do.
    # --remove-path is an explicit signal to try even when --yes is not set.
    attempt_path = args.remove_path or yes or (not yes and not dry)
    if attempt_path or dry:
        print()
        info("Attempting system PATH cleanup ...")
        remove_system_path(dry)

    # Always print manual steps regardless of what was auto-removed
    print_manual_steps()

    if dry:
        print()
        info("Dry run complete — no changes were made.")
    else:
        print()
        ok("Uninstall complete.")
        warn("Open a new shell — env changes do not reach already-running sessions.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
