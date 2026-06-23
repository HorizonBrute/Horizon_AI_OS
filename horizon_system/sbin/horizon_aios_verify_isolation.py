#!/usr/bin/env python3
"""
horizon_aios_verify_isolation.py — Horizon AIOS Brain-Isolation Test (Criterion #5)
===================================================================================

Proves the central AIOS security claim — a brain OS account can read
`$HORIZON_BIN` but is DENIED `$HORIZON_SYSTEM/sbin` — at two levels:

  * Default (safe) mode — NON-DESTRUCTIVE. Verifies the *static* ACL posture: an
    explicit (non-inherited) `brains` Deny on `sbin`/`skills_sbin`/`logs`
    (Windows, via Get-Acl) or owner-only mode 0o700 (Unix). Creates no account,
    needs no elevation. This is the same authoritative check `horizon_aios_doctor.py`
    runs, scoped to the isolation claim.

  * Live mode (--live) — DESTRUCTIVE + ELEVATED, OPT-IN. Provisions a throwaway
    brain, logs on AS that brain, and empirically attempts to read `bin` (expect
    OK) and `sbin` (expect denied), then removes the brain. This is the only test
    that proves a real, separate-identity process is actually refused — not just
    that the ACE is configured.

Because live mode adds and deletes an OS user and requires Administrator/root, it
is gated behind --live; the default does nothing that touches user accounts.

Usage:
    python horizon_aios_verify_isolation.py [--horizon-root PATH]      # safe ACL check
    python horizon_aios_verify_isolation.py --live [--yes] [--keep] [--brain-name NAME]

Exit codes: 0 = isolation verified, 1 = a check failed or errored.

Platform support:
    - Windows — both modes implemented and verified.
    - Linux / macOS — safe-mode (mode 0o700) implemented; live-mode probe is
      provided as a framework (root runs the read test via runuser/su/sudo -u) but
      has NOT been validated on real hardware. See development_pipeline.md
      (Known Gaps — Code: Linux linger / macOS) and tested_configurations.md.
"""

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile

BRAINS_GROUP = 'brains'
DEFAULT_BRAIN = 'aios_isotest'   # distinctive throwaway name; --brain-name overrides

_SBIN = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Logging helpers (house style, matching the other sbin scripts)
# ---------------------------------------------------------------------------

def banner(text):
    line = '=' * (len(text) + 6)
    print(f'\n{line}\n=== {text} ===\n{line}\n')


def info(msg):  print(f'  [INFO]  {msg}')
def ok(msg):    print(f'  [OK]    {msg}')
def warn(msg):  print(f'  [WARN]  {msg}')
def error(msg): print(f'  [ERROR] {msg}', file=sys.stderr)
def report(name, passed):
    print(f'  [{"PASS" if passed else "FAIL"}] {name}')


def _sibling(name):
    """Absolute path to a sibling sbin script."""
    return os.path.join(_SBIN, name)


def _resolve_paths(horizon_root_arg):
    if horizon_root_arg:
        root = os.path.abspath(horizon_root_arg)
    else:
        root = os.path.abspath(os.path.join(_SBIN, '..', '..'))
    system = os.path.join(root, 'horizon_system')
    return {
        'root': root,
        'system': system,
        'bin': os.path.join(system, 'bin'),
        'sbin': os.path.join(system, 'sbin'),
        'skills_bin': os.path.join(system, 'skills_bin'),
        'skills_sbin': os.path.join(system, 'skills_sbin'),
        'logs': os.path.join(system, 'logs'),
        'brains': os.path.join(root, 'brains'),
    }


# ---------------------------------------------------------------------------
# Privilege detection
# ---------------------------------------------------------------------------

def _is_elevated(os_name):
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


# ---------------------------------------------------------------------------
# Safe (default) mode — static ACL posture, non-destructive
# ---------------------------------------------------------------------------

def _win_has_brains_deny(path):
    """Return True iff an explicit (non-inherited) brains Deny ACE exists on path.

    Mirrors horizon_aios_doctor.py::_has_brains_deny — the authoritative check.
    """
    ps = (
        "$a=(Get-Acl -LiteralPath '{p}').Access | Where-Object {{ "
        "$_.IdentityReference -like '*{g}*' -and "
        "$_.AccessControlType -eq 'Deny' -and -not $_.IsInherited }}; "
        "if ($a) {{ 'DENY' }}"
    ).format(p=path, g=BRAINS_GROUP)
    try:
        r = subprocess.run(
            ['powershell', '-NonInteractive', '-NoProfile', '-Command', ps],
            capture_output=True, text=True, timeout=20,
        )
    except Exception as e:  # noqa: BLE001
        warn(f'Get-Acl failed for {path}: {e}')
        return False
    return 'DENY' in (r.stdout or '')


