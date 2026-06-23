# Horizon AIOS — Documentation Index

Every document is referenced by its **full repo-relative path** (the ID column).
When you add, move, rename, or remove a doc, update this index in the **same
change** — run `/horizon_aios_documentation_index_update`. (Enforced by CC-G4 in
`horizon_system/documentation/development_tools/consistency_checks.md`.)

**New here?** After setup, run `/doctor` to verify the install, and `/handoff`
at the end of a session to save state. Start with the setup guide in
[getting_started](#getting_started).

## Skill indexes
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/skills_sbin/index.md` | Skills Index — skills_sbin | Owner-only privileged skills (primary user). Check first when looking for an owner skill. |
| `horizon_system/skills_bin/index.md` | Skills Index — skills_bin | Group-readable skills available to all brains. Check first when looking for a brain skill. |

## Documentation root
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/documentation/cloud_sync_exclusions.md` | Cloud Sync Exclusions for Horizon AIOS | How to exclude sensitive/large files when running AIOS under OneDrive/Google Drive/Dropbox instead of (or alongside) git. |
| `horizon_system/documentation/context_loading.md` | Context Loading — Horizon AIOS | How the Claude Code harness assembles its system prompt: loading layers, @-import mechanics, real per-session token numbers, per-layer config guidance, and token-economy rules. |
| `horizon_system/documentation/dev_values.md` | Horizon AIOS — Development Values | The engineering values guiding AIOS design (agent-first architecture, token economy, security posture); authority tier above architecture decisions. |
| `horizon_system/documentation/development_pipeline.md` | Horizon AIOS — Development Pipeline | Placeholder backlog tracking known work items, gaps, and research threads before formal issue management is integrated. |
| `horizon_system/documentation/philosophy.md` | Horizon AIOS — Philosophy and Conceptual Framework | The "why" behind the architecture and the Brain vs. AI-OS vocabulary; highest authority tier. |
| `horizon_system/documentation/sync_setup.md` | Horizon AIOS — Sync Setup Reference | How auto-sync keeps a local install current via fast-forward-only git fetch/merge, and the `aios_local.conf` keys that configure it. |
| `horizon_system/documentation/tested_configurations.md` | Horizon AIOS — Tested Configurations | The verified harness/OS/deployment compatibility matrix and what "tested" means. |
| `horizon_system/documentation/utilities.md` | Horizon AIOS — Utilities Reference | Quick-lookup catalog of all `sbin/` utility scripts: purpose, flags, and skill cross-references. (Tool catalog — maintained separately.) |
| `horizon_system/documentation/skills.md` | Horizon AIOS — Skills Reference | Index of all AIOS-native skills with per-skill onboarding/offboarding impact and aggregate summary. |

## getting_started
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/documentation/getting_started/ReadMeToSetupYourSystem.md` | Horizon AIOS — System Setup Guide | Human SOP and agent-executable protocol for bootstrapping AIOS on a new machine. |
| `horizon_system/documentation/getting_started/dependencies_and_footprint.md` | Horizon AIOS — Dependencies and System Footprint Reference | Declarative, scannable reference: all AIOS dependencies with per-platform install commands, and a complete system footprint for both AIOS install and brain addition across Windows, macOS, and Linux. |
| `horizon_system/documentation/getting_started/updating.md` | How to Update Horizon AIOS | Step-by-step procedure for pulling upstream changes (fast-forward-only sync), what to do when an update refuses, post-update verification, and rollback. |
| `horizon_system/documentation/getting_started/lifecycle_test.md` | Horizon AIOS — End-to-End Lifecycle Test | Runbook for proving the full install → AIOS-switch → provision/update/back up → uninstall → clean-reset lifecycle on a dedicated clean machine, with per-step verification. |

## system
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/documentation/system/aios_switching.md` | Switching between AIOSs | Run multiple AIOS installs on one machine and switch which one the local Claude config points at, via `horizon_aios_switch.py`. |
| `horizon_system/documentation/system/distribution_and_updates.md` | Distribution, Updates, and Backing Up Your Data | The framework vs. user-space model: getting upstream updates without losing customizations, protecting your config, and backing up memory/handoffs/objectives to your own remote. |
| `horizon_system/documentation/system/memory.md` | Harness Memory and Per-Project State | Where harness transcripts and agent memory live (`$HORIZON_ROOT/memory/` via the `~/.claude/projects` junction), how the owner/brain redirects work, why it's centralized, and that uninstalling the AIOS destroys memory unless the user backs it up first. |
| `horizon_system/documentation/system/system_configuration_reference.md` | Horizon AIOS — System Configuration Reference | Authoritative reference for the full configuration architecture: what each file controls, dependencies, and how components fit together. |
| `horizon_system/documentation/system/uninstall.md` | Uninstalling Horizon AIOS | Authoritative runbook for removing the AIOS footprint: how to run the uninstall, what it removes vs. preserves, a post-uninstall verification checklist, and the full install→uninstall validation cycle for a fresh machine. |

## deployment
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/documentation/deployment/brain_automation.md` | Horizon AIOS — Brain Automation | Opt-in, least-privilege OS logon rights (Windows `SeBatchLogonRight`/`SeServiceLogonRight`, Unix linger/systemd analogs) that let a brain run unattended via scheduled task or service; how to provision, register, and tear down. |
| `horizon_system/documentation/deployment/desktop.md` | Horizon AIOS — Desktop Deployment | The primary local always-on deployment model: AIOS and brains run as OS accounts on the user's own machine. |
| `horizon_system/documentation/deployment/docker.md` | Horizon AIOS — Docker Deployment | Deploying the AIOS layer as a Linux-based Docker container with brains as sub-containers or OS users. |
| `horizon_system/documentation/deployment/server.md` | Horizon AIOS — Server / Headless Deployment | Running AIOS headless on a remote/always-on machine, accessed via SSH with the audit log as the operational interface. |

## build_decisions
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/documentation/build_decisions/architecture_decisions.md` | Architecture Decisions — Horizon AIOS | The append-only ADR log recording the "why" behind structural decisions; beats all other docs in the authority hierarchy. |

## security
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/documentation/security/audit_logging.md` | Audit Logging — AIOS Filesystem Monitor | How `horizon_aios_monitor.py` watches AIOS system directories and logs unexpected file changes as JSON-line audit events. |
| `horizon_system/documentation/security/brain_isolation_test.md` | Horizon AIOS — Brain Isolation Test (Criterion #5) | `horizon_aios_verify_isolation.py`: safe ACL check by default, opt-in `--live` provision/probe/teardown that proves a brain reads `bin` but is denied `sbin`. |

## development_tools
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/documentation/development_tools/consistency_checks.md` | Horizon AIOS — Consistency Checks | Machine-readable definition of "consistent" for the project plus the iterative validation-pass protocol and check IDs. |
| `horizon_system/documentation/development_tools/windows_install_switch_uninstall_test_prompt.md` | Windows — Install / Switch / Uninstall End-to-End Test Prompt | Ready-to-run admin prompt for a fresh Claude Code on a clean Windows box to dog-food the full lifecycle (install → brain → 2nd AIOS → switch → backup → delete); generated by `/pre-flight-tooling-validation`. |

## authoring
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/documentation/authoring/claude_md_authoring.md` | Authoring CLAUDE.md Files — Horizon AIOS | Conventions for writing `CLAUDE.md` files, including that `@`-imports are always loaded unconditionally by the harness. |

## Authority & invariants
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/ai_os_etc/ai_os_personalizations.md` | AI OS Personalizations — Horizon AIOS | The settings-layer ownership model and personalization rules (which config belongs in global vs. devroot vs. project layers). |
| `horizon_system/ai_os_etc/file_structure_invariants.md` | File Structure Invariants — Horizon AIOS | Hard constraints on path variables, the directory tree, what the repo tracks vs. ignores, and structural conventions. |
| `horizon_system/ai_os_etc/horizon_aios_agents.md` | Horizon AIOS — Agent Configuration (OS Layer) | Harness-agnostic agent instructions (orchestration model, agent usage) loaded into every session. |
| `horizon_system/ai_os_etc/horizon_aios_model_prefs.md` | Model Preferences — Horizon AIOS | Advisory preferences for model selection when harnesses spawn agents or sub-agents: per-session slot preferences and named model groups (#lowcost, #debug, etc.). Best-effort -- reliability depends on the harness and session model. Extend via `horizon_aios_model_prefs.extend.md` (gitignored). |
| `horizon_system/ai_os_etc/security_invariants.md` | Security Invariants — Horizon AIOS | Hard security constraints for all users, harnesses, and brains, including the three-tier principal model. |
