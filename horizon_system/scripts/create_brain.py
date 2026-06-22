#!/usr/bin/env python3
"""
create_brain.py — Horizon AIOS Brain Provisioning Script
=========================================================

Creates and configures everything needed for a new AI brain:
  - OS user account  (<brain-name>)
  - Group: brains    (common AIOS group, grants horizon_system/bin rx)
  - Group: <brain-name> (brain-specific group, grants rwx on brain folder)
  - Brain folder:    $HORIZON_ROOT/brains/<brain-name>/
  - Permissions:     brain folder (770 / icacls full-control for user+group)
                     horizon_system/bin + skills_bin (group brains rx)
                     sbin/skills_sbin/logs locked to owner-only AFTER
                     all grants (security invariant)
  - Password:        stored in OS native keystore (Windows Credential Manager /
                     macOS Keychain / Linux Secret Service) via brain_credential.py
  - Shell profile:   sets HORIZON_* env vars and cds to brain folder on
                     interactive login as the brain user

Usage:
    python create_brain.py <brain-name> [--horizon-root /path] [--dry-run]

Requirements:
    - Python 3.6+, stdlib only
    - Must be run as Administrator (Windows) or root (Unix)

Platform support:
    - Windows  — PowerShell cmdlets + icacls
    - Linux    — useradd / groupadd / usermod / chown / chmod
    - macOS    — dscl / dseditgroup (AddUser via dscl) / chown / chmod

Security invariants honored (see $HORIZON_ETC/security_invariants.md):
    - sbin/skills_sbin Deny ACEs are always set AFTER all brains-group grants
      so inherited permissions can never accidentally reach privileged dirs.
    - Brain user gets rwx on its own folder, rx on bin + skills_bin, nothing on sbin.
    - No credentials are stored in this script.
    - Account password is auto-generated (random 64-char) and stored in
      the OS native keystore via brain_credential.py (sbin/).
"""

import argparse
import datetime
import json
import os
import platform
import re
import secrets
import stat
import subprocess
import sys

# ---------------------------------------------------------------------------
# Optional credential store (brain_credential.py in sbin/)
# ---------------------------------------------------------------------------

try:
    import sys as _sys
    import os as _os
    _sbin = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'sbin')
    _sys.path.insert(0, _sbin)
    from brain_credential import store_password as _store_password
    _HAS_CRED_STORE = True
except Exception:
    _HAS_CRED_STORE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Regex enforcing brain names: start with lowercase letter, then 1-31 chars
# of lowercase letters, digits, or underscores.  Total length: 2-32 chars.
BRAIN_NAME_RE = re.compile(r'^[a-z][a-z0-9_]{1,31}$')

# The common group that every brain belongs to.  Members of this group get
# read+execute on $HORIZON_BIN but are explicitly denied access to sbin.
BRAINS_GROUP = 'brains'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def banner(text):
    """Print a phase banner to stdout."""
    line = '=' * (len(text) + 6)
    print(f'\n{line}')
    print(f'=== {text} ===')
    print(f'{line}\n')


def info(msg):
    """Print an informational message."""
    print(f'  [INFO]  {msg}')


def warn(msg):
    """Print a warning message."""
    print(f'  [WARN]  {msg}')


def error(msg):
    """Print an error message (does not exit — callers decide that)."""
    print(f'  [ERROR] {msg}', file=sys.stderr)


def run(cmd, dry_run=False, check=True, capture=False):
    """
    Execute a shell command.

    Parameters
    ----------
    cmd      : list[str]  — argv-style command; no shell=True for safety
    dry_run  : bool       — if True, print the command but do not execute it
    check    : bool       — if True, raise on non-zero exit code
    capture  : bool       — if True, return stdout as a string

    Returns
    -------
    str | None  — stdout if capture=True, else None
    """
    display = ' '.join(str(a) for a in cmd)
    if dry_run:
        print(f'  [DRY-RUN] {display}')
        return ''
    info(f'Running: {display}')
    result = subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )
    if capture:
        return result.stdout.strip()
    return None


def run_ps(ps_expr, dry_run=False, check=True, capture=False):
    """
    Execute a PowerShell expression on Windows.

    Parameters
    ----------
    ps_expr : str   — PowerShell code to run
    Others  : same as run()
    """
    cmd = ['powershell', '-NonInteractive', '-Command', ps_expr]
    return run(cmd, dry_run=dry_run, check=check, capture=capture)


def _generate_password():
    """
    Generate a cryptographically random 64-character account password.

    Uses token_urlsafe (URL-safe base64) which avoids special characters
    that can break shell quoting on any platform.  48 bytes → 64 chars.
    """
    return secrets.token_urlsafe(48)


# ---------------------------------------------------------------------------
# Phase 1: Preflight
# ---------------------------------------------------------------------------

