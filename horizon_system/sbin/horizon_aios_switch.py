#!/usr/bin/env python3
"""Horizon AIOS - switch which AIOS this machine's local config points at.

A machine is bound to one AIOS by five machine-global pointers, all of which
otherwise hardcode a single HORIZON_ROOT:

  1. Env vars (HORIZON_ROOT + 8 derived) - sourced by the shell profile.
  2. ~/.claude/CLAUDE.md       - an "@<root>/.claude/CLAUDE.md" redirect.
  3. ~/.claude/skills/         - a junction/symlink into <root>/horizon_system/skills_sbin.
  4. ~/.claude/settings.json   - statusline + hook commands.
  5. The upstream sync schedule - a per-AIOS scheduled task (advisory here).

This tool makes switching a pointer write rather than a re-stamp. Two pointers
go through indirection so settings.json and the profile never change on switch:

  - Env (#1): we generate ~/.horizon/active_env.{ps1,sh}; the profile sources
    that one file. A switch regenerates it.
  - settings.json (#4): it points once at stable wrappers in ~/.horizon/bin/
    (aios-exec.{ps1,sh}) that resolve the active AIOS at run time. A switch
    leaves settings.json untouched.

The three cheap pointers (#2, #3, and the active_env regen) are rewritten
directly on each switch. #5 is advisory: re-pointing a scheduled task is
platform-specific and is left to the operator (we print the exact command).

Registry: ~/.horizon/aios_registry.json (machine-local, never synced). It is
self-healing: any command rebuilds it silently if missing, registering THIS
tree (resolved from the script's own location) as the sole, active AIOS.

Usage:
    horizon_aios_switch.py list
    horizon_aios_switch.py current
    horizon_aios_switch.py register <name> <path> [--yes]
    horizon_aios_switch.py unregister <name> [--yes]
    horizon_aios_switch.py switch <name> [--dry-run] [--yes]
    horizon_aios_switch.py uninstall [--dry-run] [--yes]

Env:
    AIOS_SWITCH_HOME   Override the home base (for testing). Defaults to ~.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

# --- This tree (the AIOS the script physically lives in) -----------------------
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))      # horizon_system/sbin
THIS_SYSTEM = os.path.dirname(SCRIPT_DIR)                      # horizon_system
THIS_ROOT = os.path.dirname(THIS_SYSTEM)                       # repo root

# --- Home-anchored paths (overridable for testing) -----------------------------
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
SKILLS_LINK = os.path.join(CLAUDE_DIR, "skills")

REGISTRY_VERSION = 1


# --- small output helpers ------------------------------------------------------
def ok(msg):   print(f"  [OK]   {msg}")
def info(msg): print(f"  [INFO] {msg}")
def warn(msg): print(f"  [WARN] {msg}")
def err(msg):  print(f"  [ERR]  {msg}", file=sys.stderr)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _confirm(prompt, yes):
    if yes:
        return True
    try:
        return input(f"  {prompt} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


# --- AIOS validation -----------------------------------------------------------
def is_valid_aios(root):
    """A directory is a Horizon AIOS root if it has the load-bearing structure."""
    if not root or not os.path.isdir(root):
        return False
    system = os.path.join(root, "horizon_system")
    return (os.path.isdir(system)
            and os.path.isdir(os.path.join(system, "ai_os_etc"))
            and os.path.isdir(os.path.join(system, "sbin")))


def horizon_vars(root):
    """The canonical HORIZON_* map derived from a root (matches bootstrap)."""
    system = os.path.join(root, "horizon_system")
    return [
        ("HORIZON_ROOT", root),
        ("HORIZON_SYSTEM", system),
        ("HORIZON_BIN", os.path.join(system, "bin")),
        ("HORIZON_SBIN", os.path.join(system, "sbin")),
        ("HORIZON_ETC", os.path.join(system, "ai_os_etc")),
        ("HORIZON_DOCS", os.path.join(system, "documentation")),
        ("HORIZON_USRBIN", os.path.join(root, "usrbin")),
        ("HORIZON_PROJECTS", os.path.join(root, "Projects")),
        ("HORIZON_LOGS", os.path.join(system, "logs")),
        ("HORIZON_SOUNDS", os.path.join(system, "sounds")),
    ]


# --- registry (self-healing) ---------------------------------------------------
def _default_name(root):
    return os.path.basename(os.path.normpath(root)) or "default"


def _write_registry(reg):
    os.makedirs(HORIZON_HOME, exist_ok=True)
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)
        f.write("\n")
    os.replace(tmp, REGISTRY)


def load_registry():
    """Return the registry, silently rebuilding it if missing or corrupt.

    A rebuilt registry registers THIS tree (the script's own AIOS) as the sole
    active entry - the honest assumption that the current filesystem is the only
    Horizon AIOS the machine knows about.
    """
    if os.path.isfile(REGISTRY):
        try:
            with open(REGISTRY, encoding="utf-8") as f:
                reg = json.load(f)
            if isinstance(reg, dict) and isinstance(reg.get("aioses"), dict):
                return reg
            warn("Registry malformed - rebuilding from the current AIOS.")
        except (json.JSONDecodeError, OSError):
            warn("Registry unreadable - rebuilding from the current AIOS.")

    name = _default_name(THIS_ROOT)
    reg = {
        "version": REGISTRY_VERSION,
        "active": name,
        "aioses": {name: {"root": THIS_ROOT, "registered": _now()}},
    }
    _write_registry(reg)
    info(f"No registry found - initialized with current AIOS '{name}' ({THIS_ROOT}).")
    return reg


def _find_name_by_root(reg, root):
    target = os.path.normcase(os.path.normpath(root))
    for name, entry in reg["aioses"].items():
        if os.path.normcase(os.path.normpath(entry.get("root", ""))) == target:
            return name
    return None


# --- pointer repointing --------------------------------------------------------
def _sh_path(p):
    """Render a path for a bash snippet. On Windows, forward slashes are accepted
    by Git Bash for most tooling (C:\\devroot -> C:/devroot)."""
    return p.replace("\\", "/")


def write_active_env(name, root, dry):
    vars_ = horizon_vars(root)
    ps = [f"# Generated by horizon_aios_switch.py for AIOS '{name}'. Do not edit.",
          "# Sourced by your PowerShell $PROFILE: . \"$HOME\\.horizon\\active_env.ps1\""]
    for k, v in vars_:
        ps.append(f'$env:{k} = "{v}"')
    # Owner convenience: put the ACTIVE AIOS's bin + sbin on PATH so the owner
    # can run bin/ and sbin/ commands by name. Owner-only — brains never source
    # this file (their env is written by horizon_aios_create_brain.py), so sbin cannot reach
    # a brain's PATH.
    ps.append("foreach ($__p in @($env:HORIZON_BIN, $env:HORIZON_SBIN)) {")
    ps.append("  if ($__p -and (($env:PATH -split ';') -notcontains $__p)) { $env:PATH = \"$__p;$env:PATH\" }")
    ps.append("}")
    ps_text = "\n".join(ps) + "\n"

    sh = [f"# Generated by horizon_aios_switch.py for AIOS '{name}'. Do not edit.",
          "# Sourced by your shell profile: . \"$HOME/.horizon/active_env.sh\""]
    for k, v in vars_:
        sh.append(f'export {k}="{_sh_path(v)}"')
    # Owner convenience: active AIOS bin + sbin on PATH (owner-only; see above).
    sh.append('case ":$PATH:" in *":$HORIZON_BIN:"*) ;; *) PATH="$HORIZON_BIN:$PATH" ;; esac')
    sh.append('case ":$PATH:" in *":$HORIZON_SBIN:"*) ;; *) PATH="$HORIZON_SBIN:$PATH" ;; esac')
    sh.append("export PATH")
    sh_text = "\n".join(sh) + "\n"

    if dry:
        info(f"would write {ACTIVE_ENV_PS1}")
        info(f"would write {ACTIVE_ENV_SH}")
        return
    os.makedirs(HORIZON_HOME, exist_ok=True)
    with open(ACTIVE_ENV_PS1, "w", encoding="utf-8") as f:
        f.write(ps_text)
    with open(ACTIVE_ENV_SH, "w", encoding="utf-8", newline="\n") as f:
        f.write(sh_text)
    ok("Wrote active_env.ps1 + active_env.sh")


def write_wrappers(dry):
    """Generate the stable aios-exec wrappers. These are AIOS-independent: they
    resolve the active AIOS at run time via active_env, so settings.json can
    point at them once and never change on switch."""
    if dry:
        info(f"would ensure {WRAPPER_PS1} + {WRAPPER_SH}")
        return
    os.makedirs(WRAPPER_DIR, exist_ok=True)
    with open(WRAPPER_PS1, "w", encoding="utf-8") as f:
        f.write(_WRAPPER_PS1)
    with open(WRAPPER_SH, "w", encoding="utf-8", newline="\n") as f:
        f.write(_WRAPPER_SH)
    if os.name != "nt":
        os.chmod(WRAPPER_SH, 0o755)
    ok("Ensured aios-exec wrappers")


def repoint_claude_md(root, dry):
    target = os.path.join(root, ".claude", "CLAUDE.md")
    redirect = f"@{target}\n"
    if dry:
        info(f"would point ~/.claude/CLAUDE.md -> {target}")
        return
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    with open(CLAUDE_MD, "w", encoding="utf-8") as f:
        f.write(redirect)
    ok(f"Pointed ~/.claude/CLAUDE.md -> {target}")


def _remove_link(path):
    """Remove an existing junction/symlink (not its target's contents)."""
    if os.name == "nt":
        # Junctions and dir symlinks are removed with rmdir; this never recurses
        # into the target for a reparse point.
        subprocess.run(["cmd", "/c", "rmdir", path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        os.unlink(path)


def _make_link(dst, target):
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", dst, target],
                       check=True, stdout=subprocess.DEVNULL)
    else:
        os.symlink(target, dst, target_is_directory=True)


def repoint_skills_junction(root, dry):
    target = os.path.join(root, "horizon_system", "skills_sbin")
    if not os.path.isdir(target):
        warn(f"skills_sbin not found in target ({target}) - skipping skills repoint.")
        return
    if dry:
        info(f"would point ~/.claude/skills -> {target}")
        return
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    if os.path.islink(SKILLS_LINK) or (os.name == "nt" and os.path.isdir(SKILLS_LINK)
                                       and _is_reparse(SKILLS_LINK)):
        _remove_link(SKILLS_LINK)
    elif os.path.exists(SKILLS_LINK):
        contents = os.listdir(SKILLS_LINK)
        if contents:
            warn(f"~/.claude/skills is a real directory with {len(contents)} item(s) "
                 "- refusing to replace. Resolve manually, then re-run switch.")
            return
        os.rmdir(SKILLS_LINK)
    _make_link(SKILLS_LINK, target)
    ok(f"Pointed ~/.claude/skills -> {target}")


def _is_reparse(path):
    """Windows: True if path is a reparse point (junction/symlink)."""
    try:
        attrs = os.stat(path, follow_symlinks=False).st_file_attributes
        return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except (OSError, AttributeError):
        return False


def update_system_path(root, dry):
    """Update the system-level PATH to point at <root>/horizon_system/bin.

    Mirrors the logic in bootstrap.ps1 / bootstrap.sh Section 7.  Requires
    admin/root; gracefully degrades with an advisory warn if not elevated.
    """
    new_bin = os.path.join(root, "horizon_system", "bin")

    if dry:
        info(f"would update system PATH -> {new_bin}")
        return

    _ADVISORY = (
        "[WARN] Could not update system PATH (insufficient privileges). "
        "Session PATH is correct. To fix system PATH, re-run: "
        "python horizon_aios_switch.py switch <name>  (as Administrator / sudo)."
    )

    if os.name == "nt":
        # Delegate to PowerShell so we can call [System.Environment].
        ps_script = (
            "$mp = [System.Environment]::GetEnvironmentVariable('Path','Machine');"
            "$entries = $mp -split ';' | ForEach-Object { $_.TrimEnd('\\').TrimEnd('/') };"
            "$cleaned = $entries | Where-Object { $_ -notmatch '(?i)horizon_system[/\\\\]bin$' };"
            f"$nb = '{new_bin.rstrip(chr(92))}';"
            "if ($cleaned -contains $nb) { exit 0 }"
            "$newPath = ($cleaned + @($nb)) -join ';';"
            "[System.Environment]::SetEnvironmentVariable('Path', $newPath, 'Machine')"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NonInteractive", "-Command", ps_script],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                # Access denied or other error
                warn(_ADVISORY)
                if result.stderr.strip():
                    info(f"  Detail: {result.stderr.strip()[:200]}")
            else:
                ok(f"Updated system PATH -> {new_bin}")
        except OSError as exc:
            warn(_ADVISORY)
            info(f"  Detail: {exc}")
    else:
        # Linux / macOS: write /etc/profile.d/horizon_aios.sh
        profile_d = "/etc/profile.d/horizon_aios.sh"
        try:
            # Read existing lines, strip any old horizon_system/bin export
            if os.path.isfile(profile_d):
                with open(profile_d, encoding="utf-8") as f:
                    lines = f.readlines()
                filtered = [l for l in lines if "horizon_system/bin" not in l]
            else:
                filtered = []
            filtered.append(f'export PATH="{new_bin}:$PATH"\n')
            with open(profile_d, "w", encoding="utf-8") as f:
                f.writelines(filtered)
            os.chmod(profile_d, 0o644)
            ok(f"Updated system PATH in {profile_d}")
        except PermissionError:
            warn(_ADVISORY)

        # macOS: also update /etc/paths.d/horizon-aios
        import platform
        if platform.system() == "Darwin":
            paths_d = "/etc/paths.d/horizon-aios"
            try:
                if os.path.isfile(paths_d):
                    with open(paths_d, encoding="utf-8") as f:
                        lines = f.readlines()
                    filtered = [l for l in lines if "horizon_system/bin" not in l]
                else:
                    filtered = []
                filtered.append(f"{new_bin}\n")
                with open(paths_d, "w", encoding="utf-8") as f:
                    f.writelines(filtered)
                os.chmod(paths_d, 0o644)
                ok(f"Updated system PATH in {paths_d}")
            except PermissionError:
                warn(_ADVISORY)


def advise_sync(root):
    sched = os.path.join(root, "horizon_system", "sbin", "horizon_aios_setup_sync_schedule.py")
    if os.path.isfile(sched):
        info("Sync schedule is per-AIOS and not auto-repointed. To point auto-sync "
             "at the new AIOS, run:")
        print(f"           python \"{sched}\"")


# --- commands ------------------------------------------------------------------
def cmd_list(reg, _args):
    active = reg.get("active")
    print("Registered Horizon AIOSs:")
    if not reg["aioses"]:
        print("  (none)")
        return 0
    for name, entry in sorted(reg["aioses"].items()):
        mark = "*" if name == active else " "
        root = entry.get("root", "?")
        valid = "" if is_valid_aios(root) else "  [MISSING/INVALID]"
        print(f"  {mark} {name:<16} {root}{valid}")
    print("\n  * = active")
    return 0


def cmd_current(reg, _args):
    active = reg.get("active")
    entry = reg["aioses"].get(active)
    if not entry:
        err("No active AIOS recorded.")
        return 1
    print(f"{active}\t{entry.get('root')}")
    return 0


def cmd_register(reg, args):
    name, path = args.name, os.path.abspath(args.path)
    if not is_valid_aios(path):
        err(f"Not a valid Horizon AIOS root: {path}")
        err("Expected horizon_system/ with ai_os_etc/ and sbin/ inside.")
        return 1

    if name in reg["aioses"] and reg["aioses"][name].get("root") != path:
        if not _confirm(f"'{name}' already points at {reg['aioses'][name]['root']}. "
                        f"Replace with {path}?", args.yes):
            info("Left existing registration unchanged.")
            return 0

    clash = _find_name_by_root(reg, path)
    if clash and clash != name:
        if not _confirm(f"{path} is already registered as '{clash}'. "
                        f"Also register it as '{name}'?", args.yes):
            info("No change made.")
            return 0

    existing = reg["aioses"].get(name, {})
    reg["aioses"][name] = {
        "root": path,
        "registered": existing.get("registered", _now()),
    }
    _write_registry(reg)
    ok(f"Registered '{name}' -> {path}")
    return 0


def cmd_unregister(reg, args):
    name = args.name
    if name not in reg["aioses"]:
        err(f"No AIOS named '{name}'.")
        return 1
    if name == reg.get("active"):
        err(f"'{name}' is the active AIOS - switch to another before unregistering.")
        return 1
    if not _confirm(f"Remove registration '{name}'?", args.yes):
        info("No change made.")
        return 0
    del reg["aioses"][name]
    _write_registry(reg)
    ok(f"Unregistered '{name}' (the AIOS files are untouched).")
    return 0


def cmd_init(reg, _args):
    """Onboarding entry point (called by bootstrap). Ensures THIS tree is in the
    registry and that active_env + wrappers exist for the ACTIVE AIOS. Unlike
    'switch', it never hijacks an existing active choice and does not touch
    ~/.claude (bootstrap owns CLAUDE.md and the skills junction)."""
    name = _find_name_by_root(reg, THIS_ROOT)
    if not name:
        name = _default_name(THIS_ROOT)
        suffix = 1
        while name in reg["aioses"]:
            suffix += 1
            name = f"{_default_name(THIS_ROOT)}{suffix}"
        reg["aioses"][name] = {"root": THIS_ROOT, "registered": _now()}
        if not reg.get("active"):
            reg["active"] = name
        _write_registry(reg)
        ok(f"Registered this tree as '{name}'.")
    else:
        ok(f"This tree is already registered as '{name}'.")

    active = reg.get("active")
    aroot = reg["aioses"][active]["root"]
    write_active_env(active, aroot, False)
    update_system_path(aroot, False)
    write_wrappers(False)
    info(f"Generated active_env + aios-exec wrappers for active AIOS '{active}'.")
    if active != name:
        warn(f"Active AIOS is '{active}', not this tree ('{name}'). "
             f"Run: aios switch {name}")
    return 0


def cmd_switch(reg, args):
    name = args.name
    entry = reg["aioses"].get(name)
    if not entry:
        err(f"No AIOS named '{name}'. Known: {', '.join(sorted(reg['aioses'])) or '(none)'}")
        return 1
    root = entry["root"]
    if not is_valid_aios(root):
        err(f"'{name}' points at {root}, which is not a valid AIOS (moved/deleted?).")
        return 1

    if name == reg.get("active") and not args.dry_run:
        info(f"'{name}' is already active - repointing anyway to repair any drift.")

    label = "DRY RUN - no changes" if args.dry_run else f"Switching to '{name}' ({root})"
    print(f"\n{label}\n")

    write_active_env(name, root, args.dry_run)
    update_system_path(root, args.dry_run)
    write_wrappers(args.dry_run)
    repoint_claude_md(root, args.dry_run)
    repoint_skills_junction(root, args.dry_run)

    if args.dry_run:
        info("Dry run complete - registry unchanged.")
        return 0

    reg["active"] = name
    _write_registry(reg)
    advise_sync(root)
    print()
    ok(f"Active AIOS is now '{name}'.")
    warn("Restart Claude Code and open a NEW shell - env changes do not reach "
         "already-running sessions.")
    return 0


def cmd_uninstall(_reg, args):
    """Delegate to the platform uninstall script next to this file
    (uninstall.ps1 on Windows, uninstall.sh elsewhere), which undoes the
    bootstrap footprint section by section. Those scripts require elevation and
    run interactively (confirming each destructive step) unless --yes is given;
    --dry-run previews every action without changing anything (and needs no
    elevation). We run them in the foreground so their prompts reach the terminal
    and return their exit code unchanged."""
    if os.name == "nt":
        script = os.path.join(SCRIPT_DIR, "uninstall.ps1")
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", script]
    else:
        script = os.path.join(SCRIPT_DIR, "uninstall.sh")
        cmd = ["bash", script]

    if not os.path.isfile(script):
        err(f"Uninstall script not found: {script}")
        return 1
    if args.dry_run:
        cmd.append("--dry-run")
    if args.yes:
        cmd.append("--yes")

    info(f"Delegating to {os.path.basename(script)} (must be run elevated) ...")
    try:
        return subprocess.run(cmd).returncode
    except OSError as exc:
        err(f"Failed to launch uninstall script: {exc}")
        return 1


# --- run-time wrapper bodies (generated into ~/.horizon/bin) --------------------
_WRAPPER_PS1 = r"""# Generated by horizon_aios_switch.py - do not edit.
# Resolves the active Horizon AIOS and dispatches a known action. settings.json
# points here so it never changes on switch; only active_env.ps1 changes.
# No param() block on purpose: Claude pipes JSON to stdin, and a declared
# parameter would make PowerShell try to bind that pipeline input (fails). We
# read the action from $args and forward stdin explicitly for the statusline.
$Action = $args[0]
$envFile = Join-Path $HOME ".horizon\active_env.ps1"
if (Test-Path $envFile) { . $envFile }
$bin = $env:HORIZON_BIN
$sys = $env:HORIZON_SYSTEM
function Play-Sound($cue) {
    $s = python "$sys\bin\resolve_sound.py" $cue --harness claude_code 2>$null
    if ($s) { (New-Object Media.SoundPlayer $s).PlaySync() }
}
switch ($Action) {
    "statusline" {
        $stdin = [Console]::In.ReadToEnd()
        $stdin | powershell.exe -NonInteractive -File "$bin\statusline\statusline-context-alerts.ps1"
    }
    "hook-stop"        { & "$sys\harness_configs\claude_code\hooks\log_hook_event.ps1" -Event Stop;             Play-Sound task_complete }
    "hook-permission"  { & "$sys\harness_configs\claude_code\hooks\log_hook_event.ps1" -Event PermissionRequest; Play-Sound input_needed }
    "hook-stopfailure" { & "$sys\harness_configs\claude_code\hooks\log_hook_event.ps1" -Event StopFailure;       Play-Sound api_error }
    default            { Write-Error "aios-exec: unknown action '$Action'"; exit 2 }
}
"""

_WRAPPER_SH = r"""#!/usr/bin/env bash
# Generated by horizon_aios_switch.py - do not edit.
# Resolves the active Horizon AIOS and dispatches a known action. settings.json
# points here so it never changes on switch; only active_env.sh changes.
action="$1"
env_file="$HOME/.horizon/active_env.sh"
[ -f "$env_file" ] && . "$env_file"
play_sound() {
    s=$(python3 "$HORIZON_SYSTEM/bin/resolve_sound.py" "$1" --harness claude_code 2>/dev/null)
    [ -n "$s" ] && bash "$HORIZON_SYSTEM/sounds/play_sound.sh" "$s"
}
log_event() { bash "$HORIZON_SYSTEM/harness_configs/claude_code/hooks/log_hook_event.sh" "$1"; }
case "$action" in
    statusline)       bash "$HORIZON_BIN/statusline/statusline-command.sh" ;;
    hook-stop)        log_event Stop;              play_sound task_complete ;;
    hook-permission)  log_event PermissionRequest; play_sound input_needed & ;;
    hook-stopfailure) log_event StopFailure;       play_sound api_error & ;;
    *) echo "aios-exec: unknown action '$action'" >&2; exit 2 ;;
esac
"""


# ===========================================================================
# 'aios setup' — one-shot new-machine installer (orchestrator).
#
# Honors three owner decisions:
#   1. This is a subcommand of horizon_aios_switch.py; it runs UNPRIVILEGED and
#      shells out to the ELEVATED bootstrap for SOP sections 2-10.
#   2. Git identity is written to a machine-local, GITIGNORED include file
#      (ai_os_etc/git_identity.local.gitconfig) pulled in via
#      `git config --global include.path`. It never appears in `git status`.
#   3. Clone-awareness: inside a tree -> skip cloning; standalone -> offer to
#      clone to the chosen root.
#
# Every step is idempotent and re-run safe: it ORCHESTRATES existing tools
# (bootstrap, horizon_aios_relocate.py, horizon_aios_doctor.py) and never
# reimplements them.
# ===========================================================================

# Machine-local git identity include file. Lives alongside aios_local.conf in
# $HORIZON_ETC (the established home for gitignored per-machine config) and is
# named with the .local. infix + matched by .gitignore so it never shows in
# `git status`. NOT the tracked harness_configs/git/gitconfig (decision 2).
GIT_IDENTITY_BASENAME = "git_identity.local.gitconfig"

# settings.local.json stub shape (SOP §12).
_SETTINGS_LOCAL_STUB = '{\n  "permissions": {\n    "allow": []\n  }\n}\n'

AIOS_REPO_URL = "git@github.com:HorizonBrute/Horizon_AI_OS.git"


def _have(cmd):
    """True if `cmd` resolves on PATH (cross-platform)."""
    from shutil import which
    return which(cmd) is not None


def _run_capture(cmd):
    """Run cmd, return (rc, stdout-stripped). Never raises on non-zero/missing."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.returncode, (r.stdout or "").strip()
    except OSError:
        return 127, ""


def _git_global_get(key):
    rc, out = _run_capture(["git", "config", "--global", "--get", key])
    return out if rc == 0 else ""


def setup_preflight():
    """Probe prerequisites. Hard-fail on missing git/claude; WARN on jq/gpg/ssh.
    Returns False if a hard prerequisite is missing. Reuses no doctor internals
    here because doctor's env checks assume a fully-installed tree; this probes
    the bare toolchain SOP section 2 requires."""
    print("\n--- Preflight: prerequisites ---")
    hard_ok = True
    for tool in ("git", "claude"):
        if _have(tool):
            ok(f"{tool} found")
        else:
            err(f"{tool} not found on PATH — required (SOP §2). Install it and re-run.")
            hard_ok = False
    for tool in ("jq", "gpg", "ssh", "python3", "bash"):
        # python3/bash are advisory on Windows where python/Git Bash cover them.
        if _have(tool) or (tool == "python3" and _have("python")):
            ok(f"{tool} found")
        else:
            warn(f"{tool} not found — recommended (some steps degrade without it).")

    # SSH / GPG guidance only (never auto-generate keys).
    if _have("ssh"):
        rc, out = _run_capture(["ssh", "-T", "-o", "BatchMode=yes",
                                "-o", "StrictHostKeyChecking=accept-new",
                                "git@github.com"])
        # GitHub returns rc 1 with a success banner even on a good auth.
        if "successfully authenticated" in out.lower():
            ok("ssh -T git@github.com authenticated")
        else:
            warn("ssh to git@github.com did not confirm auth — ensure your key is "
                 "registered before cloning/pushing (SOP §2.2). Not auto-generating keys.")
    if _have("gpg"):
        rc, out = _run_capture(["gpg", "--list-secret-keys"])
        if rc == 0 and out:
            ok("gpg secret key present")
        else:
            warn("no gpg secret key found — commit signing will fail until you "
                 "create one (SOP §2.3). Not auto-generating keys.")
    return hard_ok


def _prompt(prompt, default, yes):
    """Prompt with a default. Under --yes, returns the default unchanged."""
    if yes:
        return default
    try:
        ans = input(f"  {prompt} [{default}]: ").strip()
    except EOFError:
        return default
    return ans or default


def setup_resolve_root(args):
    """Decision 2 (ROOT) + decision 3 (CLONE-awareness).

    Returns (chosen_root, inside_tree) or (None, _) on a fatal clone failure.
    """
    inside_tree = is_valid_aios(THIS_ROOT)
    default_root = THIS_ROOT if inside_tree else os.path.join(HOME, "devroot")
    chosen = os.path.abspath(_prompt("Path for $HORIZON_ROOT", default_root, args.yes))

    if inside_tree:
        info(f"Running inside an existing AIOS tree ({THIS_ROOT}) — clone skipped.")
        return chosen, True

    # Standalone: offer to clone to the chosen root.
    if is_valid_aios(chosen):
        info(f"{chosen} already contains an AIOS — clone skipped.")
        return chosen, True
    if not _confirm(f"No AIOS tree here. Clone {AIOS_REPO_URL} into {chosen}?", args.yes):
        info("Clone declined — set $HORIZON_ROOT to an existing tree and re-run.")
        return None, False
    os.makedirs(os.path.dirname(chosen) or ".", exist_ok=True)
    rc = subprocess.run(["git", "clone", AIOS_REPO_URL, chosen]).returncode
    if rc != 0 or not is_valid_aios(chosen):
        err(f"git clone failed (rc={rc}) or result is not a valid AIOS.")
        return None, False
    ok(f"Cloned AIOS into {chosen}")
    return chosen, True


def setup_relocate(chosen_root):
    """Step 4: if the chosen root differs from THIS_ROOT, delegate to
    horizon_aios_relocate.py --apply. Never reimplement path rewriting."""
    if os.path.normcase(os.path.normpath(chosen_root)) == \
       os.path.normcase(os.path.normpath(THIS_ROOT)):
        return  # same location — nothing to relocate
    script = os.path.join(chosen_root, "horizon_system", "sbin", "horizon_aios_relocate.py")
    if not os.path.isfile(script):
        warn(f"relocate script not found at {script} — skipping relocate.")
        return
    info(f"Chosen root differs from this tree — relocating pointers to {chosen_root}.")
    py = sys.executable or ("python" if os.name == "nt" else "python3")
    subprocess.run([py, script, "--new-root", chosen_root, "--apply"])


def setup_profile_line(yes):
    """Step 5: idempotently append the active_env source line to the user's shell
    profile (the line bootstrap currently only PRINTS). Guards against duplicates."""
    if os.name == "nt":
        rc, profile = _run_capture(["powershell", "-NoProfile", "-Command", "$PROFILE"])
        if rc != 0 or not profile:
            profile = os.path.join(HOME, "Documents", "WindowsPowerShell",
                                   "Microsoft.PowerShell_profile.ps1")
        line = 'if (Test-Path "$HOME\\.horizon\\active_env.ps1") { . "$HOME\\.horizon\\active_env.ps1" }'
        marker = "active_env.ps1"
    else:
        profile = os.path.join(HOME, ".bashrc")
        line = '[ -f "$HOME/.horizon/active_env.sh" ] && . "$HOME/.horizon/active_env.sh"'
        marker = "active_env.sh"

    try:
        existing = ""
        if os.path.isfile(profile):
            with open(profile, encoding="utf-8", errors="replace") as f:
                existing = f.read()
        if marker in existing:
            ok(f"Profile already sources active_env ({profile}).")
            return
        os.makedirs(os.path.dirname(profile) or ".", exist_ok=True)
        with open(profile, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(line + "\n")
        ok(f"Appended active_env source line to {profile}.")
    except OSError as exc:
        warn(f"Could not update profile {profile}: {exc} — add manually:\n      {line}")


def setup_invoke_bootstrap(chosen_root, yes):
    """Step 6: shell out to the platform bootstrap (sections 2-10) ELEVATED.
    Windows: relaunch via an elevated PowerShell (Start-Process -Verb RunAs).
    Unix: sudo. Pass --yes through when non-interactive."""
    sbin = os.path.join(chosen_root, "horizon_system", "sbin")
    if os.name == "nt":
        script = os.path.join(sbin, "bootstrap.ps1")
        if not os.path.isfile(script):
            err(f"bootstrap.ps1 not found at {script}")
            return 1
        # Build an elevated relaunch. -Wait so we see it complete; the elevated
        # window shows progress. Forward --yes when non-interactive.
        arglist = f"-ExecutionPolicy Bypass -File '{script}'"
        if yes:
            arglist += " --yes"
        ps = (f"$p = Start-Process powershell -Verb RunAs -Wait -PassThru "
              f"-ArgumentList \"{arglist}\"; exit $p.ExitCode")
        info("Launching elevated bootstrap (UAC prompt expected)...")
        return subprocess.run(["powershell", "-NoProfile", "-Command", ps]).returncode
    else:
        script = os.path.join(sbin, "bootstrap.sh")
        if not os.path.isfile(script):
            err(f"bootstrap.sh not found at {script}")
            return 1
        cmd = ["sudo", "bash", script]
        if yes:
            cmd.append("--yes")
        info("Launching bootstrap via sudo (password prompt expected)...")
        return subprocess.run(cmd).returncode


def setup_git_identity(chosen_root, args):
    """Step 7 (decision 2): write git identity to a machine-local, GITIGNORED
    include file and wire `git config --global include.path` to it (idempotent).
    Also ensures the SOP §9 include for the framework gitconfig is present."""
    etc = os.path.join(chosen_root, "horizon_system", "ai_os_etc")
    identity_file = os.path.join(etc, GIT_IDENTITY_BASENAME)

    cur_name = _git_global_get("user.name")
    cur_email = _git_global_get("user.email")
    cur_key = _git_global_get("user.signingkey")

    name = _prompt("git user.name", cur_name or "", args.yes)
    email = _prompt("git user.email", cur_email or "", args.yes)
    key = _prompt("git user.signingkey (GPG fingerprint)", cur_key or "", args.yes)

    body = "# Horizon AIOS machine-local git identity. GITIGNORED — never committed.\n"
    body += "# Pulled in via: git config --global include.path <this file>\n"
    body += "[user]\n"
    if name:
        body += f"\tname = {name}\n"
    if email:
        body += f"\temail = {email}\n"
    if key:
        body += f"\tsigningkey = {key}\n"
    try:
        os.makedirs(etc, exist_ok=True)
        with open(identity_file, "w", encoding="utf-8") as f:
            f.write(body)
        ok(f"Wrote machine-local git identity -> {identity_file}")
    except OSError as exc:
        err(f"Failed to write identity file {identity_file}: {exc}")
        return

    # Wire include.path entries idempotently (git stores multivar include.path).
    rc, existing = _run_capture(["git", "config", "--global", "--get-all", "include.path"])
    existing_paths = set(existing.splitlines()) if rc == 0 else set()

    def _ensure_include(path):
        # Compare on normalized basis; git stores the literal string we add.
        if any(os.path.normcase(os.path.normpath(p)) ==
               os.path.normcase(os.path.normpath(path)) for p in existing_paths):
            ok(f"include.path already set: {path}")
            return
        rc2 = subprocess.run(["git", "config", "--global", "--add",
                              "include.path", path]).returncode
        if rc2 == 0:
            existing_paths.add(path)
            ok(f"Added include.path -> {path}")
        else:
            warn(f"Failed to add include.path {path} (rc={rc2}).")

    _ensure_include(identity_file)
    # SOP §9: framework gitconfig include (gpgsign/signoff/etc.).
    framework_gitconfig = os.path.join(chosen_root, "horizon_system",
                                       "harness_configs", "git", "gitconfig")
    if os.path.isfile(framework_gitconfig):
        _ensure_include(framework_gitconfig)

    # Prove the identity file is gitignored (must not show in `git status`).
    rc, out = _run_capture(["git", "-C", chosen_root, "status", "--porcelain",
                            "--", identity_file])
    rel = os.path.relpath(identity_file, chosen_root)
    rc2, ign = _run_capture(["git", "-C", chosen_root, "check-ignore", rel])
    if rc2 == 0 and ign:
        ok(f"Identity file is gitignored ({rel}) — will not appear in git status.")
    elif not out:
        ok(f"Identity file does not appear in git status ({rel}).")
    else:
        warn(f"Identity file MAY be visible to git: {out!r} — add '{rel}' to .gitignore.")


def setup_git_init(chosen_root, args):
    """Step 8: git init if absent (so bootstrap §6 wires hooks). Bootstrap §6
    only wires hooks when .git already exists, so we init BEFORE bootstrap runs.
    The first signed commit is opt-in and decoupled from --yes (the framework
    gitconfig forces gpgsign=true, so an unattended install must not require a
    signing key): --first-commit / --no-first-commit force it; left unset it
    prompts (default N) interactively and stays OFF under --yes."""
    git_dir = os.path.join(chosen_root, ".git")
    if os.path.isdir(git_dir):
        ok(".git already present — skipping git init.")
    else:
        rc = subprocess.run(["git", "-C", chosen_root, "init"]).returncode
        if rc == 0:
            ok("Ran git init (bootstrap will wire hooks in §6).")
        else:
            warn(f"git init failed (rc={rc}).")
            return

    # First signed commit — opt-in, decoupled from --yes. --first-commit /
    # --no-first-commit force it on/off; left unset, prompt interactively
    # (default N) but stay OFF under --yes so an unattended install never
    # requires a GPG signing key.
    if args.first_commit is None:
        do_commit = False if args.yes else _confirm("Make the first signed commit now?", False)
    else:
        do_commit = args.first_commit
    if not do_commit:
        info("Skipped first commit — run `git commit -s` later.")
        return
    subprocess.run(["git", "-C", chosen_root, "add",
                    ".claude/CLAUDE.md", ".claude/settings.json",
                    "horizon_system", ".gitignore", ".gitignore.user.template"])
    rc = subprocess.run(["git", "-C", chosen_root, "commit", "-s", "-m",
                         "Initial Horizon AIOS OS layer commit"]).returncode
    if rc == 0:
        ok("Created initial signed commit.")
    else:
        warn(f"Initial commit did not complete (rc={rc}) — commit manually.")


def setup_settings_local(chosen_root):
    """Step 9: create the {\"permissions\":{\"allow\":[]}} stub if absent (SOP §12)."""
    path = os.path.join(chosen_root, ".claude", "settings.local.json")
    if os.path.isfile(path):
        ok("settings.local.json already exists.")
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_SETTINGS_LOCAL_STUB)
        ok(f"Created settings.local.json stub -> {path}")
    except OSError as exc:
        warn(f"Could not create settings.local.json: {exc}")


def setup_model_prefs(chosen_root, args):
    """Step 10: OFFER to copy the model-prefs extend template to its active
    .extend.md (SOP §15). Do not run catalog refresh."""
    etc = os.path.join(chosen_root, "horizon_system", "ai_os_etc")
    template = os.path.join(etc, "horizon_aios_model_prefs.extend.template.md")
    active = os.path.join(etc, "horizon_aios_model_prefs.extend.md")
    if os.path.isfile(active):
        ok("model-prefs extend file already exists.")
        return
    if not os.path.isfile(template):
        warn("model-prefs extend template not found — skipping.")
        return
    if not _confirm("Copy the model-prefs extend template to its active file?", args.yes):
        info("Skipped model-prefs — run /model-prefs later.")
        return
    try:
        import shutil
        shutil.copyfile(template, active)
        ok(f"Created {os.path.basename(active)} — edit it or run /model-prefs.")
    except OSError as exc:
        warn(f"Could not copy model-prefs template: {exc}")


def setup_local_agents(chosen_root):
    """Step 10b: materialize each tracked agents.md's sibling local.agents.md from
    its local.agents.md.template if absent (file_structure_invariants §12). The live
    file is gitignored — never tracked, never clobbered by upstream sync — so creating
    it here guarantees the `@local.agents.md` import never dangles. NOT confirm-gated:
    its existence is structural (the import contract), not an optional extra."""
    import shutil
    # Every directory that ships an agents.md gets a sibling local.agents.md.
    agents_dirs = [chosen_root, os.path.join(chosen_root, ".claude")]
    stub = ("# Local Agent Instructions — machine-local override "
            "(gitignored; never synced or clobbered)\n")
    for d in agents_dirs:
        template = os.path.join(d, "local.agents.md.template")
        active = os.path.join(d, "local.agents.md")
        rel = os.path.relpath(active, chosen_root)
        if os.path.isfile(active):
            ok(f"local.agents.md already exists ({rel}).")
            continue
        try:
            if os.path.isfile(template):
                shutil.copyfile(template, active)
                ok(f"Created {rel} from template — edit it for machine-local overrides.")
            else:
                with open(active, "w", encoding="utf-8") as f:
                    f.write(stub)
                ok(f"Created stub {rel} (no template found).")
        except OSError as exc:
            warn(f"Could not create {rel}: {exc}")


def setup_verify_gate(chosen_root):
    """Step 11: run horizon_aios_doctor.py --post-setup as a NON-FATAL gate.
    A muted-sound SKIP must not fail setup; report PASS/FAIL summary."""
    script = os.path.join(chosen_root, "horizon_system", "sbin", "horizon_aios_doctor.py")
    if not os.path.isfile(script):
        warn(f"doctor not found at {script} — skipping verify gate.")
        return
    py = sys.executable or ("python" if os.name == "nt" else "python3")
    print("\n--- Verify gate: horizon_aios_doctor.py --post-setup ---")
    rc = subprocess.run([py, script, "--post-setup"]).returncode
    if rc == 0:
        ok("Doctor gate PASSED.")
    else:
        warn("Doctor gate reported FAILURES (non-fatal for setup). Review the "
             "output above and revisit the indicated step, then re-run `aios setup`.")


def cmd_setup(_reg, args):
    """One-shot new-machine installer. Orchestrates existing tools end to end.
    Every step is idempotent and re-run safe."""
    print("\n=== Horizon AIOS — one-shot setup ===")
    if args.yes:
        info("Non-interactive (--yes): accepting defaults for every prompt.")

    if not setup_preflight():
        err("Preflight failed on a hard prerequisite. Resolve the above and re-run.")
        return 1

    chosen_root, ok_tree = setup_resolve_root(args)
    if not chosen_root:
        return 1

    setup_relocate(chosen_root)
    setup_profile_line(args.yes)

    # git init BEFORE bootstrap so bootstrap §6 wires the hooks on this repo.
    setup_git_init(chosen_root, args)

    rc = setup_invoke_bootstrap(chosen_root, args.yes)
    if rc != 0:
        warn(f"Bootstrap exited non-zero (rc={rc}). Continuing with local steps; "
             "review bootstrap output and re-run if needed.")

    setup_git_identity(chosen_root, args)
    setup_settings_local(chosen_root)
    setup_model_prefs(chosen_root, args)
    setup_local_agents(chosen_root)
    setup_verify_gate(chosen_root)

    print()
    ok("Setup complete. Open a NEW shell so the profile env line takes effect, "
       "then run `aios setup` again any time — it is idempotent.")
    info("Point your harness at /model-prefs to finish model configuration.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="aios", description="Switch which Horizon AIOS this machine points at.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List registered AIOSs (active marked with *).")
    sub.add_parser("current", help="Print the active AIOS name and root.")
    sub.add_parser("init", help="Onboarding: register this tree + write env/wrappers.")

    p_reg = sub.add_parser("register", help="Register (or replace) a named AIOS.")
    p_reg.add_argument("name")
    p_reg.add_argument("path")
    p_reg.add_argument("--yes", "-y", action="store_true", help="Skip confirmations.")

    p_unreg = sub.add_parser("unregister", help="Remove a registration (files untouched).")
    p_unreg.add_argument("name")
    p_unreg.add_argument("--yes", "-y", action="store_true", help="Skip confirmation.")

    p_sw = sub.add_parser("switch", help="Point local config at a registered AIOS.")
    p_sw.add_argument("name")
    p_sw.add_argument("--dry-run", action="store_true", help="Show actions, change nothing.")
    p_sw.add_argument("--yes", "-y", action="store_true", help="Skip confirmations.")

    p_setup = sub.add_parser("setup",
                             help="One-shot new-machine install: orchestrate the full setup "
                                  "(preflight, clone/relocate, profile, elevated bootstrap, "
                                  "git identity, doctor gate). Idempotent and re-run safe.")
    p_setup.add_argument("--yes", "-y", action="store_true",
                         help="Non-interactive: accept defaults for every prompt "
                              "(mirrors bootstrap's --yes).")
    # The first commit is opt-in and decoupled from --yes: the framework gitconfig
    # forces commit.gpgsign=true, so an unattended install must NOT require a
    # signing key. --first-commit / --no-first-commit force it on/off; left unset
    # it prompts interactively (default N) and stays OFF under --yes.
    p_setup.add_argument("--first-commit", dest="first_commit",
                         action="store_true", default=None,
                         help="Make the initial signed commit during setup "
                              "(requires a working GPG signing key). Default: off.")
    p_setup.add_argument("--no-first-commit", dest="first_commit",
                         action="store_false",
                         help="Skip the initial commit even when prompted "
                              "(explicit off; the default).")
    # Reserved for a future declarative install (not implemented yet).
    p_setup.add_argument("--config", metavar="FILE",
                         help="(reserved) declarative setup config — not yet implemented.")

    p_un = sub.add_parser("uninstall",
                          help="Remove the Horizon AIOS bootstrap footprint from this machine.")
    p_un.add_argument("--dry-run", action="store_true",
                      help="Preview every action; change nothing (no elevation needed).")
    p_un.add_argument("--yes", "-y", action="store_true",
                      help="Skip confirmations (non-interactive). Requires elevation.")

    args = parser.parse_args()
    reg = load_registry()

    handlers = {
        "list": cmd_list, "current": cmd_current, "init": cmd_init,
        "register": cmd_register, "unregister": cmd_unregister, "switch": cmd_switch,
        "setup": cmd_setup, "uninstall": cmd_uninstall,
    }
    return handlers[args.command](reg, args)


if __name__ == "__main__":
    sys.exit(main())
