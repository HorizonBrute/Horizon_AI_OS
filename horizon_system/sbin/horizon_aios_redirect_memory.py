#!/usr/bin/env python3
"""Horizon AIOS - redirect the harness's per-project state (incl. memory) into the AIOS.

Claude Code stores per-project state - conversation transcripts AND the file-based
memory the agent writes - under `~/.claude/projects/<cwd-hash>/`. By default that
lives OUTSIDE the AIOS, ungoverned by its gitignore / sync-exclusion / logging /
hardening rules. This script redirects the whole `~/.claude/projects/` directory
into the AIOS so every per-project hash dir (existing and future) lands under
`$HORIZON_ROOT/memory/` - centrally available to any harness the operator points
at the AIOS, and subject to AIOS governance.

This is the OWNER redirect. Brains are handled separately by horizon_aios_create_brain.py,
whose `~/.claude` → `brains/<name>/.claude/` redirect already places each brain's
projects/memory inside its own isolated, group-owned brain folder.

Mechanism (mirrors the skills symlink):
    ~/.claude/projects/   ->  $HORIZON_ROOT/memory/      (directory symlink on Windows,
                                                          symlink on Unix)

The migration MOVES existing content from ~/.claude/projects/ into the memory
root (merging), after taking a backup. It is idempotent: if the symlink is
already in place pointing at the memory root, it does nothing.

IMPORTANT: close Claude Code before running - the active session holds its own
project dir open. Run this, then restart Claude.

Usage:
    python horizon_aios_redirect_memory.py [--horizon-root PATH] [--dry-run] [--no-backup]
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))      # horizon_system/sbin
THIS_SYSTEM = os.path.dirname(SCRIPT_DIR)                      # horizon_system
THIS_ROOT = os.path.dirname(THIS_SYSTEM)                       # repo root


def ok(m):   print(f"  [OK]   {m}")
def info(m): print(f"  [INFO] {m}")
def warn(m): print(f"  [WARN] {m}")
def err(m):  print(f"  [ERR]  {m}", file=sys.stderr)


def is_reparse(path):
    """True if path is a junction/symlink (reparse point), without following it."""
    if os.path.islink(path):
        return True
    if os.name == "nt":
        try:
            attrs = os.stat(path, follow_symlinks=False).st_file_attributes
            return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
        except (OSError, AttributeError):
            return False
    return False


def link_target(path):
    try:
        return os.path.realpath(path)
    except OSError:
        return None


def make_link(link, target):
    """Create link -> target (directory symlink on Windows, dir symlink on Unix)."""
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/D", link, target],
                       check=True, stdout=subprocess.DEVNULL)
    else:
        os.symlink(target, link, target_is_directory=True)


def remove_link(path):
    """Remove a junction/symlink WITHOUT touching the target's contents."""
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "rmdir", path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        os.unlink(path)


def merge_move(src_dir, dst_dir, dry):
    """Move every child of src_dir into dst_dir. Skip (warn) on name collisions
    so nothing in dst is overwritten; the operator can reconcile leftovers."""
    leftovers = []
    for name in os.listdir(src_dir):
        s = os.path.join(src_dir, name)
        d = os.path.join(dst_dir, name)
        if os.path.exists(d):
            warn(f"collision, left in place: {name} (already in memory root)")
            leftovers.append(name)
            continue
        if dry:
            info(f"would move {name} -> {dst_dir}")
        else:
            shutil.move(s, d)
    return leftovers


def main():
    p = argparse.ArgumentParser(description="Redirect ~/.claude/projects into $HORIZON_ROOT/memory.")
    p.add_argument("--horizon-root", default=None,
                   help="HORIZON_ROOT path. Default: env HORIZON_ROOT, else derived from this script.")
    p.add_argument("--dry-run", action="store_true", help="Show actions, change nothing.")
    p.add_argument("--no-backup", action="store_true", help="Skip the safety backup of ~/.claude/projects.")
    args = p.parse_args()
    dry = args.dry_run

    root = os.path.abspath(args.horizon_root or os.environ.get("HORIZON_ROOT") or THIS_ROOT)
    if not os.path.isdir(os.path.join(root, "horizon_system")):
        err(f"Not a valid HORIZON_ROOT: {root}")
        return 1

    memory_root = os.path.join(root, "memory")
    projects = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    print(f"\nOwner memory redirect:\n  ~/.claude/projects  ->  {memory_root}\n")

    # Already redirected?
    if is_reparse(projects):
        tgt = link_target(projects)
        if tgt and os.path.normcase(tgt) == os.path.normcase(os.path.realpath(memory_root)
                                                             if os.path.exists(memory_root) else memory_root):
            ok("Already redirected to the AIOS memory root - nothing to do.")
            return 0
        warn(f"~/.claude/projects is already a link, but points elsewhere: {tgt}")
        warn("Resolve manually, then re-run.")
        return 1

    if not os.path.exists(projects):
        # Nothing to migrate; just create the memory root and link.
        info("~/.claude/projects does not exist yet - creating memory root + link only.")
        if not dry:
            os.makedirs(memory_root, exist_ok=True)
            os.makedirs(os.path.dirname(projects), exist_ok=True)
            make_link(projects, memory_root)
        ok("Linked ~/.claude/projects -> AIOS memory root.")
        return 0

    # projects is a real directory with content - migrate it.
    if not dry:
        os.makedirs(memory_root, exist_ok=True)

    if not args.no_backup:
        backup = projects + ".backup-" + datetime.now().strftime("%Y%m%d_%H%M%S")
        if dry:
            info(f"would back up ~/.claude/projects -> {backup}")
        else:
            shutil.copytree(projects, backup, symlinks=True)
            ok(f"Backed up ~/.claude/projects -> {backup}")
            info("Keep this backup until you've confirmed memory works; delete it when satisfied.")

    leftovers = merge_move(projects, memory_root, dry)

    if dry:
        info("Dry run complete - no changes made.")
        return 0

    if leftovers:
        warn(f"{len(leftovers)} item(s) left in ~/.claude/projects due to collisions - "
             "reconcile them, then re-run to finish linking.")
        return 1

    # projects is now empty - replace it with the symlink.
    os.rmdir(projects)
    make_link(projects, memory_root)
    ok(f"Redirected ~/.claude/projects -> {memory_root}")
    print()
    warn("Restart Claude Code now - it must re-open its project dir through the new link.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
