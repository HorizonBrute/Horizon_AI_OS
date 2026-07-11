# Deployment How-Tos

Quick-reference guides for specific deployment scenarios.

---

## Windows Install/Switch/Uninstall Lifecycle Test

The Testing Stack provides a complete deployment package for validating the full AIOS lifecycle on Windows.

**Package location:** `testing_stack/tests/01-Win_Install_switch_uninstall/`

**What it tests:** Same 9-phase lifecycle as Linux (install → brain → switch → relocate → backup → uninstall → cleanup).

**Package contents:**

| File | Purpose |
|------|---------|
| `DEPLOYMENT_README.md` | Windows deployment guide with prerequisites, quick-start |
| `deploy_to_target.ps1` | PowerShell deployment script |
| `run_sheet_final.md` | Paste-and-go coordinator with values pre-filled |
| `checklists/pre_flight_checklist.md` | Box prerequisites validation |
| `checklists/post_install_checklist.md` | Verification checklist per phase |

**Quick start:**
```powershell
# From dev machine (elevated PowerShell):
.\testing_stack\tests\01-Win_Install_switch_uninstall\deploy_to_target.ps1
```

**Prerequisites on target:**
- Windows 10/11 with PowerShell 5.1+
- Python 3.10+, Git 2.40+
- Developer Mode enabled (or elevation for symlinks)
- Claude Code CLI (`aios` command available)
- Administrator privileges (UAC elevation)

**Security posture:** Lane B decharacterized — keyring required. Monitor scheduled tasks (Batch B) MUST be present for Run 2.

See `testing_stack/tests/01-Win_Install_switch_uninstall/DEPLOYMENT_README.md` for complete documentation.

---

## Linux Install/Switch/Uninstall Lifecycle Test

The Testing Stack provides a complete deployment package for validating the full AIOS lifecycle on Linux targets.

**Package location:** `testing_stack/tests/02-Linux_Install_switch_uninstall/`

**What it tests:**
1. Fresh install (Slot A) with `--profile workstation --yes`
2. Install verification (doctor + leakage scan)
3. Brain creation + isolation verification
4. Second install (Slot B)
5. Switch + context-shift proof
6. Relocate + re-verify
7. Backup + sync
8. Uninstall (both slots)
9. Cleanup + restore

**Package contents:**

| File | Purpose |
|------|---------|
| `DEPLOYMENT_README.md` | Full deployment guide with prerequisites, quick-start, and test values |
| `deploy_to_target.sh` | Deployment script that SCPs harness and validates round-trip |
| `run_sheet_final.md` | Paste-and-go coordinator with all values pre-filled |
| `checklists/pre_flight_checklist.md` | Box prerequisites validation checklist |
| `checklists/post_install_checklist.md` | Verification checklist per phase |

**Quick start:**
```bash
# From dev machine, with SSH access to target:
bash testing_stack/tests/02-Linux_Install_switch_uninstall/deploy_to_target.sh horizon-testadmin
```

**Prerequisites on target:**
- Fedora 44 / Ubuntu 24.04 / Debian 12 (other modern distros may work)
- Bash 5.2+, Python 3.10+, Git 2.40+
- ACL support (`setfacl` present)
- Keyring backend (`gnome-keyring` or `secretstorage`)
- Claude Code binary (`/usr/local/bin/claude`)
- SSH access with passwordless sudo capability

**Security posture:** Runs full secure-by-default verification (monitor ON, ACLs, hardening). Lane B (NOCRED) is decharacterized — keyring availability is required.

See `testing_stack/tests/02-Linux_Install_switch_uninstall/DEPLOYMENT_README.md` for complete documentation.