#!/usr/bin/env python3
"""
remove_brain.py — Horizon AIOS Brain Deprovisioning
===================================================

Reverses create_brain.py: removes a brain's OS user account, its per-brain
group, its workspace folder, its user-profile config, and its stored
credential. The shared `brains` group is left intact (other brains may use it).

This is the deprovisioning counterpart to create_brain.py. Run it as the
administrative context (Administrator on Windows, root on Unix).

Removal footprint (mirrors what create_brain.py provisions):
    - OS user account            <brain-name>
    - Per-brain OS group         <brain-name>   (the shared `brains` group stays)
    - Workspace folder           $HORIZON_ROOT/brains/<brain-name>/
                                 (CLAUDE.md, settings.json, .aios_provision.json)
    - User profile config        <home>/.claude/  incl. the skills junction
    - User profile dir           <home>           (Unix: via userdel -r)
    - Stored credential          OS keystore (via brain_credential.py delete)

Safety:
    - Validates the brain name and refuses reserved names (brains, the invoking
      user, administrator/root, etc.).
    - The ~/.claude/skills entry is a JUNCTION to $HORIZON_SYSTEM/skills_bin.
      It is removed with `rmdir` (reparse-point delete) BEFORE any recursive
      delete, so the junction target (skills_bin) is never followed/destroyed.
    - Prompts for confirmation unless --yes. Supports --dry-run.

Usage:
    python remove_brain.py <brain-name> [--horizon-root PATH] [--yes] [--dry-run]
"""

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys

# Reuse the exact group name and credential deletion from the provisioning side.
BRAINS_GROUP = 'brains'
BRAIN_NAME_RE = re.compile(r'^[a-z][a-z0-9_]{1,31}$')

# Names we must never attempt to remove as a "brain".
RESERVED_NAMES = {
    'brains', 'administrator', 'admin', 'root', 'system', 'guest',
    'default', 'public', 'users',
}

_sys_path_added = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sbin')
if os.path.isdir(_sys_path_added):
    sys.path.insert(0, os.path.abspath(_sys_path_added))
try:
    from brain_credential import _delete_credential as _cred_delete
except Exception:  # noqa: BLE001 — keyring cleanup is best-effort
    _cred_delete = None


# ---------------------------------------------------------------------------
# Logging helpers (house style, matching create_brain.py)
# ---------------------------------------------------------------------------

def banner(text):
    line = '=' * (len(text) + 6)
    print(f'\n{line}\n=== {text} ===\n{line}\n')


def info(msg):  print(f'  [INFO]  {msg}')
def ok(msg):    print(f'  [OK]    {msg}')
def warn(msg):  print(f'  [WARN]  {msg}')
def error(msg): print(f'  [ERROR] {msg}', file=sys.stderr)


def run(cmd, dry_run=False, check=True):
    display = ' '.join(str(a) for a in cmd)
    if dry_run:
        print(f'  [DRY-RUN] {display}')
        return True
    info(f'Running: {display}')
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        if check:
            warn(f'Command failed ({result.returncode}): {display}')
            if result.stderr.strip():
                warn(f'  stderr: {result.stderr.strip()}')
        return False
    return True


def run_ps(ps_expr, dry_run=False, check=True):
    return run(['powershell', '-NonInteractive', '-Command', ps_expr],
               dry_run=dry_run, check=check)


# ---------------------------------------------------------------------------
# Privilege + existence checks
# ---------------------------------------------------------------------------

def check_privileges(os_name):
    if os_name == 'Windows':
        try:
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_admin = False
        if not is_admin:
            error('This script must be run as Administrator. Re-run from an '
                  'elevated terminal.')
            sys.exit(1)
        info('Running as Administrator: OK')
    else:
        if os.geteuid() != 0:
            error('This script must be run as root. Re-run with sudo.')
            sys.exit(1)
        info('Running as root: OK')


def user_exists(name, os_name):
    if os_name == 'Windows':
        r = subprocess.run(['powershell', '-NonInteractive', '-Command',
                            f'Get-LocalUser -Name "{name}" -ErrorAction SilentlyContinue'],
                           capture_output=True, text=True)
        return bool(r.stdout.strip())
    return subprocess.run(['id', name], capture_output=True).returncode == 0


