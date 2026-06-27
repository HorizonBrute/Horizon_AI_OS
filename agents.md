# Horizon AIOS — Agent Instructions
Invariant documents — authoritative:
- Security invariants: `$HORIZON_DOCS/security_architecture_invariants.md`
- Branding invariants: `$HORIZON_DOCS/branding_invariants.md`
- File structure invariants: `$HORIZON_ETC/file_structure_invariants.md`
- Personalization model: `$HORIZON_ETC/ai_os_personalizations.md`
- Terseness contract: `$HORIZON_DOCS/terseness_contract_index.md`

User documentation — constitutional (the canonical user-facing reference):
- Documentation index: `$HORIZON_DOCS/index.md`
- Operational wiki: `$HORIZON_DOCS/user_guides/using_Horizon.AIOS.md`

# OS Overhead
Never hardcode paths — use $HORIZON_ROOT, $HORIZON_SYSTEM, $HORIZON_BIN, $HORIZON_ETC, $HORIZON_DOCS.
@horizon_system/ai_os_etc/horizon_aios_agents.md
@horizon_system/ai_os_etc/horizon_aios_model_prefs.md

## Agent Teams
If asked to send/spawn an agent team, consult these (local overrides win):
@agent_teams.md
Role-flag vocabulary (if needed / if asked / parallel / wait / loop, plus any custom flags); local overrides win:
@horizon_system/ai_os_etc/agent_team_flags.md
@horizon_system/ai_os_etc/local.agent_team_flags.md

# Local Over Rides
@includes/local.agent_teams.md
@includes/local.agents.md
@horizon_system/ai_os_etc/horizon_aios_model_prefs.local.md