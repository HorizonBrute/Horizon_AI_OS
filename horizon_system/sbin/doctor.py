#!/usr/bin/env python3
"""Horizon AIOS health-check. Run as the primary OS user."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

OK   = "[OK]  "
WARN = "[WARN]"
FAIL = "[FAIL]"

passed = warnings = failures = 0


def ok(name):
    global passed
    passed += 1
    print(f"  {OK} {name}")


def warn(name, reason):
    global warnings
    warnings += 1
    print(f"  {WARN} {name}: {reason}")


def fail(name, reason):
    global failures
    failures += 1
    print(f"  {FAIL} {name}: {reason}")


# ---------------------------------------------------------------------------
# 1. Environment variables
# ---------------------------------------------------------------------------
def check_env_vars():
    vars_ = ["HORIZON_ROOT", "HORIZON_SYSTEM", "HORIZON_BIN", "HORIZON_ETC", "HORIZON_DOCS"]
    results = {}
    for v in vars_:
        val = os.environ.get(v)
        if not val:
            fail(f"Env: ${v}", "not set")
            results[v] = None
        elif not Path(val).is_dir():
            fail(f"Env: ${v}", f"set to '{val}' but directory does not exist")
            results[v] = None
        else:
            ok(f"Env: ${v}")
            results[v] = Path(val)
    return results


# ---------------------------------------------------------------------------
# 2. Skills (junction architecture)
# Primary user skills live in skills_sbin/. ~/.claude/skills/ must be a
# junction/symlink pointing there — not a real directory copy.
# ---------------------------------------------------------------------------
def check_skills(horizon_system):
    skills_sbin = horizon_system / "skills_sbin"
    skills_dst = Path.home() / ".claude" / "skills"

    # Sub-check 1: skills_sbin/ exists and has at least one skill directory
    if not skills_sbin.is_dir():
        fail("Skills: skills_sbin/", f"{skills_sbin} does not exist")
    else:
        skill_dirs = [d for d in skills_sbin.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
        if skill_dirs:
            ok(f"Skills: skills_sbin/ contains {len(skill_dirs)} skill(s)")
        else:
            warn("Skills: skills_sbin/", "no skill directories found (each must contain SKILL.md)")

    # Sub-check 2: ~/.claude/skills/ is a symlink or junction, not a real dir
    dst_str = str(skills_dst)
    if not skills_dst.exists() and not os.path.islink(dst_str):
        fail("Skills: ~/.claude/skills/", "does not exist — run bootstrap to create the junction")
        return
    if not os.path.islink(dst_str):
        fail("Skills: ~/.claude/skills/", "is a real directory, not a junction/symlink — run bootstrap to redirect it")
        return
    ok("Skills: ~/.claude/skills/ is a junction/symlink")

    # Sub-check 3: junction target resolves to skills_sbin/
    try:
        actual_target = Path(os.readlink(dst_str)).resolve()
        expected_target = skills_sbin.resolve()
        if actual_target == expected_target:
            ok("Skills: junction target matches skills_sbin/")
        else:
            fail("Skills: junction target", f"expected {expected_target}, got {actual_target}")
    except OSError as e:
        warn("Skills: junction target", f"could not read link target: {e}")


# ---------------------------------------------------------------------------
# 3 & 4. Git hooks installed
# ---------------------------------------------------------------------------
def check_hook(name, hook_filename, harness_configs_git_hooks, horizon_root):
    src = harness_configs_git_hooks / hook_filename
    dst = horizon_root / ".git" / "hooks" / hook_filename
    if not src.exists():
        warn(f"Hook: {name} source", f"{src} missing from harness_configs")
        return
    if not dst.exists():
        fail(f"Hook: {name}", f".git/hooks/{hook_filename} not installed — run bootstrap or copy manually")
    else:
        ok(f"Hook: {name}")


# ---------------------------------------------------------------------------
# 5. aios_local.conf
# ---------------------------------------------------------------------------
def check_local_conf(horizon_system):
    conf = horizon_system / "ai_os_etc" / "aios_local.conf"
    template = horizon_system / "templates" / "aios_local.conf.template"
    if not conf.exists():
        hint = f"copy {template} → {conf} and fill in your values" if template.exists() else "copy the template from $HORIZON_SYSTEM/templates/aios_local.conf.template"
        fail("aios_local.conf", f"not found — {hint}")
    else:
        ok("aios_local.conf")


# ---------------------------------------------------------------------------
# 6. .gitignore.user
# ---------------------------------------------------------------------------
def check_gitignore_user(horizon_root):
    f = horizon_root / ".gitignore.user"
    if not f.exists():
        template = horizon_root / ".gitignore.user.template"
        hint = f"copy {template} → {f}" if template.exists() else "create .gitignore.user at $HORIZON_ROOT"
        fail(".gitignore.user", f"not found — {hint}")
    else:
        ok(".gitignore.user")


# ---------------------------------------------------------------------------
# 7. sbin ACL (Windows only)
# ---------------------------------------------------------------------------
def check_sbin_acl(horizon_system):
    sbin = horizon_system / "sbin"
    if not sbin.exists():
        warn("sbin ACL", f"{sbin} does not exist")
        return
    try:
        result = subprocess.run(
            ["icacls", str(sbin)],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout
        broad = [g for g in ("Everyone", "Users", "Authenticated Users") if g.lower() in output.lower()]
        if broad:
            groups = ", ".join(broad)
            warn("sbin ACL", f"broad read access detected for: {groups} — add explicit Deny ACL per security_invariants.md")
        else:
            ok("sbin ACL (no broad read groups detected)")
    except Exception as e:
        warn("sbin ACL", f"could not run icacls: {e}")


# ---------------------------------------------------------------------------
# 8. Global Claude settings
# ---------------------------------------------------------------------------
def check_claude_settings():
    f = Path.home() / ".claude" / "settings.json"
    if not f.exists():
        fail("Claude global settings", f"{f} not found — Claude Code may not be configured")
    else:
        ok("Claude global settings")


# ---------------------------------------------------------------------------
# 9. Stub CLAUDE.md
# ---------------------------------------------------------------------------
def check_claude_md(horizon_root):
    f = horizon_root / ".claude" / "CLAUDE.md"
    if not f.exists():
        fail("CLAUDE.md stub", f"{f} not found")
    else:
        ok("CLAUDE.md stub")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"Horizon AIOS Doctor — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    env = check_env_vars()
    print()

    horizon_root   = env.get("HORIZON_ROOT")
    horizon_system = env.get("HORIZON_SYSTEM")

    if horizon_system:
        check_skills(horizon_system)
        hooks_src = horizon_system / "harness_configs" / "git" / "hooks"
        if horizon_root:
            check_hook("DCO commit-msg", "commit-msg", hooks_src, horizon_root)
            check_hook("pre-commit", "pre-commit", hooks_src, horizon_root)
        check_local_conf(horizon_system)
        if sys.platform == "win32":
            check_sbin_acl(horizon_system)
    else:
        fail("Skills / hooks / aios_local.conf", "skipped — $HORIZON_SYSTEM not available")

    if horizon_root:
        check_gitignore_user(horizon_root)
        check_claude_md(horizon_root)
    else:
        fail(".gitignore.user / CLAUDE.md", "skipped — $HORIZON_ROOT not available")

    check_claude_settings()

    print()
    print(f"  {passed} checks passed, {warnings} warnings, {failures} failures")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
