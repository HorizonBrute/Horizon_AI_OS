# Horizon AIOS — Brain Automation

By default a brain is an OS user account you use **interactively** — you log in
as it (or `runas` the harness) and the brain runs while you are present. **Brain
automation** is the opt-in capability that lets a brain run **unattended**: a
scheduled task or service launches the harness as the brain with no human at the
keyboard.

Running unattended requires the OS to let the account **log on without an
interactive session**. On Windows that is a *logon right* — a piece of local
security policy, distinct from filesystem ACLs. Granting one is
**privilege/attack-surface expansion**, so AIOS treats automation as opt-in,
least-privilege, and reversible.

**Status:** Windows-first (verified). Unix analogs are documented guidance, not
yet auto-applied. See `tested_configurations.md`.

---

## The Security Frame (read this first)

A logon right governs **how** the account may log on — *not* **what** it can
read or write.

- **Opt-in per brain.** No brain gets a logon right unless you ask for one. The
  default automation tier is `none`.
- **Least privilege.** Each automation tier needs exactly one logon right. AIOS
  grants only that one — `brain_logon_rights.py` changes a single LSA right on a
  single account and never touches the rest of local security policy (mirroring
  the additive-ACL philosophy in `harden_aios.py`).
- **Revoked on teardown.** `remove_brain.py` strips the logon rights before
  deleting the account, so a right can never orphan to a recycled SID.
- **Read/write posture is untouched.** Granting a logon right does **not** change
  the brain's ACLs: the no-write Deny on `sbin`/`skills_sbin`/`logs` and the
  read-only `bin`/`skills_bin` grants are exactly as `harden_aios.py` set them
  (see `security_invariants.md §2`). A scheduled brain can log on headlessly but
  still cannot write the AIOS layer or reach `sbin`.
- **The password is the keystore password.** The credential Task Scheduler or a
  service consumes is the one AIOS already stored for the brain
  (`brain_credential.py`). It is never printed during provisioning.

---

## The Three Logon Tiers

There are three distinct Windows logon rights. They are **not interchangeable** —
each maps to a different automation style.

| Tier | Windows right | Logon type | What it enables | Cross-platform analog |
|---|---|---|---|---|
| `none` *(default)* | *(none)* | — | Interactive/manual use only; no automation. | — |
| `scheduled` | `SeBatchLogonRight` ("Log on as a batch job") | Batch | A Task Scheduler task set to **Run whether user is logged on or not**, using the stored password — a headless scheduled trigger with **no desktop session**. | Linux: `loginctl enable-linger` + a `systemd --user` unit, or `crontab -u <brain>`. macOS: a `launchd` LaunchDaemon. |
| `daemon` *(reserved / future)* | `SeServiceLogonRight` ("Log on as a service") | Service | A Windows Service running continuously as the brain: starts at boot, auto-restarts — an "always-on / supervised harness". | Linux: a system `systemd` unit with `User=<brain>`. macOS: a LaunchDaemon. |
| *(discouraged)* | `SeInteractiveLogonRight` ("Allow log on locally") + autologon | Interactive | A real desktop session at boot that runs the deployed shell profile. | Linux/macOS: graphical autologin. |

**`--automation` currently accepts only `none` and `scheduled`.** The `daemon`
tier is a documented future path: the `SeServiceLogonRight` constant exists in
`brain_logon_rights.py`, but `create_brain.py` does not yet provision it. You can
grant it by hand today (see *Manual right management*) and register the service
yourself; AIOS will still revoke it on teardown.

**Autologon is discouraged.** A real interactive desktop session at boot is
fragile, stores the password at rest in the registry, and is limited to a single
session. Use it only when a genuine interactive desktop/GUI is required. For
"keep the harness up" / resilience, the right pattern is a **service** or a
**scheduled task with restart-on-failure**, not interactive autologon.

---

## How To: Scheduled Automation (Windows)

### 1. Provision the brain with scheduled automation

Run elevated (administrative context):

```bash
python $HORIZON_SYSTEM/sbin/create_brain.py mybrain --automation scheduled
```

On Windows this grants `SeBatchLogonRight` to the brain account and verifies the
right took. The chosen tier is recorded in the brain's `.aios_provision.json`
manifest under an `"automation"` key. On Unix, `create_brain.py` instead prints
`loginctl enable-linger <brain>` / `crontab -u <brain> -e` guidance (not yet
auto-applied — see *Unix analogs*).

