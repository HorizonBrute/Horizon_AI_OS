# documentation — Root Index

## Files (root)

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-0046 | documentation.index.md | documentation.index.md | Root index of the documentation directory | — | — | File |
| DOC-0001 | branding_invariants.md | branding_invariants.md | Naming and identification conventions: the Horizon.AIOS / horizon_aios_ brand tokens, required self-identifying artifacts, and deliberately exempt functional identifiers | DOC-0008 | canon | File |
| DOC-0002 | cloud_sync_exclusions.md | cloud_sync_exclusions.md | How to exclude sensitive or large files when running AIOS under OneDrive/Google Drive/Dropbox instead of (or alongside) git | DOC-0010, DOC-0042 | implementation | File |
| DOC-0003 | context_loading.md | context_loading.md | How the Claude Code harness assembles its system prompt: loading layers, @-import mechanics, real per-session token numbers, per-layer config guidance, and token-economy rules | DOC-0011, DOC-0042 | implementation | File |
| DOC-0004 | dev_values.md | dev_values.md | Engineering values guiding AIOS design (agent-first architecture, token economy, security posture); authority tier above architecture decisions | DOC-0007, DOC-0017 | canon | File |
| DOC-0005 | development_pipeline.md | development_pipeline.md | Placeholder backlog tracking known work items, gaps, and research threads before formal issue management is integrated | DOC-0017 | canon | File |
| DOC-0006 | model_prefs_details.md | model_prefs_details.md | Full reference for the model-preference layer: member grammar, slot descriptions, group purposes, task-class routing format, scope precedence and merge rules, and reliability framing | DOC-0040 | implementation | File |
| DOC-0007 | philosophy.md | philosophy.md | The "why" behind the architecture and the Brain vs. AI-OS vocabulary; highest authority tier in the documentation hierarchy | DOC-0004, DOC-0008 | canon | File |
| DOC-0008 | security_architecture_invariants.md | security_architecture_invariants.md | Full security specification: three-tier principal model, brain isolation, bin/sbin boundary, tool provisioning, least privilege, no sensitive data, audit trail, and branding rationale (§0–§8) | DOC-0007, DOC-0001 | canon | File |
| DOC-0009 | skills.md | skills.md | Index of all AIOS-native skills with per-skill onboarding/offboarding impact and aggregate summary | DOC-0013, DOC-0041 | implementation | File |
| DOC-0010 | sync_setup.md | sync_setup.md | How auto-sync keeps a local install current via fast-forward-only git fetch/merge, and the aios_local.conf keys that configure it | DOC-0031, DOC-0038 | implementation | File |
| DOC-0011 | terseness_contract_index.md | terseness_contract_index.md | Canonical list of every file loaded unconditionally at session start, the seven terseness criteria each must satisfy, and advisory guidance for gitignored/user-controlled files | DOC-0025, DOC-0003 | canon | File |
| DOC-0012 | tested_configurations.md | tested_configurations.md | The verified harness/OS/deployment compatibility matrix and what "tested" means | DOC-0028, DOC-0029 | implementation | File |
| DOC-0013 | utilities.md | utilities.md | Quick-lookup catalog of all sbin/ utility scripts: purpose, flags, and skill cross-references | DOC-0009 | implementation | File |

## Directories

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-0014 | authoring/ | authoring/ | Conventions for authoring AIOS documentation and config files | — | — | Directory |
| DOC-0016 | build_decisions/ | build_decisions/ | Append-only ADR log for structural design decisions | DOC-0004, DOC-0007 | — | Directory |
| DOC-0018 | deployment/ | deployment/ | Deployment model docs for all supported topologies (desktop, server, docker, multi-brain) | — | — | Directory |
| DOC-0024 | development_tools/ | development_tools/ | Developer tooling: consistency checks, test prompts, and validation protocols | — | — | Directory |
| DOC-0027 | getting_started/ | getting_started/ | Onboarding docs: setup, dependencies, lifecycle test, and update procedure | — | — | Directory |
| DOC-0032 | security/ | security/ | Security implementation docs: audit logging and brain isolation testing | DOC-0008 | — | Directory |
| DOC-0035 | system/ | system/ | Core system reference: configuration, memory, switching, model prefs, agent teams, uninstall | — | — | Directory |
| DOC-0044 | user_guides/ | user_guides/ | Operational wiki for post-install usage | — | — | Directory |