def phase1_preflight(args):
    """
    Detect OS, validate inputs, check privileges, validate paths, and confirm
    that the brain does not already exist.

    Returns a dict of resolved paths used by later phases.
    """
    banner('Phase 1: Preflight')

    # --- OS detection ---
    os_name = platform.system()  # 'Windows', 'Linux', 'Darwin'
    if os_name not in ('Windows', 'Linux', 'Darwin'):
        error(f'Unsupported platform: {os_name}')
        sys.exit(1)
    info(f'Detected OS: {os_name}')

    # --- Brain name validation ---
    brain_name = args.brain_name
    if not BRAIN_NAME_RE.match(brain_name):
        error(
            f'Invalid brain name: "{brain_name}"\n'
            '  Must match ^[a-z][a-z0-9_]{{1,31}}$ '
            '(start with lowercase letter, then 1-31 lowercase letters/digits/underscores)'
        )
        sys.exit(1)
    info(f'Brain name is valid: {brain_name}')

    # --- Admin / root check ---
    _check_privileges(os_name)

    # --- Resolve HORIZON_ROOT ---
    if args.horizon_root:
        horizon_root = os.path.abspath(args.horizon_root)
    else:
        # Derive from ../../ relative to the script's own location.
        # Script lives at $HORIZON_ROOT/horizon_system/scripts/create_brain.py
        # so ../../ is $HORIZON_ROOT.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        horizon_root = os.path.abspath(os.path.join(script_dir, '..', '..'))

    info(f'HORIZON_ROOT: {horizon_root}')

    if not os.path.isdir(horizon_root):
        error(f'HORIZON_ROOT does not exist or is not a directory: {horizon_root}')
        sys.exit(1)

    # --- Derive dependent paths ---
    horizon_system      = os.path.join(horizon_root, 'horizon_system')
    horizon_bin         = os.path.join(horizon_system, 'bin')
    horizon_sbin        = os.path.join(horizon_system, 'sbin')
    horizon_skills_bin  = os.path.join(horizon_system, 'skills_bin')
    horizon_skills_sbin = os.path.join(horizon_system, 'skills_sbin')
    brains_dir          = os.path.join(horizon_root, 'brains')
    brain_dir           = os.path.join(brains_dir,   brain_name)
    logs_dir            = os.path.join(horizon_root, 'logs')

    for label, path in [('HORIZON_SYSTEM', horizon_system),
                        ('HORIZON_BIN',    horizon_bin),
                        ('HORIZON_SYSTEM/sbin', horizon_sbin)]:
        if not os.path.isdir(path):
            error(f'{label} does not exist: {path}')
            sys.exit(1)
        info(f'{label}: {path}')

    # brains/ directory will be created in Phase 3 if it doesn't exist yet.
    info(f'brains dir       : {brains_dir}')
    info(f'brain dir        : {brain_dir}')

    # --- Current (invoking) user ---
    try:
        import getpass
        invoking_user = getpass.getuser()
    except Exception:
        invoking_user = os.getlogin()
    info(f'Invoking user (will be added to <brain-name> group): {invoking_user}')

    # --- Check whether the brain user already exists ---
    if _user_exists(brain_name, os_name):
        warn(f'User "{brain_name}" already exists.  Nothing to do.')
        sys.exit(0)
    info(f'User "{brain_name}" does not yet exist — will be created.')

    return {
        'os_name':              os_name,
        'brain_name':           brain_name,
        'invoking_user':        invoking_user,
        'horizon_root':         horizon_root,
        'horizon_system':       horizon_system,
        'horizon_bin':          horizon_bin,
        'horizon_sbin':         horizon_sbin,
        'horizon_skills_bin':   horizon_skills_bin,
        'horizon_skills_sbin':  horizon_skills_sbin,
        'brains_dir':           brains_dir,
        'brain_dir':            brain_dir,
        'logs_dir':             logs_dir,
    }


def _check_privileges(os_name):
    """Exit with a clear message if the script is not running elevated."""
    if os_name == 'Windows':
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = False
        if not is_admin:
            error(
                'This script must be run as Administrator.\n'
                '  Right-click your terminal and choose "Run as administrator",\n'
                '  then re-run the script.'
            )
            sys.exit(1)
        info('Running as Administrator: OK')
    else:
        if os.geteuid() != 0:
            error(
                'This script must be run as root.\n'
                '  Re-run with: sudo python create_brain.py <brain-name>'
            )
            sys.exit(1)
        info('Running as root: OK')


def _user_exists(name, os_name):
    """Return True if an OS user account named *name* already exists."""
    if os_name == 'Windows':
        result = subprocess.run(
            ['powershell', '-NonInteractive', '-Command',
             f'Get-LocalUser -Name "{name}" -ErrorAction SilentlyContinue'],
            capture_output=True, text=True
        )
        return bool(result.stdout.strip())
    else:
        result = subprocess.run(['id', name], capture_output=True)
        return result.returncode == 0


# ---------------------------------------------------------------------------
# Phase 2: User and group creation
# ---------------------------------------------------------------------------

def phase2_create_user_and_groups(ctx, dry_run=False):
    """
    Generate account password, create the brains group, brain-specific group,
    and brain user account.  Add users to appropriate groups.

    The generated password is stored in ctx['password'] and persisted to the
    OS native keystore via brain_credential.store_password (never printed).
    """
    banner('Phase 2: User and Group Creation')

    os_name       = ctx['os_name']
    brain_name    = ctx['brain_name']
    invoking_user = ctx['invoking_user']

    # Generate a random 64-char password and store in the OS keystore.
    password = _generate_password()
    ctx['password'] = password
    info('Generated random account password — will be stored in the OS native keystore.')
    info('  Password will NOT be printed here. Retrieve with: brain_credential.py get <name>')

    if os_name == 'Windows':
        _phase2_windows(brain_name, invoking_user, password, dry_run)
    else:
        _phase2_unix(brain_name, invoking_user, os_name, password, dry_run)

    if _HAS_CRED_STORE:
        if _store_password(brain_name, password):
            info('Account password stored in OS keystore (keyring). Retrieve with: brain_credential.py get <name>')
        else:
            warn('Password not stored in keystore — reset manually if needed for runas/Task Scheduler.')
    else:
        warn('brain_credential module not found in sbin/ — password not stored. Reset manually if needed.')


