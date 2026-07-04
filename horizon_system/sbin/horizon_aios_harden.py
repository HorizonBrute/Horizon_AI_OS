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

ACL model applied:

  brains group (conventionally `brains`):
    $HORIZON_SYSTEM/bin          -> brains: Read+Execute (explicit grant)
    $HORIZON_SYSTEM/skills_bin    -> brains: Read+Execute (explicit grant)
    $HORIZON_SYSTEM/sbin          -> brains: DENY (explicit, full)
    $HORIZON_SYSTEM/skills_sbin   -> brains: DENY (explicit, full)
    $HORIZON_SYSTEM/logs          -> brains: DENY (explicit, full)  [canonical log path]
    $HORIZON_SYSTEM (everything else: ai_os_etc, scripts, templates,
                     documentation, sounds, harness_configs, ...)
                                  -> brains: NO WRITE anywhere (inheritable
                                     Deny-Write; reads stay allowed)

  horizon_humans group (flesh-and-blood human operators; created on every
  install, secure-by-onboarding — empty is fine, an empty grant grants nobody):
    $HORIZON_ROOT (whole AIOS tree) -> humans: Full control
    $HORIZON_ROOT/brains            -> humans: Read-Only (explicit Deny-Write;
                                       to write there a human elevates to admin
                                       or changes permissions)

  owner + SYSTEM + Administrators -> Full control, always preserved. Root
  inheritance is broken and these are re-granted, so broad inherited grants
  from the volume root (Authenticated Users, sandbox groups, stray SIDs) no
  longer reach the AIOS tree.

Human operators are ENROLLED into horizon_humans by onboarding (bootstrap),
not by this engine. This script only creates the groups and applies the ACLs.

Root inheritance (Windows): ALWAYS controlled. The engine breaks inheritance at
    $HORIZON_ROOT and re-grants only owner + SYSTEM + Administrators + the
    horizon_humans group. This is the secure-by-onboarding baseline that removes
    broad inherited write grants from the volume root; you cannot suppress an
    inherited Allow (e.g. Authenticated Users:Modify) without breaking
    inheritance, and a Deny on Authenticated Users would also catch the human
    owner/admins (who are themselves authenticated).

Two modes for the $HORIZON_SYSTEM subtree (Windows):
    additive (default) -- Preserve the system subtree's existing/inherited ACLs
        (GPO/SCCM/Intune pushes, SYSTEM, Administrators). Enforce the brains
        model by ADDING ACEs: an inheritable brains Deny-Write plus full Deny on
        the privileged dirs. Right for managed machines AND home boxes.
    --strict -- Additionally drop inherited ACEs (/inheritance:r) on the system
        dir and each privileged dir, re-establishing owner + SYSTEM +
        Administrators first. For locked-down standalone installs. Never
        silently drops SYSTEM/Administrators.

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

# The AIOS-managed group for flesh-and-blood human operators (secure-by-
# onboarding: created on every install alongside `brains`, even when empty).
# Members get Full control of the AIOS tree but are held Read-Only on brains/
# (brain locations are for brains — to write there a human elevates to admin or
# changes permissions). An EMPTY horizon_humans is harmless: an empty group
# granted Full grants nobody, so a server with no enrolled humans reduces to
# "only owner/SYSTEM/Administrators write" without a separate code path.
HUMANS_GROUP = 'horizon_humans'
HUMANS_GROUP_DESC = 'Horizon.AIOS Actual Humans'

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
        # brains/ lives under HORIZON_ROOT (not HORIZON_SYSTEM). The humans model
        # holds this subtree Read-Only for the horizon_humans group.
        'brains':              os.path.join(horizon_root, 'brains'),
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