This does **not** change the brain's ACLs — only its logon rights.

### 2. Retrieve the brain's password

Task Scheduler needs the brain's credential to run the task while logged out.
Retrieve it from the OS keystore (elevated):

```bash
python $HORIZON_SYSTEM/sbin/brain_credential.py get mybrain --show
```

### 3. Register the scheduled task

Create a task whose principal is the **brain account**, set to **Run whether
user is logged on or not** — the mode that requires batch-logon — supplying the
keystore password. Example with `schtasks` (illustrative paths shown concrete;
use your own `$HORIZON_*` values):

```powershell
schtasks /Create /TN "AIOS-mybrain-harness" `
  /TR "C:\devroot\horizon_system\bin\run_brain_harness.ps1 mybrain" `
  /SC DAILY /ST 06:00 `
  /RU "mybrain" /RP "<keystore-password>" `
  /RL LIMITED
```

`/RU` + `/RP` with a non-empty password makes the task run in **batch logon**
mode (logged on or not). Equivalent with PowerShell, which lets you add
restart-on-failure for resilience:

```powershell
$action  = New-ScheduledTaskAction -Execute "powershell" `
    -Argument "-File C:\devroot\horizon_system\bin\run_brain_harness.ps1 mybrain"
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00"
# Principal = the brain account, batch logon (S4U requires no stored password;
# Password requires the keystore password and enables 'run whether logged on or not')
$principal = New-ScheduledTaskPrincipal -UserId "mybrain" -LogonType Password -RunLevel Limited
$settings  = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "AIOS-mybrain-harness" `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -User "mybrain" -Password "<keystore-password>"
```

The task launches the harness/agent as the brain. Because the brain's harness
config was wired at provisioning (see `deployment/desktop.md`), it comes up
already pointed at the AIOS layer.

---

## Manual Right Management

`create_brain.py --automation scheduled` is the normal path, but you can manage
the underlying logon right directly with the surgical helper (elevated,
Windows-only):

```bash
python $HORIZON_SYSTEM/sbin/brain_logon_rights.py grant mybrain   # grant SeBatchLogonRight (default)
python $HORIZON_SYSTEM/sbin/brain_logon_rights.py check mybrain   # query whether the right is held
python $HORIZON_SYSTEM/sbin/brain_logon_rights.py revoke mybrain  # remove it

# Target a specific right (e.g. the reserved service tier):
python $HORIZON_SYSTEM/sbin/brain_logon_rights.py grant mybrain --right SeServiceLogonRight
```

It changes exactly one right on one account via `LsaAddAccountRights` /
`LsaRemoveAccountRights` / `LsaEnumerateAccountRights`, leaving the rest of local
security policy alone.

---

## Teardown

`remove_brain.py` revokes **both** `SeBatchLogonRight` and `SeServiceLogonRight`
from the account **before** deleting it — idempotently, while the SID still
resolves — so logon rights never orphan to a future account that reuses the SID.
No manual cleanup of logon rights is needed when you deprovision a brain.

```bash
python $HORIZON_SYSTEM/sbin/remove_brain.py mybrain --yes
```

---

## Unix Analogs (guidance, not yet auto-applied)

On Unix, `create_brain.py --automation scheduled` prints guidance rather than
applying it. The equivalent setups:

- **Scheduled (batch analog):**
  ```sh
  loginctl enable-linger mybrain        # allow the user's services to run while logged out
  # then a systemd --user unit that launches the harness, OR:
  crontab -u mybrain -e                 # schedule the harness as the brain
  ```
- **Daemon (service analog):** a system `systemd` unit with `User=mybrain`
  (Linux), or a `launchd` LaunchDaemon (macOS).
- **Interactive (discouraged):** graphical autologin — fragile and stores the
  password at rest; use only when a real desktop session is required.

---

## See Also

- `deployment/desktop.md` — provisioning and removing brains; how a brain's
  harness is wired to AIOS.
- `security/audit_logging.md` — service/scheduled-task registration patterns for
  the AIOS monitor (the same Windows mechanics apply here).
- `ai_os_etc/security_invariants.md §2` — the Deny/read-only ACL posture that
  automation leaves untouched.
