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
    - User profile dir           Windows: every path ProfileList records for this brain
                                 (ProfileImagePath — NOT C:\\Users\\<brain>; Windows suffixes a
                                  colliding profile, e.g. C:\\Users\\<brain>.LEATHERDECK), plus
                                  its ProfileList row
                                 Unix: <home> (via userdel -r)
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
    _strip_junctions(path)

    def _retry(func, p, _exc):
        if _is_reparse(p):
            os.rmdir(p)          # a junction that appeared mid-walk: drop the LINK
            return
        os.chmod(p, stat.S_IWRITE)
        func(p)
    # 3.12 deprecated onerror in favour of onexc; this callable fits both signatures.
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_retry)
    else:
        shutil.rmtree(path, onerror=_retry)


def _is_reparse(p):
    isjunction = getattr(os.path, 'isjunction', None)
    try:
        return bool(isjunction and isjunction(p)) or os.path.islink(p)
    except OSError:
        return False


def _strip_junctions(root):
    """Delete the legacy shell-folder JUNCTIONS inside a profile before the rmtree.

    Every Windows profile carries pre-Vista compatibility junctions (Documents\\My Music,
    My Pictures, My Videos, Application Data, Local Settings, …). Each one has an explicit
    DENY ACE precisely so applications cannot enumerate it — so rmtree hits a bare
    "WinError 5 Access is denied" ON THE JUNCTION, which reads like the READONLY problem but
    is not one: clearing READONLY and retrying cannot fix a Deny ACE, and elevation does not
    override it either.

    Removing them link-first is also the SAFE order: os.rmdir on a reparse point removes only
    the link, never the target. Descending into one would delete the target's contents, and
    some of these targets are elsewhere in the profile.
    """
    removed = 0
    for dirpath, dirnames, _files in os.walk(root, topdown=True):
        for d in list(dirnames):
            p = os.path.join(dirpath, d)
            if _is_reparse(p):
                dirnames.remove(d)        # never descend into a reparse point
                try:
                    os.rmdir(p)
                    removed += 1
                except OSError:
                    pass                  # rmtree/_retry reports it if it still blocks
    if removed:
        info(f'  cleared {removed} shell-folder junction(s) from the profile')
    return removed


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
#   2. The WSL utility VM holds AppData\Local\Temp\<guid>\swap.vhdx. Unregistering the distro
#      does NOT stop the VM, and Restart Manager CANNOT see this holder — the VHDX is owned by
#      vmmemWSL, not by a user-mode process with an ordinary handle, so _profile_lockers names
#      nobody and there is no PID to kill. `wsl --shutdown` is the only remedy.
#   3. A live process holds a file INSIDE the profile (observed: wslsettings.exe pinning
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


def _profile_name_re(brain_name):
    """Match a profile directory belonging to `brain_name`: the plain name, or one of Windows'
    collision suffixes (<name>.LEATHERDECK, then <name>.LEATHERDECK.000, .001, ...).

    Anchored and dot-delimited deliberately. A bare prefix glob (`<name>*`) would make brain
    `test` claim `testbrain`'s profile — deleting another live brain's profile is the worst
    failure this script could have, so the suffix must be a real dot-separated one.
    """
    return re.compile(rf'^{re.escape(brain_name)}(\.[^\\/]*)?$', re.IGNORECASE)


def _profilelist_rows():
    """[(sid, expanded ProfileImagePath), ...] for every row in ProfileList."""
    r = subprocess.run(
        ['powershell', '-NonInteractive', '-NoProfile', '-Command',
         r'Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList" | '
         'ForEach-Object { $p = (Get-ItemProperty $_.PSPath -Name ProfileImagePath '
         '-ErrorAction SilentlyContinue).ProfileImagePath; '
         'if ($p) { "$($_.PSChildName)|'
         '$([Environment]::ExpandEnvironmentVariables($p))" } }'],
        check=False, capture_output=True, text=True)
    rows = []
    for line in (r.stdout or '').splitlines():
        sid, sep, path = line.strip().partition('|')
        if sep and sid and path:
            rows.append((sid, path.rstrip('\\/')))
    return rows


