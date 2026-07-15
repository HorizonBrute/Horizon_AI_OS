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
import stat
import subprocess
import sys
import time

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


def _rmtree_clear_readonly(path):
    """rmtree a Windows PROFILE tree, clearing READONLY on the way down.

    Windows stamps READONLY on a profile's shell folders (Documents, Music, Pictures,
    Videos, Favorites, WinX/GroupN...) to mark them shell-customized (desktop.ini). A
    READONLY *directory* cannot be removed and fails as a bare WinError 5 "Access is
    denied" — which reads like a permissions problem but is not one, so elevation /
    takeown / icacls never help, and neither does a reboot (it does not clear an
    attribute). Leaving the profile behind makes the next create-brain mint a new SID +
    a <name>.NNN profile, orphaning a ProfileList entry every cycle.

    os.chmod on Windows maps to exactly one bit: READONLY. Clear it, then retry.
    """
    def _retry(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    # 3.12 deprecated onerror in favour of onexc; this callable fits both signatures.
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_retry)
    else:
        shutil.rmtree(path, onerror=_retry)


# --- Profile handle release (the WinError 32 layer, under the READONLY one) -------------
#
# Clearing READONLY (above) fixes WinError 5. A SECOND blocker sits underneath it and shows
# up as WinError 32 "used by another process":
#
#   1. The deleted account's hives (HKU\<SID> + HKU\<SID>_Classes) stay MOUNTED. A mounted
#      hive IS an open handle on NTUSER.DAT / UsrClass.dat. This is the grain of truth in the
#      old "loaded NTUSER.DAT hive" warning, but its remedy was wrong: a reboot is NOT needed.
#      `reg unload` also fails here — an elevated token leaves SeRestorePrivilege DISABLED,
#      and open keys inside the hive defeat a non-forced unload. Enable the privilege and call
#      NtUnloadKey2(REG_FORCE_UNLOAD): it evicts the hive in place.
#   2. A live process holds a file INSIDE the profile (observed: wslsettings.exe pinning
#      AppData\LocalLow\Intel\ShaderCache\*, which `wsl --shutdown` does NOT kill).
#
# Mirrors windows_deploy_brain.py's helpers of the same names — duplicated deliberately: this
# provisioner must run on hosts that have no factory tree (same reason _rmtree_clear_readonly
# is duplicated). Keep the two in sync.

_REG_FORCE_UNLOAD = 1
_SE_PRIVILEGE_ENABLED = 0x2
_TOKEN_ADJUST_PRIVILEGES = 0x20
_TOKEN_QUERY = 0x8
_OBJ_CASE_INSENSITIVE = 0x40


def _windows_brain_sid(brain_name):
    """Resolve the brain account's SID, or None. MUST be called while the account still
    exists — it keys the HKU hives, and Get-LocalUser stops resolving once it is deleted."""
    r = subprocess.run(['powershell', '-NonInteractive', '-Command',
                        f'(Get-LocalUser -Name "{brain_name}" '
                        f'-ErrorAction SilentlyContinue).SID.Value'],
                       capture_output=True, text=True)
    return (r.stdout or '').strip() or None


def _enable_privilege(name):
    """Enable a privilege the elevated token HOLDS but leaves DISABLED (else the unload
    returns STATUS_PRIVILEGE_NOT_HELD). Returns True on success."""
    import ctypes
    from ctypes import wintypes

    class _LUID(ctypes.Structure):
        _fields_ = [('LowPart', wintypes.DWORD), ('HighPart', ctypes.c_long)]

    class _LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [('Luid', _LUID), ('Attributes', wintypes.DWORD)]

    class _TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [('PrivilegeCount', wintypes.DWORD),
                    ('Privileges', _LUID_AND_ATTRIBUTES * 1)]

    advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    # Explicit prototypes are required on x64: without them GetCurrentProcess's (HANDLE)-1
    # is truncated to 32 bits and the call silently fails.
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                          ctypes.POINTER(wintypes.HANDLE)]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
                                               ctypes.POINTER(_LUID)]
    advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
    advapi32.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL,
                                               ctypes.POINTER(_TOKEN_PRIVILEGES),
                                               wintypes.DWORD, ctypes.c_void_p,
                                               ctypes.c_void_p]
    advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(),
                                     _TOKEN_ADJUST_PRIVILEGES | _TOKEN_QUERY,
                                     ctypes.byref(token)):
        return False
    try:
        luid = _LUID()
        if not advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
            return False
        tp = _TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = _SE_PRIVILEGE_ENABLED
        ctypes.set_last_error(0)
        if not advapi32.AdjustTokenPrivileges(token, False, ctypes.byref(tp),
                                              ctypes.sizeof(tp), None, None):
            return False
        # Succeeds with ERROR_NOT_ALL_ASSIGNED (1300) if the token lacks the privilege.
        return ctypes.get_last_error() == 0
    finally:
        kernel32.CloseHandle(token)