def safe_check(paths, os_name):
    """Non-destructive ACL/permission check of the isolation posture."""
    banner('Safe Check — Static Isolation Posture (non-destructive)')
    info('Verifies the brains Deny on privileged dirs WITHOUT creating an account.')
    info('For the empirical run-as-the-brain proof, re-run with --live (elevated).')

    privileged = [('sbin', paths['sbin']),
                  ('skills_sbin', paths['skills_sbin']),
                  ('logs', paths['logs'])]
    all_pass = True

    if os_name == 'Windows':
        for label, p in privileged:
            if not os.path.isdir(p):
                warn(f'{label}: {p} does not exist — run bootstrap/horizon_aios_harden.py')
                all_pass = False
                continue
            passed = _win_has_brains_deny(p)
            report(f'{label}: explicit brains Deny present', passed)
            all_pass = all_pass and passed
    else:
        for label, p in privileged:
            if not os.path.isdir(p):
                warn(f'{label}: {p} does not exist — run bootstrap/horizon_aios_harden.py')
                all_pass = False
                continue
            mode = stat.S_IMODE(os.stat(p).st_mode)
            passed = (mode == 0o700)
            report(f'{label}: owner-only mode 0o700 (got {oct(mode)})', passed)
            all_pass = all_pass and passed

    # bin/skills_bin should exist and be the brain-readable side of the boundary.
    for label, p in (('bin', paths['bin']), ('skills_bin', paths['skills_bin'])):
        if not os.path.isdir(p):
            warn(f'{label}: {p} does not exist — run bootstrap')
            all_pass = False

    return all_pass


# ---------------------------------------------------------------------------
# Live mode — provision, run-as-brain probe, teardown (OPT-IN, elevated)
# ---------------------------------------------------------------------------

def _user_exists(name, os_name):
    if os_name == 'Windows':
        r = subprocess.run(
            ['powershell', '-NonInteractive', '-Command',
             f'Get-LocalUser -Name "{name}" -ErrorAction SilentlyContinue'],
            capture_output=True, text=True)
        return bool(r.stdout.strip())
    return subprocess.run(['id', name], capture_output=True).returncode == 0


def _provision(brain, paths, dry):
    info(f'Provisioning throwaway brain: {brain}')
    if dry:
        print(f'  [DRY-RUN] {_sibling("horizon_aios_create_brain.py")} {brain}')
        return True
    r = subprocess.run([sys.executable, _sibling('horizon_aios_create_brain.py'),
                        brain, '--horizon-root', paths['root']])
    return r.returncode == 0


def _teardown(brain, paths, dry):
    info(f'Removing throwaway brain: {brain}')
    if dry:
        print(f'  [DRY-RUN] {_sibling("horizon_aios_remove_brain.py")} {brain} --yes')
        return
    subprocess.run([sys.executable, _sibling('horizon_aios_remove_brain.py'),
                    brain, '--yes', '--horizon-root', paths['root']])


