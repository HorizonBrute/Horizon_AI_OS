# Horizon AIOS — Documentation Index

Every document is referenced by its **path** (the ID column). When you add, move,
rename, or remove a doc, update this index in the **same change** — run
`/horizon_aios_documentation_index_update`. (Enforced by CC-G4 in
`development_tools/consistency_checks.md`.)

## Documentation root
| ID (path) | Title | Purpose |
|---|---|---|
| `documentation/cloud_sync_exclusions.md` | Cloud Sync Exclusions for Horizon AIOS | How to exclude sensitive/large files when running AIOS under OneDrive/Google Drive/Dropbox instead of (or alongside) git. |
| `documentation/dev_values.md` | Horizon AIOS — Development Values | The engineering values guiding AIOS design (agent-first architecture, token economy, security posture); authority tier above architecture decisions. |
| `documentation/philosophy.md` | Horizon AIOS — Philosophy and Conceptual Framework | The "why" behind the architecture and the Brain vs. AI-OS vocabulary; highest authority tier. |
| `documentation/sync_setup.md` | Horizon AIOS — Sync Setup Reference | How auto-sync keeps a local install current via fast-forward-only git fetch/merge, and the `aios_local.conf` keys that configure it. |
| `documentation/tested_configurations.md` | Horizon AIOS — Tested Configurations | The verified harness/OS/deployment compatibility matrix and what "tested" means. |
| `documentation/context_loading.md` | Context Loading — Horizon AIOS | End-to-end reference for how the Claude Code harness assembles its system prompt: loading layers, @-import mechanics, what loads in a standard AIOS session with real token numbers, per-layer configuration guidance, and token economy rules. |
| `documentation/utilities.md` | Horizon AIOS — Utilities Reference | Quick-lookup index of all `sbin/` utility scripts: purpose, flags, and skill cross-references. |

## authoring
| ID (path) | Title | Purpose |
|---|---|---|
| `documentation/authoring/claude_md_authoring.md` | Authoring CLAUDE.md Files — Horizon AIOS | Conventions for writing `CLAUDE.md` files, including the critical clarification that `@`-imports are always loaded unconditionally by the harness. |

## getting_started
| ID (path) | Title | Purpose |
|---|---|---|
| `documentation/getting_started/ReadMeToSetupYourSystem.md` | Horizon AIOS — System Setup Guide | Human SOP and agent-executable protocol for bootstrapping AIOS on a new machine. |

## system
| ID (path) | Title | Purpose |
|---|---|---|
| `documentation/system/aios_switching.md` | Switching between AIOSs | Run multiple AIOS installs on one machine and switch which one the local Claude config points at, via `aios_switch.py`. |
| `documentation/system/system_configuration_reference.md` | Horizon AIOS — System Configuration Reference | Authoritative reference for the full configuration architecture: what each file controls, dependencies, and how components fit together. |

## deployment
| ID (path) | Title | Purpose |
|---|---|---|
| `documentation/deployment/desktop.md` | Horizon AIOS — Desktop Deployment | The primary local always-on deployment model: AIOS and brains run as OS accounts on the user's own machine. |
| `documentation/deployment/docker.md` | Horizon AIOS — Docker Deployment | Deploying the AIOS layer as a Linux-based Docker container with brains as sub-containers or OS users. |
| `documentation/deployment/server.md` | Horizon AIOS — Server / Headless Deployment | Running AIOS headless on a remote/always-on machine, accessed via SSH with the audit log as the operational interface. |

## build_decisions
| ID (path) | Title | Purpose |
|---|---|---|
| `documentation/build_decisions/architecture_decisions.md` | Architecture Decisions — Horizon AIOS | The append-only ADR log recording the "why" behind structural decisions; beats all other docs in the authority hierarchy. |

## security
| ID (path) | Title | Purpose |
|---|---|---|
| `documentation/security/audit_logging.md` | Audit Logging — AIOS Filesystem Monitor | How `monitor_aios.py` watches AIOS system directories and logs unexpected file changes as JSON-line audit events. |

## development_tools
| ID (path) | Title | Purpose |
|---|---|---|
| `documentation/development_tools/consistency_checks.md` | Horizon AIOS — Consistency Checks | Machine-readable definition of "consistent" for the project plus the iterative validation-pass protocol and check IDs. |

## Authority & invariants
| ID (path) | Title | Purpose |
|---|---|---|
| `horizon_system/ai_os_etc/ai_os_personalizations.md` | AI OS Personalizations — Horizon AIOS | The settings-layer ownership model and personalization rules (which config belongs in global vs. devroot vs. project layers). |
| `horizon_system/ai_os_etc/file_structure_invariants.md` | File Structure Invariants — Horizon AIOS | Hard constraints on path variables, the directory tree, what the repo tracks vs. ignores, and structural conventions. |
| `horizon_system/ai_os_etc/horizon_aios_agents.md` | Horizon AIOS — Agent Configuration (OS Layer) | Harness-agnostic agent instructions (orchestration model, agent usage) loaded into every session. |
| `horizon_system/ai_os_etc/security_invariants.md` | Security Invariants — Horizon AIOS | Hard security constraints for all users, harnesses, and brains, including the three-tier principal model. |
