# Horizon AIOS sbin/ Index

Privileged scripts for system administration. Requires elevation (Administrator on Windows, root on Unix). Never accessible to brain user accounts. See `README.md` in this directory for the privilege/security boundary model.

| Utility | Description |
|---------|-------------|
| [bootstrap.ps1](./bootstrap.ps1) | Bootstrap script (PowerShell) — sets up a new machine with all required Horizon AIOS configuration; safe to run multiple times (idempotent) |
| [bootstrap.sh](./bootstrap.sh) | Bootstrap script (Bash) — sets up a new machine with all required Horizon AIOS configuration; works on Windows (Git Bash), macOS, Linux |
| [bootstrap_docker.ps1](./bootstrap_docker.ps1) | Docker bootstrap (PowerShell) — runs standard bootstrap in Docker mode with non-interactive prompts and skipped shell/sync setup |
| [bootstrap_docker.sh](./bootstrap_docker.sh) | Docker bootstrap (Bash) — runs standard bootstrap in Docker mode; executed automatically during docker build |
| [horizon_aios_backup_user_data.py](./horizon_aios_backup_user_data.py) | Back up user data (memory, handoffs, objectives) to a personal remote without publishing to upstream |
| [horizon_aios_brain_credential.py](./horizon_aios_brain_credential.py) | Brain credential manager — stores and retrieves brain OS account passwords in the native OS keystore |
| [horizon_aios_brain_logon_rights.py](./horizon_aios_brain_logon_rights.py) | Grant/revoke/query Windows LSA logon rights on a brain account for opt-in automation tiers |
| [horizon_aios_create_brain.py](./horizon_aios_create_brain.py) | Brain provisioning script — creates OS user account, groups, workspace folder, permissions, password storage, and shell profile |
| [horizon_aios_doctor.py](./horizon_aios_doctor.py) | Health-check utility for AIOS installation; run as primary OS user; supports --post-setup for post-install verifications |
| [horizon_aios_harden.py](./horizon_aios_harden.py) | Layer hardening — applies the authoritative brains-group ACL model to $HORIZON_SYSTEM independent of brain creation |
| [horizon_aios_maintain_logs.py](./horizon_aios_maintain_logs.py) | Log maintenance — prunes old logs and rotates oversized files per configured retention policy |
| [horizon_aios_maintain_logs_runner.ps1](./horizon_aios_maintain_logs_runner.ps1) | PowerShell wrapper for horizon_aios_maintain_logs.py; resolves Python and delegates execution |
| [horizon_aios_nightly_maintenance.py](./horizon_aios_nightly_maintenance.py) | Nightly maintenance runner — runs doctor (report drift) then harden (re-assert permission model) unattended; logs each step; --dry-run |
| [horizon_aios_monitor.py](./horizon_aios_monitor.py) | AIOS filesystem integrity monitor — watches AIOS layer for unexpected file changes and logs events as JSON lines |
| [horizon_aios_monitor_analyze.py](./horizon_aios_monitor_analyze.py) | Monitor log analyzer — reads horizon_aios_monitor.py JSON-line logs, checks for file changes and uptime gaps, writes security summary |
| [horizon_aios_monitor_analyze_runner.ps1](./horizon_aios_monitor_analyze_runner.ps1) | PowerShell wrapper for horizon_aios_monitor_analyze.py; intended for periodic Task Scheduler or cron execution |
| [horizon_aios_monitor_runner.ps1](./horizon_aios_monitor_runner.ps1) | PowerShell launcher for horizon_aios_monitor.py; for manual use or service wrapper |
| [horizon_aios_redirect_memory.py](./horizon_aios_redirect_memory.py) | Redirect the harness's per-project state (memory) into the AIOS under $HORIZON_ROOT/memory/ for centralized governance |
| [horizon_aios_register_user_skills.py](./horizon_aios_register_user_skills.py) | Aggregate the owner's skill view by linking brain-tier and machine-local skills into skills_sbin; idempotent and safe to re-run |
| [horizon_aios_relocate.py](./horizon_aios_relocate.py) | Relocate an AIOS install to a new root path; auto-detects old root and rewrites machine-local instance pointers |
| [horizon_aios_remove_brain.py](./horizon_aios_remove_brain.py) | Brain deprovisioning — reverses horizon_aios_create_brain.py by removing OS user, groups, workspace, profile, and credential |
| [horizon_aios_setup_maintenance_schedule.py](./horizon_aios_setup_maintenance_schedule.py) | Install/remove the on-by-default nightly maintenance schedule (Windows Scheduled Task or Unix cron) running horizon_aios_nightly_maintenance.py |
| [horizon_aios_setup_monitor_service.py](./horizon_aios_setup_monitor_service.py) | Install AIOS filesystem monitor as scheduled service (Windows Task Scheduler or Unix cron) |
| [horizon_aios_setup_sync_schedule.py](./horizon_aios_setup_sync_schedule.py) | Install AIOS auto-sync scheduled task (Windows) or cron job (Unix) |
| [horizon_aios_switch.py](./horizon_aios_switch.py) | Switch which AIOS this machine's local config points at via machine-global pointers |
| [horizon_aios_sync.py](./horizon_aios_sync.py) | Upstream sync script — lives in sbin (do not expose to brain users); syncs AIOS framework from remote |
| [horizon_aios_sync_runner.ps1](./horizon_aios_sync_runner.ps1) | PowerShell launcher for Windows Task Scheduler — resolves Python and delegates to horizon_aios_sync.py |
| [horizon_aios_update.py](./horizon_aios_update.py) | (Empty stub; appears to be deprecated or under development) |
| [horizon_aios_verify_isolation.py](./horizon_aios_verify_isolation.py) | Brain-isolation test (Criterion #5) — proves a brain OS account can read bin but is denied sbin (static ACL or live mode) |
| [uninstall.ps1](./uninstall.ps1) | Uninstall script (PowerShell) — undoes everything bootstrap.ps1 does; safe to run multiple times, non-destructive on user content |
| [uninstall.sh](./uninstall.sh) | Uninstall script (Bash) — undoes everything bootstrap.sh does; works on macOS, Linux, and Git Bash on Windows |
