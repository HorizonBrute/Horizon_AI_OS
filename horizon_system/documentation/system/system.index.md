# system — Documentation Index

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