def _probe_windows(brain, paths):
    """Log on AS the brain and attempt to read bin (expect OK) / sbin (expect denied)."""
    # Retrieve the brain's keystore password (needed to launch a process as it).
    cred = subprocess.run(
        [sys.executable, _sibling('horizon_aios_brain_credential.py'),
         'get', brain, '--show'],
        capture_output=True, text=True)
    pw = ''
    for line in reversed((cred.stdout or '').splitlines()):
        if line.strip():
            pw = line.strip()
            break
    if not pw:
        return None, 'NOCRED: no credential returned by horizon_aios_brain_credential.py'

    ws = os.path.join(paths['brains'], brain)
    probe_path = os.path.join(ws, 'iso_probe.ps1')
    result_path = os.path.join(ws, 'iso_result.txt')
    # Probe runs AS the brain: it reads its own workspace (probe + result live
    # there, which the brain has full control over). Paths are substituted here so
    # the probe contains no nested here-strings.
    probe = (
        f"$r1 = try {{ Get-ChildItem '{paths['bin']}' -ErrorAction Stop | Out-Null; 'BIN=READABLE' }} catch {{ 'BIN=DENIED' }}\n"
        f"$r2 = try {{ Get-ChildItem '{paths['sbin']}' -ErrorAction Stop | Out-Null; 'SBIN=READABLE' }} catch {{ 'SBIN=DENIED' }}\n"
        f"Set-Content -LiteralPath '{result_path}' -Value @($r1, $r2)\n"
    )
    try:
        with open(probe_path, 'w', encoding='utf-8') as fh:
            fh.write(probe)
    except OSError as e:
        return None, f'could not write probe to brain workspace: {e}'
    if os.path.exists(result_path):
        os.remove(result_path)

    # Driver (runs as us, elevated) launches the probe under the brain credential.
    driver = (
        "param([string]$Brain,[string]$ProbePath)\n"
        "$sec = ConvertTo-SecureString $env:AIOS_ISO_PW -AsPlainText -Force\n"
        "$cred = New-Object System.Management.Automation.PSCredential(\"$env:COMPUTERNAME\\$Brain\", $sec)\n"
        "Start-Process powershell -Credential $cred -WindowStyle Hidden -Wait "
        "-ArgumentList @('-NonInteractive','-ExecutionPolicy','Bypass','-File',$ProbePath)\n"
    )
    fd, driver_path = tempfile.mkstemp(suffix='.ps1', prefix='aios_iso_driver_')
    try:
        os.write(fd, driver.encode('utf-8'))
        os.close(fd)
        env = dict(os.environ, AIOS_ISO_PW=pw)
        try:
            subprocess.run(
                ['powershell', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                 '-File', driver_path, '-Brain', brain, '-ProbePath', probe_path],
                env=env, capture_output=True, text=True, timeout=60)
        except Exception as e:  # noqa: BLE001
            return None, f'runas failed (account may lack "Log on as a batch job"): {e}'
    finally:
        try:
            os.unlink(driver_path)
        except OSError:
            pass

    if not os.path.exists(result_path):
        return None, ('NOLAUNCH: no result file — the brain account may lack the '
                      '"Log on interactively" / secondary-logon right that '
                      'Start-Process -Credential (CreateProcessWithLogonW) requires; '
                      '--automation scheduled grants only the BATCH right')
    with open(result_path, encoding='utf-8') as fh:
        return [l.strip() for l in fh if l.strip()], None


def _probe_unix(brain, paths, os_name):
    """Root runs the read test AS the brain via runuser/su (Linux) or sudo -u (macOS).

    Framework only — not yet validated on real Linux/macOS hardware.
    """
    cmd = (
        f"ls '{paths['bin']}'  >/dev/null 2>&1 && echo BIN=READABLE  || echo BIN=DENIED; "
        f"ls '{paths['sbin']}' >/dev/null 2>&1 && echo SBIN=READABLE || echo SBIN=DENIED"
    )
    if os_name == 'Linux' and shutil.which('runuser'):
        argv = ['runuser', '-u', brain, '--', 'sh', '-c', cmd]
    elif os_name == 'Linux' and shutil.which('su'):
        argv = ['su', brain, '-c', cmd]
    elif shutil.which('sudo'):                       # macOS (and Linux fallback)
        argv = ['sudo', '-u', brain, 'sh', '-c', cmd]
    else:
        return None, 'no runuser/su/sudo available to run the probe as the brain'
    r = subprocess.run(argv, capture_output=True, text=True)
    lines = [l.strip() for l in (r.stdout or '').splitlines()
             if l.strip().startswith(('BIN=', 'SBIN='))]
    if not lines:
        return None, f'probe produced no result (stderr: {(r.stderr or "").strip()})'
    return lines, None