def ensure_group(os_name, group, description, dry_run):
    """
    Ensure a local OS group exists so group-based ACEs are settable. An empty
    group is fine (it grants nobody until members are enrolled). Returns True if
    the group exists (or was / would be created), False if absent and could not
    be created (caller continues with owner-side hardening only).
    """
    if _group_exists(os_name, group):
        ok(f'Group already exists: {group}')
        return True

    if dry_run:
        info(f'Group "{group}" absent — would create it.')
        return True

    try:
        if os_name == 'Windows':
            run(['powershell', '-NonInteractive', '-Command',
                 f'New-LocalGroup -Name "{group}" -Description "{description}"'],
                dry_run=dry_run)
        elif os_name == 'Linux':
            run(['groupadd', group], dry_run=dry_run)
        else:  # Darwin
            run(['dseditgroup', '-o', 'create', group], dry_run=dry_run)
        ok(f'Created group: {group}')
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        warn(f'Could not create group "{group}": {exc}')
        warn('Continuing with owner-side hardening only. Group-based grant/deny '
             'ACEs will be skipped until the group exists (re-run after it does).')
        return False


def ensure_brains_group(os_name, dry_run):
    """Ensure the `brains` group exists (group-based brain ACEs need it)."""
    return ensure_group(os_name, BRAINS_GROUP,
                        f'Horizon.AIOS group: {BRAINS_GROUP}', dry_run)


def ensure_humans_group(os_name, dry_run):
    """Ensure the `horizon_humans` group exists. Created on every install
    (secure-by-onboarding), even with zero members — an empty group grants
    nobody, so the humans:F grant is a harmless no-op on a bare server."""
    return ensure_group(os_name, HUMANS_GROUP, HUMANS_GROUP_DESC, dry_run)


def _group_exists(os_name, group):
    if os_name == 'Windows':
        result = subprocess.run(
            ['powershell', '-NonInteractive', '-Command',
             f'Get-LocalGroup -Name "{group}" -ErrorAction SilentlyContinue'],
            capture_output=True, text=True)
        return bool(result.stdout.strip())
    try:
        result = subprocess.run(['getent', 'group', group], capture_output=True)
        if result.returncode == 0:
            return True
    except (FileNotFoundError, OSError):
        pass
    # macOS without getent: fall back to dscl (macOS-only binary — never Linux).
    if os_name == 'Darwin':
        try:
            result = subprocess.run(
                ['dscl', '.', '-read', f'/Groups/{group}'], capture_output=True)
            return result.returncode == 0
        except (FileNotFoundError, OSError):
            pass
    return False


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