def _windows_brain_sid(brain_name):
    """Resolve the brain account's SID, or None.

    Prefers Get-LocalUser, which is authoritative while the account exists. Falls back to the
    ProfileList row whose ProfileImagePath BASENAME is this brain's (plain or suffixed): a
    teardown that fails partway leaves the profile + row behind but deletes the ACCOUNT, and
    without this fallback the SID is unrecoverable — the re-run cannot unload the hives or drop
    the row, so the residue is stuck forever and only a human with an rmtree can clear it.
    Teardown must be able to finish its own unfinished work.

    Matching on the basename, not on a constructed C:\\Users\\<brain>, is what lets the fallback
    see a SUFFIXED profile at all — see _windows_profile_dir.
    """
    r = subprocess.run(['powershell', '-NonInteractive', '-Command',
                        f'(Get-LocalUser -Name "{brain_name}" '
                        f'-ErrorAction SilentlyContinue).SID.Value'],
                       capture_output=True, text=True)
    sid = (r.stdout or '').strip()
    if sid:
        return sid

    pat = _profile_name_re(brain_name)
    hits = [(s, p) for s, p in _profilelist_rows() if pat.match(os.path.basename(p))]
    if hits:
        # Several rows are the NORMAL residue shape here, not an anomaly: each failed cycle
        # suffixes another profile (testbrain.LEATHERDECK, then .LEATHERDECK.000). They are all
        # this brain's, and none can belong to a live account — Get-LocalUser just found none by
        # this name. The first is returned for hive-unload/logon-rights; _windows_profile_targets
        # collects every one of them for removal.
        for s, p in hits:
            info(f'  account gone; recovered SID from ProfileList: {s} ({p})')
        return hits[0][0]
    return None


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


