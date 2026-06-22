#!/usr/bin/env python3
"""Horizon AIOS - back up user data (memory, handoffs, objectives) to YOUR remote.

The framework `.gitignore` deliberately excludes per-machine user data (memory =
conversation transcripts + agent memory, handoffs, objectives) so it never ships
with the AIOS or leaks into the public upstream. But you may want that data
version-controlled on YOUR OWN git remote for backup and cross-machine awareness.

This helper does that WITHOUT editing the framework `.gitignore` (which would
collide with upstream updates). It force-adds the data paths into a temporary
git index, builds a commit containing ONLY those paths, and pushes it to a
dedicated per-machine backup branch on YOUR remote. The working tree, the staging
area, and the framework branch are never touched - so this is safe to run from an
active session and never pollutes the framework history.

SAFETY: it refuses to push to the canonical Horizon AIOS upstream
(HorizonBrute/Horizon_AI_OS) - that would publish your private transcripts. You
must configure your OWN remote.

Config (horizon_system/ai_os_etc/aios_local.conf), overridable by CLI flags:
    AIOS_BACKUP_REMOTE=<git remote name or URL>     # required (no default)
    AIOS_BACKUP_BRANCH=aios-backup/<hostname>       # default: per-machine
    AIOS_BACKUP_PATHS=memory handoffs objectives    # default

Usage:
    python backup_user_data.py [--remote R] [--branch B] [--paths P ...]
                               [--message M] [--dry-run]
"""

import argparse
import os
import re
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
THIS_SYSTEM = os.path.dirname(SCRIPT_DIR)
THIS_ROOT = os.path.dirname(THIS_SYSTEM)

# Pushing user data to THIS slug would publish private transcripts to the public
# project. The guard matches org/repo (case-insensitive) so downstream forks
# under a different org are allowed.
UPSTREAM_SLUG = re.compile(r"horizonbrute/horizon_ai_os(\.git)?$", re.IGNORECASE)

DEFAULT_PATHS = ["memory", "handoffs", "objectives"]


def ok(m):   print(f"  [OK]   {m}")
def info(m): print(f"  [INFO] {m}")
def warn(m): print(f"  [WARN] {m}")
def err(m):  print(f"  [ERR]  {m}", file=sys.stderr)


def git(args, root, capture=True, env=None, check=True):
    full = dict(os.environ)
    if env:
        full.update(env)
    r = subprocess.run(["git", "-C", root] + args, capture_output=capture,
                       text=True, env=full)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return (r.stdout or "").strip()


def read_conf(root):
    """Best-effort parse of aios_local.conf (KEY=value)."""
    conf = {}
    path = os.path.join(root, "horizon_system", "ai_os_etc", "aios_local.conf")
    if not os.path.isfile(path):
        return conf
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            conf[k.strip()] = v.strip()
    return conf


def resolve_remote_url(remote, root):
    """If `remote` is a configured remote name, return its push URL; else assume
    it is already a URL."""
    try:
        return git(["remote", "get-url", "--push", remote], root)
    except RuntimeError:
        return remote  # treat as a literal URL


def main():
    p = argparse.ArgumentParser(description="Back up AIOS user data to your own remote.")
    p.add_argument("--remote", help="Git remote name or URL to push to (or AIOS_BACKUP_REMOTE).")
    p.add_argument("--branch", help="Backup branch (default AIOS_BACKUP_BRANCH or aios-backup/<host>).")
    p.add_argument("--paths", nargs="+", help="Paths to back up (default AIOS_BACKUP_PATHS or memory handoffs objectives).")
    p.add_argument("--message", help="Commit message (default: timestamped).")
    p.add_argument("--dry-run", action="store_true", help="Show what would be backed up; do not commit or push.")
    args = p.parse_args()

    root = os.environ.get("HORIZON_ROOT") or THIS_ROOT
    if not os.path.isdir(os.path.join(root, ".git")):
        err(f"Not a git repo: {root}")
        return 1
    conf = read_conf(root)

    remote = args.remote or conf.get("AIOS_BACKUP_REMOTE")
    if not remote:
        err("No backup remote configured. Set AIOS_BACKUP_REMOTE in aios_local.conf "
            "or pass --remote. It must be YOUR remote, not the public upstream.")
        return 1

    host = socket.gethostname().lower()
    branch = args.branch or conf.get("AIOS_BACKUP_BRANCH") or f"aios-backup/{host}"
    paths = args.paths or (conf.get("AIOS_BACKUP_PATHS") or "").split() or DEFAULT_PATHS

    # --- leak guard ---
    url = resolve_remote_url(remote, root)
    if UPSTREAM_SLUG.search(url):
        err(f"REFUSING: backup remote '{remote}' ({url}) is the public Horizon AIOS "
            "upstream. Pushing your memory/transcripts there would publish private "
            "data. Configure a remote pointing at YOUR OWN repository.")
        return 2

    # --- only existing paths ---
    present = [p for p in paths if os.path.exists(os.path.join(root, p))]
    missing = [p for p in paths if p not in present]
    for m in missing:
        info(f"skip (not present): {m}")
    if not present:
        err("None of the backup paths exist - nothing to back up.")
        return 1

    print(f"\nBack up {present} -> remote '{remote}' branch '{branch}'\n")

    # --- build a commit containing ONLY the data paths, via a temp index ---
    tmp_index = tempfile.NamedTemporaryFile(prefix="aios_backup_idx_", delete=False).name
    os.unlink(tmp_index)  # git wants to create it itself
    env = {"GIT_INDEX_FILE": tmp_index}
    try:
        git(["read-tree", "--empty"], root, env=env)
        # -f bypasses .gitignore (these paths are intentionally ignored).
        git(["add", "-f", "--"] + present, root, env=env)
        files = [l for l in git(["ls-files"], root, env=env).splitlines() if l]
        info(f"{len(files)} file(s) staged into the backup snapshot.")

        if args.dry_run:
            info("Dry run - not committing or pushing.")
            return 0

        tree = git(["write-tree"], root, env=env)
        parent = None
        try:
            parent = git(["rev-parse", "--verify", f"refs/heads/{branch}"], root)
        except RuntimeError:
            pass  # first backup on this branch
        msg = args.message or f"aios backup {datetime.now(timezone.utc).isoformat()} ({host})"
        commit_args = ["commit-tree", tree, "-m", msg]
        if parent:
            commit_args += ["-p", parent]
        commit = git(commit_args, root)
        git(["update-ref", f"refs/heads/{branch}", commit], root)
        ok(f"Committed snapshot {commit[:10]} to local branch '{branch}'.")
    finally:
        if os.path.exists(tmp_index):
            os.unlink(tmp_index)

    # --- push to YOUR remote ---
    info(f"Pushing '{branch}' -> {remote} ...")
    git(["push", remote, f"refs/heads/{branch}:refs/heads/{branch}"], root, capture=False)
    ok(f"Backed up to {remote}/{branch}. Pull it on another machine for cross-machine awareness.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