def harden_windows(paths, owner, have_group, have_humans, dry_run, strict):
    """
    Apply the uniform ACL model on Windows with icacls.

    Secure-by-onboarding baseline (always applied):
      A. Establish a CONTROLLED ROOT ACL on $HORIZON_ROOT: break inheritance
         (/inheritance:r) and re-grant only the known-good principals. This is
         what removes the human-side write hole — broad inherited grants from the
         volume root (Authenticated Users:Modify, sandbox groups, stray cloud
         SIDs) no longer reach the tree. owner + SYSTEM + Administrators are
         re-granted FIRST (never collateral; re-granted by well-known SID so this
         is locale-independent).
      B. Grant the horizon_humans group Full control across the tree. An EMPTY
         horizon_humans grants nobody, so a server with no enrolled humans
         reduces to "only owner/SYSTEM/Administrators write" with no separate
         code path. Human operators are enrolled by onboarding (bootstrap).

    Brain model (unchanged, scoped to $HORIZON_SYSTEM):
      1. owner + SYSTEM + Administrators Full (idempotent under the inherited
         root ACEs; strict additionally strips system inheritance).
      2. Inheritable brains Deny-Write across $HORIZON_SYSTEM (write/delete only;
         reads stay allowed). An explicit/inherited Deny beats any Allow.
      3. brains Read+Execute on bin and skills_bin (explicit Allow satisfies a
         read/exec request before the Deny-Write is consulted).
      4. Full Deny on sbin/skills_sbin/logs AFTER all grants.

    Humans-on-brains (C, after the humans grant):
      C. Explicit horizon_humans Deny-Write on $HORIZON_ROOT/brains so human
         operators are Read-Only there (brain locations are for brains). Reads
         flow through the inherited humans Full; the deny removes write/delete.
         Escape hatches by construction: Administrators are not in
         horizon_humans (elevate-to-admin writes) and the mask omits WRITE_DAC
         (a human retains the right to re-permission).

    --strict additionally drops inherited ACEs on each privileged dir,
    re-establishing the must-have principals first. It never drops
    SYSTEM/Administrators.
    """
    root   = paths['horizon_root']
    system = paths['horizon_system']
    brains = paths['brains']

    # --- A. Controlled root ACL: break inheritance + re-grant known-good set. ---
    info(f'Establishing controlled root ACL (break inheritance + re-grant): {root}')
    run(['icacls', root, '/inheritance:r'], dry_run=dry_run)
    _grant_must_have_full(root, owner, dry_run)

    # --- B. horizon_humans Full control across the tree (empty group = no-op). --
    if have_humans:
        run(['icacls', root, '/grant', f'{HUMANS_GROUP}:(OI)(CI)F'], dry_run=dry_run)
        grant(f'humans Full control on AIOS tree: {HUMANS_GROUP} -> {root}')
    else:
        warn('horizon_humans group unavailable — skipping humans grant. Re-run '
             'after the group exists to grant human operators tree access.')

    # --- 1. System: ensure must-haves; strict additionally strips inheritance. --
    if strict:
        info(f'STRICT: dropping inherited ACEs on AIOS system dir: {system}')
        run(['icacls', system, '/inheritance:r'], dry_run=dry_run)
    _grant_must_have_full(system, owner, dry_run)

    if have_group:
        # 2. Broad invariant: brains never WRITE/DELETE anywhere in $HORIZON_SYSTEM.
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
                run(['icacls', path, '/inheritance:r'], dry_run=dry_run)
                _grant_must_have_full(path, owner, dry_run)
            run(['icacls', path, '/deny', f'{BRAINS_GROUP}:(OI)(CI)F'],
                dry_run=dry_run)
            deny(f'brains DENY (full) on {label}: {path}')
    else:
        warn('brains group unavailable — skipping all brains grant/deny ACEs. '
             'owner/SYSTEM/Administrators/humans control is ensured; re-run '
             'after the group exists to apply the brains restrictions.')

    # --- C. horizon_humans Read-Only on brains/ (after the humans Full grant). --
    if have_humans:
        if not os.path.isdir(brains):
            info(f'Creating brains dir so its humans deny can be applied: {brains}')
            if not dry_run:
                try:
                    os.makedirs(brains, exist_ok=True)
                except OSError as exc:
                    warn(f'Could not create brains dir {brains}: {exc}')
        if os.path.isdir(brains) or dry_run:
            run(['icacls', brains, '/deny',
                 f'{HUMANS_GROUP}:(OI)(CI){BRAINS_NOWRITE_MASK}'], dry_run=dry_run)
            deny(f'humans Read-Only on brains (DENY write/delete): {HUMANS_GROUP} '
                 f'-> {brains}')
        else:
            warn(f'brains dir missing, skipping humans read-only deny: {brains}')


# ---------------------------------------------------------------------------
# Unix / macOS hardening (chown / chmod / setfacl)
# ---------------------------------------------------------------------------

