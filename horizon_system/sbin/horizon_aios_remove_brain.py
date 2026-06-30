#!/usr/bin/env python3
"""
horizon_aios_remove_brain.py — Horizon AIOS Brain Deprovisioning
===================================================

Reverses horizon_aios_create_brain.py: removes a brain's OS user account, its per-brain
group, its workspace folder, its user-profile config, and its stored
credential. The shared `brains` group is left intact (other brains may use it).

This is the deprovisioning counterpart to horizon_aios_create_brain.py. Run it as the
administrative context (Administrator on Windows, root on Unix).

Removal footprint (mirrors what horizon_aios_create_brain.py provisions):
    - OS user account            <brain-name>
    - Per-brain OS group         <brain-name>_group (Windows) / <brain-name> (Unix)
                                 (the shared `brains` group stays)
    - Home link                  <home>/.claude  -> brains/<brain-name>/.claude
    - Workspace folder           $HORIZON_ROOT/brains/<brain-name>/
                                 (CLAUDE.md, settings.json, .aios_provision.json,
                                  and skills -> skills_bin)
    - User profile dir           <home>           (Unix: via userdel -r)
    - Stored credential          OS keystore (via horizon_aios_brain_credential.py delete)

Safety:
    - Validates the brain name and refuses reserved names (brains, the invoking
      user, administrator/root, etc.).
    - The brain's links — home <home>/.claude -> workspace, and workspace
      .claude/skills -> $HORIZON_SYSTEM/skills_bin — are JUNCTIONS/symlinks.
      Every link is removed with `rmdir`/unlink (reparse-point delete) BEFORE
      any recursive delete, so neither the workspace nor skills_bin is ever
      followed/destroyed. Also handles the old topology (~/.claude/skills).
    - Prompts for confirmation unless --yes. Supports --dry-run.

Usage:
    python horizon_aios_remove_brain.py <brain-name> [--horizon-root PATH] [--yes] [--dry-run]
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
    from horizon_aios_brain_credential import _delete_credential as _cred_delete
except Exception:  # noqa: BLE001 — keyring cleanup is best-effort
    _cred_delete = None

# Logon-rights cleanup (Windows). Any automation logon rights granted by
# horizon_aios_create_brain.py --automation must be revoked BEFORE the account is deleted,
# while the SID still resolves. Best-effort; harmless if none were granted.
try:
    from horizon_aios_brain_logon_rights import revoke as _revoke_logon_right, BATCH_LOGON, SERVICE_LOGON
    _AUTOMATION_RIGHTS = (BATCH_LOGON, SERVICE_LOGON)
except Exception:  # noqa: BLE001
    _revoke_logon_right = None
    _AUTOMATION_RIGHTS = ()


# ---------------------------------------------------------------------------
# Logging helpers (house style, matching horizon_aios_create_brain.py)
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


def _remove_reparse(path, dry_run):
    """
    Delete a junction/symlink at `path` as a REPARSE POINT — `rmdir` (Windows) /
    `unlink` (Unix) removes only the link, never following it into its target.
    This is the safety mechanism: the brain's links point at the workspace and
    at skills_bin, and a recursive delete that followed them would destroy those
    targets. Always call this on every link BEFORE any recursive delete.
    Safe no-op if absent; a real non-empty dir makes `rmdir` fail harmlessly.
    """
    if dry_run:
        print(f'  [DRY-RUN] reparse-point delete (rmdir/unlink — does NOT follow target): {path}')
        return
    if not (os.path.islink(path) or os.path.exists(path)):
        return
    info(f'Removing link (reparse-point delete): {path}')
    if platform.system() == 'Windows':
        run(['cmd', '/c', 'rmdir', path], check=False)
    elif os.path.islink(path):
        run(['rm', '-f', path], check=False)
    else:
        run(['rmdir', path], check=False)  # empty dir only; never recursive


def remove_windows(brain_name, brain_dir, dry_run):
    profile_dir  = _windows_profile_dir(brain_name)
    home_claude  = os.path.join(profile_dir, '.claude')                 # symlink -> workspace .claude (new topology)
    home_skills  = os.path.join(profile_dir, '.claude', 'skills')       # symlink -> skills_bin (old topology)
    brain_group  = f'{brain_name}_group'                                # per-brain group is <name>_group on Windows

    # 1. Remove reparse points FIRST, so no later recursive delete can follow a
    #    symlink into the workspace or into skills_bin. Covers both the new
    #    topology (~/.claude -> workspace) and the old one (~/.claude/skills).
    _remove_reparse(home_claude, dry_run)
    _remove_reparse(home_skills, dry_run)

    # 1b. Revoke any AIOS automation logon rights BEFORE deleting the account,
    #     while the SID still resolves. Idempotent: harmless if none were granted.
    if _revoke_logon_right is not None and (dry_run or user_exists(brain_name, 'Windows')):
        for right in _AUTOMATION_RIGHTS:
            if dry_run:
                print(f'  [DRY-RUN] revoke logon right (if held): {right} from {brain_name}')
                continue
            revoked, detail = _revoke_logon_right(brain_name, right)
            if revoked:
                info(f'Revoked logon right (if held): {right}')
            else:
                warn(f'Could not revoke {right}: {detail}')

    # 2. Remove the OS user account.
    if dry_run or user_exists(brain_name, 'Windows'):
        run_ps(f'Remove-LocalUser -Name "{brain_name}"', dry_run=dry_run)
    else:
        info(f'User does not exist (skipping): {brain_name}')

    # 3. Remove the per-brain group (leave the shared `brains` group).
    if dry_run or group_exists(brain_group, 'Windows'):
        run_ps(f'Remove-LocalGroup -Name "{brain_group}"', dry_run=dry_run)
    else:
        info(f'Per-brain group does not exist (skipping): {brain_group}')

    # 4. Remove the user profile directory (now symlink-free after step 1).
    if dry_run:
        print(f'  [DRY-RUN] Remove-Item -Recurse -Force {profile_dir}')
    elif os.path.isdir(profile_dir):
        info(f'Removing user profile directory: {profile_dir}')
        run_ps(f'Remove-Item -LiteralPath "{profile_dir}" -Recurse -Force '
               f'-ErrorAction SilentlyContinue', check=False)
    else:
        info(f'No user profile directory at: {profile_dir}')

    # 5. Remove the workspace folder (its skills symlink is cleared first).
    _remove_workspace(brain_dir, dry_run)


# ---------------------------------------------------------------------------
# Unix removal
# ---------------------------------------------------------------------------

def _unix_home(brain_name, os_name):
    try:
        import pwd
        return pwd.getpwnam(brain_name).pw_dir
    except (KeyError, ImportError):
        return f'/Users/{brain_name}' if os_name == 'Darwin' else f'/home/{brain_name}'


def remove_unix(brain_name, brain_dir, os_name, dry_run):
    # 1. Remove the home ~/.claude symlink first (reparse-safe). `userdel -r`
    #    also clears the home tree on Linux, but be explicit and cover macOS
    #    (dscl delete does not remove the home directory).
    home = _unix_home(brain_name, os_name)
    _remove_reparse(os.path.join(home, '.claude'), dry_run)

    # Disable systemd lingering (scheduled-tier automation) before deleting the
    # account, mirroring the Windows logon-right revoke. Best-effort/idempotent.
    if os_name == 'Linux' and shutil.which('loginctl') and (dry_run or user_exists(brain_name, os_name)):
        if dry_run:
            print(f'  [DRY-RUN] loginctl disable-linger {brain_name}')
        else:
            run(['loginctl', 'disable-linger', brain_name], check=False)

    if dry_run or user_exists(brain_name, os_name):
        if os_name == 'Linux':
            run(['userdel', '-r', brain_name], dry_run=dry_run, check=False)
        else:  # macOS
            run(['dscl', '.', '-delete', f'/Users/{brain_name}'], dry_run=dry_run, check=False)
    else:
        info(f'User does not exist (skipping): {brain_name}')

    if dry_run or group_exists(brain_name, os_name):
        if os_name == 'Linux':
            run(['groupdel', brain_name], dry_run=dry_run, check=False)
        else:
            run(['dseditgroup', '-o', 'delete', brain_name], dry_run=dry_run, check=False)
    else:
        info(f'Per-brain group does not exist (skipping): {brain_name}')

    _remove_workspace(brain_dir, dry_run)


def _remove_workspace(brain_dir, dry_run):
    """
    Remove $HORIZON_ROOT/brains/<name>/. The workspace .claude/skills is a
    directory symlink to skills_bin, so it is deleted as a reparse point FIRST —
    otherwise a recursive delete could follow it and destroy skills_bin.
    """
    _remove_reparse(os.path.join(brain_dir, '.claude', 'skills'), dry_run)
    if dry_run:
        print(f'  [DRY-RUN] rmtree {brain_dir}')
        return
    if not os.path.isdir(brain_dir):
        info(f'No workspace folder at: {brain_dir}')
        return
    info(f'Removing workspace folder: {brain_dir}')
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

    # Per-brain group name: <brain>_group on Windows, <brain> on Unix.
    per_brain_group = f'{brain_name}_group' if os_name == 'Windows' else brain_name

    # --- Nothing-to-do short-circuit ---
    exists_user = user_exists(brain_name, os_name)
    exists_ws = os.path.isdir(brain_dir)
    if not exists_user and not exists_ws and not group_exists(per_brain_group, os_name):
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
             f'manually: horizon_aios_brain_credential.py delete {brain_name}')
    else:
        if _cred_delete(brain_name):
            ok('Stored credential removed from OS keystore.')
        else:
            warn('Could not remove stored credential — remove manually: '
                 f'horizon_aios_brain_credential.py delete {brain_name}')

    # --- Post-removal verification ---
    banner('Verify removal')
    remaining = []
    if not args.dry_run:
        if user_exists(brain_name, os_name):
            remaining.append('user account')
        if group_exists(per_brain_group, os_name):
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