def group_exists(name, os_name):
    if os_name == 'Windows':
        r = subprocess.run(['powershell', '-NonInteractive', '-Command',
                            f'Get-LocalGroup -Name "{name}" -ErrorAction SilentlyContinue'],
                           capture_output=True, text=True)
        return bool(r.stdout.strip())
    return subprocess.run(['getent', 'group', name], capture_output=True).returncode == 0


def invoking_user():
    try:
        import getpass
        return getpass.getuser()
    except Exception:
        try:
            return os.getlogin()
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Windows removal
# ---------------------------------------------------------------------------

def _windows_profile_dir(brain_name):
    system_drive = os.environ.get('SystemDrive', 'C:')
    return os.path.join(system_drive + '\\', 'Users', brain_name)


def _remove_skills_junction(profile_dir, dry_run):
    """
    Remove the brain's ~/.claude/skills JUNCTION before any recursive delete,
    using rmdir so the reparse point is deleted WITHOUT following it into
    skills_bin. Safe no-op if absent.
    """
    skills = os.path.join(profile_dir, '.claude', 'skills')
    if not os.path.exists(skills) and not os.path.islink(skills):
        return
    info(f'Removing skills junction (reparse-point delete): {skills}')
    # `rmdir` on a junction removes only the link. On a real dir it removes it
    # only if empty — it will NOT recurse into / delete a junction target.
    run(['cmd', '/c', 'rmdir', skills], dry_run=dry_run, check=False)


def remove_windows(brain_name, brain_dir, dry_run):
    profile_dir = _windows_profile_dir(brain_name)

    # 1. Junction first (never recurse through it).
    _remove_skills_junction(profile_dir, dry_run)

    # 2. Remove the OS user account.
    if user_exists(brain_name, 'Windows'):
        run_ps(f'Remove-LocalUser -Name "{brain_name}"', dry_run=dry_run)
    else:
        info(f'User does not exist (skipping): {brain_name}')

    # 3. Remove the per-brain group (leave the shared `brains` group).
    if group_exists(brain_name, 'Windows'):
        run_ps(f'Remove-LocalGroup -Name "{brain_name}"', dry_run=dry_run)
    else:
        info(f'Per-brain group does not exist (skipping): {brain_name}')

    # 4. Remove the user profile directory (config, profile script).
    if os.path.isdir(profile_dir):
        info(f'Removing user profile directory: {profile_dir}')
        run_ps(f'Remove-Item -LiteralPath "{profile_dir}" -Recurse -Force '
               f'-ErrorAction SilentlyContinue', dry_run=dry_run, check=False)
    else:
        info(f'No user profile directory at: {profile_dir}')

    # 5. Remove the workspace folder.
    _remove_workspace(brain_dir, dry_run)


# ---------------------------------------------------------------------------
# Unix removal
# ---------------------------------------------------------------------------

def remove_unix(brain_name, brain_dir, os_name, dry_run):
    if user_exists(brain_name, os_name):
        if os_name == 'Linux':
            run(['userdel', '-r', brain_name], dry_run=dry_run, check=False)
        else:  # macOS
            run(['dscl', '.', '-delete', f'/Users/{brain_name}'], dry_run=dry_run, check=False)
    else:
        info(f'User does not exist (skipping): {brain_name}')

    if group_exists(brain_name, os_name):
        if os_name == 'Linux':
            run(['groupdel', brain_name], dry_run=dry_run, check=False)
        else:
            run(['dseditgroup', '-o', 'delete', brain_name], dry_run=dry_run, check=False)
    else:
        info(f'Per-brain group does not exist (skipping): {brain_name}')

    _remove_workspace(brain_dir, dry_run)


