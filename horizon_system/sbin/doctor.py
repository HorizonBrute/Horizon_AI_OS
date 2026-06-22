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
    # Dir vars must exist on disk; non-dir vars just need to be set
    dir_vars = ["HORIZON_ROOT", "HORIZON_SYSTEM", "HORIZON_BIN", "HORIZON_ETC", "HORIZON_DOCS",
                "HORIZON_SOUNDS", "HORIZON_LOGS"]
    str_vars = ["HORIZON_USRBIN", "HORIZON_PROJECTS"]
    results = {}
    for v in dir_vars:
        val = os.environ.get(v)
        if not val:
            fail(f"Env: ${v}", "not set")
            results[v] = None
        elif not Path(val).is_dir():
            warn(f"Env: ${v}", f"set to '{val}' but directory does not exist (create it or run bootstrap)")
            results[v] = Path(val)
        else:
            ok(f"Env: ${v}")
            results[v] = Path(val)
    for v in str_vars:
        val = os.environ.get(v)
        if not val:
            warn(f"Env: ${v}", "not set — optional but expected on a full install")
        else:
            ok(f"Env: ${v}")
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

    # Sub-check 2 + 3: ~/.claude/skills/ redirects to skills_sbin/
    # Use resolve() as the authoritative check — works for symlinks, NTFS junctions,
    # and any other redirect mechanism. os.path.islink() does not reliably detect
    # NTFS directory junctions on all Python/Windows configurations.
    if not skills_dst.exists():
        fail("Skills: ~/.claude/skills/", "does not exist — run bootstrap to create the junction")
        return

    try:
        actual_target = skills_dst.resolve()
        expected_target = skills_sbin.resolve()
        if actual_target == expected_target:
            ok("Skills: ~/.claude/skills/ junction/symlink points to skills_sbin/")
        elif actual_target == skills_dst.absolute():
            fail("Skills: ~/.claude/skills/", "is a real directory, not a junction/symlink — run bootstrap to redirect it")
        else:
            fail("Skills: junction target", f"expected {expected_target}, got {actual_target}")
    except OSError as e:
        warn("Skills: junction target", f"could not resolve target: {e}")


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
# 7. Privileged-dir ACLs (Windows only)
# Verify an explicit DENY ACE for the brains group exists on each privileged
# directory (sbin, skills_sbin, logs). Per security_invariants.md §3, the
# default "no entry" posture is insufficient — an explicit Deny is required.
# A missing Deny is a FAIL (the central security claim is unenforced).
# ---------------------------------------------------------------------------
BRAINS_GROUP = "brains"


def _has_brains_deny(path):
    """
    Return (status, detail) where status is 'deny', 'nodeny', or 'error'.

    Verifies an EXPLICIT (non-inherited) Deny ACE for the brains group exists on
    `path`, via Get-Acl rather than parsing icacls text. icacls renders a
    full-control Deny as "(N)" and a partial Deny as "(DENY)(bits)" — too
    fragile to string-match. Get-Acl exposes the authoritative AccessControlType.

    Requiring an explicit (IsInherited=False) Deny matches security_invariants
    §3 ("an explicit Deny is required") and holds in both harden_aios modes:
    additive sets the explicit Deny alongside inherited ACEs; --strict sets it
    after stripping inheritance. An inherited-only Deny would NOT satisfy this.
    """
    ps = (
        "$a=(Get-Acl -LiteralPath '{p}').Access | Where-Object {{ "
        "$_.IdentityReference -like '*{g}*' -and "
        "$_.AccessControlType -eq 'Deny' -and -not $_.IsInherited }}; "
        "if ($a) {{ $a | ForEach-Object {{ $_.FileSystemRights }} }}"
    ).format(p=str(path), g=BRAINS_GROUP)
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=20,
        )
    except Exception as e:  # noqa: BLE001 — surface any failure
        return ("error", str(e))

    detail = result.stdout.strip()
    if detail:
        return ("deny", f"explicit brains Deny ({detail})")
    return ("nodeny", "")


