#!/usr/bin/env python3
"""
brain_logon_rights.py — Horizon AIOS brain automation logon rights (Windows)
============================================================================

Grant / revoke / query a single Windows LSA *logon right* on a brain account,
for the opt-in brain "automation" tiers (see create_brain.py --automation).

Why LSA and not secedit
------------------------
This uses the LSA policy API (`LsaAddAccountRights` / `LsaRemoveAccountRights`)
so exactly one right on one account is changed and nothing else in local
security policy is touched. That mirrors the AIOS *additive* model used for
ACLs in harden_aios.py: never clobber existing/infra-pushed policy, only add
(or remove) the specific ACE/right we own. `secedit /configure` would reimport
a whole policy template and risk side effects, so it is deliberately avoided.

Rights AIOS uses for brain automation
-------------------------------------
    SeBatchLogonRight    "Log on as a batch job"   — Task Scheduler tasks set to
                         "Run whether user is logged on or not" (the `scheduled`
                         automation tier). This is NOT an interactive session.
    SeServiceLogonRight  "Log on as a service"     — reserved for a future
                         `daemon` tier (always-on supervised harness).

Security note: granting a logon right widens a brain's privilege/attack surface,
so it is opt-in per brain and revoked on teardown (remove_brain.py). The brain's
no-write/Deny ACL posture is unaffected — this only governs *how* the account may
log on, not what it can read or write.

Platform: Windows only. On other platforms every function raises
NotImplementedError; callers must gate on platform.system() == 'Windows'.

API (stdlib only):
    grant(account, right=BATCH_LOGON)  -> (ok: bool, detail: str)
    revoke(account, right=BATCH_LOGON) -> (ok: bool, detail: str)
    holds(account, right=BATCH_LOGON)  -> bool
"""

import os
import platform
import subprocess
import tempfile

# Logon rights AIOS uses for brain automation (LSA privilege constant names).
BATCH_LOGON = 'SeBatchLogonRight'      # "Log on as a batch job" (scheduled tier)
SERVICE_LOGON = 'SeServiceLogonRight'  # "Log on as a service" (future daemon tier)

# C# shim invoked via Add-Type. Surgical: adds/removes/enumerates exactly one
# right for one account SID via the LSA policy API. winerror 2 on remove means
# "right was not held" and is treated as success (idempotent revoke).
_CSHARP = r'''
using System;
using System.Runtime.InteropServices;
using System.Security.Principal;

public static class AiosLsa
{
    [StructLayout(LayoutKind.Sequential)]
    struct LSA_UNICODE_STRING { public ushort Length; public ushort MaximumLength; public IntPtr Buffer; }
    [StructLayout(LayoutKind.Sequential)]
    struct LSA_OBJECT_ATTRIBUTES { public int Length; public IntPtr RootDirectory; public IntPtr ObjectName; public uint Attributes; public IntPtr SecurityDescriptor; public IntPtr SecurityQualityOfService; }

    [DllImport("advapi32.dll", SetLastError=true)]
    static extern uint LsaOpenPolicy(IntPtr SystemName, ref LSA_OBJECT_ATTRIBUTES ObjectAttributes, uint DesiredAccess, out IntPtr PolicyHandle);
    [DllImport("advapi32.dll", SetLastError=true)]
    static extern uint LsaAddAccountRights(IntPtr PolicyHandle, byte[] AccountSid, LSA_UNICODE_STRING[] UserRights, uint CountOfRights);
    [DllImport("advapi32.dll", SetLastError=true)]
    static extern uint LsaRemoveAccountRights(IntPtr PolicyHandle, byte[] AccountSid, bool AllRights, LSA_UNICODE_STRING[] UserRights, uint CountOfRights);
    [DllImport("advapi32.dll", SetLastError=true)]
    static extern uint LsaEnumerateAccountRights(IntPtr PolicyHandle, byte[] AccountSid, out IntPtr UserRights, out uint CountOfRights);
    [DllImport("advapi32.dll")]
    static extern uint LsaClose(IntPtr PolicyHandle);
    [DllImport("advapi32.dll")]
    static extern uint LsaFreeMemory(IntPtr Buffer);
    [DllImport("advapi32.dll")]
    static extern int LsaNtStatusToWinError(uint Status);

    const uint POLICY_ALL_ACCESS = 0x000F0FFF;

    static LSA_UNICODE_STRING Str(string s) {
        LSA_UNICODE_STRING u = new LSA_UNICODE_STRING();
        u.Buffer = Marshal.StringToHGlobalUni(s);
        u.Length = (ushort)(s.Length * 2);
        u.MaximumLength = (ushort)((s.Length + 1) * 2);
        return u;
    }
    static byte[] Sid(string account) {
        SecurityIdentifier sid = (SecurityIdentifier)(new NTAccount(account)).Translate(typeof(SecurityIdentifier));
        byte[] b = new byte[sid.BinaryLength];
        sid.GetBinaryForm(b, 0);
        return b;
    }
    static IntPtr Open() {
        LSA_OBJECT_ATTRIBUTES attrs = new LSA_OBJECT_ATTRIBUTES();
        IntPtr h;
        uint st = LsaOpenPolicy(IntPtr.Zero, ref attrs, POLICY_ALL_ACCESS, out h);
        if (st != 0) throw new Exception("LsaOpenPolicy failed (winerr " + LsaNtStatusToWinError(st) + ")");
        return h;
    }

    public static void Modify(string account, string right, bool grant) {
        byte[] sid = Sid(account);
        IntPtr h = Open();
        try {
            LSA_UNICODE_STRING[] rights = new LSA_UNICODE_STRING[] { Str(right) };
            uint st = grant ? LsaAddAccountRights(h, sid, rights, 1)
                            : LsaRemoveAccountRights(h, sid, false, rights, 1);
            int err = LsaNtStatusToWinError(st);
            if (st != 0 && !(!grant && err == 2))
                throw new Exception((grant ? "LsaAddAccountRights" : "LsaRemoveAccountRights") + " failed (winerr " + err + ")");
        } finally { LsaClose(h); }
    }

    public static bool Holds(string account, string right) {
        byte[] sid = Sid(account);
        IntPtr h = Open();
        try {
            IntPtr buf; uint count;
            uint st = LsaEnumerateAccountRights(h, sid, out buf, out count);
            if (st != 0) return false;   // winerr 2: account holds no rights at all
            bool found = false;
            long p = buf.ToInt64();
            int sz = Marshal.SizeOf(typeof(LSA_UNICODE_STRING));
            for (uint i = 0; i < count; i++) {
                LSA_UNICODE_STRING u = (LSA_UNICODE_STRING)Marshal.PtrToStructure(new IntPtr(p), typeof(LSA_UNICODE_STRING));
                string s = Marshal.PtrToStringUni(u.Buffer, u.Length / 2);
                if (string.Equals(s, right, StringComparison.OrdinalIgnoreCase)) found = true;
                p += sz;
            }
            LsaFreeMemory(buf);
            return found;
        } finally { LsaClose(h); }
    }
}
'''