def _remove_workspace(brain_dir, dry_run):
    """Remove $HORIZON_ROOT/brains/<name>/. Contains no junctions."""
    if not os.path.isdir(brain_dir):
        info(f'No workspace folder at: {brain_dir}')
        return
    info(f'Removing workspace folder: {brain_dir}')
    if dry_run:
        print(f'  [DRY-RUN] rmtree {brain_dir}')
        return
    try:
        shutil.rmtree(brain_dir)
        ok(f'Removed workspace: {brain_dir}')
    except OSError as exc:
        warn(f'Could not fully remove {brain_dir}: {exc}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description='Horizon AIOS — deprovision (remove) a brain.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument('brain_name', help='Brain to remove (^[a-z][a-z0-9_]{1,31}$)')
    p.add_argument('--horizon-root', metavar='PATH', default=None,
                   help='Absolute HORIZON_ROOT. Default: ../../ from this script.')
    p.add_argument('--yes', '-y', action='store_true', default=False,
                   help='Skip the confirmation prompt.')
    p.add_argument('--keep-credential', action='store_true', default=False,
                   help='Do not delete the stored OS-keystore credential.')
    p.add_argument('--dry-run', action='store_true', default=False,
                   help='Print every action without executing anything.')
    return p.parse_args()


def main():
    args = parse_args()
    os_name = platform.system()
    if os_name not in ('Windows', 'Linux', 'Darwin'):
        error(f'Unsupported platform: {os_name}')
        sys.exit(1)

    brain_name = args.brain_name
    banner('Horizon AIOS — Remove Brain')
    if args.dry_run:
        print('  *** DRY-RUN MODE — no changes will be made ***\n')

    # --- Validation / safety guards ---
    if not BRAIN_NAME_RE.match(brain_name):
        error(f'Invalid brain name: {brain_name!r}. Must match ^[a-z][a-z0-9_]{{1,31}}$')
        sys.exit(1)
    if brain_name.lower() in RESERVED_NAMES:
        error(f'Refusing to remove reserved name: {brain_name!r}')
        sys.exit(1)
    me = invoking_user()
    if me and brain_name.lower() == me.lower():
        error(f'Refusing to remove the invoking user ({me}).')
        sys.exit(1)

    # --- Resolve paths ---
    if args.horizon_root:
        horizon_root = os.path.abspath(args.horizon_root)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        horizon_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
    brain_dir = os.path.join(horizon_root, 'brains', brain_name)
    info(f'HORIZON_ROOT : {horizon_root}')
    info(f'Brain        : {brain_name}')
    info(f'Workspace    : {brain_dir}')

    if not args.dry_run:
        check_privileges(os_name)

    # --- Nothing-to-do short-circuit ---
    exists_user = user_exists(brain_name, os_name)
    exists_ws = os.path.isdir(brain_dir)
    if not exists_user and not exists_ws and not group_exists(brain_name, os_name):
        warn(f'No trace of brain "{brain_name}" (user/group/workspace). Nothing to do.')
        sys.exit(0)

    # --- Confirmation ---
    if not args.yes and not args.dry_run:
        print()
        warn(f'This will permanently remove brain "{brain_name}": OS user, '
             f'per-brain group, workspace folder, profile config, and stored '
             f'credential. The shared "{BRAINS_GROUP}" group is kept.')
        answer = input(f'  Type the brain name to confirm removal: ').strip()
        if answer != brain_name:
            error('Confirmation did not match. Aborting.')
            sys.exit(1)

    banner('Removing')
    if os_name == 'Windows':
        remove_windows(brain_name, brain_dir, args.dry_run)
    else:
        remove_unix(brain_name, brain_dir, os_name, args.dry_run)

    # --- Credential cleanup (best-effort) ---
    if args.keep_credential:
        info('Keeping stored credential (--keep-credential).')
    elif args.dry_run:
        print(f'  [DRY-RUN] delete OS-keystore credential for {brain_name}')
    elif _cred_delete is None:
        warn('brain_credential module unavailable — delete the credential '
             f'manually: brain_credential.py delete {brain_name}')
    else:
        if _cred_delete(brain_name):
            ok('Stored credential removed from OS keystore.')
        else:
            warn('Could not remove stored credential — remove manually: '
                 f'brain_credential.py delete {brain_name}')

    # --- Post-removal verification ---
    banner('Verify removal')
    remaining = []
    if not args.dry_run:
        if user_exists(brain_name, os_name):
            remaining.append('user account')
        if group_exists(brain_name, os_name):
            remaining.append('per-brain group')
        if os.path.isdir(brain_dir):
            remaining.append('workspace folder')
    if remaining:
        warn(f'Still present after removal: {", ".join(remaining)}. Review above.')
        sys.exit(2)
    ok(f'Brain "{brain_name}" fully removed.' if not args.dry_run
       else 'Dry-run complete — no changes made.')
    sys.exit(0)


if __name__ == '__main__':
    main()
