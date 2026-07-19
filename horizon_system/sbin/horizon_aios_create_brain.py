#!/usr/bin/env python3
"""
horizon_aios_create_brain.py — Horizon AIOS Brain Provisioning Script
=========================================================

Creates and configures everything needed for a new AI brain:
  - OS user account  (<brain-name>)
  - Group: brains    (common AIOS group, grants horizon_system/bin rx)
  - Group: <brain-name>_group (brain-specific group on Windows) or <brain-name> (Linux/macOS)
                     — the per-brain RUNTIME group: the set of accounts that may run AS
                     the brain. On WINDOWS only brain-runner accounts join it (NOT the
                     human invoker), so the security model can deny that whole group
                     write on the brain's edit-source without catching the human — the
                     writer is never the runner (brain_security_model.md #2/#7). The human
                     keeps write via an explicit invoking-user ACE. On UNIX the human is
                     still a member (their 770 write path; no Unix edit-source lock yet).
  - Brain folder:    $HORIZON_ROOT/brains/<brain-name>/
  - Permissions:     Windows — full-control for the brain user + runtime group + the human
                     invoker (explicit ACE, independent of group); horizon_humans RX.
                     Unix — 770 owned brain:brain (human writes via runtime-group
                     membership); horizon_humans read-only via setfacl.
                     horizon_system/bin + skills_bin (group brains rx)
                     sbin/skills_sbin/logs locked to owner-only AFTER
                     all grants (security invariant)
  - Password:        stored in OS native keystore (Windows Credential Manager /
                     macOS Keychain / Linux Secret Service) via horizon_aios_brain_credential.py
  - Shell profile:   sets HORIZON_* env vars and cds to brain folder on
                     interactive login as the brain user

Usage:
    python horizon_aios_create_brain.py <brain-name> [--horizon-root /path] [--dry-run]

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
      the OS native keystore via horizon_aios_brain_credential.py (sbin/).
"""

import argparse
import datetime
import json
import os
import platform
import re
import secrets
import shutil
import stat
import subprocess
import sys

# Make stdout/stderr robust on legacy Windows code pages (e.g. cp1252) so the
# tool never crashes with UnicodeEncodeError on non-ASCII output. Self-healing
# regardless of PYTHONIOENCODING; guarded for Pythons without reconfigure().
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Optional credential store (horizon_aios_brain_credential.py in sbin/)
# ---------------------------------------------------------------------------

try:
    import sys as _sys
    import os as _os
    _sbin = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'sbin')
    _sys.path.insert(0, _sbin)
    from horizon_aios_brain_credential import store_password as _store_password
    _HAS_CRED_STORE = True
except Exception:
    _HAS_CRED_STORE = False

# Optional logon-rights helper (horizon_aios_brain_logon_rights.py in sbin/) — used only by
# the opt-in --automation tiers to grant a Windows logon right to the brain.
try:
    from horizon_aios_brain_logon_rights import (
        grant as _grant_logon_right,
        holds as _holds_logon_right,
        BATCH_LOGON,
        SERVICE_LOGON,
    )
    _HAS_LOGON_RIGHTS = True
except Exception:
    _HAS_LOGON_RIGHTS = False
    # Stable LSA right names — defined even when the helper is unavailable so the
    # automation tiers can still name the right in guidance messages.
    BATCH_LOGON = 'SeBatchLogonRight'
    SERVICE_LOGON = 'SeServiceLogonRight'


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Regex enforcing brain names: start with lowercase letter, then 1-19 chars
# of lowercase letters, digits, or underscores.  Total length: 2-20 chars.
# 20-char cap matches the Windows local user name limit.
BRAIN_NAME_RE = re.compile(r'^[a-z][a-z0-9_]{1,19}$')

# The common group that every brain belongs to.  Members of this group get
# read+execute on $HORIZON_BIN but are explicitly denied access to sbin.
BRAINS_GROUP = 'brains'

