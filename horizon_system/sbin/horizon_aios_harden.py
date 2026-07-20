#!/usr/bin/env python3
"""
horizon_aios_harden.py — Horizon AIOS Layer Hardening
=============================================

Applies the authoritative brains-group ACL model to the AIOS layer
($HORIZON_SYSTEM) INDEPENDENT of brain creation, so a freshly bootstrapped
machine is protected before any brain account exists.

The ACL POSTURE (which principal gets which rights on which path) is no longer
hardcoded here: it is sourced from ai_os_etc/file_acl_hardening.toml — deep-merged
with an optional ai_os_etc/file_acl_hardening.local.toml deployer override —
loaded and translated to native ops (setfacl / chmod +a / icacls) by
horizon_aios_acl_posture.py. harden_unix / harden_windows now LOOP over those
rules. horizon_aios_doctor.py verifies the SAME loaded posture, so enforcer and
verifier can never disagree. This script remains the enforcement point.

This is the real enforcement point for the ACL model documented in
documentation/security_architecture_invariants.md §2/§3/§5 (the terse,
context-loaded ai_os_etc/security_invariants.md is the operator-facing summary): the
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
    $HORIZON_ROOT (user space OUTSIDE horizon_system/) -> humans: Full control
    $HORIZON_SYSTEM (the install itself)               -> humans: Read-Only
                                       (read+execute, NO write). Install-wide
                                       config/canon/tooling is admin-authored;
                                       humans extend via scope-local (project /
                                       folder) overrides that live outside
                                       horizon_system. Writable executable dirs
                                       are avoided here to close the privesc path
                                       (a human-writable tool later run by root).
    root-level canon (agents.md, CLAUDE.md, .claude/agents.md,
                      .claude/CLAUDE.md)               -> humans: Read-Only
                                       (install-wide canon lives outside
                                       horizon_system but is still admin-owned).
    $HORIZON_ROOT/brains               -> humans: Read/Write (near-admins modify
                                       brains/apps; brain-to-brain isolation
                                       rides on ownership + per-brain group)
    $HORIZON_ROOT/{projects,handoffs,objectives,usrbin}
                                       -> humans: SELF-SERVICE per-user isolation.
                                       Each parent grants create-traverse (-wx:
                                       create+enter, NO list) + sticky + no setgid;
                                       new entries born owner-only + creator's own
                                       private group via the isolating default ACL.
                                       Peers cannot enumerate/read/delete them. Each
                                       area has one group-shared shared/ drop-zone.

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
    brain isolation (see documentation/security_architecture_invariants.md §2).

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

# The ACL posture (WHAT is granted/denied on each path) is now sourced from
# ai_os_etc/file_acl_hardening.toml (+ optional file_acl_hardening.local.toml
# override) and translated to native ops by horizon_aios_acl_posture. This
# module remains the enforcement point; the posture module is the single source
# of truth shared with horizon_aios_doctor.py. Ensure the sibling module is
# importable even when this script is invoked by absolute path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import horizon_aios_acl_posture as posture_engine  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The common group every brain belongs to. Brain ACEs are group-based, so this
# group must exist for the grants/denies below to be settable.
BRAINS_GROUP = 'brains'

# The AIOS-managed group for flesh-and-blood human operators (secure-by-
# onboarding: created on every install alongside `brains`, even when empty).
# Members get Full control of the AIOS tree, Read/Write on brains/ (near-admins
# who modify brains/apps), and are self-service isolated from each other on the
# four human areas (create-traverse parent, entries born owner-only). An EMPTY horizon_humans is
# harmless: an empty group
# granted Full grants nobody, so a server with no enrolled humans reduces to
# "only owner/SYSTEM/Administrators write" without a separate code path.
HUMANS_GROUP = 'horizon_humans'
HUMANS_GROUP_DESC = 'Horizon.AIOS Actual Humans'

# The human-facing areas directly under $HORIZON_ROOT that share ONE model:
# SELF-SERVICE per-user isolation. Any horizon_humans member creates their OWN
# entries directly (owner + own private group; no admin/enrollment tooling),
# peers cannot enumerate/read them, and each area carries one group-shared
# `shared/` drop-zone. Shared by harden + doctor so both agree on the set.
HUMAN_SHARED_DIRS = ['projects', 'handoffs', 'objectives', 'usrbin']

# Install-wide canon at the AIOS root that governs agent behavior but lives
# OUTSIDE $HORIZON_SYSTEM (so the tree-wide humans Full grant would otherwise
# leave it human-writable). horizon_humans are held Read-Only on these too, so
# the only human-writable config is scope-local (project/folder) overrides.
ROOT_CANON_RELPATHS = (
    'agents.md',
    'CLAUDE.md',
    os.path.join('.claude', 'agents.md'),
    os.path.join('.claude', 'CLAUDE.md'),
)

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
        # holds this subtree Read/Write for the horizon_humans group (near-admins).
        'brains':              os.path.join(horizon_root, 'brains'),
        # projects/ lives under HORIZON_ROOT. One of the four self-service human
        # areas (create-traverse parent, entries born owner-only); see the posture
        # config file_acl_hardening.toml and horizon_aios_acl_posture.py.
        'projects':            os.path.join(horizon_root, 'projects'),
    }


def human_shared_dirs(paths):
    """Absolute paths of the four self-service human areas under HORIZON_ROOT
    (see HUMAN_SHARED_DIRS). Kept as a helper so harden and doctor share the
    concept without each area needing its own resolve_paths key."""
    root = paths['horizon_root']
    return [os.path.join(root, name) for name in HUMAN_SHARED_DIRS]


def root_canon_files(paths, dry_run=False):
    """Existing root-level canon files (outside $HORIZON_SYSTEM) that humans are
    held Read-Only on. In dry-run, return all candidates so the plan is visible
    even before the files exist."""
    root = paths['horizon_root']
    out = []
    for rel in ROOT_CANON_RELPATHS:
        candidate = os.path.join(root, rel)
        if dry_run or os.path.isfile(candidate):
            out.append(candidate)
    return out


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


def _run_ops(ops, dry_run):
    """Execute a list of translator Ops (from horizon_aios_acl_posture): run each
    op.argv (argv-style, never a shell; check=False so a single failing ACL
    command does not abort the pass — the historical behavior) and emit its
    house-style log line via the matching logger. Ops with argv=None are
    log-only; ops with msg=None run silently."""
    _LOG = {'grant': grant, 'deny': deny, 'ok': ok, 'info': info, 'warn': warn}
    for op in ops:
        if op.argv:
            run(list(op.argv), dry_run=dry_run, check=False)
        if op.msg:
            _LOG.get(op.kind, info)(op.msg)


def _rule_allowed(rule, have_group, have_humans):
    """Guard: skip a rule whose principal's group is unavailable (mirrors the
    original have_group / have_humans gating). Returns (ok, warn_msg)."""
    if rule.principal == BRAINS_GROUP and not have_group:
        return (False, f'{rule.name}: brains group unavailable — skipping')
    if rule.principal == HUMANS_GROUP and not have_humans:
        return (False, f'{rule.name}: horizon_humans group unavailable — skipping')
    return (True, None)


def harden_windows(paths, owner, have_group, have_humans, dry_run, strict):
    """
    Apply the ACL model on Windows with icacls, LOOPING over the loaded posture
    (horizon_aios_acl_posture) instead of hardcoded steps. Structure preserved:

      A.  Controlled root ACL: break inheritance (/inheritance:r) at $HORIZON_ROOT
          and re-grant must_have_full (owner + SYSTEM S-1-5-18 + Administrators
          S-1-5-32-544). Removes broad inherited grants (Authenticated Users, etc.)
          from the tree.
      1.  Ensure must_have_full on $HORIZON_SYSTEM; --strict also strips its
          inheritance first.
      GRANT then DENY phase over the posture rules (grant-before-deny invariant):
        * humans-userspace-full  -> humans (OI)(CI)F across the tree (grant B).
        * humans-system-readonly / root canon -> explicit Deny-Write (a broad-Full
          holder is reduced to Read-Only via Deny, never an Allow) — see
          windows_rule_ops(broad_allow=...).
        * humans-brains-readwrite -> humans keep inherited Full (Modify grant).
        * humans-*-selfservice -> SELF-SERVICE isolation on ALL FOUR areas
          (projects/, handoffs/, objectives/, usrbin/): break inheritance, re-grant
          must-haves, grant create-but-not-list (WD,AD,X) this-folder-only, and
          isolate existing children via OWNER RIGHTS (*S-1-3-4) — NOT a group Deny
          (a Deny would lock the owner out; the owner is a horizon_humans member).
        * humans-*-shared -> group-accessible drop-zone (Modify).
        * brains-bin/skills_bin -> brains (OI)(CI)RX (positive grant).
        * brains-system-nowrite -> inheritable brains Deny-Write across the install.
        * brains-sbin/skills_sbin/logs -> full brains Deny (after all grants;
          --strict strips inheritance + re-grants must-haves first).

    This replaces the former TODO(windows-parity) block: self-service write +
    per-area shared/ now covers all four areas, matching the Unix model. Windows
    is DRY-RUN PRINT ONLY on this Linux host — never applied live here.
    """
    root   = paths['horizon_root']
    system = paths['horizon_system']

    posture = posture_engine.load_posture(paths)
    info(f'ACL posture source: {posture.source} ({len(posture.rules)} rules)')
    broad = frozenset(r.principal for r in posture.rules if r.rights == 'full')

    # --- A. Controlled root ACL: break inheritance + re-grant must-haves. ---
    info(f'Establishing controlled root ACL (break inheritance + re-grant): {root}')
    run(['icacls', root, '/inheritance:r'], dry_run=dry_run)
    _run_ops(posture_engine.windows_must_have_grants(root, owner), dry_run)

    # --- 1. System: ensure must-haves; strict additionally strips inheritance. --
    if strict:
        info(f'STRICT: dropping inherited ACEs on AIOS system dir: {system}')
        run(['icacls', system, '/inheritance:r'], dry_run=dry_run)
    _run_ops(posture_engine.windows_must_have_grants(system, owner), dry_run)

    if not have_group:
        warn('brains group unavailable — brains grant/deny ACEs will be skipped.')
    if not have_humans:
        warn('horizon_humans group unavailable — humans ACEs will be skipped.')

    # --- GRANT phase then DENY phase (grant-before-deny). -------------------
    for phase, rules in (('grant', posture.grant_rules()),
                         ('deny', posture.deny_rules())):
        for rule in rules:
            allowed, why = _rule_allowed(rule, have_group, have_humans)
            if not allowed:
                warn(why)
                continue
            _run_ops(posture_engine.windows_rule_ops(
                rule, paths, owner=owner, strict=strict, dry_run=dry_run,
                broad_allow=broad), dry_run)


def harden_unix(paths, os_name, owner, have_group, have_humans, dry_run, strict):
    """
    Apply the ACL model on Linux/macOS by LOOPING over the loaded posture
    (horizon_aios_acl_posture) rather than hardcoded steps.

    Additive Linux (setfacl present): the posture is realized verbatim via the
    setfacl translator — humans rules (userspace Full, system Read-Only, root
    canon, brains/ Read/Write, and the four SELF-SERVICE areas with their shared/
    drop-zones), then brains grants (bin/skills_bin Read+Execute), a Linux-only
    brains traverse (--x) reachability step, then brains denies (system no-write
    r-x, and full --- + owner-only 700 on sbin/skills_sbin/logs). This is the
    branch this host runs and the one the getfacl oracle pins.

    --strict / no-setfacl: the mode-bit DELIVERY MECHANISM (chown -R + go-w + 700)
    the TOML schema notes carve out as orthogonal to the posture. The humans
    self-service model still needs setfacl (named-group ACEs) and is applied
    whenever setfacl is present, in both modes; strict adds ownership + mode-bit
    lockdown for the brains side. Target dir lists are DERIVED from the posture
    (privileged-deny dirs, read-exec dirs, self-service areas) so nothing is
    hardcoded that the posture also defines.
    """
    system   = paths['horizon_system']
    root     = paths['horizon_root']
    brains   = paths['brains']
    have_setfacl = shutil.which('setfacl') is not None
    linux_acls = (have_setfacl and os_name == 'Linux')

    posture = posture_engine.load_posture(paths)
    info(f'ACL posture source: {posture.source} ({len(posture.rules)} rules)')

    # --- horizon_humans model via setfacl (applied in BOTH additive & strict; a
    #     named-group grant + isolating defaults can only be expressed with ACLs). ---
    if have_humans and linux_acls:
        info('Applying horizon_humans posture rules via setfacl translator')
        for rule in posture.rules:
            if rule.principal != HUMANS_GROUP:
                continue
            _run_ops(posture_engine.linux_rule_ops(rule, paths, dry_run=dry_run),
                     dry_run)
    elif have_humans:
        warn('horizon_humans model needs setfacl (Linux) to express a named-group '
             'grant + brains Read-Only. On this platform, enroll humans as the '
             'owner or manage their access with the OS/identity tooling directly.')

    # --- brains model, ADDITIVE Linux (setfacl): grants, traverse, denies. -----
    if not strict and have_group and linux_acls:
        info('Applying brains posture rules via setfacl translator (additive)')
        # Grant phase: bin/skills_bin Read+Execute.
        for rule in posture.grant_rules():
            if rule.principal != BRAINS_GROUP:
                continue
            _run_ops(posture_engine.linux_rule_ops(rule, paths, dry_run=dry_run),
                     dry_run)
        # Linux-only reachability: brains traverse (--x) on root + brains/.
        _run_ops(posture_engine.linux_traverse_ops(posture, paths), dry_run)
        # Deny phase: system no-write, then full deny on privileged dirs.
        for rule in posture.deny_rules():
            if rule.principal != BRAINS_GROUP:
                continue
            _run_ops(posture_engine.linux_rule_ops(rule, paths, dry_run=dry_run),
                     dry_run)
        return

    if not strict and not (have_group and linux_acls):
        warn('Additive Unix hardening needs the brains group + setfacl (Linux). '
             'Falling back to mode-bit hardening; existing ownership is '
             'preserved (no recursive chown in additive mode).')

    # --- Strict (or additive fallback without setfacl): mode-bit delivery. ------
    # Dir lists derived from the posture so harden + the posture agree.
    if strict and owner:
        info(f'STRICT: ensuring owner ({owner}) owns $HORIZON_SYSTEM subtree')
        run(['chown', '-R', f'{owner}:', system], dry_run=dry_run, check=False)
        grant(f'owner ownership on $HORIZON_SYSTEM: {owner}')

    info('Removing group/other write across $HORIZON_SYSTEM (go-w)')
    run(['chmod', '-R', 'go-w', system], dry_run=dry_run, check=False)
    ok('brains (and all non-owners) have no write under $HORIZON_SYSTEM')

    if have_group:
        for path in posture.brains_readexec_dirs():
            label = os.path.basename(path)
            if os.path.isdir(path):
                run(['chown', '-R', f':{BRAINS_GROUP}', path],
                    dry_run=dry_run, check=False)
                run(['chmod', '-R', 'g+rX', path], dry_run=dry_run, check=False)
                grant(f'brains Read+Execute on {label}: {path}')
            else:
                warn(f'{label} missing, skipping grant: {path}')
    else:
        warn('brains group unavailable — skipping brains rx grants on bin/skills_bin. '
             'Owner-side hardening (go-w + 700 on privileged dirs) is applied.')

    # Brains traverse (--x) on AIOS root + brains/ (needs setfacl on Linux).
    if have_group and linux_acls:
        _run_ops(posture_engine.linux_traverse_ops(posture, paths), dry_run)

    # Privileged dirs: owner-only 700 — AFTER the grants above.
    for path in posture.brains_deny_dirs():
        label = os.path.basename(path)
        if not os.path.isdir(path):
            warn(f'{label} missing, skipping deny: {path}')
            continue
        run(['chmod', '-R', 'u=rwX,go=', path], dry_run=dry_run, check=False)
        if have_group and linux_acls:
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
    print('    user space (outside horizon_system/, projects/) -> Full control (empty group = only admins write)')
    print('    $HORIZON_SYSTEM + root canon         -> Read-Only (read+execute, no write)')
    print('    brains/                              -> Read/Write (near-admins; brain-to-brain isolation via ownership + per-brain group)')
    print('    projects/, handoffs/, objectives/, usrbin/ -> self-service per-user isolation (create-traverse parent, entries born owner-only; per-area shared/ drop-zone)')
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
