# Skills Index — skills_bin

Group-readable skills available to all brains. Check this file first when looking for a skill.

**When adding a skill to skills_bin: add an entry here in the same commit.**

| Skill | Trigger | Purpose |
|---|---|---|
| context-cost | `/context-cost` | Report KB, word count, and estimated tokens for all CLAUDE.md / agents.md / @-import files the harness auto-loads above a given path |
| doctor | `/doctor` | Run the read-only AIOS health check (env vars, skills junction, hooks, registry, privileged-dir Deny ACLs) and report passed/warnings/failures |
| monitor | `/monitor` | Start the AIOS filesystem integrity monitor (watches the system dirs, logs create/modify/delete/move events as JSON lines); requires elevation |
| model-catalog-refresh | `/model-catalog-refresh` | Fetch current models + pricing from live provider docs (Anthropic, OpenAI, Gemini, Ollama) and return a structured catalog to populate or validate the model-preference config |