# The AIOS-managed group for flesh-and-blood human operators (see
# horizon_aios_harden.py). Brain folders are Read-Only to humans: brain
# locations are for brains — to write into one a human elevates to admin or
# changes permissions. The brain folder has its inheritance stripped below, so
# the humans grant must be applied EXPLICITLY here (the tree-level humans Full
# from harden does not reach a broken-inheritance child).
HUMANS_GROUP = 'horizon_humans'


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
            '  Must match ^[a-z][a-z0-9_]{{1,19}}$ '
            '(start with lowercase letter, then 1-19 lowercase letters/digits/underscores; max 20 chars)'
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
        # Script lives at $HORIZON_ROOT/horizon_system/sbin/horizon_aios_create_brain.py
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
    logs_dir            = os.path.join(horizon_system, 'logs')

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
    info(f'Invoking user (Windows: explicit Full ACE, NOT in the runtime group; '
         f'Unix: member of the runtime group for 770 write): {invoking_user}')

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
                '  Re-run with: sudo python horizon_aios_create_brain.py <brain-name>'
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
    info('  Password will NOT be printed here. Retrieve with: horizon_aios_brain_credential.py get <name>')

    if os_name == 'Windows':
        _phase2_windows(brain_name, invoking_user, password, dry_run)
    else:
        _phase2_unix(brain_name, invoking_user, os_name, password, dry_run)

    if _HAS_CRED_STORE:
        if _store_password(brain_name, password):
            info('Account password stored in OS keystore (keyring). Retrieve with: horizon_aios_brain_credential.py get <name>')
        else:
            warn('Password not stored in keystore — reset manually if needed for runas/Task Scheduler.')
    else:
        warn('brain_credential module not found in sbin/ — password not stored. Reset manually if needed.')


# ---- Windows implementation ----

def _phase2_windows(brain_name, invoking_user, password, dry_run):
    """Windows: use PowerShell Local* cmdlets.

    Windows' SAM shares a single namespace for local users and groups, so a
    group named after the brain would collide with the brain user account.
    Fix: use <brain-name>_group as the per-brain group name on Windows.
    """
    brain_group = f'{brain_name}_group'

    _win_create_group_if_absent(BRAINS_GROUP, dry_run)
    _win_create_group_if_absent(brain_group, dry_run)

    info(f'Creating local user: {brain_name}')
    # Pass the password via an environment variable rather than interpolating it
    # into the command string. This avoids any quoting/injection fragility and
    # keeps the secret out of process command lines and the run_ps echo/log.
    _win_create_user_with_password(brain_name, password, dry_run)

    info(f'Adding {brain_name} to group: {BRAINS_GROUP}')
    run_ps(
        f'Add-LocalGroupMember -Group "{BRAINS_GROUP}" -Member "{brain_name}"',
        dry_run=dry_run,
    )

    info(f'Adding {brain_name} to group: {brain_group}')
    run_ps(
        f'Add-LocalGroupMember -Group "{brain_group}" -Member "{brain_name}"',
        dry_run=dry_run,
    )

    # The human invoker is deliberately NOT added to the runtime group. <brain>_group
    # means "runs as the brain", and the security model denies that group write on the
    # brain's edit-source (code + policy). The human keeps folder access via an explicit
    # invoking-user Full ACE granted in phase 3 — independent of the group — so the
    # writer≠runner split holds (brain_security_model.md #2/#7).


