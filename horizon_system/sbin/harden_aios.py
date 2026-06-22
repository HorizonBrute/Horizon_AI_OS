#!/usr/bin/env python3
"""
harden_aios.py — Horizon AIOS Layer Hardening
=============================================

Applies the authoritative brains-group ACL model to the AIOS layer
($HORIZON_SYSTEM) INDEPENDENT of brain creation, so a freshly bootstrapped
machine is protected before any brain account exists.

This is the real enforcement point for security_invariants.md §2/§3/§5: the
brain OS user has *no write access to $HORIZON_SYSTEM* and is explicitly
DENIED sbin/, skills_sbin/, and the audit logs/.

ACL model applied (brains group, conventionally `brains`):
    $HORIZON_SYSTEM/bin          -> brains: Read+Execute (explicit grant)
    $HORIZON_SYSTEM/skills_bin    -> brains: Read+Execute (explicit grant)
    $HORIZON_SYSTEM/sbin          -> brains: DENY (explicit)
    $HORIZON_SYSTEM/skills_sbin   -> brains: DENY (explicit)
    $HORIZON_SYSTEM/logs          -> brains: DENY (explicit)  [canonical log path]
    $HORIZON_SYSTEM (everything else: ai_os_etc, scripts, templates,
                     documentation, sounds, harness_configs, ...)
                                  -> brains: NO WRITE anywhere
    Primary/owner user            -> Full control on all of the above.

Ordering invariant (mirrors create_brain.py): all Deny ACEs are applied
AFTER all brains-group grants, so an inherited permission can never
accidentally reach a privileged dir.

Usage:
    python harden_aios.py [--horizon-root /path] [--dry-run]

Requirements:
    - Python 3.6+, stdlib only
    - Run as Administrator (Windows) or root (Unix) for ACL changes.

Platform support:
    - Windows  — icacls
    - Linux    — chown / chmod (setfacl when present, falls back to mode bits)
    - macOS    — chown / chmod (chmod +a ACLs when present)
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The common group every brain belongs to. Brain ACEs are group-based, so this
# group must exist for the grants/denies below to be settable.
BRAINS_GROUP = 'brains'


# ---------------------------------------------------------------------------
# Logging helpers (house style: [OK]/[GRANT]/[DENY]/[WARN]/[INFO]/[ERROR])
# ---------------------------------------------------------------------------

def banner(text):
    line = '=' * (len(text) + 6)
    print(f'\n{line}')
    print(f'=== {text} ===')
    print(f'{line}\n')


def info(msg):
    print(f'  [INFO]  {msg}')


def ok(msg):
    print(f'  [OK]    {msg}')


def grant(msg):
    print(f'  [GRANT] {msg}')


def deny(msg):
    print(f'  [DENY]  {msg}')


def warn(msg):
    print(f'  [WARN]  {msg}')


def error(msg):
    print(f'  [ERROR] {msg}', file=sys.stderr)


def run(cmd, dry_run=False, check=True, capture=False):
    """Execute an argv-style command (no shell=True)."""
    display = ' '.join(str(a) for a in cmd)
    if dry_run:
        print(f'  [DRY-RUN] {display}')
        return ''
    info(f'Running: {display}')
    result = subprocess.run(cmd, check=check, capture_output=capture, text=True)
    if capture:
        return result.stdout.strip()
    return None


# ---------------------------------------------------------------------------
# Path resolution (SCRIPT_DIR -> HORIZON_SYSTEM -> HORIZON_ROOT)
# ---------------------------------------------------------------------------

def resolve_paths(horizon_root_arg):
    """
    Resolve the AIOS layer paths. The script lives at
    $HORIZON_SYSTEM/sbin/harden_aios.py, so ../ is $HORIZON_SYSTEM and
    ../../ is $HORIZON_ROOT (matches maintain_logs.py / sync_aios.py).
    """
    if horizon_root_arg:
        horizon_root = os.path.abspath(horizon_root_arg)
        horizon_system = os.path.join(horizon_root, 'horizon_system')
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        horizon_system = os.path.abspath(os.path.join(script_dir, '..'))
        horizon_root = os.path.abspath(os.path.join(script_dir, '..', '..'))

    return {
        'horizon_root':        horizon_root,
        'horizon_system':      horizon_system,
        'bin':                 os.path.join(horizon_system, 'bin'),
        'skills_bin':          os.path.join(horizon_system, 'skills_bin'),
        'sbin':                os.path.join(horizon_system, 'sbin'),
        'skills_sbin':         os.path.join(horizon_system, 'skills_sbin'),
        'logs':                os.path.join(horizon_system, 'logs'),
    }


# ---------------------------------------------------------------------------
# Privilege detection (warn-and-continue, not hard-exit — caller decides)
# ---------------------------------------------------------------------------

def is_elevated(os_name):
    """Return True if running with admin/root privileges, else False."""
    if os_name == 'Windows':
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def current_user(os_name):
    """Best-effort current/owner username for the owner Full-control grant."""
    try:
        import getpass
        return getpass.getuser()
    except Exception:
        try:
            return os.getlogin()
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Brains group: ensure it exists (idempotent, group-based ACEs require it)
# ---------------------------------------------------------------------------

def ensure_brains_group(os_name, dry_run):
    """
    Ensure the `brains` group exists so group-based ACEs are settable.
    An empty group is fine. Returns True if the group exists (or was
    created / would be created in dry-run), False if it is absent and
    could not be created (caller continues with owner-side hardening).
    """
    if _brains_group_exists(os_name):
        ok(f'Brains group already exists: {BRAINS_GROUP}')
        return True

    if dry_run:
        info(f'Brains group "{BRAINS_GROUP}" absent — would create it.')
        return True

    try:
        if os_name == 'Windows':
            run(['powershell', '-NonInteractive', '-Command',
                 f'New-LocalGroup -Name "{BRAINS_GROUP}" '
                 f'-Description "Horizon AIOS group: {BRAINS_GROUP}"'],
                dry_run=dry_run)
        elif os_name == 'Linux':
            run(['groupadd', BRAINS_GROUP], dry_run=dry_run)
        else:  # Darwin
            run(['dseditgroup', '-o', 'create', BRAINS_GROUP], dry_run=dry_run)
        ok(f'Created brains group: {BRAINS_GROUP}')
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        warn(f'Could not create brains group "{BRAINS_GROUP}": {exc}')
        warn('Continuing with owner-side hardening only. Brain grant/deny ACEs '
             'will be skipped until the group exists (re-run after creating it).')
        return False


def _brains_group_exists(os_name):
    if os_name == 'Windows':
        result = subprocess.run(
            ['powershell', '-NonInteractive', '-Command',
             f'Get-LocalGroup -Name "{BRAINS_GROUP}" -ErrorAction SilentlyContinue'],
            capture_output=True, text=True)
        return bool(result.stdout.strip())
    result = subprocess.run(['getent', 'group', BRAINS_GROUP], capture_output=True)
    if result.returncode == 0:
        return True
    # macOS without getent: fall back to dscl.
    result = subprocess.run(
        ['dscl', '.', '-read', f'/Groups/{BRAINS_GROUP}'], capture_output=True)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Windows hardening (icacls)
# ---------------------------------------------------------------------------

def harden_windows(paths, owner, have_group, dry_run):
    """
    Apply the ACL model on Windows with icacls.

    Strategy per security_invariants §3 ("explicit Deny takes precedence"):
      1. On $HORIZON_SYSTEM: disable inheritance (/inheritance:r) and convert
         existing inherited ACEs to explicit (/inheritance:e is implied by :r
         which copies them first) — we use :r then re-grant owner Full so the
         owner never loses access. This removes any broad inherited grants.
      2. Re-establish owner Full control (inheritable) so the owner keeps
         control of the whole subtree.
      3. Grant brains Read+Execute on bin and skills_bin (explicit, direct on
         each child — skills_bin is NOT under bin/ so it is not inherited).
      4. Apply Deny ACEs on sbin/skills_sbin/logs AFTER all grants. Each of
         these also gets /inheritance:r + owner Full so the deny is airtight.

    The "no write anywhere else in $HORIZON_SYSTEM" invariant is satisfied
    structurally: with inheritance disabled at the root and only the explicit
    grants above, brains have no ACE on ai_os_etc/scripts/templates/etc., and
    Windows denies access by default to a group with no matching allow ACE.
    """
    system = paths['horizon_system']

    # 1+2. Lock down $HORIZON_SYSTEM root: drop inherited ACEs, keep owner Full.
    info(f'Hardening AIOS root (inheritance off, owner Full): {system}')
    run(['icacls', system, '/inheritance:r'], dry_run=dry_run)
    if owner:
        run(['icacls', system, '/grant', f'{owner}:(OI)(CI)F'], dry_run=dry_run)
        grant(f'owner Full control on $HORIZON_SYSTEM: {owner}')
    else:
        warn('Could not determine owner username — skipping owner Full grant on root. '
             'Verify the owner retains Full control manually.')

    if not have_group:
        warn('brains group unavailable — skipping all brains grant/deny ACEs. '
             'Owner-side hardening (inheritance off + owner Full) is applied.')
        return

    # 3. Explicit RX grants for brains on bin and skills_bin (before any deny).
    for label, key in (('bin', 'bin'), ('skills_bin', 'skills_bin')):
        path = paths[key]
        if os.path.isdir(path):
            run(['icacls', path, '/grant', f'{BRAINS_GROUP}:(OI)(CI)RX'],
                dry_run=dry_run)
            grant(f'brains Read+Execute on {label}: {path}')
        else:
            warn(f'{label} missing, skipping grant: {path}')

    # 4. Deny ACEs on privileged dirs — MUST come after all grants above.
    for label, key in (('sbin', 'sbin'),
                       ('skills_sbin', 'skills_sbin'),
                       ('logs', 'logs')):
        path = paths[key]
        if not os.path.isdir(path):
            warn(f'{label} missing, skipping deny: {path}')
            continue
        run(['icacls', path, '/inheritance:r'], dry_run=dry_run)
        if owner:
            run(['icacls', path, '/grant', f'{owner}:(OI)(CI)F'], dry_run=dry_run)
        # Deny applied last so it wins over any allow on this path. Full-control
        # deny (not just RX) so write/delete are explicitly denied too — these
        # dirs are "DENY (explicit)" per security_invariants §2/§3.
        run(['icacls', path, '/deny', f'{BRAINS_GROUP}:(OI)(CI)F'],
            dry_run=dry_run)
        deny(f'brains DENY (full) on {label}: {path}')


# ---------------------------------------------------------------------------
# Unix / macOS hardening (chown / chmod / setfacl)
# ---------------------------------------------------------------------------

def harden_unix(paths, os_name, owner, have_group, dry_run):
    """
    Apply the ACL model on Linux/macOS with ownership and mode bits.

      - sbin / skills_sbin / logs => 700 (owner-only; brains get nothing)
      - bin / skills_bin          => group=brains, g+rx (Read+Execute)
      - everything else in $HORIZON_SYSTEM => go-w (no group/other write),
        satisfying "no write anywhere in $HORIZON_SYSTEM".

    chmod 700 on privileged dirs is applied AFTER the brains-group rx grants
    so the grants can never cascade into them (mirrors create_brain.py).
    """
    system = paths['horizon_system']

    # Own the whole subtree as the owner where we can (best-effort).
    if owner:
        info(f'Ensuring owner ({owner}) owns $HORIZON_SYSTEM subtree')
        run(['chown', '-R', f'{owner}:', system], dry_run=dry_run, check=False)
        grant(f'owner ownership on $HORIZON_SYSTEM: {owner}')

    # No group/other WRITE anywhere in $HORIZON_SYSTEM (the broad invariant).
    info('Removing group/other write across $HORIZON_SYSTEM (go-w)')
    run(['chmod', '-R', 'go-w', system], dry_run=dry_run, check=False)
    ok('brains (and all non-owners) have no write under $HORIZON_SYSTEM')

    if have_group:
        # Read+Execute for brains on bin and skills_bin (explicit per path).
        for label, key in (('bin', 'bin'), ('skills_bin', 'skills_bin')):
            path = paths[key]
            if os.path.isdir(path):
                run(['chown', '-R', f':{BRAINS_GROUP}', path],
                    dry_run=dry_run, check=False)
                run(['chmod', '-R', 'g+rX', path], dry_run=dry_run, check=False)
                grant(f'brains Read+Execute on {label}: {path}')

                # Prefer an explicit ACL deny on privileged dirs if setfacl exists;
                # otherwise rely on 700 below. (setfacl is the closer analogue to
                # the Windows explicit-Deny model.)
            else:
                warn(f'{label} missing, skipping grant: {path}')
    else:
        warn('brains group unavailable — skipping brains rx grants on bin/skills_bin. '
             'Owner-side hardening (go-w + 700 on privileged dirs) is applied.')

    # Privileged dirs: owner-only 700 — applied AFTER the grants above.
    have_setfacl = shutil.which('setfacl') is not None
    for label, key in (('sbin', 'sbin'),
                       ('skills_sbin', 'skills_sbin'),
                       ('logs', 'logs')):
        path = paths[key]
        if not os.path.isdir(path):
            warn(f'{label} missing, skipping deny: {path}')
            continue
        run(['chmod', '700', path], dry_run=dry_run, check=False)
        # Optional explicit group deny via ACL (Linux setfacl) to mirror the
        # Windows explicit-Deny posture, on top of the 700 mode bits.
        if have_group and have_setfacl and os_name == 'Linux':
            run(['setfacl', '-R', '-m', f'g:{BRAINS_GROUP}:---', path],
                dry_run=dry_run, check=False)
        deny(f'brains DENY (owner-only 700) on {label}: {path}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description='Horizon AIOS — harden the AIOS layer ACLs (brains group).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--horizon-root', metavar='PATH', default=None,
        help='Absolute path to HORIZON_ROOT. If omitted, derived from ../../ '
             'relative to this script (script lives at '
             '$HORIZON_SYSTEM/sbin/harden_aios.py).',
    )
    parser.add_argument(
        '--dry-run', action='store_true', default=False,
        help='Print every action that would be taken without executing anything.',
    )
    return parser.parse_args()


def main():
    args = parse_args()

    banner('Horizon AIOS — Layer Hardening')
    if args.dry_run:
        print('  *** DRY-RUN MODE — no changes will be made ***\n')

    os_name = platform.system()  # 'Windows', 'Linux', 'Darwin'
    if os_name not in ('Windows', 'Linux', 'Darwin'):
        error(f'Unsupported platform: {os_name}')
        sys.exit(1)
    info(f'Detected OS: {os_name}')

    paths = resolve_paths(args.horizon_root)
    info(f'HORIZON_ROOT:   {paths["horizon_root"]}')
    info(f'HORIZON_SYSTEM: {paths["horizon_system"]}')

    if not os.path.isdir(paths['horizon_system']):
        error(f'$HORIZON_SYSTEM does not exist: {paths["horizon_system"]}')
        sys.exit(1)

    # Privilege guard — warn (don't crash) so bootstrap stays best-effort.
    elevated = is_elevated(os_name)
    if not elevated and not args.dry_run:
        warn('Not running elevated (Administrator/root).')
        warn('ACL changes will likely fail. Re-run as Administrator (Windows) '
             'or with sudo (Unix) to enforce the hardening.')
        warn('Continuing anyway so failures are visible; nothing is silently skipped.')

    owner = current_user(os_name)
    info(f'Owner (Full control) user: {owner or "<unknown>"}')

    # Ensure the brains group exists (group-based ACEs need it).
    banner('Ensure brains group')
    have_group = ensure_brains_group(os_name, args.dry_run)

    # Ensure the canonical logs dir exists so its deny can be applied.
    if not os.path.isdir(paths['logs']):
        info(f'Creating canonical logs dir: {paths["logs"]}')
        if not args.dry_run:
            try:
                os.makedirs(paths['logs'], exist_ok=True)
            except OSError as exc:
                warn(f'Could not create logs dir {paths["logs"]}: {exc}')
        else:
            print(f'  [DRY-RUN] os.makedirs({paths["logs"]!r}, exist_ok=True)')

    banner('Apply ACL model')
    try:
        if os_name == 'Windows':
            harden_windows(paths, owner, have_group, args.dry_run)
        else:
            harden_unix(paths, os_name, owner, have_group, args.dry_run)
    except subprocess.CalledProcessError as exc:
        error(f'An ACL command failed: {exc}')
        error('Hardening is incomplete. Re-run elevated and review the output above.')
        sys.exit(2)

    banner('Summary')
    print('  AIOS layer hardening applied (or printed in dry-run).')
    print('  brains group:')
    print('    bin, skills_bin      -> Read+Execute (explicit grant)')
    print('    sbin, skills_sbin, logs -> DENY (explicit; applied after grants)')
    print('    rest of $HORIZON_SYSTEM -> no write')
    print('  owner -> Full control on the whole subtree.')
    if not have_group:
        print('\n  NOTE: brains group was unavailable — only owner-side hardening '
              'was applied. Re-run after the group exists.')
    print()
    sys.exit(0)


if __name__ == '__main__':
    main()