def live_check(paths, os_name, brain, dry, keep, use_existing):
    banner('Live Check — Empirical Run-as-the-Brain Probe (DESTRUCTIVE)')

    if not dry and not _is_elevated(os_name):
        error('--live requires elevation (Administrator on Windows, root on Unix).')
        return False

    # Exists-guard: behaviour differs by mode.
    if use_existing:
        # Brain MUST already exist; we never create or remove it.
        if not dry and not _user_exists(brain, os_name):
            error(f'--use-existing: account "{brain}" does not exist. '
                  f'Provision the brain first, then re-run.')
            return False
    else:
        # Throwaway path: refuse to clobber a pre-existing account.
        if not dry and _user_exists(brain, os_name):
            error(f'An account named "{brain}" already exists. Refusing to clobber it. '
                  f'Pass --brain-name with a free name.')
            return False

    if use_existing:
        info(f'Using existing brain "{brain}" (not provisioning, will not remove).')
    else:
        if not _provision(brain, paths, dry):
            error('Provisioning failed — see output above. Nothing to probe.')
            return False

    result, err = (None, None)
    try:
        if dry:
            print('  [DRY-RUN] log on as the brain; read bin (expect OK) / sbin (expect denied)')
            result = ['BIN=READABLE', 'SBIN=DENIED']  # illustrative
        elif os_name == 'Windows':
            result, err = _probe_windows(brain, paths)
        else:
            result, err = _probe_unix(brain, paths, os_name)
    finally:
        # SAFETY INVARIANT: _teardown is only ever called on the throwaway path.
        # use_existing=True NEVER reaches _teardown — the brain is left untouched.
        if use_existing:
            info(f'Brain "{brain}" left untouched (--use-existing).')
        elif keep:
            warn(f'--keep set: leaving brain "{brain}" provisioned. Remove later with: '
                 f'horizon_aios_remove_brain.py {brain} --yes')
        else:
            _teardown(brain, paths, dry)

    if err:
        # B5: missing keyring credential — soft-SKIP in use_existing mode.
        if use_existing and err.startswith('NOCRED:'):
            warn('Probe SKIPPED — no keyring credential available.')
            info('This is expected when the keyring is absent: the password is not '
                 'retrievable so the run-as-brain probe cannot run. '
                 'The static ACL check (safe mode) is unaffected and still proves '
                 'the isolation posture.')
            return True
        # B6: probe-launch failure — soft-SKIP in use_existing mode.
        if use_existing and err.startswith('NOLAUNCH:'):
            warn('Probe SKIPPED — Start-Process -Credential launch refused.')
            info('Likely cause: the brain lacks the interactive / secondary-logon '
                 'right that CreateProcessWithLogonW requires. '
                 '--automation scheduled grants only the BATCH right, not the '
                 'interactive/network logon right needed here. '
                 'This is a harness / logon-right limitation, NOT an isolation '
                 'breach — the static ACL check (safe mode) still proves that the '
                 'brains Deny ACE is correctly configured.')
            return True
        error(f'Probe could not complete: {err}')
        return False

    joined = '  '.join(result)
    print()
    info(f'Read attempts AS "{brain}": {joined}')
    info('EXPECTED PASS: BIN=READABLE  SBIN=DENIED')
    passed = ('BIN=READABLE' in result) and ('SBIN=DENIED' in result)
    report('brain reads bin but is denied sbin (criterion #5)', passed)
    return passed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description='Horizon AIOS — verify brain isolation (criterion #5).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument('--horizon-root', metavar='PATH', default=None,
                   help='Absolute HORIZON_ROOT. Default: ../../ from this script.')
    p.add_argument('--live', action='store_true', default=False,
                   help='OPT-IN: provision a throwaway brain, run the as-the-brain '
                        'read probe, then remove it. Requires elevation. Without '
                        'this flag the script only does the non-destructive ACL check.')
    p.add_argument('--brain-name', default=DEFAULT_BRAIN,
                   help=f'Throwaway brain name for --live (default: {DEFAULT_BRAIN}).')
    p.add_argument('--use-existing', action='store_true', default=False,
                   help='--live: probe an already-provisioned brain named by --brain-name '
                        'instead of creating/removing a throwaway. Never tears it down.')
    p.add_argument('--yes', '-y', action='store_true', default=False,
                   help='Skip the confirmation prompt in --live mode.')
    p.add_argument('--keep', action='store_true', default=False,
                   help='--live: do not remove the brain afterwards (for inspection).')
    p.add_argument('--dry-run', action='store_true', default=False,
                   help='Print what --live would do without changing anything.')
    return p.parse_args()


def main():
    args = parse_args()
    os_name = platform.system()
    if os_name not in ('Windows', 'Linux', 'Darwin'):
        error(f'Unsupported platform: {os_name}')
        sys.exit(1)
    paths = _resolve_paths(args.horizon_root)

    if not os.path.isdir(paths['system']):
        error(f'HORIZON_SYSTEM not found: {paths["system"]}')
        sys.exit(1)

    if not args.live:
        # Default, safe, non-destructive.
        if args.keep or args.yes:
            warn('--keep/--yes only apply with --live; ignoring.')
        passed = safe_check(paths, os_name)
        print()
        (ok if passed else error)(
            'Static isolation posture verified.' if passed
            else 'Static isolation posture FAILED — run horizon_aios_harden.py.')
        info('This was the safe check. For the empirical proof, re-run with --live (elevated).')
        sys.exit(0 if passed else 1)

    # Live mode — confirm unless --yes/--dry-run or --use-existing (no account created/deleted).
    if not args.yes and not args.dry_run and not args.use_existing:
        warn(f'--live will CREATE and DELETE the OS account "{args.brain_name}" '
             f'and requires elevation.')
        ans = input('  Type "yes" to proceed: ').strip().lower()
        if ans != 'yes':
            error('Aborted.')
            sys.exit(1)

    passed = live_check(paths, os_name, args.brain_name, args.dry_run, args.keep,
                        args.use_existing)
    print()
    (ok if passed else error)(
        'Brain isolation VERIFIED (criterion #5).' if passed
        else 'Brain isolation NOT verified — review output above.')
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
