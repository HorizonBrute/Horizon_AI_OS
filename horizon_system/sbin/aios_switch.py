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
    aios_switch.py list
    aios_switch.py current
    aios_switch.py register <name> <path> [--yes]
    aios_switch.py unregister <name> [--yes]
    aios_switch.py switch <name> [--dry-run] [--yes]

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
    ps = [f"# Generated by aios_switch.py for AIOS '{name}'. Do not edit.",
          "# Sourced by your PowerShell $PROFILE: . \"$HOME\\.horizon\\active_env.ps1\""]
    for k, v in vars_:
        ps.append(f'$env:{k} = "{v}"')
    ps_text = "\n".join(ps) + "\n"

    sh = [f"# Generated by aios_switch.py for AIOS '{name}'. Do not edit.",
          "# Sourced by your shell profile: . \"$HOME/.horizon/active_env.sh\""]
    for k, v in vars_:
        sh.append(f'export {k}="{_sh_path(v)}"')
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


def advise_sync(root):
    sched = os.path.join(root, "horizon_system", "sbin", "setup_sync_schedule.py")
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


# --- run-time wrapper bodies (generated into ~/.horizon/bin) --------------------
_WRAPPER_PS1 = r"""# Generated by aios_switch.py - do not edit.
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
# Generated by aios_switch.py - do not edit.
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

    args = parser.parse_args()
    reg = load_registry()

    handlers = {
        "list": cmd_list, "current": cmd_current, "init": cmd_init,
        "register": cmd_register, "unregister": cmd_unregister, "switch": cmd_switch,
    }
    return handlers[args.command](reg, args)


if __name__ == "__main__":
    sys.exit(main())