# ---- Windows implementation ----

def _phase2_windows(brain_name, invoking_user, password, dry_run):
    """Windows: use PowerShell Local* cmdlets."""

    _win_create_group_if_absent(BRAINS_GROUP, dry_run)
    _win_create_group_if_absent(brain_name, dry_run)

    info(f'Creating local user: {brain_name}')
    run_ps(
        f'$pw = ConvertTo-SecureString "{password}" -AsPlainText -Force; '
        f'New-LocalUser -Name "{brain_name}" -Password $pw '
        f'-FullName "{brain_name} (Horizon Brain)" '
        f'-Description "Horizon AIOS brain account" '
        f'-PasswordNeverExpires',
        dry_run=dry_run,
    )

    info(f'Adding {brain_name} to group: {BRAINS_GROUP}')
    run_ps(
        f'Add-LocalGroupMember -Group "{BRAINS_GROUP}" -Member "{brain_name}"',
        dry_run=dry_run,
    )

    info(f'Adding {brain_name} to group: {brain_name}')
    run_ps(
        f'Add-LocalGroupMember -Group "{brain_name}" -Member "{brain_name}"',
        dry_run=dry_run,
    )

    info(f'Adding invoking user ({invoking_user}) to group: {brain_name}')
    run_ps(
        f'Add-LocalGroupMember -Group "{brain_name}" -Member "{invoking_user}"',
        dry_run=dry_run,
    )


def _win_create_group_if_absent(group_name, dry_run):
    """Create a Windows local group only if it does not already exist."""
    result = subprocess.run(
        ['powershell', '-NonInteractive', '-Command',
         f'Get-LocalGroup -Name "{group_name}" -ErrorAction SilentlyContinue'],
        capture_output=True, text=True,
    )
    if result.stdout.strip():
        info(f'Group already exists (skipping): {group_name}')
        return
    info(f'Creating local group: {group_name}')
    run_ps(
        f'New-LocalGroup -Name "{group_name}" '
        f'-Description "Horizon AIOS group: {group_name}"',
        dry_run=dry_run,
    )


# ---- Unix implementation ----

def _phase2_unix(brain_name, invoking_user, os_name, password, dry_run):
    """Linux/macOS: use groupadd / useradd / usermod."""

    _unix_create_group_if_absent(BRAINS_GROUP, dry_run)
    _unix_create_group_if_absent(brain_name, dry_run)

    info(f'Creating OS user: {brain_name}')
    if os_name == 'Linux':
        run(
            ['useradd',
             '--create-home',
             '--shell', '/bin/bash',
             '--comment', f'Horizon AIOS brain account',
             '--password', _linux_hash_password(password, brain_name),
             brain_name],
            dry_run=dry_run,
        )
    else:
        _macos_create_user(brain_name, password, dry_run)

    info(f'Adding {brain_name} to group: {BRAINS_GROUP}')
    _unix_add_user_to_group(brain_name, BRAINS_GROUP, os_name, dry_run)

    info(f'Adding {brain_name} to group: {brain_name}')
    _unix_add_user_to_group(brain_name, brain_name, os_name, dry_run)

    info(f'Adding invoking user ({invoking_user}) to group: {brain_name}')
    _unix_add_user_to_group(invoking_user, brain_name, os_name, dry_run)


def _unix_create_group_if_absent(group_name, dry_run):
    """Create a Unix group only if it does not already exist."""
    result = subprocess.run(['getent', 'group', group_name], capture_output=True)
    if result.returncode == 0:
        info(f'Group already exists (skipping): {group_name}')
        return
    info(f'Creating group: {group_name}')
    run(['groupadd', group_name], dry_run=dry_run)


def _unix_add_user_to_group(user, group, os_name, dry_run):
    """Add *user* to *group* using the platform-appropriate command."""
    if os_name == 'Linux':
        run(['usermod', '-aG', group, user], dry_run=dry_run)
    else:
        run(['dseditgroup', '-o', 'edit', '-a', user, '-t', 'user', group],
            dry_run=dry_run)