def _wait_for_wsl_vm_exit(timeout=90):
    """Block until the WSL utility VM process is really gone.

    `wsl --shutdown` is ASYNCHRONOUS: it returns as soon as the shutdown is requested, while
    vmmemWSL keeps running for seconds afterwards and keeps swap.vhdx open. Deleting the
    profile straight after the call therefore races the VM and loses — WinError 32 on
    swap.vhdx, with the VM exiting moments later and leaving the residue behind. Waiting for
    the process to disappear is what makes the stop actually mean stopped.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = subprocess.run(
            ['powershell', '-NonInteractive', '-Command',
             '@(Get-Process -Name vmmemWSL,vmmem -ErrorAction SilentlyContinue).Count'],
            check=False, capture_output=True, text=True)
        if (r.stdout or '').strip() == '0':
            info('  WSL VM stopped (swap.vhdx released)')
            return True
        time.sleep(1)
    warn(f'  WSL VM still running {timeout}s after `wsl --shutdown` — the profile delete below '
         f'will likely fail with WinError 32 on swap.vhdx.')
    return False


_wsl_vm_stopped = False


def _stop_wsl_vm():
    """Stop the WSL utility VM and its GUI apps, which hold files inside a brain profile.

    Unconditional: Restart Manager cannot name vmmemWSL, so there is nothing to detect and no
    PID to kill — the only way to release swap.vhdx is to stop the VM. Safe at this point: the
    brain's distro is already unregistered, and any other distro restarts on next use.
    `wsl --shutdown` stops distros but NOT the WSL GUI apps, so wslsettings is killed by name.

    Once per run: a brain with several suffixed profiles has several targets, and the VM does
    not come back on its own between them — re-stopping would just re-pay the exit wait.
    """
    global _wsl_vm_stopped
    if _wsl_vm_stopped:
        return
    _wsl_vm_stopped = True
    info('  Stopping the WSL VM (holds swap.vhdx inside the brain profile)')
    subprocess.run(['wsl', '--shutdown'], check=False, capture_output=True, text=True)
    subprocess.run(['taskkill', '/IM', 'wslsettings.exe', '/F'],
                   check=False, capture_output=True, text=True)
    _wait_for_wsl_vm_exit()


def _profilelist_key(sid):
    return (r'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList' '\\' + sid)


def _profilelist_entry_exists(sid):
    if not sid:
        return False
    r = subprocess.run(['powershell', '-NonInteractive', '-Command',
                        f'if (Test-Path "{_profilelist_key(sid)}") {{ "yes" }}'],
                       check=False, capture_output=True, text=True)
    return (r.stdout or '').strip() == 'yes'


def _remove_profilelist_entry(sid, dry_run=False):
    """Delete the account's ProfileList row.

    Remove-LocalUser does NOT remove it. A row left behind — even pointing at a directory that
    is already gone — is what makes the next create-brain mint a fresh SID and a <name>.NNN
    profile, orphaning a row per cycle. Removing the directory alone does not break the pileup.
    """
    if not sid:
        return
    if dry_run:
        print(f'  [DRY-RUN] remove ProfileList row {sid}')
        return
    r = subprocess.run(
        ['powershell', '-NonInteractive', '-Command',
         f'$k = "{_profilelist_key(sid)}"; '
         f'if (Test-Path $k) {{ Remove-Item -LiteralPath $k -Recurse -Force; "removed" }} '
         f'else {{ "absent (nothing to do)" }}'],
        check=False, capture_output=True, text=True)
    out = (r.stdout or '').strip()
    if r.returncode == 0 and out:
        info(f'  ProfileList row {sid}: {out}')
    else:
        warn(f'  Could not remove ProfileList row {sid}: {(r.stderr or "").strip()}')


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
    _stop_wsl_vm()
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

def _users_dir():
    return os.path.join(os.environ.get('SystemDrive', 'C:') + '\\', 'Users')


def _windows_profile_targets(brain_name, sid):
    """Every (sid_or_None, directory) pair that is this brain's profile residue.

    NEVER construct C:\\Users\\<brain>. When Windows cannot use the plain profile name — a
    leftover directory, a mounted hive, a name collision — it creates the profile under a
    SUFFIXED one (C:\\Users\\<brain>.LEATHERDECK, then .000 on repeat collisions) and records the
    real path in ProfileList\\<SID>\\ProfileImagePath. That row is the only authority for where a
    profile actually is. Deriving the path from the USERNAME instead is the mechanism that
    generated every orphan on this box: the teardown deleted the constructed path (absent, or an
    unrelated stray), never touched the real profile, and exited 0 — a wrong path does not fail
    loudly, it succeeds at deleting nothing.

    Three sources, because each one alone misses a case that is live on this box today:
      - ProfileList\\<sid>\\ProfileImagePath — the authority for the current account's profile,
        and the only thing that knows a suffixed path.
      - Rows whose path basename is <brain>[.suffix] — residue from an earlier teardown whose
        account is already gone, which the SID lookup above can no longer reach.
      - C:\\Users\\<brain>[.suffix] directories with NO row — a profile whose row was dropped
        while the directory survived. Not a rare corner: several brains on this box have a
        directory and no row right now, and ProfileImagePath alone would never see them.

    A directory claimed by some OTHER account's row is never a target: that is someone else's
    profile and deleting it would be catastrophic.
    """
    pat = _profile_name_re(brain_name)
    rows = _profilelist_rows()
    targets = {}

    for row_sid, path in rows:
        if (sid and row_sid.lower() == sid.lower()) or pat.match(os.path.basename(path)):
            targets[os.path.normcase(path)] = (row_sid, path)

    claimed = {os.path.normcase(p) for _s, p in rows}
    try:
        entries = os.listdir(_users_dir())
    except OSError:
        entries = []
    for name in entries:
        path = os.path.join(_users_dir(), name)
        key = os.path.normcase(path)
        if key in targets or not pat.match(name) or not os.path.isdir(path):
            continue
        if key in claimed:
            warn(f'  {path} is claimed by another account\'s ProfileList row — leaving it alone.')
            continue
        targets[key] = (None, path)

    return sorted(targets.values(), key=lambda t: t[1].lower())


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


def _delete_profile_via_api(sid, profile_dir):
    """Delete the profile the SUPPORTED way: Win32_UserProfile.Delete().

    This is what Windows itself uses. It removes the profile DIRECTORY and its ProfileList row
    together, in the right context, and it copes with what a hand-written rmtree cannot: the
    legacy shell-folder junctions (Documents\\My Music, …) are SYSTEM-owned and carry an
    explicit Everyone:(DENY)(RD) ACE. Explicit Deny beats an Administrator's INHERITED Allow,
    so rmdir/takeown/icacls are denied even ELEVATED and even AS SYSTEM (SYSTEM is in Everyone).
    They are undeletable in place by any principal — but Windows deletes the profile as a whole
    just fine.

    THE ONE HARD REQUIREMENT: the WSL VM must already be STOPPED. The API copes with ACLs, not
    with live handles — vmmemWSL holding swap.vhdx makes it fail "being used by another process".
    It gets one attempt, so calling it against a running VM does not merely fail, it forfeits the
    only mechanism that can finish the job (rmtree cannot beat the Deny'd junctions).

    It does NOT require a live account — 2026-07-15, verified: this deleted the dir AND the
    ProfileList row for an account that Remove-LocalUser had already removed, given only a SID
    recovered from ProfileList. An earlier docstring asserted a live account as a hard
    requirement and made profile-before-account "the whole ballgame"; that misread a
    handle-in-use failure as an account-resolution failure. Profile-before-account is retained
    because it is the sane order, not because the API depends on it.

    Returns True only if the profile is really gone — VERIFIED, not merely reported. A clean
    Remove-CimInstance is not proof: it has been observed returning success while leaving the
    directory on disk, which printed an [OK] on one line and "falling back to manual profile
    removal" on the next. Success is the postcondition (dir gone AND row gone), so that is what
    is checked, and the [OK] is emitted only once it holds.
    """
    if not sid:
        return False
    ps = (f'$p = Get-CimInstance Win32_UserProfile -Filter "SID=\'{sid}\'" '
          f'-ErrorAction SilentlyContinue; '
          f'if (-not $p) {{ "absent"; exit 0 }}; '
          f'try {{ $p | Remove-CimInstance -ErrorAction Stop; "deleted" }} '
          f'catch {{ "failed: $($_.Exception.Message)" }}')
    r = subprocess.run(['powershell', '-NonInteractive', '-NoProfile', '-Command', ps],
                       check=False, capture_output=True, text=True)
    out = (r.stdout or '').strip()

    if out not in ('deleted', 'absent'):
        warn(f'  Win32_UserProfile.Delete() did not succeed for {sid}: {out or r.stderr.strip()}')
        return False

    leftover = []
    if profile_dir and os.path.isdir(profile_dir):
        leftover.append(f'directory {profile_dir}')
    if _profilelist_entry_exists(sid):
        leftover.append(f'ProfileList row {sid}')
    if leftover:
        warn(f'  Win32_UserProfile.Delete() reported "{out}" for {sid} but left '
             f'{" and ".join(leftover)} behind — treating as FAILED.')
        return False

    if out == 'absent':
        info(f'  no Win32_UserProfile for {sid} (nothing to delete)')
    else:
        ok(f'  profile deleted via Win32_UserProfile.Delete() (dir + ProfileList row): {sid}')
    return True


def _remove_windows_profiles(targets, dry_run):
    """Remove every profile in `targets` — [(sid_or_None, dir), ...] from
    _windows_profile_targets. Returns True only if all of them are really gone."""
    if not targets:
        info('No profile directory or ProfileList row to remove.')
        return True
    return all([_remove_one_windows_profile(d, s, dry_run) for s, d in targets])


def _remove_one_windows_profile(profile_dir, sid, dry_run):
    """Remove one brain profile: release handles, supported API, manual as fallback.

    What is load-bearing is STOPPING THE VM FIRST, not the account ordering. The manual path is
    the source of every WinError 5 (READONLY, Deny'd junctions) and WinError 32 (mounted hives,
    vmmemWSL holding swap.vhdx) in this teardown's history, so the job is to never need it: give
    the API the one condition it requires and it takes the dir and the ProfileList row together.

    Returns True only if the directory and the ProfileList row are both gone.
    """
    if dry_run:
        print(f'  [DRY-RUN] stop WSL VM + unload hives, Win32_UserProfile.Delete() for '
              f'{sid or profile_dir}, else rmtree {profile_dir}')
        return True

    dir_exists = bool(profile_dir) and os.path.isdir(profile_dir)
    if not dir_exists and not _profilelist_entry_exists(sid):
        info(f'No user profile directory at: {profile_dir}')
        return True

    # A row whose ProfileImagePath is already gone is residue on its own: it is what makes the
    # next create-brain mint a fresh SID and a suffixed profile. Drop it — there is nothing to
    # release handles on, and no directory for the API to delete.
    if not dir_exists:
        info(f'ProfileList row {sid} points at {profile_dir}, which is gone — removing the row.')
        _remove_profilelist_entry(sid)
        return not _profilelist_entry_exists(sid)

    info(f'Removing user profile: {profile_dir}')

    # Releasing the handles is a PRECONDITION OF THE API, not a fallback step. Win32_UserProfile
    # .Delete() is not magic about live handles: with the VM up it fails "being used by another
    # process" on swap.vhdx and burns its single attempt, dropping us into the manual path — and
    # the manual path CANNOT finish, because the Deny'd junctions are undeletable in place. That
    # is a guaranteed teardown failure, and it is exactly what shipping this call before the stop
    # produced. Stop the VM and unload the hives FIRST, then let the supported API do its job.
    _release_profile_handles(profile_dir, sid, dry_run=False)

    if _delete_profile_via_api(sid, profile_dir):
        _remove_profilelist_entry(sid)          # no-op if the API already took the row
        return True

    # FALLBACK: the API could not do it — no SID resolved at all, or WMI refused. NOT "the
    # account is gone": that was measured 2026-07-15 and the API handles it fine. Handles are
    # already released above; delete by hand and fail loudly if that cannot finish.
    warn('  falling back to manual profile removal (the supported API could not be used)')
    # Two attempts, because the hives are the one blocker worth re-clearing: a handle can be
    # re-taken between the release above and the rmtree. Anything still holding after a second
    # unload is not going to yield to a third.
    for attempt in (1, 2):
        try:
            _rmtree_clear_readonly(profile_dir)
            ok(f'Removed user profile directory: {profile_dir}')
            # ONLY on success. The row is the sole way to recover the SID once the account is
            # gone (_windows_brain_sid's fallback); dropping it while the directory survives
            # strands the residue permanently and only a human can finish the job.
            _remove_profilelist_entry(sid)
            return True
        except OSError as exc:
            if attempt == 1:
                warn(f'  manual removal blocked ({exc}) — re-unloading the hives and retrying.')
                _release_profile_handles(profile_dir, sid, dry_run=False)
                continue
            warn(f'Could not remove user profile directory {profile_dir}: {exc}')
            warn('  Keeping the ProfileList row: it is what lets a re-run recover the SID and '
                 'finish this teardown.')
            # NEVER rename the directory aside to free the name. It looks like success, exits 0,
            # and leaves a profile nobody is tracking — that is precisely how the residue on this
            # box accumulated unnoticed. A teardown that cannot finish must SAY so and exit
            # non-zero, so the next run (or a human) knows there is work left.
            warn('  Do NOT rename the profile aside to free the name — a silent rename is how '
                 'orphans accumulate. This teardown is INCOMPLETE and exits non-zero.')
            warn('  WinError 5 = READONLY (cleared above) or a SYSTEM-owned junction with an '
                 'explicit Deny; WinError 32 = a live handle (any user-mode holder is named '
                 'above). Getting here means the supported API was skipped or refused — fix '
                 'THAT first. If the holder cannot be named or killed, REBOOT and re-run: the '
                 'reboot drops the handle, and the re-run finishes from the ProfileList row.')
            return False


def remove_windows(brain_name, brain_dir, dry_run):
    brain_group = f'{brain_name}_group'                 # per-brain group is <name>_group on Windows

    # 0. SID FIRST — the profile path is derived FROM it (ProfileList\<SID>\ProfileImagePath),
    #    never from the username, and Get-LocalUser stops resolving the moment the account is
    #    gone. Everything below operates on the paths Windows actually recorded.
    brain_sid = _windows_brain_sid(brain_name)
    targets = _windows_profile_targets(brain_name, brain_sid)
    for tsid, tdir in targets:
        info(f'Brain profile: {tdir}   (ProfileList row: {tsid or "none"})')

    # 1. Remove reparse points FIRST, so no later recursive delete can follow a
    #    symlink into the workspace or into skills_bin. Covers both the new
    #    topology (~/.claude -> workspace) and the old one (~/.claude/skills).
    for _tsid, tdir in targets:
        _remove_reparse(os.path.join(tdir, '.claude'), dry_run)
        _remove_reparse(os.path.join(tdir, '.claude', 'skills'), dry_run)

    # 2. PROFILE BEFORE ACCOUNT. This ordering is the whole ballgame — see
    #    _delete_profile_via_api. The account must still exist here.
    _remove_windows_profiles(targets, dry_run)

    # 3. Revoke any AIOS automation logon rights BEFORE deleting the account,
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

    # 4. Remove the OS user account. AFTER the profile — never before it.
    if dry_run or user_exists(brain_name, 'Windows'):
        run_ps(f'Remove-LocalUser -Name "{brain_name}"', dry_run=dry_run)
    else:
        info(f'User does not exist (skipping): {brain_name}')

    # 5. Remove the per-brain group (leave the shared `brains` group).
    if dry_run or group_exists(brain_group, 'Windows'):
        run_ps(f'Remove-LocalGroup -Name "{brain_group}"', dry_run=dry_run)
    else:
        info(f'Per-brain group does not exist (skipping): {brain_group}')

    # 6. Remove the workspace folder (its skills symlink is cleared first).
    _remove_workspace(brain_dir, dry_run)
    return brain_sid


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
    # Profile residue counts as a trace. A teardown that failed at the profile step deletes the
    # account/group/workspace first, so user/group/workspace alone are all absent while the
    # profile is still on disk — short-circuiting on those three made the re-run print "Nothing
    # to do", exit 0, and strand the residue that mints the NEXT deploy's suffixed profile.
    # Resolved from ProfileList, never constructed: a suffixed profile is invisible to a
    # C:\Users\<brain> check, which is how this short-circuit used to miss the very residue it
    # exists to catch.
    profile_residue = (_windows_profile_targets(brain_name, _windows_brain_sid(brain_name))
                       if os_name == 'Windows' else [])
    if not exists_user and not exists_ws and not profile_residue \
            and not group_exists(per_brain_group, os_name):
        warn(f'No trace of brain "{brain_name}" (user/group/workspace/profile). Nothing to do.')
        sys.exit(0)
    if profile_residue and not exists_user:
        info(f'Account already gone but profile residue remains at '
             f'{", ".join(d for _s, d in profile_residue)} — resuming an interrupted teardown.')

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
    brain_sid = None
    if os_name == 'Windows':
        # The SID cannot be re-resolved from the account once it is deleted, so verification
        # below has to be handed the value removal actually used.
        brain_sid = remove_windows(brain_name, brain_dir, args.dry_run)
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
        # The profile dir and its ProfileList row are the two things that actually cause the
        # next deploy to mint a suffixed profile. Verifying only user/group/workspace is how a
        # teardown that left the profile behind still reported "fully removed", exit 0.
        #
        # Re-resolved from scratch rather than re-checking the paths removal started with: that
        # is what makes this an independent check, and it is also the straggler sweep — a row
        # whose directory is gone, or a directory with no row, still shows up here and still
        # fails the run.
        if os_name == 'Windows':
            for tsid, tdir in _windows_profile_targets(brain_name, brain_sid):
                if os.path.isdir(tdir):
                    remaining.append(f'user profile directory ({tdir})')
                if tsid and _profilelist_entry_exists(tsid):
                    remaining.append(f'ProfileList row ({tsid} -> {tdir})')
    if remaining:
        warn(f'Still present after removal: {", ".join(remaining)}. Review above.')
        sys.exit(2)
    ok(f'Brain "{brain_name}" fully removed.' if not args.dry_run
       else 'Dry-run complete — no changes made.')
    sys.exit(0)


if __name__ == '__main__':
    main()