def _require_windows():
    if platform.system() != 'Windows':
        raise NotImplementedError(
            'brain_logon_rights is Windows-only; on Unix use loginctl '
            'enable-linger / crontab -u for the scheduled tier.'
        )


def _run_ps(body):
    """Build a temp .ps1 that compiles the shim and runs `body`, then execute it.

    Using a temp file (not -Command) keeps the C# here-string off the command
    line and avoids all quoting fragility. Returns the CompletedProcess.
    """
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$src = @'\n" + _CSHARP.strip('\n') + "\n'@\n"
        "Add-Type -TypeDefinition $src -Language CSharp\n"
        + body + "\n"
    )
    fd, path = tempfile.mkstemp(suffix='.ps1', prefix='aios_lsa_')
    try:
        os.write(fd, script.encode('utf-8'))
        os.close(fd)
        return subprocess.run(
            ['powershell', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', path],
            capture_output=True, text=True,
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _modify(account, right, grant):
    _require_windows()
    verb = '$true' if grant else '$false'
    body = (
        f"[AiosLsa]::Modify('{account}', '{right}', {verb})\n"
        "Write-Output 'RESULT:OK'"
    )
    r = _run_ps(body)
    if r.returncode == 0 and 'RESULT:OK' in (r.stdout or ''):
        return True, 'ok'
    detail = (r.stderr or r.stdout or '').strip() or f'exit {r.returncode}'
    return False, detail


def grant(account, right=BATCH_LOGON):
    """Grant `right` to `account`. Returns (ok, detail)."""
    return _modify(account, right, True)


def revoke(account, right=BATCH_LOGON):
    """Revoke `right` from `account` (idempotent). Returns (ok, detail)."""
    return _modify(account, right, False)


def holds(account, right=BATCH_LOGON):
    """Return True iff `account` currently holds `right`."""
    _require_windows()
    body = (
        f"if ([AiosLsa]::Holds('{account}', '{right}')) "
        "{ Write-Output 'RESULT:TRUE' } else { Write-Output 'RESULT:FALSE' }"
    )
    r = _run_ps(body)
    return r.returncode == 0 and 'RESULT:TRUE' in (r.stdout or '')


# Tiny CLI so the right can be inspected/managed by hand if ever needed.
if __name__ == '__main__':
    import argparse
    import sys

    p = argparse.ArgumentParser(description='Manage a Windows logon right for a brain account.')
    p.add_argument('action', choices=['grant', 'revoke', 'check'])
    p.add_argument('account', help='Brain account name')
    p.add_argument('--right', default=BATCH_LOGON,
                   help=f'LSA right name (default: {BATCH_LOGON})')
    a = p.parse_args()
    try:
        if a.action == 'check':
            print('HELD' if holds(a.account, a.right) else 'NOT-HELD')
            sys.exit(0)
        ok_, detail = (grant if a.action == 'grant' else revoke)(a.account, a.right)
        print('OK' if ok_ else f'FAILED: {detail}')
        sys.exit(0 if ok_ else 1)
    except NotImplementedError as exc:
        print(exc, file=sys.stderr)
        sys.exit(2)