def _force_unload_profile_hives(sid):
    """Force-unload HKU\\<sid> and HKU\\<sid>_Classes in place. Returns readable results."""
    import ctypes
    from ctypes import wintypes

    class _UNICODE_STRING(ctypes.Structure):
        _fields_ = [('Length', ctypes.c_ushort),
                    ('MaximumLength', ctypes.c_ushort),
                    ('Buffer', ctypes.c_wchar_p)]

    class _OBJECT_ATTRIBUTES(ctypes.Structure):
        _fields_ = [('Length', ctypes.c_ulong),
                    ('RootDirectory', ctypes.c_void_p),
                    ('ObjectName', ctypes.POINTER(_UNICODE_STRING)),
                    ('Attributes', ctypes.c_ulong),
                    ('SecurityDescriptor', ctypes.c_void_p),
                    ('SecurityQualityOfService', ctypes.c_void_p)]

    ntdll = ctypes.WinDLL('ntdll')
    ntdll.NtUnloadKey2.argtypes = [ctypes.POINTER(_OBJECT_ATTRIBUTES), ctypes.c_ulong]
    ntdll.NtUnloadKey2.restype = ctypes.c_long
    _enable_privilege('SeRestorePrivilege')
    _enable_privilege('SeBackupPrivilege')

    results = []
    for key in (f'{sid}_Classes', sid):
        nt_path = f'\\Registry\\User\\{key}'
        name = _UNICODE_STRING()
        name.Buffer = nt_path
        name.Length = len(nt_path) * 2
        name.MaximumLength = name.Length + 2
        oa = _OBJECT_ATTRIBUTES()
        oa.Length = ctypes.sizeof(_OBJECT_ATTRIBUTES)
        oa.RootDirectory = None
        oa.ObjectName = ctypes.pointer(name)
        oa.Attributes = _OBJ_CASE_INSENSITIVE
        status = ntdll.NtUnloadKey2(ctypes.byref(oa), _REG_FORCE_UNLOAD) & 0xFFFFFFFF
        # "Not loaded" is the common healthy case and must not read as a failure. Windows
        # reports it as STATUS_INVALID_PARAMETER (0xC000000D) for a non-hive-root name;
        # STATUS_OBJECT_NAME_NOT_FOUND (0xC0000034) is accepted too.
        if status == 0:
            results.append(f'unloaded HKU\\{key}')
        elif status in (0xC000000D, 0xC0000034):
            results.append(f'HKU\\{key} not loaded (nothing to do)')
        else:
            results.append(f'HKU\\{key} unload FAILED (NTSTATUS 0x{status:08X})')
    return results


def _profile_lockers(paths):
    """Restart Manager: [(pid, app_name), ...] holding handles on `paths`. Naming the holder
    is what turns a bare "Access is denied" into an actionable diagnosis."""
    import ctypes
    from ctypes import wintypes

    class _FILETIME(ctypes.Structure):
        _fields_ = [('dwLowDateTime', wintypes.DWORD), ('dwHighDateTime', wintypes.DWORD)]

    class _RM_UNIQUE_PROCESS(ctypes.Structure):
        _fields_ = [('dwProcessId', wintypes.DWORD), ('ProcessStartTime', _FILETIME)]

    class _RM_PROCESS_INFO(ctypes.Structure):
        _fields_ = [('Process', _RM_UNIQUE_PROCESS),
                    ('strAppName', ctypes.c_wchar * 256),
                    ('strServiceShortName', ctypes.c_wchar * 64),
                    ('ApplicationType', ctypes.c_uint),
                    ('AppStatus', ctypes.c_ulong),
                    ('TSSessionId', wintypes.DWORD),
                    ('bRestartable', wintypes.BOOL)]

    try:
        rm = ctypes.WinDLL('rstrtmgr')
    except OSError:
        return []

    session = wintypes.DWORD()
    key = ctypes.create_unicode_buffer(33)
    if rm.RmStartSession(ctypes.byref(session), 0, key) != 0:
        return []
    try:
        arr = (ctypes.c_wchar_p * len(paths))(*paths)
        if rm.RmRegisterResources(session, len(paths), arr, 0, None, 0, None) != 0:
            return []
        needed, count, reasons = wintypes.UINT(), wintypes.UINT(0), wintypes.DWORD()
        rc = rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), None,
                          ctypes.byref(reasons))
        if rc != 234 or needed.value == 0:      # 234 = ERROR_MORE_DATA => there ARE lockers
            return []
        count = wintypes.UINT(needed.value)
        info_arr = (_RM_PROCESS_INFO * needed.value)()
        if rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), info_arr,
                        ctypes.byref(reasons)) != 0:
            return []
        return [(info_arr[i].Process.dwProcessId, info_arr[i].strAppName)
                for i in range(count.value)]
    finally:
        rm.RmEndSession(session)


