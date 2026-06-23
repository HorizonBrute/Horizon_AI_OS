#!/usr/bin/env python3
"""Horizon AIOS — aggregate the owner's skill view.

The primary user's ~/.claude/skills symlink points at skills_sbin, so skills_sbin
is the owner's skill *view*. The owner should see every tier (like /usr/bin is on
root's PATH while /usr/sbin is root-only), so this script links the two non-owner
skill sources into that view via per-skill directory symlink (Windows) / symlink (Unix):

  - $HORIZON_SYSTEM/skills_bin/<name>   — brain-tier skills (group-readable; OS,
                                          tracked). Brains see these directly via
                                          their own symlink; the owner sees them
                                          through these links.
  - $HORIZON_USRBIN/usr_skills/<name>   — the owner's machine-local skills
                                          (gitignored, never synced).

Each linked skill surfaces flat in ~/.claude/skills alongside the real skills_sbin
skills. Brains are unaffected: their ~/.claude/skills points at skills_bin only.

Idempotent. Safe to re-run after an upstream sync refreshes skills_sbin: real OS
skill directories in skills_sbin are never touched, stale links are pruned, and
links for skills currently present in the sources are (re)created. A source skill
whose name collides with a real skills_sbin OS skill is skipped (never shadows it).

The links are invisible to git via skills_sbin/.gitignore (whitelist of OS skills).
"""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
HORIZON_SYSTEM = os.path.dirname(SCRIPT_DIR)
HORIZON_ROOT = os.path.dirname(HORIZON_SYSTEM)
SKILLS_SBIN = os.path.join(HORIZON_SYSTEM, "skills_sbin")
SKILLS_BIN = os.path.join(HORIZON_SYSTEM, "skills_bin")
USR_SKILLS = os.path.join(HORIZON_ROOT, "usrbin", "usr_skills")

# Sources aggregated into the owner's view (skills_sbin), in precedence order.
SOURCES = [("skills_bin", SKILLS_BIN), ("usr_skills", USR_SKILLS)]

DRY_RUN = "--dry-run" in sys.argv
CHECK = "--check" in sys.argv  # report drift, change nothing, exit 1 if out of sync


def norm(p):
    return os.path.normcase(os.path.realpath(p))


def is_managed(entry_path):
    """True if entry_path resolves under one of the aggregated sources (our link)."""
    target = norm(entry_path)
    for _, base in SOURCES:
        b = norm(base)
        if target == b or target.startswith(b + os.sep):
            return True
    return False


def make_link(dst, target):
    if DRY_RUN:
        print(f"[LINK] {os.path.basename(dst)} -> {target} (dry-run)")
        return
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/D", dst, target],
                       check=True, stdout=subprocess.DEVNULL)
    else:
        os.symlink(target, dst, target_is_directory=True)
    print(f"[LINK] {os.path.basename(dst)} -> {target}")


def remove_link(dst):
    if DRY_RUN:
        print(f"[STALE] {os.path.basename(dst)} (would remove)")
        return
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "rmdir", dst], check=True, stdout=subprocess.DEVNULL)
    else:
        os.unlink(dst)
    print(f"[STALE] {os.path.basename(dst)} (removed)")


def collect_desired():
    """Map skill-name -> source path across all sources. First source wins on a
    name clash between sources (skills_bin before usr_skills)."""
    desired = {}
    for label, base in SOURCES:
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            src = os.path.join(base, name)
            if not os.path.isdir(src):
                continue
            if not os.path.isfile(os.path.join(src, "SKILL.md")):
                print(f"[SKIP] {label}/{name} has no SKILL.md - not a skill.")
                continue
            if name in desired:
                print(f"[SKIP] {label}/{name}: name already provided by another "
                      f"source - keeping the first.")
                continue
            desired[name] = src
    return desired


def compute_plan(desired):
    """Classify the current state vs desired. Returns (to_link, stale, shadowed,
    in_sync_count) without changing anything.
      to_link  : [(name, src)]   source skills missing a correct link
      stale    : [name]          managed links no longer backed by a source
      shadowed : [(name, src)]   source skills blocked by a real OS skill
    """
    to_link, stale, shadowed, in_sync = [], [], [], []
    for name in sorted(os.listdir(SKILLS_SBIN)):
        dst = os.path.join(SKILLS_SBIN, name)
        if is_managed(dst) and name not in desired:
            stale.append(name)
    for name, src in desired.items():
        dst = os.path.join(SKILLS_SBIN, name)
        if os.path.exists(dst) or os.path.islink(dst):
            if not is_managed(dst):
                shadowed.append((name, src))
            elif norm(dst) == norm(src):
                in_sync.append(name)
            else:
                to_link.append((name, src))  # managed but points elsewhere
        else:
            to_link.append((name, src))
    return to_link, stale, shadowed, in_sync


def report_check(desired, plan):
    to_link, stale, shadowed, in_sync = plan
    print(f"[CHECK] owner view: {SKILLS_SBIN}")
    print(f"[CHECK] sources: {len(desired)} skill(s) across skills_bin + usr_skills")
    for name in sorted(in_sync):
        print(f"  [OK]     {name} — linked")
    for name, _ in to_link:
        print(f"  [DRIFT]  {name} — missing/incorrect link")
    for name in stale:
        print(f"  [DRIFT]  {name} — stale link (source gone)")
    for name, _ in shadowed:
        print(f"  [SHADOW] {name} — blocked by a real OS skill of the same name")
    drift = len(to_link) + len(stale)
    if drift == 0:
        print("[OK] In sync — owner view matches the filesystem sources.")
        return 0
    print(f"[DRIFT] {drift} item(s) out of sync — run without --check to heal.")
    return 1


def main():
    # usr_skills is owner-local and may not exist yet; create it so the path is
    # stable. skills_bin is part of the OS tree and is expected to exist.
    # In --check mode, make no changes at all (read-only).
    if not os.path.isdir(USR_SKILLS) and not CHECK:
        os.makedirs(USR_SKILLS, exist_ok=True)
        print(f"[INFO] Created {USR_SKILLS} (empty).")
    if not CHECK:
        os.makedirs(SKILLS_SBIN, exist_ok=True)

    desired = collect_desired()
    plan = compute_plan(desired)

    if CHECK:
        sys.exit(report_check(desired, plan))

    to_link, stale, shadowed, _ = plan
    for name in stale:
        remove_link(os.path.join(SKILLS_SBIN, name))
    for name, _ in shadowed:
        print(f"[SKIP] {name}: a real OS skill of this name exists in "
              f"skills_sbin - refusing to shadow it.")
    for name, src in to_link:
        dst = os.path.join(SKILLS_SBIN, name)
        if (os.path.exists(dst) or os.path.islink(dst)) and is_managed(dst):
            remove_link(dst)  # repoint a managed link
        make_link(dst, src)

    print(f"[OK] owner view aggregated (skills_bin + usr_skills): "
          f"{len(desired) - len(shadowed)} skill(s) linked, "
          f"{len(stale)} stale removed.")


if __name__ == "__main__":
    main()