---

## Rollup: authoring

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-0047 | authoring.index.md | authoring/authoring.index.md | Index of this directory | — | — | File |
| DOC-0015 | claude_md_authoring.md | authoring/claude_md_authoring.md | Conventions for authoring CLAUDE.md files, including the rule that @-imports are always loaded unconditionally by the harness | DOC-0011 | implementation | File |

---

## Rollup: build_decisions

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-0048 | build_decisions.index.md | build_decisions/build_decisions.index.md | Index of this directory | — | — | File |
| DOC-0017 | architecture_decisions.md | build_decisions/architecture_decisions.md | Append-only ADR log recording the "why" behind structural decisions; beats all other docs in the authority hierarchy | DOC-0004, DOC-0007 | canon | File |

---

## Rollup: deployment

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-0049 | deployment.index.md | deployment/deployment.index.md | Index of this directory | — | — | File |
| DOC-0019 | brain_automation.md | deployment/brain_automation.md | Opt-in, least-privilege OS logon rights (Windows SeBatchLogonRight/SeServiceLogonRight, Unix linger/systemd) for unattended brain execution via scheduled task or service | DOC-0028, DOC-0008 | implementation | File |
| DOC-0020 | desktop.md | deployment/desktop.md | Primary local deployment model: AIOS and brains run as OS accounts on the user's own machine | DOC-0028 | implementation | File |
| DOC-0021 | docker.md | deployment/docker.md | Deploying AIOS as a Linux-based Docker container with brains as sub-containers or OS users | DOC-0028 | implementation | File |
| DOC-0022 | multi_brain_deployment.md | deployment/multi_brain_deployment.md | Hosting multiple brains on one AIOS install: parallel expert systems, filesystem peer coordination, isolation tradeoff table, provisioning and teardown | DOC-0020, DOC-0008 | implementation | File |
| DOC-0023 | server.md | deployment/server.md | Running AIOS headless on a remote machine, accessed via SSH with the audit log as the operational interface | DOC-0033, DOC-0020 | implementation | File |

---

## Rollup: development_tools

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-0050 | development_tools.index.md | development_tools/development_tools.index.md | Index of this directory | — | — | File |
| DOC-0025 | consistency_checks.md | development_tools/consistency_checks.md | Machine-readable definition of "consistent" for the project, iterative validation-pass protocol, and all check IDs (CC-*) | DOC-0017, DOC-0011 | implementation | File |
| DOC-0026 | windows_install_switch_uninstall_test_prompt.md | development_tools/windows_install_switch_uninstall_test_prompt.md | Ready-to-run admin prompt for a fresh Claude Code on a clean Windows box to dog-food the full lifecycle (install → brain → 2nd AIOS → switch → backup → delete); generated by /pre-flight-tooling-validation | DOC-0030 | implementation | File |

---

## Rollup: getting_started

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-0051 | getting_started.index.md | getting_started/getting_started.index.md | Index of this directory | — | — | File |
| DOC-0028 | ReadMeToSetupYourSystem.md | getting_started/ReadMeToSetupYourSystem.md | Human SOP and agent-executable protocol for bootstrapping AIOS on a new machine | DOC-0029, DOC-0030 | implementation | File |
| DOC-0029 | dependencies_and_footprint.md | getting_started/dependencies_and_footprint.md | Declarative reference: all AIOS dependencies with per-platform install commands, and a complete system footprint for both AIOS install and brain addition across Windows, macOS, and Linux | DOC-0028 | implementation | File |
| DOC-0030 | lifecycle_test.md | getting_started/lifecycle_test.md | End-to-end lifecycle test runbook: install → AIOS-switch → provision/update/backup → uninstall → clean-reset, with per-step verification | DOC-0028, DOC-0043 | implementation | File |
| DOC-0031 | updating.md | getting_started/updating.md | Step-by-step procedure for pulling upstream changes (fast-forward-only sync), handling refused updates, post-update verification, and rollback | DOC-0038 | implementation | File |