def _release_profile_handles(profile_dir, sid, dry_run=False):
    """Free a torn-down brain profile so it can actually be deleted. No reboot, ever.

    Only WSL-owned holders are killed: the distro is already gone by this point, so they have
    no business in this profile and are trivially restartable. Anything else is REPORTED, not
    killed — a teardown must never shoot down a user's applications.
    """
    if dry_run:
        print(f'  [DRY-RUN] force-unload HKU\\{sid}[_Classes]; release file holders under '
              f'{profile_dir}')
        return
    if sid:
        for line in _force_unload_profile_hives(sid):
            info(f'  profile hive: {line}')
    else:
        warn('  Brain SID unresolved — leftover HKU hives (if any) not unloaded; the profile '
             'delete may fail with WinError 32.')

    files = []
    for root, _dirs, names in os.walk(profile_dir):
        files.extend(os.path.join(root, n) for n in names)
        if len(files) > 500:                     # a representative sample is enough for RM
            break
    if not files:
        return
    for pid, app in _profile_lockers(files):
        if 'wsl' in (app or '').lower():
            info(f'  Releasing WSL holder of the brain profile: {app} (PID {pid})')
            run(['taskkill', '/PID', str(pid), '/F'], check=False)
        else:
            warn(f'  {app} (PID {pid}) holds a file inside {profile_dir} and was NOT killed — '
                 f'close it and re-run if the profile delete below fails.')


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

    # 0. Capture the SID while the account still resolves — step 2 deletes it, and the SID
    #    keys the HKU hives that step 4 must unload to free the profile. Same reason step 1b
    #    revokes logon rights before the delete.
    brain_sid = _windows_brain_sid(brain_name)

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
        print(f'  [DRY-RUN] rmtree (clearing READONLY) {profile_dir}')
    elif os.path.isdir(profile_dir):
        info(f'Removing user profile directory: {profile_dir}')
        # Release BEFORE the rmtree: READONLY (WinError 5) is cleared on the way down by
        # _rmtree_clear_readonly, but a mounted hive / live file holder (WinError 32) must be
        # cleared up front — no amount of retrying beats an open handle.
        _release_profile_handles(profile_dir, brain_sid, dry_run=False)
        try:
            _rmtree_clear_readonly(profile_dir)
            ok(f'Removed user profile directory: {profile_dir}')
        except OSError as exc:
            warn(f'Could not remove user profile directory {profile_dir}: {exc}')
            warn('  A reboot is NOT the remedy: WinError 5 means READONLY (cleared '
                 'automatically above) and WinError 32 means a live handle — any holder is '
                 'named above. Do NOT leave it: a leftover profile makes the NEXT '
                 'create-brain mint a fresh SID + a <name>.NNN profile, orphaning a '
                 'ProfileList entry each cycle.')
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
    # A WSL distro's ext4.vhdx handle can linger for several seconds after
    # `wsl --unregister` returns, so a bare rmtree loses the race with a
    # WinError 32 (sharing violation) and orphans the ~GB vhdx. Retry with
    # backoff (1,2,4,8,16s) to let the handle release before giving up.
    last_exc = None
    for attempt in range(6):
        try:
            shutil.rmtree(brain_dir)
            ok(f'Removed workspace: {brain_dir}')
            return
        except OSError as exc:
            last_exc = exc
            if attempt < 5:
                delay = 2 ** attempt
                info(f'workspace still locked (vhdx handle releasing); '
                     f'retry {attempt + 1}/5 in {delay}s...')
                time.sleep(delay)
    warn(f'Could not fully remove {brain_dir} after retries: {last_exc}')


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
