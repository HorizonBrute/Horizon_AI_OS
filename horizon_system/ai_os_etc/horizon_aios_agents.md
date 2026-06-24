# Horizon AIOS — Agent Configuration (OS Layer)

Harness-specific config: `horizon_system/harness_configs/<harness>/`. Invariants: `horizon_system/ai_os_etc/`.

---

# System-Level Preferences

## Agent Usage

**The main session is an orchestrator, not a worker.** Decompose tasks, spawn agents, synthesize results. Never read files, write code, or run commands inline if the work can be delegated.

**"Send an agent team"** resolves through the Agent Teams framework defined in
`$HORIZON_ROOT/agent_teams.md`. Named variants select the matching team by name.

When in doubt, delegate.

**Agents are self-sufficient.** Resolve problems independently before reporting back. Return to the main session only if: (a) the user must be informed, or (b) a decision only the user can make is required.

## Lists

Always use hierarchical numbered format: `1.` top-level, `1.1` items, `1.1.1` sub-items. Never use bullets or lettered lists.

## Token-Efficient File Operations

Prefer CLI tools over file-content tools for mechanical operations:

- **Search:** `grep`/`Select-String`/`rg` — not Read + scan
- **Move/copy/rename:** `mv`/`Copy-Item`/`Rename-Item` — not Read + Write + delete
- **Bulk replace:** `sed`/`Get-Content | ForEach-Object | Set-Content` — not Read + Edit
- **Directory listing:** `ls`/`Get-ChildItem` — not Glob
- **Check existence:** `Test-Path`/`[ -f ]` — not Read

Use Read/Write/Edit only when content must be reasoned about or precisely modified.

## Session Start

Check whether the AIOS filesystem monitor is running:

```
python $HORIZON_BIN/monitor_status.py
```

Output: `running` or `stopped`. If `stopped`, ask the user: "The AIOS filesystem monitor is not running. Enable file access logging? Run: `python $HORIZON_SYSTEM/sbin/horizon_aios_monitor.py` (administrative context required)."

Do not start the monitor yourself.

## Skills

`~/.claude/skills/` is a symlink — not a copy. Primary user → `skills_sbin/`. Brain users → `skills_bin/`. Skills are live on disk immediately; only a session restart is needed.

Check the index before searching individual skill files:
- `$HORIZON_SYSTEM/skills_sbin/index.md` — owner-only privileged skills (primary user)
- `$HORIZON_SYSTEM/skills_bin/index.md` — group-readable skills (all brains)

To make a skill available to brains: add it to `skills_bin/` and update `skills_bin/index.md` in the same commit.

When adding any skill, update the appropriate index.md in the same commit.

**New skills must follow the `skill-creation` skill template.** Invoke `/skill-creation` or read `$HORIZON_SYSTEM/skills_sbin/skill-creation/SKILL.md` before creating any new skill to ensure correct structure and registration.

## OS-Layer Development Values

When making architectural or design decisions on the AIOS OS layer, read on demand:

    $HORIZON_DOCS/dev_values.md       — engineering values and rules
    $HORIZON_DOCS/philosophy.md       — conceptual vocabulary (Brain vs. AIOS, blue team answerability, BYOH)

Do **not** import at session start.

## Commits

Always use `git commit -s` (DCO sign-off required). Never omit `-s`.