---

## Rollup: security

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-0052 | security.index.md | security/security.index.md | Index of this directory | — | — | File |
| DOC-0033 | audit_logging.md | security/audit_logging.md | How horizon_aios_monitor.py watches AIOS system directories and logs unexpected file changes as JSON-line audit events | DOC-0008, DOC-0025 | implementation | File |
| DOC-0034 | brain_isolation_test.md | security/brain_isolation_test.md | horizon_aios_verify_isolation.py: safe ACL check by default, opt-in --live provision/probe/teardown that proves a brain reads bin but is denied sbin (Criterion #5) | DOC-0008, DOC-0025 | implementation | File |

---

## Rollup: system

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-0053 | system.index.md | system/system.index.md | Index of this directory | — | — | File |
| DOC-0036 | agent_teams.md | system/agent_teams.md | Agent Teams: in-session invocation pattern, four shipped starter teams, local.agent_teams.md override, loop/retry constructs (loop-back target, pass/fail condition, iteration cap), and /agent-teams skill | DOC-0040, DOC-0042 | implementation | File |
| DOC-0037 | aios_switching.md | system/aios_switching.md | Running multiple AIOS installs on one machine and switching which one the local Claude config points at via horizon_aios_switch.py | DOC-0038, DOC-0010 | implementation | File |
| DOC-0038 | distribution_and_updates.md | system/distribution_and_updates.md | Framework vs. user-space model: getting upstream updates without losing customizations, protecting config, and backing up memory/handoffs/objectives | DOC-0031, DOC-0039 | implementation | File |
| DOC-0039 | memory.md | system/memory.md | Where harness transcripts and agent memory live ($HORIZON_ROOT/memory/ via the ~/.claude/projects symlink), owner/brain redirect mechanics, and uninstall warning | DOC-0043, DOC-0042 | implementation | File |
| DOC-0040 | model_preferences.md | system/model_preferences.md | How-to and reference for the in-context model-preference layer: BYO approach, member grammar, gitignored extend file, /model-prefs and /model-catalog-refresh skills | DOC-0006, DOC-0041 | implementation | File |
| DOC-0041 | skill_model_groups.md | system/skill_model_groups.md | How AIOS skills declare a model-preference group via body callout (not frontmatter), choosing a group, /skill-creation defaults, and /model-prefs-assign auditing | DOC-0040 | implementation | File |
| DOC-0042 | system_configuration_reference.md | system/system_configuration_reference.md | Authoritative reference for the full configuration architecture: what each file controls, dependencies, and how all components fit together | DOC-0003, DOC-0010 | implementation | File |
| DOC-0043 | uninstall.md | system/uninstall.md | Authoritative runbook for removing the AIOS footprint: what it removes vs. preserves, post-uninstall verification checklist, and full install→uninstall validation cycle | DOC-0030, DOC-0039 | implementation | File |

---

## Rollup: user_guides

| Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type |
|--------|----------|----------------------|-------------|------------|--------|------|
| DOC-0054 | user_guides.index.md | user_guides/user_guides.index.md | Index of this directory | — | — | File |
| DOC-0045 | using_Horizon.AIOS.md | user_guides/using_Horizon.AIOS.md | Post-install operational wiki: security model, building and configuring brains, projects, handoffs/objectives, BYOH/local.agents.md, model preferences, agent teams, context management, gitignore conventions, enterprise deployment, and IaC/containerization | DOC-0003, DOC-0040, DOC-0036 | implementation | File |
