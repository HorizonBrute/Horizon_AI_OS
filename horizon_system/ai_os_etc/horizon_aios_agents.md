**"Send an agent team"** 
- "Send an Agent team" , "send a team" "send a [name-ish] to..."  resolves through "Agent Teams" defined in
- `$HORIZON_ROOT/agent_teams.md`. Named variants select the matching team by name.
- Delegate to agents and teams to save primary context window. Decompose tasks, spawn agents, synthesize results. Never read files, write code, or run commands inline if the work can be delegated.

**Agents are self-sufficient.** Resolve problems independently before reporting back. Return to the main session only if: (a) the user must be informed, or (b) a decision only the user can make is required.


# Your top priority: Be  Token-Efficient 
Prefer CLI tools over file-content tools for mechanical operations:
- **Search:** `grep`/`Select-String`/`rg` — not Read + scan
- **Move/copy/rename:** `mv`/`Copy-Item`/`Rename-Item` — not Read + Write + delete
- **Bulk replace:** `sed`/`Get-Content | ForEach-Object | Set-Content` — not Read + Edit
- **Directory listing:** `ls`/`Get-ChildItem` — not Glob
- **Check existence:** `Test-Path`/`[ -f ]` — not Read
Use Read/Write/Edit only when content must be reasoned about or precisely modified.
GIt commit silently
DO not read large files, or multiple large files unless its specifically asked for by your tasking.


# Using Skills:
`~/.claude/skills/` is a symlink: not a copy. 
If you are a brain or stem your skills are located at `$HORIZON_BRAIN_ROOT/[brain name]/skills/`
If you are a brain or stem unfamiliar with a skill, check  `$HORIZON_SYSTEM/skills_bin/index.md` 
If you are not a brain or a stem, you malso check `$HORIZON_SYSTEM/skills_bin/index.md` if you get a file system ACL permission error this is by design, move on.
Check index before searching individual skill files:
IF creating skills ask if its common for AIOS, or for a Brain or a Stem, if for AIOS: `/hz_aios_skill-creation` — never hand-crafted — to ensure correct structure, indexing. 
Do **not** import at session start.

# Agent Behavior:
## Lists
Always use hierarchical numbered format: `1.` top-level, `1.1` items, `1.1.1` sub-items. Never use bullets or lettered lists.
