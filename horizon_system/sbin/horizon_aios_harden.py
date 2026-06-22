#!/usr/bin/env python3
"""
horizon_aios_harden.py — Horizon AIOS Layer Hardening
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
    $HORIZON_SYSTEM/sbin          -> brains: DENY (explicit, full)
    $HORIZON_SYSTEM/skills_sbin   -> brains: DENY (explicit, full)
    $HORIZON_SYSTEM/logs          -> brains: DENY (explicit, full)  [canonical log path]
    $HORIZON_SYSTEM (everything else: ai_os_etc, scripts, templates,
                     documentation, sounds, harness_configs, ...)
                                  -> brains: NO WRITE anywhere (inheritable
                                     Deny-Write; reads stay allowed)
    owner + SYSTEM + Administrators -> Full control, always preserved.

Two modes (Windows):
    additive (default) -- Preserve all existing/inherited ACLs (GPO/SCCM/Intune
        pushes, SYSTEM, Administrators). Enforce the brains model purely by
        ADDING ACEs: an inheritable brains Deny-Write at the root (an
        explicit/inherited Deny beats any Allow, so this holds even under broad
        infra grants) plus full Deny on the privileged dirs. Nothing is
        stripped. This is the right default for managed machines AND home boxes.
    --strict -- Additionally drop inherited ACEs (/inheritance:r) at the root
        and on each privileged dir, re-establishing owner + SYSTEM +
        Administrators first. For locked-down standalone installs that want no
        inherited ACEs at all. Never silently drops SYSTEM/Administrators.

Ordering invariant (mirrors horizon_aios_create_brain.py): all Deny ACEs are applied
AFTER all brains-group grants, so an inherited permission can never
accidentally reach a privileged dir.

Docker note:
    In Docker builds, this script is invoked as a root-context RUN step before
    the USER switch (see bootstrap_docker.sh / Dockerfile). bootstrap.sh detects
    this via AIOS_SKIP_HARDEN=1 and skips the normal Section 9 invocation to
    avoid running horizon_aios_harden.py twice. Never set AIOS_SKIP_HARDEN=1 in native
    (non-Docker) deployments — doing so bypasses the ACL hardening that enforces
    brain isolation (see security_invariants.md §2).

Usage:
    python horizon_aios_harden.py [--horizon-root /path] [--strict] [--dry-run]

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

# Principals that must NEVER lose control of the AIOS tree, regardless of mode.
# Well-known SIDs are used (locale-independent: works on non-English Windows).
#   S-1-5-18      = NT AUTHORITY\SYSTEM
#   S-1-5-32-544  = BUILTIN\Administrators
WINDOWS_MUST_HAVE = (
    ('SYSTEM',         '*S-1-5-18'),
    ('Administrators', '*S-1-5-32-544'),
)

# Specific-rights mask denying all write/create/append/delete while leaving
# read/execute/read-attributes intact, so "no write anywhere" does not also
# revoke the reads brains legitimately need (etc/templates/docs):
#   WD=write-data/add-file  AD=append-data/add-subdir  WEA=write-EA
#   WA=write-attrs  DE=delete  DC=delete-child
BRAINS_NOWRITE_MASK = '(WD,AD,WEA,WA,DE,DC)'


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
    $HORIZON_SYSTEM/sbin/horizon_aios_harden.py, so ../ is $HORIZON_SYSTEM and
    ../../ is $HORIZON_ROOT (matches horizon_aios_maintain_logs.py / horizon_aios_sync.py).
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
                 f'-Description "Horizon.AIOS group: {BRAINS_GROUP}"'],
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

def _grant_must_have_full(path, owner, dry_run):
    """Idempotently (re)grant Full control to the principals that must never
    lose access — the owner, SYSTEM, and the local Administrators group.
    Well-known SIDs keep this locale-independent. Adding an existing grant is
    a harmless no-op, so this is safe to call in either mode."""
    if owner:
        run(['icacls', path, '/grant', f'{owner}:(OI)(CI)F'], dry_run=dry_run)
        grant(f'owner Full control (preserved): {owner}')
    else:
        warn('Could not determine owner username — skipping owner Full grant. '
             'Verify the owner retains Full control manually.')
    for label, sid in WINDOWS_MUST_HAVE:
        run(['icacls', path, '/grant', f'{sid}:(OI)(CI)F'], dry_run=dry_run)
        grant(f'{label} Full control (preserved)')


def harden_windows(paths, owner, have_group, dry_run, strict):
    """
    Apply the ACL model on Windows with icacls.

    Default (additive) strategy — preserve everything, enforce by adding ACEs:
      1. Ensure owner + SYSTEM + Administrators have Full control (idempotent).
         Existing/inherited ACLs (GPO/SCCM/Intune, etc.) are left untouched.
      2. Add an inheritable brains Deny-Write across $HORIZON_SYSTEM. Per
         security_invariants §3, an explicit/inherited Deny beats any Allow, so
         this enforces "no write anywhere" even when infra grants broad write
         (e.g. Authenticated Users:Modify). The mask denies write/create/delete
         only — brains keep whatever READ they were granted (etc/templates/docs
         are not in the deny list; the model forbids writes there, not reads).
      3. Grant brains Read+Execute on bin and skills_bin. Windows satisfies a
         read/exec request from this explicit Allow before consulting the
         inherited Deny-Write; a write/delete falls through to the Deny.
      4. Apply full Deny on sbin/skills_sbin/logs AFTER all grants. No
         inheritance strip — SYSTEM/Administrators/owner stay via the ACEs
         already on those dirs.

    --strict adds: drop inherited ACEs (/inheritance:r) at the root and on each
    privileged dir, re-establishing the must-have principals FIRST. For
    locked-down standalone installs. It never drops SYSTEM/Administrators.
    """
    system = paths['horizon_system']

    # 1. Root: ensure must-have principals; strict additionally strips inheritance.
    if strict:
        info(f'STRICT: dropping inherited ACEs on AIOS root: {system}')
        run(['icacls', system, '/inheritance:r'], dry_run=dry_run)
    else:
        info(f'ADDITIVE: preserving existing/inherited ACLs on AIOS root: {system}')
    _grant_must_have_full(system, owner, dry_run)

    if not have_group:
        warn('brains group unavailable — skipping all brains grant/deny ACEs. '
             'owner/SYSTEM/Administrators control is ensured; re-run after the '
             'group exists to apply the brains restrictions.')
        return

    # 2. Broad invariant: brains never WRITE/DELETE anywhere under $HORIZON_SYSTEM.
    run(['icacls', system, '/deny', f'{BRAINS_GROUP}:(OI)(CI){BRAINS_NOWRITE_MASK}'],
        dry_run=dry_run)
    deny(f'brains DENY write/delete across $HORIZON_SYSTEM: {system}')

    # 3. Explicit RX grants for brains on bin and skills_bin (before any deny).
    for label, key in (('bin', 'bin'), ('skills_bin', 'skills_bin')):
        path = paths[key]
        if os.path.isdir(path):
            run(['icacls', path, '/grant', f'{BRAINS_GROUP}:(OI)(CI)RX'],
                dry_run=dry_run)
            grant(f'brains Read+Execute on {label}: {path}')
        else:
            warn(f'{label} missing, skipping grant: {path}')

    # 4. Full Deny on privileged dirs — MUST come after all grants above.
    for label, key in (('sbin', 'sbin'),
                       ('skills_sbin', 'skills_sbin'),
                       ('logs', 'logs')):
        path = paths[key]
        if not os.path.isdir(path):
            warn(f'{label} missing, skipping deny: {path}')
            continue
        if strict:
            # Strip the dir's inheritance, then re-establish the must-have
            # principals before the Deny so they are never collateral.
            run(['icacls', path, '/inheritance:r'], dry_run=dry_run)
            _grant_must_have_full(path, owner, dry_run)
        # Full-control deny (read+write+delete) — these dirs are "DENY
        # (explicit)" per security_invariants §2/§3. Applied last so it wins.
        run(['icacls', path, '/deny', f'{BRAINS_GROUP}:(OI)(CI)F'],
            dry_run=dry_run)
        deny(f'brains DENY (full) on {label}: {path}')


# ---------------------------------------------------------------------------
# Unix / macOS hardening (chown / chmod / setfacl)
# ---------------------------------------------------------------------------

def harden_unix(paths, os_name, owner, have_group, dry_run, strict):
    """
    Apply the ACL model on Linux/macOS.

      - sbin / skills_sbin / logs => brains denied (setfacl g:brains:--- where
        available; 700 owner-only otherwise)
      - bin / skills_bin          => brains Read+Execute
      - everything else in $HORIZON_SYSTEM => brains/non-owners have no write,
        satisfying "no write anywhere in $HORIZON_SYSTEM".

    Default (additive) preserves existing ownership and ACLs: it uses POSIX.1e
    ACLs (setfacl) to add a brains entry without rewriting owner/group/other or
    recursively chowning the tree — the analogue of the Windows additive mode.
    --strict takes ownership of the subtree (chown -R) and uses mode bits
    (go-w / 700), the heavier standalone posture. There is no SYSTEM/
    Administrators analogue on Unix; the owner is the must-have principal.

    Privileged-dir denies are applied AFTER the brains rx grants so the grants
    can never cascade into them (mirrors horizon_aios_create_brain.py).
    """
    system = paths['horizon_system']
    have_setfacl = shutil.which('setfacl') is not None

    if not strict and have_group and have_setfacl and os_name == 'Linux':
        # Additive: add a brains ACL entry (read+exec, no write) across the tree
        # plus a default ACL so new files inherit it. Owner/group/other and any
        # existing ACLs are left intact.
        info('ADDITIVE: setfacl brains r-x (no write) across $HORIZON_SYSTEM')
        run(['setfacl', '-R', '-m', f'g:{BRAINS_GROUP}:r-x', system],
            dry_run=dry_run, check=False)
        run(['setfacl', '-R', '-d', '-m', f'g:{BRAINS_GROUP}:r-x', system],
            dry_run=dry_run, check=False)
        ok('brains have read+execute but no write under $HORIZON_SYSTEM')
        for label, key in (('sbin', 'sbin'), ('skills_sbin', 'skills_sbin'),
                           ('logs', 'logs')):
            path = paths[key]
            if not os.path.isdir(path):
                warn(f'{label} missing, skipping deny: {path}')
                continue
            run(['setfacl', '-R', '-m', f'g:{BRAINS_GROUP}:---', path],
                dry_run=dry_run, check=False)
            run(['setfacl', '-R', '-d', '-m', f'g:{BRAINS_GROUP}:---', path],
                dry_run=dry_run, check=False)
            deny(f'brains DENY (setfacl ---) on {label}: {path}')
        return

    if not strict and not (have_group and have_setfacl):
        warn('Additive Unix hardening needs the brains group + setfacl (Linux). '
             'Falling back to mode-bit hardening; existing ownership is '
             'preserved (no recursive chown in additive mode).')

    # Strict (or additive fallback without setfacl): mode-bit hardening.
    # Only strict takes ownership of the whole subtree.
    if strict and owner:
        info(f'STRICT: ensuring owner ({owner}) owns $HORIZON_SYSTEM subtree')
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
    for label, key in (('sbin', 'sbin'),
                       ('skills_sbin', 'skills_sbin'),
                       ('logs', 'logs')):
        path = paths[key]
        if not os.path.isdir(path):
            warn(f'{label} missing, skipping deny: {path}')
            continue
        run(['chmod', '-R', '700', path], dry_run=dry_run, check=False)
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
             '$HORIZON_SYSTEM/sbin/horizon_aios_harden.py).',
    )
    parser.add_argument(
        '--strict', action='store_true', default=False,
        help='Strip inherited ACEs (/inheritance:r on Windows; chown -R + mode '
             'bits on Unix) for a locked-down standalone install. The default '
             '(additive) preserves existing/infra ACLs and enforces the model '
             'by adding ACEs only. Either way, owner + SYSTEM + Administrators '
             'always retain Full control on Windows.',
    )
    parser.add_argument(
        '--dry-run', action='store_true', default=False,
        help='Print every action that would be taken without executing anything.',
    )
    return parser.parse_args()


def main():
    args = parse_args()

    banner('Horizon AIOS — Layer Hardening')
    print(f'  Mode: {"STRICT (inheritance stripped)" if args.strict else "ADDITIVE (existing ACLs preserved)"}\n')
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
            harden_windows(paths, owner, have_group, args.dry_run, args.strict)
        else:
            harden_unix(paths, os_name, owner, have_group, args.dry_run, args.strict)
    except subprocess.CalledProcessError as exc:
        error(f'An ACL command failed: {exc}')
        error('Hardening is incomplete. Re-run elevated and review the output above.')
        sys.exit(2)

    banner('Summary')
    print('  AIOS layer hardening applied (or printed in dry-run).')
    print(f'  Mode: {"STRICT" if args.strict else "ADDITIVE (existing ACLs preserved)"}')
    print('  brains group:')
    print('    bin, skills_bin      -> Read+Execute (explicit grant)')
    print('    sbin, skills_sbin, logs -> DENY (explicit, full; after grants)')
    print('    rest of $HORIZON_SYSTEM -> no write (inheritable Deny-Write)')
    if os_name == 'Windows':
        print('  owner + SYSTEM + Administrators -> Full control (preserved).')
    else:
        print('  owner -> Full control on the whole subtree.')
    if not have_group:
        print('\n  NOTE: brains group was unavailable — only owner-side hardening '
              'was applied. Re-run after the group exists.')
    print()
    sys.exit(0)


if __name__ == '__main__':
    main()
