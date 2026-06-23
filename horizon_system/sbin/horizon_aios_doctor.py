#!/usr/bin/env python3
"""Horizon AIOS health-check. Run as the primary OS user.

Run with --post-setup to additionally run post-install verifications
(test sound, statusline command, git commit.gpgsign).
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Make stdout/stderr robust on legacy Windows code pages (e.g. cp1252) so the
# tool never crashes with UnicodeEncodeError on non-ASCII output. Self-healing
# regardless of PYTHONIOENCODING; guarded for Pythons without reconfigure().
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OK   = "[OK]  "
WARN = "[WARN]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

passed = warnings = failures = skipped = 0


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


def skip(name, reason):
    """A clean, non-failing skip (e.g. a feature deliberately disabled)."""
    global skipped
    skipped += 1
    print(f"  {SKIP} {name}: {reason}")


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
# 2. Skills (symlink architecture)
# Primary user skills live in skills_sbin/. ~/.claude/skills/ must be a
# directory symlink pointing there — not a real directory copy.
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
    # Use resolve() as the authoritative check — works for directory symlinks
    # and any other redirect mechanism. os.path.islink() does not reliably detect
    # NTFS reparse points on all Python/Windows configurations.
    if not skills_dst.exists():
        fail("Skills: ~/.claude/skills/", "does not exist — run bootstrap to create the symlink")
        return

    try:
        actual_target = skills_dst.resolve()
        expected_target = skills_sbin.resolve()
        if actual_target == expected_target:
            ok("Skills: ~/.claude/skills/ symlink points to skills_sbin/")
        elif actual_target == skills_dst.absolute():
            fail("Skills: ~/.claude/skills/", "is a real directory, not a symlink — run bootstrap to redirect it")
        else:
            fail("Skills: symlink target", f"expected {expected_target}, got {actual_target}")
    except OSError as e:
        warn("Skills: symlink target", f"could not resolve target: {e}")


# ---------------------------------------------------------------------------
# 2b. Harness memory redirect
# Claude Code's ~/.claude/projects/ holds per-project memory. horizon_aios_redirect_memory.py
# replaces it with a directory symlink into $HORIZON_ROOT/memory/ so harness
# memory falls under AIOS governance. Use resolve() as the authoritative check —
# same rationale as check_skills (NTFS reparse points aren't reliably detected by
# os.path.islink()).
# ---------------------------------------------------------------------------
def check_memory_redirect(horizon_root):
    memory_dir = horizon_root / "memory"
    projects_dst = Path.home() / ".claude" / "projects"

    if not projects_dst.exists():
        warn("Memory: ~/.claude/projects/",
             "does not exist — Claude Code may not have run yet")
        return

    try:
        actual_target = projects_dst.resolve()
        expected_target = memory_dir.resolve()
        if actual_target == expected_target:
            ok("Memory: harness memory redirected into AIOS")
        elif actual_target == projects_dst.absolute():
            warn("Memory: ~/.claude/projects/",
                 "harness memory not under AIOS governance — run sbin/horizon_aios_redirect_memory.py "
                 "with Claude Code closed, then restart")
        else:
            fail("Memory: redirect target", f"expected {expected_target}, got {actual_target}")
    except OSError as e:
        warn("Memory: redirect target", f"could not resolve target: {e}")


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
        hint = f"copy {template} -> {conf} and fill in your values" if template.exists() else "copy the template from $HORIZON_SYSTEM/templates/aios_local.conf.template"
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
        hint = f"copy {template} -> {f}" if template.exists() else "create .gitignore.user at $HORIZON_ROOT"
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
            warn(name, f"{path} does not exist — run bootstrap/horizon_aios_harden.py")
            continue
        status, detail = _has_brains_deny(path)
        if status == "deny":
            ok(f"{label} ACL — explicit brains Deny present")
        elif status == "nodeny":
            fail(name, f"no explicit Deny ACE for '{BRAINS_GROUP}' on {path} — "
                       "run horizon_aios_harden.py (security_invariants.md §3)")
        else:
            warn(name, f"could not run icacls: {detail}")


def check_sbin_acl_unix(horizon_system):
    """
    Unix equivalent of check_sbin_acl: verify that sbin/, skills_sbin/, and
    logs/ are mode 0o700 and owned by the current user (not root, not another
    user). This mirrors the horizon_aios_harden.py 'chmod -R 700' posture applied to
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
            warn(name, f"{path} does not exist — run bootstrap/horizon_aios_harden.py")
            continue
        try:
            st = path.stat()
        except OSError as e:
            warn(name, f"could not stat {path}: {e}")
            continue

        mode = stat.S_IMODE(st.st_mode)
        if mode != 0o700:
            fail(name, f"{path} mode is {oct(mode)}, expected 0o700 — "
                       "run horizon_aios_harden.py (security_invariants.md §3)")
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
            ok("Monitor: horizon_aios_monitor.py is running")
        elif status == "stopped":
            warn("Monitor: horizon_aios_monitor.py", "not running — filesystem audit logging is inactive (optional)")
        else:
            warn("Monitor: horizon_aios_monitor.py", f"unexpected status: {status!r}")
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
# 11. AIOS switcher (registry + indirection layer)
# The machine-local registry at ~/.horizon/aios_registry.json records which
# AIOSs this machine knows and which is active. active_env.* and the aios-exec
# wrappers are the indirection layer the profile and settings.json point at.
# A missing registry is WARN (switcher not initialized — bootstrap creates it);
# a corrupt registry or an active AIOS that no longer exists is FAIL.
# ---------------------------------------------------------------------------
def check_aios_registry():
    horizon_home = Path.home() / ".horizon"
    registry = horizon_home / "aios_registry.json"
    if not registry.exists():
        warn("AIOS registry", "~/.horizon/aios_registry.json not found — "
             "run 'python horizon_aios_switch.py init' (or bootstrap) to initialize")
        return

    try:
        reg = json.loads(registry.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        fail("AIOS registry", f"unreadable/corrupt: {e} — re-init with horizon_aios_switch.py")
        return

    aioses = reg.get("aioses")
    active = reg.get("active")
    if not isinstance(aioses, dict) or not aioses:
        fail("AIOS registry", "no registered AIOSs — re-init with horizon_aios_switch.py")
        return
    ok(f"AIOS registry — {len(aioses)} registered, active: '{active}'")

    entry = aioses.get(active)
    if not entry:
        fail("AIOS active", f"active '{active}' is not in the registry")
    else:
        root = Path(entry.get("root", ""))
        if (root / "horizon_system" / "ai_os_etc").is_dir():
            ok(f"AIOS active root — {root} is a valid AIOS")
        else:
            fail("AIOS active root", f"'{root}' is not a valid AIOS (moved/deleted?)")

    # Indirection layer: platform-appropriate env snippet + wrappers.
    env_snippet = horizon_home / ("active_env.ps1" if sys.platform == "win32"
                                  else "active_env.sh")
    wrapper = horizon_home / "bin" / ("aios-exec.ps1" if sys.platform == "win32"
                                      else "aios-exec.sh")
    if env_snippet.exists():
        ok(f"AIOS env snippet — {env_snippet.name} present")
    else:
        warn("AIOS env snippet", f"{env_snippet} missing — run horizon_aios_switch.py init/switch")
    if wrapper.exists():
        ok(f"AIOS exec wrapper — {wrapper.name} present")
    else:
        warn("AIOS exec wrapper", f"{wrapper} missing — run horizon_aios_switch.py init/switch")


# ===========================================================================
# Post-setup verifications (--post-setup only)
# Run AFTER an install to confirm the user-facing plumbing actually works.
# ===========================================================================

# Mirror resolve_sound.py's mute vocabulary so a muted install is reported as a
# clean SKIP rather than being indistinguishable from an unmapped/missing sound.
_SOUND_ENABLE_KEY = "sounds_enabled"
_SOUND_FALSY = {"0", "false", "no", "off", "disabled"}


def _conf_sounds_disabled(conf_path):
    """True only if conf_path exists and sets sounds_enabled to a falsy value."""
    try:
        with conf_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() == _SOUND_ENABLE_KEY:
                    return v.strip().lower() in _SOUND_FALSY
    except OSError:
        pass
    return False


def _sounds_muted(horizon_system, horizon_root, cwd):
    """Replicate resolve_sound.py mute logic: master kill switch, then nearest
    per-project aios_sounds.conf walking up from cwd to $HORIZON_ROOT."""
    master = horizon_system / "sounds" / "aios_sounds.conf"
    if _conf_sounds_disabled(master):
        return True, f"master kill switch ({master})"
    try:
        current = cwd.resolve()
        root = horizon_root.resolve()
    except OSError:
        return False, ""
    while True:
        candidate = current / "aios_sounds.conf"
        if candidate.exists() and _conf_sounds_disabled(candidate):
            return True, f"project mute ({candidate})"
        if current == root or current.parent == current:
            break
        current = current.parent
    return False, ""


# ---------------------------------------------------------------------------
# P1. Test sound through the canonical sound chokepoint
# Resolves (and plays) a test event via $HORIZON_BIN/resolve_sound.py. Honors
# the sounds_enabled mute switch: a muted install is a clean SKIP, not a FAIL.
# ---------------------------------------------------------------------------
def check_test_sound(horizon_system, horizon_bin, horizon_root):
    name = "Sound: test event via resolve_sound.py"
    resolve_script = horizon_bin / "resolve_sound.py"
    if not resolve_script.exists():
        fail(name, f"{resolve_script} not found — sound chokepoint missing")
        return

    muted, why = _sounds_muted(horizon_system, horizon_root, Path.cwd())
    if muted:
        skip(name, f"sounds disabled — {why}")
        return

    # Resolve a canonical test event through the chokepoint.
    try:
        result = subprocess.run(
            [sys.executable, str(resolve_script), "task_complete",
             "--harness", "claude_code"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:  # noqa: BLE001 — surface any failure
        fail(name, f"resolve_sound.py failed to run: {e}")
        return

    sound_path = result.stdout.strip()
    if not sound_path:
        # Not muted but nothing resolved — the test event is unmapped.
        warn(name, "no sound mapped for 'task_complete' — nothing to play")
        return
    if not Path(sound_path).exists():
        fail(name, f"resolved to '{sound_path}' but file does not exist")
        return

    # Fire it through the canonical player so the user hears install succeeded.
    player = horizon_system / "sounds" / "play_sound.sh"
    played = ""
    if player.exists():
        try:
            subprocess.run(["bash", str(player), sound_path],
                           capture_output=True, text=True, timeout=15)
            played = " (played)"
        except Exception:  # noqa: BLE001 — playback is best-effort
            played = " (resolved; playback unavailable)"
    else:
        played = " (resolved; play_sound.sh not found)"
    ok(f"{name} — {Path(sound_path).name}{played}")


# ---------------------------------------------------------------------------
# P2. Statusline command resolves
# Verifies the configured statusline command exists and is invocable. Does NOT
# require it to be wired into settings.json — only that the command resolves.
# ---------------------------------------------------------------------------
def check_statusline(horizon_bin):
    name = "Statusline: command resolves"
    statusline_dir = horizon_bin / "statusline"
    # statusline.sh is the cross-platform dispatcher; it routes to the
    # platform-appropriate script.
    dispatcher = statusline_dir / "statusline.sh"
    if not dispatcher.exists():
        fail(name, f"{dispatcher} not found — statusline command does not resolve")
        return

    # The dispatcher delegates to a platform-appropriate target; confirm it exists.
    target = (statusline_dir / "statusline-context-alerts.ps1"
              if sys.platform == "win32"
              else statusline_dir / "statusline-command.sh")
    if not target.exists():
        fail(name, f"dispatcher present but target {target.name} missing")
        return

    ok(f"{name} — {dispatcher.name} -> {target.name}")


# ---------------------------------------------------------------------------
# P3. git commit.gpgsign enabled
# The repo enforces signed commits / DCO, so commit.gpgsign must be on.
# ---------------------------------------------------------------------------
def check_gpgsign(horizon_root):
    name = "Git: commit.gpgsign enabled"
    try:
        result = subprocess.run(
            ["git", "-C", str(horizon_root), "config", "--get", "commit.gpgsign"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:  # noqa: BLE001 — surface any failure
        warn(name, f"could not run git: {e}")
        return

    val = result.stdout.strip().lower()
    if val in ("true", "1", "yes", "on"):
        ok(name)
    elif not val:
        fail(name, "commit.gpgsign is not set — run 'git config commit.gpgsign true' "
                   "(repo enforces signed commits / DCO)")
    else:
        fail(name, f"commit.gpgsign is '{val}', expected true — "
                   "run 'git config commit.gpgsign true'")


def run_post_setup(env):
    print("Post-setup verifications:")
    horizon_system = env.get("HORIZON_SYSTEM")
    horizon_bin    = env.get("HORIZON_BIN")
    horizon_root   = env.get("HORIZON_ROOT")

    if horizon_system and horizon_bin and horizon_root:
        check_test_sound(horizon_system, horizon_bin, horizon_root)
    else:
        warn("Sound: test event", "skipped — $HORIZON_SYSTEM/$HORIZON_BIN/$HORIZON_ROOT not available")

    if horizon_bin:
        check_statusline(horizon_bin)
    else:
        warn("Statusline: command resolves", "skipped — $HORIZON_BIN not available")

    if horizon_root:
        check_gpgsign(horizon_root)
    else:
        warn("Git: commit.gpgsign enabled", "skipped — $HORIZON_ROOT not available")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Horizon AIOS health-check. Run as the primary OS user.")
    parser.add_argument(
        "--post-setup", action="store_true",
        help="additionally run post-install verifications: a test sound through "
             "the canonical sound chokepoint, the statusline command, and "
             "git commit.gpgsign.")
    args = parser.parse_args()

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
        check_memory_redirect(horizon_root)
    else:
        fail(".gitignore.user / CLAUDE.md", "skipped — $HORIZON_ROOT not available")

    check_claude_settings()
    check_aios_registry()

    print()

    if args.post_setup:
        run_post_setup(env)

    summary = f"  {passed} checks passed, {warnings} warnings, {failures} failures"
    if skipped:
        summary += f", {skipped} skipped"
    print(summary)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
