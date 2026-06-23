# Horizon AIOS — Agent Instructions

Invariant documents — authoritative:
- Security invariants: `$HORIZON_ETC/security_invariants.md`
- File structure invariants: `$HORIZON_ETC/file_structure_invariants.md`
- Personalization model: `$HORIZON_ETC/ai_os_personalizations.md`

Never hardcode paths — use $HORIZON_ROOT, $HORIZON_SYSTEM, $HORIZON_BIN, $HORIZON_ETC, $HORIZON_DOCS.

@horizon_system/ai_os_etc/horizon_aios_agents.md
@horizon_system/ai_os_etc/horizon_aios_model_prefs.md
@horizon_system/ai_os_etc/horizon_aios_model_prefs.extend.md

## Agent Teams

Agent Teams define how the user prefers to spawn agents. If asked to send/spawn an agent team, consult these (local overrides win):

@./agent_teams.md
@./local.agent_teams.md

<!-- Machine-local override — last so it wins. Gitignored; never synced or clobbered. See file_structure_invariants §12. -->
@local.agents.md