def _linux_hash_password(password, brain_name):
    """
    Hash a plaintext password for use with useradd --password.

    Uses 'openssl passwd -6' (SHA-512).  Falls back to a locked-account
    marker if openssl is unavailable.
    """
    try:
        result = subprocess.run(
            ['openssl', 'passwd', '-6', password],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        warn(
            'openssl not found — password hash could not be generated.\n'
            f'  Set the password manually after provisioning: passwd {brain_name}'
        )
        return '!'


def _macos_create_user(brain_name, password, dry_run):
    """
    Create a macOS local user account via dscl.
    """
    next_uid = _macos_next_uid()
    info(f'Assigning UID: {next_uid}')

    base = f'/Local/Default/Users/{brain_name}'
    cmds = [
        ['dscl', '.', '-create',   base],
        ['dscl', '.', '-create',   base, 'UserShell',    '/bin/bash'],
        ['dscl', '.', '-create',   base, 'RealName',     f'{brain_name} (Horizon Brain)'],
        ['dscl', '.', '-create',   base, 'UniqueID',     str(next_uid)],
        ['dscl', '.', '-create',   base, 'PrimaryGroupID', '20'],
        ['dscl', '.', '-create',   base, 'NFSHomeDirectory', f'/Users/{brain_name}'],
        ['dscl', '.', '-passwd',   base, password],
    ]
    for cmd in cmds:
        run(cmd, dry_run=dry_run)

    home = f'/Users/{brain_name}'
    run(['createhomedir', '-c', '-u', brain_name], dry_run=dry_run, check=False)
    if not dry_run and not os.path.isdir(home):
        os.makedirs(home, mode=0o755, exist_ok=True)


def _macos_next_uid():
    """Return the next available UID >= 1000 on macOS."""
    result = subprocess.run(
        ['dscl', '.', '-list', '/Local/Default/Users', 'UniqueID'],
        capture_output=True, text=True,
    )
    used_uids = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                used_uids.add(int(parts[1]))
            except ValueError:
                pass
    uid = 1000
    while uid in used_uids:
        uid += 1
    return uid


# ---------------------------------------------------------------------------
# Phase 3: Folder creation and permissions
# ---------------------------------------------------------------------------

def phase3_folders_and_permissions(ctx, dry_run=False):
    """
    Create folders and set all permissions per security_invariants.md §2 table.

    Order matters on Windows — explicit Deny on sbin/skills_sbin/logs MUST
    come AFTER the brains-group RX grants, so that Deny takes precedence
    over any inherited permission.
    """
    banner('Phase 3: Folder Creation and Permissions')

    os_name              = ctx['os_name']
    brain_name           = ctx['brain_name']
    invoking_user        = ctx['invoking_user']
    brains_dir           = ctx['brains_dir']
    brain_dir            = ctx['brain_dir']
    horizon_bin          = ctx['horizon_bin']
    horizon_sbin         = ctx['horizon_sbin']
    horizon_skills_bin   = ctx['horizon_skills_bin']
    horizon_skills_sbin  = ctx['horizon_skills_sbin']
    logs_dir             = ctx['logs_dir']

    # 3.1 Create brain folder
    info(f'Creating brain folder: {brain_dir}')
    if not dry_run:
        os.makedirs(brain_dir, exist_ok=True)
    else:
        print(f'  [DRY-RUN] os.makedirs({brain_dir!r}, exist_ok=True)')

    if os_name == 'Windows':
        _phase3_windows(
            brain_name, invoking_user,
            brain_dir,
            horizon_bin, horizon_sbin, horizon_skills_bin, horizon_skills_sbin, logs_dir,
            dry_run,
        )
    else:
        _phase3_unix(
            brain_name, invoking_user, os_name,
            brain_dir,
            horizon_bin, horizon_sbin, horizon_skills_bin, horizon_skills_sbin, logs_dir,
            dry_run,
        )


# ---- Windows permission implementation ----

def _phase3_windows(brain_name, invoking_user,
                    brain_dir,
                    horizon_bin, horizon_sbin, horizon_skills_bin, horizon_skills_sbin, logs_dir,
                    dry_run):
    """
    Set ACLs on Windows using icacls.

    All Deny ACEs MUST be applied AFTER all brains-group RX grants — Deny
    takes precedence over Allow, and applying after ensures inherited
    permissions never accidentally reach privileged dirs.
    """

    # -- Brain folder: remove inheritance, grant brain user + group full control --
    info(f'Setting ACLs on brain folder: {brain_dir}')
    run(['icacls', brain_dir,
         '/inheritance:r',
         '/grant', f'{brain_name}:(OI)(CI)F',
         '/grant', f'{invoking_user}:(OI)(CI)F'],
        dry_run=dry_run)

    # -- horizon_system/bin: grant brains group RX --
    info(f'Granting brains group RX on bin: {horizon_bin}')
    run(['icacls', horizon_bin,
         '/grant', f'{BRAINS_GROUP}:(OI)(CI)RX'],
        dry_run=dry_run)

    # -- skills_bin: explicit grant (not under bin/, so not inherited) --
    info(f'Granting brains group RX on skills_bin: {horizon_skills_bin}')
    run(['icacls', horizon_skills_bin,
         '/grant', f'{BRAINS_GROUP}:(OI)(CI)RX'],
        dry_run=dry_run)

    # -- Deny on privileged dirs (MUST be after all grants above) --
    for label, path in [('sbin', horizon_sbin),
                        ('skills_sbin', horizon_skills_sbin),
                        ('logs', logs_dir)]:
        if os.path.isdir(path):
            info(f'Denying brains group on {label}: {path}')
            run(['icacls', path,
                 '/inheritance:r',
                 '/grant', f'{invoking_user}:(OI)(CI)F',
                 '/deny',  f'{BRAINS_GROUP}:(OI)(CI)RX'],
                dry_run=dry_run)

    # -- Brain ~/.claude/skills/ → skills_bin/ (junction; no admin needed) --
    system_drive = os.environ.get('SystemDrive', 'C:')
    brain_home = os.path.join(system_drive + '\\', 'Users', brain_name)
    brain_claude_dir = os.path.join(brain_home, '.claude')
    brain_skills_dir = os.path.join(brain_claude_dir, 'skills')
    info(f'Redirecting brain ~/.claude/skills/ → skills_bin/')
    if not dry_run:
        os.makedirs(brain_claude_dir, exist_ok=True)
    if os.path.exists(brain_skills_dir):
        run(['cmd', '/c', 'rmdir', brain_skills_dir], dry_run=dry_run)
    run(['cmd', '/c', 'mklink', '/J', brain_skills_dir, horizon_skills_bin],
        dry_run=dry_run)


# ---- Unix permission implementation ----

def _phase3_unix(brain_name, invoking_user, os_name,
                 brain_dir,
                 horizon_bin, horizon_sbin, horizon_skills_bin, horizon_skills_sbin, logs_dir,
                 dry_run):
    """
    Set ownership and mode bits on Linux/macOS.

    sbin/skills_sbin/logs chmod 700 MUST happen AFTER all brains-group rx
    grants so that those grants cannot cascade into privileged dirs.
    """

    # -- Brain folder: chown brain_name:brain_name, chmod 770 --
    info(f'Setting ownership of brain folder: {brain_dir}')
    run(['chown', '-R', f'{brain_name}:{brain_name}', brain_dir], dry_run=dry_run)
    run(['chmod', '770', brain_dir], dry_run=dry_run)

    # -- bin: set brains group and grant rx --
    info(f'Setting bin group to "{BRAINS_GROUP}" and granting rx')
    run(['chown', f':{BRAINS_GROUP}', horizon_bin], dry_run=dry_run)
    run(['chmod', 'g+rx', horizon_bin], dry_run=dry_run)

    # -- skills_bin: explicit grant (not under bin/, so not inherited) --
    info(f'Setting skills_bin group to "{BRAINS_GROUP}" and granting rx')
    run(['chown', f':{BRAINS_GROUP}', horizon_skills_bin], dry_run=dry_run)
    run(['chmod', 'g+rx', horizon_skills_bin], dry_run=dry_run)

    # -- Brain ~/.claude/skills/ → skills_bin/ (symlink) --
    try:
        import pwd as _pwd
        brain_home = _pwd.getpwnam(brain_name).pw_dir
    except KeyError:
        brain_home = f'/home/{brain_name}'
    brain_claude_dir = os.path.join(brain_home, '.claude')
    brain_skills_dir = os.path.join(brain_claude_dir, 'skills')
    info(f'Redirecting brain ~/.claude/skills/ → skills_bin/')
    run(['mkdir', '-p', brain_claude_dir], dry_run=dry_run)
    run(['chown', f'{brain_name}:{brain_name}', brain_claude_dir], dry_run=dry_run)
    run(['ln', '-sfn', horizon_skills_bin, brain_skills_dir], dry_run=dry_run)
    run(['chown', '-h', f'{brain_name}:{brain_name}', brain_skills_dir], dry_run=dry_run)

    # -- Privileged dirs: owner-only — MUST be after all grants above --
    for label, path in [('sbin', horizon_sbin),
                        ('skills_sbin', horizon_skills_sbin),
                        ('logs', logs_dir)]:
        if os.path.isdir(path):
            info(f'Setting {label} to owner-only (chmod 700): {path}')
            run(['chmod', '700', path], dry_run=dry_run)


# ---------------------------------------------------------------------------
# Phase 4: Verify
# ---------------------------------------------------------------------------

def phase4_verify(ctx, dry_run=False):
    """
    Confirm that everything was set up correctly and print a summary.
    Returns True if all checks pass, False otherwise.
    """
    banner('Phase 4: Verification')

    os_name             = ctx['os_name']
    brain_name          = ctx['brain_name']
    brain_dir           = ctx['brain_dir']
    horizon_sbin        = ctx['horizon_sbin']
    horizon_skills_sbin = ctx['horizon_skills_sbin']

    results = {}

    # -- User exists --
    results['user_exists'] = _user_exists(brain_name, os_name)
    _report_check('User exists', results['user_exists'])

    # -- Group memberships --
    results['in_brains_group'] = _check_group_membership(brain_name, BRAINS_GROUP, os_name)
    _report_check(f'User in "{BRAINS_GROUP}" group', results['in_brains_group'])

    results['in_brain_group'] = _check_group_membership(brain_name, brain_name, os_name)
    _report_check(f'User in "{brain_name}" group', results['in_brain_group'])

    # -- Brain folder exists --
    results['brain_dir_exists'] = os.path.isdir(brain_dir)
    _report_check(f'Brain folder exists: {brain_dir}', results['brain_dir_exists'])

    if results['brain_dir_exists'] and not dry_run:
        results['brain_dir_perms'] = _check_folder_permissions(brain_dir, os_name)
        _report_check('Brain folder permissions OK', results['brain_dir_perms'])
    else:
        results['brain_dir_perms'] = None
        info('Brain folder permission check skipped (dry-run or folder missing)')

    # -- sbin / skills_sbin permissions (Unix only) --
    if os_name != 'Windows' and not dry_run:
        for label, path in [('sbin', horizon_sbin), ('skills_sbin', horizon_skills_sbin)]:
            if os.path.isdir(path):
                mode = oct(stat.S_IMODE(os.stat(path).st_mode))
                results[f'{label}_locked'] = (mode == '0o700')
                _report_check(f'{label} is owner-only (700, got {mode})',
                               results[f'{label}_locked'])

    all_passed = all(
        v for v in results.values() if v is not None
    )

    # -- Summary --
    banner('Summary')
    if all_passed:
        print(f'  Brain "{brain_name}" provisioned successfully.\n')
    else:
        print(f'  Brain "{brain_name}" provisioning completed with warnings/failures.\n')
        print('  Review the [FAIL] items above.\n')

    print('  Next steps:')
    print(f'    1. Log in as "{brain_name}" and verify read+execute on $HORIZON_BIN.')
    print(f'    2. Review and customize the deployed workspace files (Phase 5):')
    print(f'       $HORIZON_ROOT/brains/{brain_name}/.claude/CLAUDE.md')
    print(f'       $HORIZON_ROOT/brains/{brain_name}/.claude/settings.json')
    print(f'    3. Provision tools from $HORIZON_USRBIN into the brain folder as needed.')
    print(f'    4. Retrieve account password: python brain_credential.py get {brain_name}')
    print(f'       (Stored in OS keystore. Windows Task Scheduler: use this password when setting up scheduled tasks.)')
    print(f'    5. Shell profile written at brain home — sets HORIZON_* env vars and')
    print(f'       changes to brain folder on interactive login as "{brain_name}".')
    print(f'    6. To run as a scheduled/automated agent:')
    print(f'         Windows: Task Scheduler → run as "{brain_name}" (use password from keystore)')
    print(f'         Linux:   sudo crontab -u {brain_name} -e')
    print(f'         macOS:   sudo crontab -u {brain_name} -e')
    print()

    if not all_passed:
        print('  Cleanup instructions (if you need to roll back manually):')
        _print_cleanup_instructions(brain_name, ctx['brain_dir'],
                                    ctx['os_name'])

    return all_passed


def _report_check(label, passed):
    status = 'PASS' if passed else 'FAIL'
    print(f'  [{status}] {label}')


def _check_group_membership(user, group, os_name):
    """Return True if *user* belongs to *group*."""
    if os_name == 'Windows':
        result = subprocess.run(
            ['powershell', '-NonInteractive', '-Command',
             f'(Get-LocalGroupMember -Group "{group}" -ErrorAction SilentlyContinue)'
             f'.Name -contains "{user}"'],
            capture_output=True, text=True,
        )
        return result.stdout.strip().lower() == 'true'
    else:
        result = subprocess.run(
            ['id', '-nG', user],
            capture_output=True, text=True,
        )
        return group in result.stdout.split()


def _check_folder_permissions(path, os_name):
    """
    Verify that the brain folder has the expected permission posture.

    Unix  : mode must be 0o770 (rwxrwx---)
    Windows: we just verify the folder exists (icacls output parsing is
             brittle; manual verification is recommended).
    """
    if os_name == 'Windows':
        return os.path.isdir(path)
    else:
        mode = stat.S_IMODE(os.stat(path).st_mode)
        expected = 0o770
        if mode != expected:
            warn(
                f'Expected mode {oct(expected)} on {path}, '
                f'got {oct(mode)}'
            )
            return False
        return True


def _print_cleanup_instructions(brain_name, brain_dir, os_name):
    """Print manual cleanup instructions in case of partial failure."""
    print()
    print('  ---- Cleanup instructions ----')
    if os_name == 'Windows':
        print(f'    Remove-LocalUser   -Name "{brain_name}"')
        print(f'    Remove-LocalGroup  -Name "{brain_name}"')
        print(f'    Remove-Item -Recurse -Force "{brain_dir}"')
        print(f'    # Also remove {brain_name} from "{BRAINS_GROUP}" if it was added.')
    else:
        print(f'    userdel -r {brain_name}')
        print(f'    groupdel {brain_name}')
        print(f'    rm -rf "{brain_dir}"')
        print(f'    # Also: gpasswd -d {brain_name} {BRAINS_GROUP}  (if user was added)')
    print()


# ---------------------------------------------------------------------------
# Phase 5: Deploy brain workspace templates, shell profile, and manifest
# ---------------------------------------------------------------------------

def phase5_deploy_templates(ctx, dry_run=False):
    """
    Deploy .aioscommon templates into the brain's .claude/ workspace directory,
    write the brain user's shell profile (sets HORIZON_* env vars and default
    working directory), and write a machine-readable provisioning manifest.

    Creates:
        brains/<brain_name>/.claude/CLAUDE.md       (from brain_CLAUDE.md.template)
        brains/<brain_name>/.claude/settings.json   (from brain_settings.json.template)
        brains/<brain_name>/.aios_provision.json    (provisioning record for auditors)
        <brain_home>/.bashrc (Linux) / .zshrc+.bash_profile (macOS) /
            Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1 (Windows)
            — sets HORIZON_* env vars and cd's to brain folder on interactive login

    Non-fatal: if templates are missing or file writes fail, a warning is
    printed and provisioning continues.  OS-level setup from Phases 1-3 is
    complete regardless of whether this phase succeeds.
    """
    banner('Phase 5: Deploy Brain Workspace Templates and Shell Profile')

    brain_name   = ctx['brain_name']
    brain_dir    = ctx['brain_dir']
    horizon_root = ctx['horizon_root']

    aioscommon_dir   = os.path.join(horizon_root, 'brains', '.aioscommon')
    brain_claude_dir = os.path.join(brain_dir, '.claude')

    if dry_run:
        print(f'  [DRY-RUN] Would create {brain_claude_dir}')
        print(f'  [DRY-RUN] Would deploy CLAUDE.md from {aioscommon_dir}/brain_CLAUDE.md.template')
        print(f'  [DRY-RUN] Would deploy settings.json from {aioscommon_dir}/brain_settings.json.template')
        print(f'  [DRY-RUN] Would write .aios_provision.json to {brain_dir}')
        print(f'  [DRY-RUN] Would write shell profile for {brain_name}')
        return

    # 5.1 Create .claude/ directory
    try:
        os.makedirs(brain_claude_dir, exist_ok=True)
        info(f'Created: {brain_claude_dir}')
    except OSError as exc:
        warn(f'Could not create {brain_claude_dir}: {exc}')
        warn('Skipping template deployment — create .claude/ manually.')
        return

    # Use forward slashes in the @ import path (Claude Code expects this on all platforms)
    horizon_root_fwd = horizon_root.replace('\\', '/')

    # 5.2 Deploy CLAUDE.md
    _deploy_template(
        src=os.path.join(aioscommon_dir, 'brain_CLAUDE.md.template'),
        dest=os.path.join(brain_claude_dir, 'CLAUDE.md'),
        substitutions={
            '[BRAIN_NAME]':        brain_name,
            '[HORIZON_ROOT_PATH]': horizon_root_fwd,
        },
    )

    # 5.3 Deploy settings.json
    _deploy_template(
        src=os.path.join(aioscommon_dir, 'brain_settings.json.template'),
        dest=os.path.join(brain_claude_dir, 'settings.json'),
        substitutions={'[BRAIN_NAME]': brain_name},
    )

    # 5.4 Write shell profile (sets HORIZON_* env vars + default working dir)
    _write_brain_shell_profile(ctx)

    # 5.5 Write provisioning manifest
    _write_provision_manifest(ctx)

    info(f'Phase 5 complete for brain: {brain_name}')


def _write_brain_shell_profile(ctx):
    """
    Write a shell profile for the brain user that:
    - Exports all HORIZON_* environment variables
    - Sets HORIZON_BRAIN_NAME to the brain name
    - Changes the default working directory to the brain's folder

    Windows: writes PowerShell profile (both legacy and Core locations)
    Linux:   writes ~/.bashrc
    macOS:   writes ~/.zshrc and ~/.bash_profile
    """
    brain_name   = ctx['brain_name']
    horizon_root = ctx['horizon_root']
    brain_dir    = ctx['brain_dir']
    os_name      = ctx['os_name']

    if os_name == 'Windows':
        _write_brain_profile_windows(brain_name, horizon_root, brain_dir)
    elif os_name == 'Linux':
        _write_brain_profile_linux(brain_name, horizon_root, brain_dir)
    else:
        _write_brain_profile_macos(brain_name, horizon_root, brain_dir)


def _brain_profile_content_posix(brain_name, horizon_root, brain_dir):
    """Return the POSIX shell profile content for a brain user."""
    horizon_system = os.path.join(horizon_root, 'horizon_system')
    horizon_bin    = os.path.join(horizon_system, 'bin')
    horizon_etc    = os.path.join(horizon_system, 'ai_os_etc')
    horizon_docs   = os.path.join(horizon_system, 'documentation')
    return (
        f'# Horizon AIOS — brain environment for {brain_name}\n'
        f'export HORIZON_ROOT="{horizon_root}"\n'
        f'export HORIZON_SYSTEM="{horizon_system}"\n'
        f'export HORIZON_BIN="{horizon_bin}"\n'
        f'export HORIZON_ETC="{horizon_etc}"\n'
        f'export HORIZON_DOCS="{horizon_docs}"\n'
        f'export HORIZON_BRAIN_NAME="{brain_name}"\n'
        f'cd "{brain_dir}"\n'
    )


def _write_brain_profile_linux(brain_name, horizon_root, brain_dir):
    """Write ~/.bashrc for the brain user on Linux."""
    try:
        import pwd as _pwd
        brain_home = _pwd.getpwnam(brain_name).pw_dir
    except KeyError:
        brain_home = f'/home/{brain_name}'

    profile_path = os.path.join(brain_home, '.bashrc')
    content = _brain_profile_content_posix(brain_name, horizon_root, brain_dir)
    _safe_write_profile(profile_path, content, brain_name)


def _write_brain_profile_macos(brain_name, horizon_root, brain_dir):
    """Write ~/.zshrc and ~/.bash_profile for the brain user on macOS."""
    brain_home = f'/Users/{brain_name}'
    content = _brain_profile_content_posix(brain_name, horizon_root, brain_dir)

    for filename in ('.zshrc', '.bash_profile'):
        profile_path = os.path.join(brain_home, filename)
        _safe_write_profile(profile_path, content, brain_name)


def _write_brain_profile_windows(brain_name, horizon_root, brain_dir):
    """Write PowerShell profile for the brain user on Windows."""
    system_drive = os.environ.get('SystemDrive', 'C:')
    brain_home   = os.path.join(system_drive + '\\', 'Users', brain_name)

    horizon_system = os.path.join(horizon_root, 'horizon_system')
    horizon_bin    = os.path.join(horizon_system, 'bin')
    horizon_etc    = os.path.join(horizon_system, 'ai_os_etc')
    horizon_docs   = os.path.join(horizon_system, 'documentation')

    content = (
        f'# Horizon AIOS — brain environment for {brain_name}\n'
        f'$env:HORIZON_ROOT        = "{horizon_root}"\n'
        f'$env:HORIZON_SYSTEM      = "{horizon_system}"\n'
        f'$env:HORIZON_BIN         = "{horizon_bin}"\n'
        f'$env:HORIZON_ETC         = "{horizon_etc}"\n'
        f'$env:HORIZON_DOCS        = "{horizon_docs}"\n'
        f'$env:HORIZON_BRAIN_NAME  = "{brain_name}"\n'
        f'Set-Location "{brain_dir}"\n'
    )

    # Windows PowerShell (5.x) profile location
    ps5_dir  = os.path.join(brain_home, 'Documents', 'WindowsPowerShell')
    # PowerShell Core (7.x) profile location
    ps7_dir  = os.path.join(brain_home, 'Documents', 'PowerShell')

    for profile_dir in (ps5_dir, ps7_dir):
        profile_path = os.path.join(profile_dir, 'Microsoft.PowerShell_profile.ps1')
        try:
            os.makedirs(profile_dir, exist_ok=True)
        except OSError as exc:
            warn(f'Could not create profile dir {profile_dir}: {exc}')
            continue
        _safe_write_profile(profile_path, content, brain_name)


def _safe_write_profile(path, content, brain_name):
    """Write profile content to path; warn on failure."""
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(content)
        info(f'Wrote shell profile: {path}')
    except OSError as exc:
        warn(f'Could not write shell profile {path}: {exc}')
        warn(f'  Add HORIZON_* exports and cd "{brain_name}_dir" manually.')


def _deploy_template(src, dest, substitutions):
    """Read src, apply substitutions, write to dest. Warns and returns on failure."""
    if not os.path.isfile(src):
        warn(f'Template not found: {src}')
        warn(f'  Skipping deployment of {os.path.basename(dest)}.')
        return
    try:
        with open(src, 'r', encoding='utf-8') as fh:
            content = fh.read()
        for placeholder, value in substitutions.items():
            content = content.replace(placeholder, value)
        with open(dest, 'w', encoding='utf-8') as fh:
            fh.write(content)
        info(f'Deployed: {dest}')
    except OSError as exc:
        warn(f'Could not write {dest}: {exc}')


def _write_provision_manifest(ctx):
    """Write .aios_provision.json to the brain directory for audit purposes."""
    brain_name   = ctx['brain_name']
    brain_dir    = ctx['brain_dir']
    horizon_root = ctx['horizon_root']

    manifest = {
        'brain_name':        brain_name,
        'provisioned_at':    datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'provisioned_by':    ctx['invoking_user'],
        'horizon_root':      horizon_root,
        'groups':            [BRAINS_GROUP, brain_name],
        'brain_dir':         brain_dir,
        'skills_bin_access': 'read+execute',
        'sbin_access':       'deny',
        'credential_store':  'OS native keystore (brain_credential.py)',
    }
    dest = os.path.join(brain_dir, '.aios_provision.json')
    try:
        with open(dest, 'w', encoding='utf-8') as fh:
            json.dump(manifest, fh, indent=2)
            fh.write('\n')
        info(f'Wrote provisioning manifest: {dest}')
    except OSError as exc:
        warn(f'Could not write provisioning manifest: {exc}')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description='Horizon AIOS — provision an OS user, groups, and folder for a new brain.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        'brain_name',
        help='Name for the new brain (must match ^[a-z][a-z0-9_]{1,31}$)',
    )
    parser.add_argument(
        '--horizon-root',
        metavar='PATH',
        default=None,
        help=(
            'Absolute path to HORIZON_ROOT.  '
            'If omitted, derived from ../../ relative to this script\'s location '
            '(i.e., the script is expected to live at '
            '$HORIZON_ROOT/horizon_system/scripts/create_brain.py).'
        ),
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Print every action that would be taken without executing anything.',
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.dry_run:
        print('\n  *** DRY-RUN MODE — no changes will be made ***\n')

    try:
        ctx = phase1_preflight(args)
    except SystemExit:
        raise
    except Exception as exc:
        error(f'Unexpected error in Phase 1: {exc}')
        sys.exit(1)

    try:
        phase2_create_user_and_groups(ctx, dry_run=args.dry_run)
    except subprocess.CalledProcessError as exc:
        error(f'Phase 2 failed: {exc}')
        error('User/group setup is incomplete.  Phase 3 (folders) will be skipped.')
        error('See cleanup instructions below.')
        _print_cleanup_instructions(
            ctx['brain_name'], ctx['brain_dir'], ctx['os_name']
        )
        sys.exit(2)
    except Exception as exc:
        error(f'Unexpected error in Phase 2: {exc}')
        sys.exit(2)

    try:
        phase3_folders_and_permissions(ctx, dry_run=args.dry_run)
    except subprocess.CalledProcessError as exc:
        error(f'Phase 3 failed: {exc}')
        error(
            'User and groups were created but folder/permission setup failed.\n'
            '  Phase 4 verification will still run to show partial state.'
        )
    except Exception as exc:
        error(f'Unexpected error in Phase 3: {exc}')

    try:
        success = phase4_verify(ctx, dry_run=args.dry_run)
    except Exception as exc:
        error(f'Unexpected error in Phase 4: {exc}')
        sys.exit(3)

    try:
        phase5_deploy_templates(ctx, dry_run=args.dry_run)
    except Exception as exc:
        warn(f'Phase 5 encountered an unexpected error: {exc}')
        warn('Brain is provisioned at the OS level. Deploy templates manually.')

    sys.exit(0 if success else 3)


if __name__ == '__main__':
    main()