def _win_create_user_with_password(brain_name, password, dry_run):
    """Create a Windows local user, passing the password via an env var.

    The password is supplied to the child process through the environment
    (AIOS_BRAIN_PW) and read inside PowerShell as $env:AIOS_BRAIN_PW. It is
    never interpolated into the command string, so it cannot break PowerShell
    quoting and is never written to the run_ps "Running:" echo or any log.
    """
    ps_expr = (
        '$pw = ConvertTo-SecureString $env:AIOS_BRAIN_PW -AsPlainText -Force; '
        f'New-LocalUser -Name "{brain_name}" -Password $pw '
        f'-FullName "{brain_name} (Horizon.AIOS Brain)" '
        '-Description "Horizon.AIOS brain account" '
        '-PasswordNeverExpires'
    )
    cmd = ['powershell', '-NonInteractive', '-Command', ps_expr]
    if dry_run:
        # Do not echo the password; it is supplied via env at run time.
        print(f'  [DRY-RUN] {" ".join(cmd)}  (password via $env:AIOS_BRAIN_PW)')
        return
    info(f'Running: {" ".join(cmd)}  (password via $env:AIOS_BRAIN_PW)')
    child_env = dict(os.environ, AIOS_BRAIN_PW=password)
    subprocess.run(cmd, check=True, env=child_env)


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
        f'New-LocalGroup -Name "{group_name}" -Description "H.AIOS group: {group_name}"',
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
             '--comment', 'Horizon.AIOS brain account',
             '--no-user-group',
             '--gid', brain_name,
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

    # NOTE (writer≠runner, Unix): on Windows the human invoker is deliberately NOT a
    # member of the runtime group (<brain>_group) — the edit-source lock denies that
    # group write, and the human keeps write via an explicit invoking-user ACE. On Unix
    # the human's WRITE path to the 770 brain folder is *this* group membership (there is
    # no per-user ACE), and there is no Unix edit-source lock yet — so removing it here
    # would only regress the human to read-only for no security gain. Keep it until a
    # Unix edit-source lock lands; at that point switch to an explicit
    # `setfacl u:{invoking_user}:rwX` grant here and drop this membership together.
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
        ['dscl', '.', '-create',   base, 'RealName',     f'{brain_name} (Horizon.AIOS Brain)'],
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
    Create folders and set all permissions per security_architecture_invariants.md §2 table.

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

    No-regression guard: this function only ADDS ACEs on the brain folder and
    the shared bin/skills_bin/sbin/skills_sbin/logs dirs. It never touches
    $HORIZON_ROOT inheritance and never re-grants Authenticated Users, so it
    cannot re-open the human-side write hole that horizon_aios_harden.py closed
    by breaking root inheritance.
    """

    # -- Brain folder: isolate it (drop inherited ACEs) but never strip the
    #    principals that must retain control. Well-known SIDs are locale-safe:
    #    *S-1-5-18 = SYSTEM, *S-1-5-32-544 = BUILTIN\Administrators.
    brain_group = f'{brain_name}_group'
    info(f'Setting ACLs on brain folder: {brain_dir}')
    run(['icacls', brain_dir,
         '/inheritance:r',
         '/grant', f'{brain_name}:(OI)(CI)F',
         '/grant', f'{brain_group}:(OI)(CI)F',
         '/grant', f'{invoking_user}:(OI)(CI)F',
         '/grant', '*S-1-5-18:(OI)(CI)F',
         '/grant', '*S-1-5-32-544:(OI)(CI)F'],
        dry_run=dry_run)

    # -- Human operators: Read-Only on this brain folder (inheritance is
    #    stripped above, so the tree-level humans Full does not reach here; grant
    #    RX explicitly). To write, a human elevates to admin (Administrators keep
    #    F above) or changes permissions. Mirrors the harden brains/ read-only. --
    info(f'Granting {HUMANS_GROUP} Read-Only on brain folder: {brain_dir}')
    run(['icacls', brain_dir,
         '/grant', f'{HUMANS_GROUP}:(OI)(CI)RX'],
        dry_run=dry_run, check=False)

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
    # Additive: add the full Deny without stripping inheritance, so SYSTEM /
    # Administrators / owner (and any infra-pushed ACLs) on these shared dirs
    # are preserved. This mirrors horizon_aios_harden.py's default mode — the two must
    # agree, since harden_aios may have already set these dirs and create_brain
    # re-touches them per brain. (harden_aios --strict owns inheritance strips.)
    for label, path in [('sbin', horizon_sbin),
                        ('skills_sbin', horizon_skills_sbin),
                        ('logs', logs_dir)]:
        if os.path.isdir(path):
            info(f'Denying brains group on {label}: {path}')
            run(['icacls', path,
                 '/deny',  f'{BRAINS_GROUP}:(OI)(CI)F'],
                dry_run=dry_run)

    # NOTE: the brain's ~/.claude layout (workspace-canonical config + skills
    # symlink, with the home ~/.claude redirecting to it) is set up in Phase 5
    # by _link_brain_claude(), after the workspace .claude/ and its templates
    # exist. Phase 3 only sets ACLs here.


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

    # -- Human operators: Read-Only on this brain folder (setfacl where
    #    available). Mirrors the Windows humans RX grant / harden brains/
    #    read-only. To write, a human uses the OS/identity tooling or elevates. --
    import shutil as _shutil
    if _shutil.which('setfacl') is not None:
        info(f'Granting {HUMANS_GROUP} Read-Only on brain folder: {brain_dir}')
        run(['setfacl', '-R', '-m', f'g:{HUMANS_GROUP}:r-x', brain_dir],
            dry_run=dry_run, check=False)
        run(['setfacl', '-R', '-d', '-m', f'g:{HUMANS_GROUP}:r-x', brain_dir],
            dry_run=dry_run, check=False)

    # -- bin: set brains group and grant rx --
    info(f'Setting bin group to "{BRAINS_GROUP}" and granting rx')
    run(['chown', f':{BRAINS_GROUP}', horizon_bin], dry_run=dry_run)
    run(['chmod', 'g+rx', horizon_bin], dry_run=dry_run)

    # -- skills_bin: explicit grant (not under bin/, so not inherited) --
    info(f'Setting skills_bin group to "{BRAINS_GROUP}" and granting rx')
    run(['chown', f':{BRAINS_GROUP}', horizon_skills_bin], dry_run=dry_run)
    run(['chmod', 'g+rx', horizon_skills_bin], dry_run=dry_run)

    # NOTE: the brain's ~/.claude layout (workspace-canonical config + skills
    # symlink, with the home ~/.claude redirecting to it) is set up in Phase 5
    # by _link_brain_claude(), after the workspace .claude/ exists.

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

    # Per-brain group: <brain-name>_group on Windows, <brain-name> on Unix.
    if os_name == 'Windows':
        brain_group = f'{brain_name}_group'
        results['in_brain_group'] = _check_group_membership(brain_name, brain_group, os_name)
        _report_check(f'User in "{brain_group}" group', results['in_brain_group'])
    else:
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
    print(f'       $HORIZON_ROOT/brains/{brain_name}/brain_core.md        (fill in [BRAIN_DESCRIPTION] / role / knowledge)')
    print(f'       $HORIZON_ROOT/brains/{brain_name}/brain_invariants.md  (brain-specific invariants)')
    print(f'       $HORIZON_ROOT/brains/{brain_name}/.aioscommon/local.agent_teams.md')
    print(f'       $HORIZON_ROOT/brains/{brain_name}/.claude/settings.local.json')
    print(f'    3. Provision tools from $HORIZON_USRBIN into the brain folder as needed.')
    print(f'    4. Retrieve account password: python horizon_aios_brain_credential.py get {brain_name} --show')
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
        # Get-LocalGroupMember returns each member's .Name fully qualified
        # (e.g. "COMPUTERNAME\testbrain"), so strip the domain/machine prefix
        # before comparing — a bare "-contains <user>" never matches.
        result = subprocess.run(
            ['powershell', '-NonInteractive', '-Command',
             f'((Get-LocalGroupMember -Group "{group}" -ErrorAction SilentlyContinue)'
             f'.Name -replace ".*\\\\","") -contains "{user}"'],
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
    print(f'    Easiest: python horizon_aios_remove_brain.py {brain_name} --yes')
    print('    Or manually:')
    if os_name == 'Windows':
        print(f'    Remove-LocalUser   -Name "{brain_name}"')
        print(f'    Remove-LocalGroup  -Name "{brain_name}_group"')
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

def _link_brain_claude(ctx, dry_run=False):
    """
    GAP 1 — unify the brain's .claude in its WORKSPACE, with the brain's HOME
    ~/.claude redirecting to it, so the brain's CLAUDE.md, settings.json, and
    skills are all surfaced at the user-level ~/.claude regardless of cwd:

        brains/<name>/.claude/skills  ->  $HORIZON_SYSTEM/skills_bin   (directory symlink)
        <brain-home>/.claude          ->  brains/<name>/.claude/       (directory symlink)

    Always skills_bin (brain tier), never skills_sbin. Idempotent: an existing
    correct link is replaced safely; symlinks are deleted as reparse
    points (rmdir / unlink) so a wrong link never has its TARGET followed.
    """
    os_name            = ctx['os_name']
    brain_name         = ctx['brain_name']
    brain_dir          = ctx['brain_dir']
    horizon_skills_bin = ctx['horizon_skills_bin']
    brain_claude_dir   = os.path.join(brain_dir, '.claude')
    workspace_skills   = os.path.join(brain_claude_dir, 'skills')

    if os_name == 'Windows':
        system_drive = os.environ.get('SystemDrive', 'C:')
        brain_home   = os.path.join(system_drive + '\\', 'Users', brain_name)
        home_claude  = os.path.join(brain_home, '.claude')

        # 1. workspace skills symlink -> skills_bin (brain tier)
        info(f'Linking workspace skills -> skills_bin: {workspace_skills}')
        if (not dry_run) and (os.path.exists(workspace_skills) or os.path.islink(workspace_skills)):
            run(['cmd', '/c', 'rmdir', workspace_skills], dry_run=False, check=False)
        run(['cmd', '/c', 'mklink', '/D', workspace_skills, horizon_skills_bin], dry_run=dry_run)

        # 2. home ~/.claude symlink -> workspace .claude (profile root may not
        #    exist before first logon, so create it first)
        info(f'Redirecting brain home ~/.claude -> {brain_claude_dir}')
        if not dry_run:
            os.makedirs(brain_home, exist_ok=True)
        else:
            print(f'  [DRY-RUN] os.makedirs({brain_home!r}, exist_ok=True)')
        if (not dry_run) and (os.path.exists(home_claude) or os.path.islink(home_claude)):
            # reparse-point delete: removes a symlink (or empty dir) WITHOUT
            # following it; a real, non-empty ~/.claude makes this fail safely.
            run(['cmd', '/c', 'rmdir', home_claude], dry_run=False, check=False)
        run(['cmd', '/c', 'mklink', '/D', home_claude, brain_claude_dir], dry_run=dry_run)

    else:
        try:
            import pwd as _pwd
            brain_home = _pwd.getpwnam(brain_name).pw_dir
        except (KeyError, ImportError):
            brain_home = f'/Users/{brain_name}' if os_name == 'Darwin' else f'/home/{brain_name}'
        home_claude = os.path.join(brain_home, '.claude')

        # 1. workspace skills symlink -> skills_bin (brain tier)
        info(f'Linking workspace skills -> skills_bin: {workspace_skills}')
        run(['ln', '-sfn', horizon_skills_bin, workspace_skills], dry_run=dry_run)
        run(['chown', '-h', f'{brain_name}:{brain_name}', workspace_skills], dry_run=dry_run, check=False)

        # 2. home ~/.claude symlink -> workspace .claude (ln -sfn replaces an
        #    existing symlink atomically; never recurse into a real dir)
        info(f'Redirecting brain home ~/.claude -> {brain_claude_dir}')
        run(['mkdir', '-p', brain_home], dry_run=dry_run, check=False)
        if (not dry_run) and os.path.islink(home_claude):
            run(['rm', '-f', home_claude], dry_run=False, check=False)
        run(['ln', '-sfn', brain_claude_dir, home_claude], dry_run=dry_run)
        run(['chown', '-h', f'{brain_name}:{brain_name}', home_claude], dry_run=dry_run, check=False)


def phase5_deploy_templates(ctx, dry_run=False):
    """
    Deploy .aioscommon templates into the brain's workspace, write the brain
    user's shell profile (sets HORIZON_* env vars and default working
    directory), and write a machine-readable provisioning manifest.

    Brain config lives in the WORKSPACE ROOT (loaded from cwd = brain root);
    .aioscommon/ holds local overrides + reference settings; .claude/ holds only
    the harness-local settings and the skills symlink. Creates:

        brains/<brain_name>/CLAUDE.md                        (from brain_CLAUDE.md.template)
        brains/<brain_name>/agents.md                        (from brain_agents.md.template)
        brains/<brain_name>/brain_core.md                    (from brain_core.md.template)
        brains/<brain_name>/brain_invariants.md              (from brain_invariants.md.template)
        brains/<brain_name>/.aioscommon/settings.json        (from brain_settings.json.template)
        brains/<brain_name>/.aioscommon/local.agent_teams.md (from brain_local.agent_teams.md.template)
        brains/<brain_name>/.aioscommon/agents.local.md      (empty local override)
        brains/<brain_name>/.aioscommon/.gitkeep             (empty)
        brains/<brain_name>/.claude/settings.local.json      (from brain_settings.local.json.template)
        brains/<brain_name>/.claude/skills          (directory symlink -> skills_bin)
        <brain_home>/.claude                        (directory symlink -> brains/<brain_name>/.claude)
        brains/<brain_name>/.aios_provision.json    (provisioning record for auditors)
        <brain_home>/.bashrc (Linux) / .zshrc+.bash_profile (macOS) /
            Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1 (Windows)
            — sets HORIZON_* env vars and cd's to brain folder on interactive login

    Every deployed text file has [BRAIN_NAME] and [HORIZON_ROOT_PATH] resolved
    ([HORIZON_ROOT_PATH] -> the portable "$HORIZON_ROOT" env-var token, not a
    hardcoded path); [BRAIN_DESCRIPTION] is left for the operator to fill in.

    Non-fatal: if templates are missing or file writes fail, a warning is
    printed and provisioning continues.  OS-level setup from Phases 1-3 is
    complete regardless of whether this phase succeeds.
    """
    banner('Phase 5: Deploy Brain Workspace Templates and Shell Profile')

    brain_name   = ctx['brain_name']
    brain_dir    = ctx['brain_dir']
    horizon_root = ctx['horizon_root']

    aioscommon_src   = os.path.join(horizon_root, 'brains', '.aioscommon')
    brain_aioscommon = os.path.join(brain_dir, '.aioscommon')
    brain_claude_dir = os.path.join(brain_dir, '.claude')

    # Placeholders resolved in every deployed file. [HORIZON_ROOT_PATH] -> the
    # "$HORIZON_ROOT" env-var token (portable, not a hardcoded absolute path);
    # [BRAIN_DESCRIPTION] is intentionally left for the operator to fill in.
    subs = {
        '[BRAIN_NAME]':        brain_name,
        '[HORIZON_ROOT_PATH]': '$HORIZON_ROOT',
    }

    if dry_run:
        print(f'  [DRY-RUN] Would create {brain_aioscommon} and {brain_claude_dir}')
        print(f'  [DRY-RUN] Would deploy CLAUDE.md, agents.md, brain_core.md, brain_invariants.md to {brain_dir}')
        print(f'  [DRY-RUN] Would deploy settings.json, local.agent_teams.md, agents.local.md to {brain_aioscommon}')
        print(f'  [DRY-RUN] Would deploy settings.local.json to {brain_claude_dir}')
        _link_brain_claude(ctx, dry_run=True)
        print(f'  [DRY-RUN] Would write .aios_provision.json to {brain_dir}')
        print(f'  [DRY-RUN] Would write shell profile for {brain_name}')
        return

    # 5.1 Create workspace subdirectories (.aioscommon/ and .claude/)
    for d in (brain_aioscommon, brain_claude_dir):
        try:
            os.makedirs(d, exist_ok=True)
            info(f'Created: {d}')
        except OSError as exc:
            warn(f'Could not create {d}: {exc}')
            warn('Skipping template deployment — create the directory manually.')
            return

    # 5.2 Brain-root config (workspace-canonical: loaded from cwd = brain root)
    for tmpl, dest in (
        ('brain_CLAUDE.md.template',     'CLAUDE.md'),
        ('brain_agents.md.template',     'agents.md'),
        ('brain_core.md.template',       'brain_core.md'),
        ('brain_invariants.md.template', 'brain_invariants.md'),
    ):
        _deploy_template(
            src=os.path.join(aioscommon_src, tmpl),
            dest=os.path.join(brain_dir, dest),
            substitutions=subs,
        )

    # 5.3 .aioscommon/ — local overrides + reference settings
    _deploy_template(
        src=os.path.join(aioscommon_src, 'brain_settings.json.template'),
        dest=os.path.join(brain_aioscommon, 'settings.json'),
        substitutions=subs,
    )
    _deploy_template(
        src=os.path.join(aioscommon_src, 'brain_local.agent_teams.md.template'),
        dest=os.path.join(brain_aioscommon, 'local.agent_teams.md'),
        substitutions=subs,
    )
    # Empty local-override files the brain config @-imports (operator fills as needed).
    for empty in ('agents.local.md', '.gitkeep'):
        _touch_empty(os.path.join(brain_aioscommon, empty))

    # 5.4 .claude/ — harness-local settings (resolved values, not placeholders)
    _deploy_template(
        src=os.path.join(aioscommon_src, 'brain_settings.local.json.template'),
        dest=os.path.join(brain_claude_dir, 'settings.local.json'),
        substitutions=subs,
    )

    # 5.5 Unify the brain's .claude: workspace skills symlink + home redirect
    #     (GAP 1 — must run after the workspace .claude/ exists)
    _link_brain_claude(ctx, dry_run=False)

    # 5.6 Write shell profile (sets HORIZON_* env vars + default working dir)
    _write_brain_shell_profile(ctx)

    # 5.7 Write provisioning manifest
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


def _brain_profile_content_posix(brain_name, horizon_root, brain_dir, brain_home):
    """Return the POSIX shell profile content for a brain user."""
    horizon_system = os.path.join(horizon_root, 'horizon_system')
    horizon_bin    = os.path.join(horizon_system, 'bin')
    horizon_etc    = os.path.join(horizon_system, 'ai_os_etc')
    horizon_docs   = os.path.join(horizon_system, 'documentation')
    horizon_sounds = os.path.join(horizon_system, 'sounds')
    horizon_logs   = os.path.join(horizon_system, 'logs')
    horizon_usrbin = os.path.join(horizon_root, 'usrbin')
    return (
        f'# Horizon AIOS — brain environment for {brain_name}\n'
        f'export HORIZON_ROOT="{horizon_root}"\n'
        f'export HORIZON_SYSTEM="{horizon_system}"\n'
        f'export HORIZON_BIN="{horizon_bin}"\n'
        f'export HORIZON_ETC="{horizon_etc}"\n'
        f'export HORIZON_DOCS="{horizon_docs}"\n'
        f'export HORIZON_SOUNDS="{horizon_sounds}"\n'
        f'export HORIZON_LOGS="{horizon_logs}"\n'
        f'export HORIZON_USRBIN="{horizon_usrbin}"\n'
        f'export HORIZON_BRAIN_NAME="{brain_name}"\n'
        f'export HORIZON_BRAIN_HOME="{brain_home}"\n'
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
    content = _brain_profile_content_posix(brain_name, horizon_root, brain_dir, brain_home)
    _safe_write_profile(profile_path, content, brain_name)


def _write_brain_profile_macos(brain_name, horizon_root, brain_dir):
    """Write ~/.zshrc and ~/.bash_profile for the brain user on macOS."""
    brain_home = f'/Users/{brain_name}'
    content = _brain_profile_content_posix(brain_name, horizon_root, brain_dir, brain_home)

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
    horizon_sounds = os.path.join(horizon_system, 'sounds')
    horizon_logs   = os.path.join(horizon_system, 'logs')
    horizon_usrbin = os.path.join(horizon_root, 'usrbin')

    content = (
        f'# Horizon AIOS — brain environment for {brain_name}\n'
        f'$env:HORIZON_ROOT        = "{horizon_root}"\n'
        f'$env:HORIZON_SYSTEM      = "{horizon_system}"\n'
        f'$env:HORIZON_BIN         = "{horizon_bin}"\n'
        f'$env:HORIZON_ETC         = "{horizon_etc}"\n'
        f'$env:HORIZON_DOCS        = "{horizon_docs}"\n'
        f'$env:HORIZON_SOUNDS      = "{horizon_sounds}"\n'
        f'$env:HORIZON_LOGS        = "{horizon_logs}"\n'
        f'$env:HORIZON_USRBIN      = "{horizon_usrbin}"\n'
        f'$env:HORIZON_BRAIN_NAME  = "{brain_name}"\n'
        f'$env:HORIZON_BRAIN_HOME  = "{brain_home}"\n'
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
    """Write profile content to path, then chown to the brain user (Unix only)."""
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(content)
        info(f'Wrote shell profile: {path}')
    except OSError as exc:
        warn(f'Could not write shell profile {path}: {exc}')
        warn(f'  Add HORIZON_* exports and cd "{brain_name}_dir" manually.')
        return

    # Unix only — transfer ownership to the brain user so the profile is
    # readable/writable by that account and not root-owned.
    if platform.system() != 'Windows':
        import pwd
        try:
            pw = pwd.getpwnam(brain_name)
            os.chown(path, pw.pw_uid, pw.pw_gid)
        except (KeyError, OSError) as e:
            warn(f'Could not chown {path} to {brain_name}: {e}')


def _touch_empty(path):
    """Create an empty file if it does not already exist (preserves existing content)."""
    if os.path.exists(path):
        return
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('')
        info(f'Created: {path}')
    except OSError as exc:
        warn(f'Could not create {path}: {exc}')


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

    # Per-brain group name differs by platform (Windows shares user/group namespace).
    brain_group = f'{brain_name}_group' if ctx['os_name'] == 'Windows' else brain_name
    manifest = {
        'brain_name':        brain_name,
        'provisioned_at':    datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'provisioned_by':    ctx['invoking_user'],
        'horizon_root':      horizon_root,
        'groups':            [BRAINS_GROUP, brain_group],
        'brain_dir':         brain_dir,
        'skills_bin_access': 'read+execute',
        'sbin_access':       'deny',
        'credential_store':  'OS native keystore (horizon_aios_brain_credential.py)',
        'automation':        ctx.get('automation', 'none'),
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
# Automation: opt-in logon rights
# ---------------------------------------------------------------------------

def apply_automation(ctx, dry_run=False):
    """
    Apply the OS capability required by the chosen automation tier.

    'none'      — no-op (default; interactive/manual use only).
    'scheduled' — Windows: grant SeBatchLogonRight ("Log on as a batch job") so the
                  brain can be a Task Scheduler principal ("Run whether user is
                  logged on or not"). Unix: enable systemd lingering so the brain's
                  user services run without an active login; print unit/cron guidance.
    'daemon'    — Windows: grant SeServiceLogonRight ("Log on as a service") so the
                  brain can be a Windows service account. Unix: print system-service
                  guidance (a system unit running as the brain needs no per-account
                  right or lingering).

    In all cases the *job/unit/service itself* is harness-specific and is left to
    the operator — like the Task Scheduler task on Windows. This step only grants
    the underlying capability.

    Best-effort and warn-only: a failure here never aborts provisioning — the brain
    is fully usable interactively and the capability can be granted later.
    """
    level = ctx.get('automation', 'none')
    if level == 'none':
        return

    banner('Automation: Logon Rights')
    os_name = ctx['os_name']
    brain   = ctx['brain_name']

    if os_name == 'Windows':
        _automation_windows(level, brain, dry_run)
    else:
        _automation_unix(level, brain, os_name, dry_run)


# Per-tier Windows logon right: (LSA constant, human label).
_WIN_AUTOMATION_RIGHT = {
    'scheduled': (BATCH_LOGON,   'Log on as a batch job'),
    'daemon':    (SERVICE_LOGON, 'Log on as a service'),
}


def _automation_windows(level, brain, dry_run):
    """Grant + verify the single logon right for the chosen tier on Windows."""
    right, label = _WIN_AUTOMATION_RIGHT[level]

    if dry_run:
        print(f'  [DRY-RUN] grant {right} ("{label}") to {brain}')
        return
    if not _HAS_LOGON_RIGHTS:
        warn(f'brain_logon_rights module unavailable — grant "{label}" to "{brain}" '
             'manually (secpol.msc → Local Policies → User Rights Assignment).')
        return

    info(f'Granting "{label}" ({right}) to {brain}')
    granted, detail = _grant_logon_right(brain, right)
    if not granted:
        warn(f'Could not grant {right}: {detail}')
        warn('  Grant it manually via secpol.msc if this automation tier is needed.')
        return
    if _holds_logon_right(brain, right):
        _report_check(f'{brain} holds "{label}"', True)
    else:
        warn(f'Grant returned OK but verification does not show {right} — inspect '
             f'with: horizon_aios_brain_logon_rights.py check {brain} --right {right}')

    if level == 'scheduled':
        info('Brain can now be the principal of a Task Scheduler task set to')
        info('  "Run whether user is logged on or not" (use the keystore password:')
        info(f'  python horizon_aios_brain_credential.py get {brain} --show).')
    else:  # daemon
        info('Brain can now be the logon account of a Windows service — register one')
        info('  with New-Service / sc.exe using the keystore password:')
        info(f'  python horizon_aios_brain_credential.py get {brain} --show.')


def _linger_enabled(brain):
    """Return True if systemd per-user lingering is enabled for *brain*."""
    try:
        r = subprocess.run(
            ['loginctl', 'show-user', brain, '--property=Linger'],
            capture_output=True, text=True,
        )
        return 'Linger=yes' in (r.stdout or '')
    except Exception:
        return False


def _automation_unix(level, brain, os_name, dry_run):
    """Apply the Unix analog of the chosen tier.

    scheduled → enable systemd lingering (the account-level capability), then
                guide the operator to the unit/crontab.
    daemon    → guidance only: a *system* service running as the brain needs no
                per-account right or lingering; the unit is the deliverable.
    """
    if level == 'scheduled':
        have_loginctl = shutil.which('loginctl') is not None
        if os_name == 'Linux' and have_loginctl:
            if dry_run:
                print(f'  [DRY-RUN] loginctl enable-linger {brain}')
            else:
                info(f'Enabling systemd lingering (run user services without login): {brain}')
                run(['loginctl', 'enable-linger', brain], check=False)
                if _linger_enabled(brain):
                    _report_check(f'lingering enabled for {brain}', True)
                else:
                    warn('enable-linger did not take — enable manually: '
                         f'loginctl enable-linger {brain}')
        else:
            info('systemd loginctl not available — enable lingering manually if needed:')
            info(f'  loginctl enable-linger {brain}')
        info('Then schedule the harness as the brain:')
        info(f'  systemd:  a "systemd --user" unit owned by {brain}, or')
        info(f'  cron:     crontab -u {brain} -e')
    else:  # daemon
        info('Daemon tier on Unix needs no per-account right — register a system service:')
        info(f'  Linux:  a systemd unit with [Service] User={brain} (system, not --user)')
        info(f'  macOS:  a launchd LaunchDaemon with UserName {brain}')


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
        help='Name for the new brain (must match ^[a-z][a-z0-9_]{1,19}$; max 20 chars)',
    )
    parser.add_argument(
        '--horizon-root',
        metavar='PATH',
        default=None,
        help=(
            'Absolute path to HORIZON_ROOT.  '
            'If omitted, derived from ../../ relative to this script\'s location '
            '(i.e., the script is expected to live at '
            '$HORIZON_ROOT/horizon_system/sbin/horizon_aios_create_brain.py).'
        ),
    )
    parser.add_argument(
        '--automation',
        choices=['none', 'scheduled', 'daemon'],
        default='none',
        help=(
            'Opt-in automation profile (default: none). '
            '"scheduled" — Windows: grant "Log on as a batch job" (SeBatchLogonRight) '
            'for Task Scheduler "Run whether user is logged on or not"; Unix: enable '
            'systemd lingering so user services run without a login. '
            '"daemon" — Windows: grant "Log on as a service" (SeServiceLogonRight) so '
            'the brain can be a Windows service account; Unix: print system-service '
            'guidance (no per-account right needed). '
            '"none" grants no logon rights (interactive/manual use only).'
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

    # Carry the chosen automation tier through to the rights step and manifest.
    ctx['automation'] = args.automation

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
        apply_automation(ctx, dry_run=args.dry_run)
    except Exception as exc:
        warn(f'Automation logon-rights step failed: {exc}')
        warn('Brain is provisioned; grant the logon right manually if needed.')

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
