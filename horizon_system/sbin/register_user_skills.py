#!/usr/bin/env python3
"""Horizon AIOS — register machine-local user skills into skills_sbin.

User skills live in $HORIZON_USRBIN/usr_skills/<name>/SKILL.md (gitignored,
never synced). This script (re)builds a per-skill junction (Windows) or symlink
(Unix) at $HORIZON_SYSTEM/skills_sbin/<name> pointing at each user skill, so they
surface flat through the existing ~/.claude/skills junction alongside OS skills.

Idempotent. Safe to re-run after an upstream sync overwrites skills_sbin: real OS
skill directories are never touched, stale user-skill links are pruned, and links
for skills currently present in usr_skills are (re)created.

The links are invisible to git via skills_sbin/.gitignore (whitelist of OS skills).
"""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
HORIZON_SYSTEM = os.path.dirname(SCRIPT_DIR)
HORIZON_ROOT = os.path.dirname(HORIZON_SYSTEM)
SKILLS_SBIN = os.path.join(HORIZON_SYSTEM, "skills_sbin")
USR_SKILLS = os.path.join(HORIZON_ROOT, "usrbin", "usr_skills")

DRY_RUN = "--dry-run" in sys.argv


def norm(p):
    return os.path.normcase(os.path.realpath(p))


def is_managed(entry_path):
    """True if entry_path resolves to a location under usr_skills (a link we own)."""
    target = norm(entry_path)
    base = norm(USR_SKILLS)
    return target == base or target.startswith(base + os.sep)


def make_link(dst, target):
    if DRY_RUN:
        print(f"[LINK] {os.path.basename(dst)} -> {target} (dry-run)")
        return
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", dst, target],
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


def main():
    if not os.path.isdir(USR_SKILLS):
        os.makedirs(USR_SKILLS, exist_ok=True)
        print(f"[INFO] Created {USR_SKILLS} (empty — no user skills to register).")
    os.makedirs(SKILLS_SBIN, exist_ok=True)

    # Desired: every usr_skills/<name>/ that contains a SKILL.md
    desired = {}
    for name in sorted(os.listdir(USR_SKILLS)):
        src = os.path.join(USR_SKILLS, name)
        if os.path.isdir(src) and os.path.isfile(os.path.join(src, "SKILL.md")):
            desired[name] = src
        elif os.path.isdir(src):
            print(f"[SKIP] usr_skills/{name} has no SKILL.md - not a skill.")

    # Prune stale managed links (point into usr_skills but no longer desired)
    for name in sorted(os.listdir(SKILLS_SBIN)):
        dst = os.path.join(SKILLS_SBIN, name)
        if is_managed(dst) and name not in desired:
            remove_link(dst)

    # Create/repair links for desired user skills
    linked = 0
    for name, src in desired.items():
        dst = os.path.join(SKILLS_SBIN, name)
        if os.path.exists(dst) or os.path.islink(dst):
            if not is_managed(dst):
                print(f"[SKIP] {name}: a real OS skill of this name exists in "
                      f"skills_sbin - refusing to shadow it. Rename the user skill.")
                continue
            if norm(dst) == norm(src):
                linked += 1
                continue  # already correct
            remove_link(dst)
        make_link(dst, src)
        linked += 1

    print(f"[OK] {linked} user skill(s) registered from {USR_SKILLS}.")


if __name__ == "__main__":
    main()
