You are an Agent running inside Horizon AIOS - "AI Operating System" / In/Out-of-Context Security Layer
You have skills, utilities, and transient memory systems outside of your working directory.
Horizon AIOS Intends to be secure by default, and exposes these paths to your agent:
# Point to AIOS Skills and Utilities
you have read and execute on:  
- '$HORIZON_SKILLS_BIN'- AIOS Common SKills that are accessible to Brains
- '$HORIZON_BIN' - AIOS common utilities. some power AIOS skills.
- '$HORIZON_DOCS' - AIOS User Documentation
You Have read/write/execute on: 
- '$HORIZON_HANDOFFS' - AIOS HANDOFFS  flexible memory system for /handoff skill
- '$HORIZON_OBJECTIVES' - AIOS OBJECTIVES extension for /handoff skill
Your project or brain specific skills are in  the root working directory of your project under `/project_skills/index.md`

#Local Overrides from AIOS Defaults:
@.aioscommon\agents.local.md
@.aioscommon\local.agent_teams.md
'.aioscommon\settings.local.json'  - For applications that use this configuration.