def check_sbin_acl(horizon_system):
    for label, sub in (("sbin", "sbin"),
                       ("skills_sbin", "skills_sbin"),
                       ("logs", "logs")):
        path = horizon_system / sub
        name = f"{label} ACL (brains DENY)"
        if not path.exists():
            warn(name, f"{path} does not exist — run bootstrap/harden_aios.py")
            continue
        status, detail = _has_brains_deny(path)
        if status == "deny":
            ok(f"{label} ACL — explicit brains Deny present")
        elif status == "nodeny":
            fail(name, f"no explicit Deny ACE for '{BRAINS_GROUP}' on {path} — "
                       "run harden_aios.py (security_invariants.md §3)")
        else:
            warn(name, f"could not run icacls: {detail}")


def check_sbin_acl_unix(horizon_system):
    """
    Unix equivalent of check_sbin_acl: verify that sbin/, skills_sbin/, and
    logs/ are mode 0o700 and owned by the current user (not root, not another
    user). This mirrors the harden_aios.py 'chmod -R 700' posture applied to
    these privileged directories.
    """
    import getpass
    import stat

    try:
        current_uid = os.getuid()
        current_user = getpass.getuser()
    except Exception as e:
        warn("sbin ACL (Unix)", f"could not determine current user: {e}")
        return

    for label, sub in (("sbin", "sbin"),
                       ("skills_sbin", "skills_sbin"),
                       ("logs", "logs")):
        path = horizon_system / sub
        name = f"{label} ACL (Unix owner-only 700)"
        if not path.exists():
            warn(name, f"{path} does not exist — run bootstrap/harden_aios.py")
            continue
        try:
            st = path.stat()
        except OSError as e:
            warn(name, f"could not stat {path}: {e}")
            continue

        mode = stat.S_IMODE(st.st_mode)
        if mode != 0o700:
            fail(name, f"{path} mode is {oct(mode)}, expected 0o700 — "
                       "run harden_aios.py (security_invariants.md §3)")
            continue

        if st.st_uid != current_uid:
            try:
                import pwd
                owner_name = pwd.getpwuid(st.st_uid).pw_name
            except Exception:
                owner_name = str(st.st_uid)
            fail(name, f"{path} is owned by '{owner_name}' (uid {st.st_uid}), "
                       f"expected current user '{current_user}' (uid {current_uid})")
            continue

        ok(f"{label} ACL — mode 0o700, owner '{current_user}'")


# ---------------------------------------------------------------------------
# 8. Monitor status
# Calls monitor_status.py ($HORIZON_BIN/monitor_status.py) and reports
# PASS/WARN.  The monitor is optional — a stopped monitor is WARN, not FAIL.
# ---------------------------------------------------------------------------
def check_monitor_status(horizon_bin):
    monitor_status_script = horizon_bin / "monitor_status.py"
    if not monitor_status_script.exists():
        warn("Monitor: monitor_status.py", f"{monitor_status_script} not found — cannot check monitor")
        return
    try:
        result = subprocess.run(
            [sys.executable, str(monitor_status_script)],
            capture_output=True, text=True, timeout=10,
        )
        status = result.stdout.strip().lower()
        if status == "running":
            ok("Monitor: monitor_aios.py is running")
        elif status == "stopped":
            warn("Monitor: monitor_aios.py", "not running — filesystem audit logging is inactive (optional)")
        else:
            warn("Monitor: monitor_aios.py", f"unexpected status: {status!r}")
    except Exception as e:
        warn("Monitor: monitor_status.py", f"check failed: {e}")


# ---------------------------------------------------------------------------
# 9. Global Claude settings
# ---------------------------------------------------------------------------
def check_claude_settings():
    f = Path.home() / ".claude" / "settings.json"
    if not f.exists():
        fail("Claude global settings", f"{f} not found — Claude Code may not be configured")
    else:
        ok("Claude global settings")


# ---------------------------------------------------------------------------
# 10. Stub CLAUDE.md
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
            check_sbin_acl_unix(horizon_system)
        horizon_bin = env.get("HORIZON_BIN")
        if horizon_bin:
            check_monitor_status(horizon_bin)
        else:
            warn("Monitor", "skipped — $HORIZON_BIN not available")
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
