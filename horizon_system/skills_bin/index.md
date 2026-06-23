# Skills Index — skills_bin

Group-readable skills available to all brains. Check this file first when looking for a skill.

**When adding a skill to skills_bin: add an entry here in the same commit.**

| Skill | Trigger | Model group | Purpose |
|---|---|---|---|
| context-cost | `/context-cost` | `#lowcost` | Report KB, word count, and estimated tokens for all CLAUDE.md / agents.md / @-import files the harness auto-loads above a given path |
| doctor | `/doctor` | `#lowcost` | Run the read-only AIOS health check (env vars, skills junction, hooks, registry, privileged-dir Deny ACLs) and report passed/warnings/failures |
| monitor | `/monitor` | `#fast` | Start the AIOS filesystem integrity monitor (watches the system dirs, logs create/modify/delete/move events as JSON lines); requires elevation |
| model-catalog-refresh | `/model-catalog-refresh` | `#investigate` | Fetch current models + pricing from live provider docs (Anthropic, OpenAI, Gemini, Ollama) and return a structured catalog to populate or validate the model-preference config |
| model-prefs-test | `/model-prefs-test` | `#lowcost` | Test how each model group resolves in the current runtime (dry-run), or spawn small agents by group to confirm the spawn honors the config and self-report the model (--live) |
