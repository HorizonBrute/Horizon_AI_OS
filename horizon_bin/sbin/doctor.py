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
    vars_ = ["HORIZON_ROOT", "HORIZON_BIN", "HORIZON_ETC", "HORIZON_DOCS"]
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
# 2. Skills deployed
# ---------------------------------------------------------------------------
def check_skills(horizon_bin):
    skills_src = horizon_bin / "skills"
    skills_dst = Path.home() / ".claude" / "skills"
    if not skills_src.is_dir():
        warn("Skills: source dir", f"{skills_src} does not exist (no skills to deploy)")
        return
    skill_files = list(skills_src.glob("*.md"))
    if not skill_files:
        warn("Skills: source dir", "no .md skill files found in $HORIZON_BIN/skills/")
        return
    if not skills_dst.is_dir():
        fail("Skills: deployed", f"~/.claude/skills/ does not exist; run the deploy step from ReadMeToSetupYourSystem.md")
        return
    missing = [s for s in skill_files if not (skills_dst / s.name).exists()]
    if missing:
        names = ", ".join(s.name for s in missing)
        fail("Skills: deployed", f"not deployed: {names} — copy from $HORIZON_BIN/skills/ to ~/.claude/skills/")
    else:
        ok(f"Skills: {len(skill_files)} deployed")


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
def check_local_conf(horizon_bin):
    conf = horizon_bin / "ai_os_etc" / "aios_local.conf"
    template = horizon_bin / "templates" / "aios_local.conf.template"
    if not conf.exists():
        hint = f"copy {template} → {conf} and fill in your values" if template.exists() else "copy the template from $HORIZON_BIN/templates/aios_local.conf.template"
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
def check_sbin_acl(horizon_bin):
    sbin = horizon_bin / "sbin"
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

    horizon_root = env.get("HORIZON_ROOT")
    horizon_bin  = env.get("HORIZON_BIN")

    if horizon_bin:
        check_skills(horizon_bin)
        hooks_src = horizon_bin / "harness_configs" / "git" / "hooks"
        if horizon_root:
            check_hook("DCO commit-msg", "commit-msg", hooks_src, horizon_root)
            check_hook("pre-commit", "pre-commit", hooks_src, horizon_root)
        check_local_conf(horizon_bin)
        if sys.platform == "win32":
            check_sbin_acl(horizon_bin)
    else:
        fail("Skills / hooks / aios_local.conf", "skipped — $HORIZON_BIN not available")

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
