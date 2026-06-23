# Horizon AIOS — Agent Instructions

Invariant documents — authoritative:
- Security invariants: `$HORIZON_ETC/security_invariants.md`
- File structure invariants: `$HORIZON_ETC/file_structure_invariants.md`
- Personalization model: `$HORIZON_ETC/ai_os_personalizations.md`

User documentation — constitutional (the canonical user-facing reference):
- Documentation index: `$HORIZON_DOCS/index.md`
- Operational wiki: `$HORIZON_DOCS/user_guides/using_your_aios.md`

Never hardcode paths — use $HORIZON_ROOT, $HORIZON_SYSTEM, $HORIZON_BIN, $HORIZON_ETC, $HORIZON_DOCS.

@horizon_system/documentation/index.md
@horizon_system/documentation/user_guides/using_your_aios.md
@horizon_system/ai_os_etc/horizon_aios_agents.md
@horizon_system/ai_os_etc/horizon_aios_model_prefs.md
@horizon_system/ai_os_etc/horizon_aios_model_prefs.extend.md

## Agent Teams

Agent Teams define how the user prefers to spawn agents. If asked to send/spawn an agent team, consult these (local overrides win):

@./agent_teams.md
@./local.agent_teams.md

<!-- Machine-local override — last so it wins. Gitignored; never synced or clobbered. See file_structure_invariants §12. -->
@local.agents.md