def harden_unix(paths, os_name, owner, have_group, have_humans, dry_run, strict):
    """
    Apply the uniform ACL model on Linux/macOS.

      - horizon_humans => Full-equivalent (rwx) across the tree, but Read-Only
        (r-x) on brains/ — the Unix analogue of the Windows humans model. An
        empty group grants nobody, so a server reduces to owner-only write.
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
    root   = paths['horizon_root']
    brains = paths['brains']
    have_setfacl = shutil.which('setfacl') is not None

    # --- horizon_humans model (tree Full-equivalent, brains/ Read-Only). ---
    # setfacl is the closest analogue to a named-group grant + brains deny.
    if have_humans and have_setfacl and os_name == 'Linux':
        info('setfacl horizon_humans rwx across the AIOS tree (Full-equivalent)')
        run(['setfacl', '-R', '-m', f'g:{HUMANS_GROUP}:rwx', root],
            dry_run=dry_run, check=False)
        run(['setfacl', '-R', '-d', '-m', f'g:{HUMANS_GROUP}:rwx', root],
            dry_run=dry_run, check=False)
        grant(f'humans Full-equivalent on AIOS tree: {HUMANS_GROUP} -> {root}')
        if os.path.isdir(brains) or dry_run:
            run(['setfacl', '-R', '-m', f'g:{HUMANS_GROUP}:r-x', brains],
                dry_run=dry_run, check=False)
            run(['setfacl', '-R', '-d', '-m', f'g:{HUMANS_GROUP}:r-x', brains],
                dry_run=dry_run, check=False)
            deny(f'humans Read-Only on brains: {HUMANS_GROUP} -> {brains}')
    elif have_humans:
        warn('horizon_humans model needs setfacl (Linux) to express a named-group '
             'grant + brains Read-Only. On this platform, enroll humans as the '
             'owner or manage their access with the OS/identity tooling directly.')

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
        # Brains must TRAVERSE the AIOS root and the brains/ parent to reach both
        # their granted paths (bin/skills_bin) and their own workspace
        # (brains/<name>/, 0o770 <name>:<name>). Grant execute-only (--x; not
        # recursive, no default) so a brain can traverse to a known path but
        # cannot enumerate the root or its siblings. Without this the brains r-x
        # grant above is unreachable on Linux (the root dir denies non-owners).
        for trav in (root, brains):
            if os.path.isdir(trav) or dry_run:
                run(['setfacl', '-m', f'g:{BRAINS_GROUP}:--x', trav],
                    dry_run=dry_run, check=False)
        grant(f'brains traverse (--x) on AIOS root + brains/: {BRAINS_GROUP}')
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
            # Also enforce owner-only base mode bits. The setfacl deny alone
            # leaves the stat mode at 0o770; doctor --post-setup asserts 0o700
            # on sbin/skills_sbin/logs, so tighten the base permissions too.
            run(['chmod', '-R', 'u=rwX,go=', path], dry_run=dry_run, check=False)
            deny(f'brains DENY (setfacl --- + owner-only 700) on {label}: {path}')
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

    # Brains traverse (--x) on AIOS root + brains/ so their bin/skills_bin grant
    # and their own workspace (brains/<name>/) are reachable -- same fix as the
    # additive branch. Execute-only: traverse without listing, preserving
    # inter-brain isolation. Requires setfacl; mode bits alone cannot express a
    # named-group traverse ACE without opening the dir to all "other".
    if have_group and have_setfacl and os_name == 'Linux':
        for trav in (root, brains):
            if os.path.isdir(trav):
                run(['setfacl', '-m', f'g:{BRAINS_GROUP}:--x', trav],
                    dry_run=dry_run, check=False)
        grant(f'brains traverse (--x) on AIOS root + brains/: {BRAINS_GROUP}')

    # Privileged dirs: owner-only 700 — applied AFTER the grants above.
    for label, key in (('sbin', 'sbin'),
                       ('skills_sbin', 'skills_sbin'),
                       ('logs', 'logs')):
        path = paths[key]
        if not os.path.isdir(path):
            warn(f'{label} missing, skipping deny: {path}')
            continue
        run(['chmod', '-R', 'u=rwX,go=', path], dry_run=dry_run, check=False)
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

    # Ensure both AIOS-managed groups exist (group-based ACEs need them). Both
    # are created on every install (secure-by-onboarding); empty is fine.
    banner('Ensure AIOS groups (brains, horizon_humans)')
    have_group  = ensure_brains_group(os_name, args.dry_run)
    have_humans = ensure_humans_group(os_name, args.dry_run)

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
            harden_windows(paths, owner, have_group, have_humans,
                           args.dry_run, args.strict)
        else:
            harden_unix(paths, os_name, owner, have_group, have_humans,
                        args.dry_run, args.strict)
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
    print(f'  {HUMANS_GROUP} group:')
    print('    AIOS tree            -> Full control (empty group = only admins write)')
    print('    brains/              -> Read-Only (DENY write/delete; elevate/re-perm to write)')
    if os_name == 'Windows':
        print('  owner + SYSTEM + Administrators -> Full control (root inheritance broken).')
    else:
        print('  owner -> Full control on the whole subtree.')
    if not have_group:
        print('\n  NOTE: brains group was unavailable — brains ACEs skipped. '
              'Re-run after the group exists.')
    if not have_humans:
        print('\n  NOTE: horizon_humans group was unavailable — humans grant/deny '
              'skipped. Re-run after the group exists.')
    print('\n  Human operators are enrolled into horizon_humans by onboarding '
          '(bootstrap); this engine only sets up the group + ACLs.')
    print()
    sys.exit(0)


if __name__ == '__main__':
    main()
