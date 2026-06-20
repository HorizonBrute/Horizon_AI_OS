# AIOS Agent Instructions

This file is the canonical instruction set for AI agents operating in a Horizon AIOS session.
It is harness-agnostic — read by Claude Code (via CLAUDE.md import), Codex, and any other
AI tool that supports agents.md or equivalent instruction files.

Harness-specific configuration lives in `horizon_bin/harness_configs/<harness>/`.
Security, file structure, and personalization invariants: `horizon_bin/ai_os_etc/`.

---

# System-Level Preferences

## Agent Usage

I prefer to use agents and keep the main session's context as light as possible. Delegate to agents aggressively rather than doing work inline.

**The main session is an orchestrator, not a worker.** It should decompose tasks, spawn agents, and synthesize results — not read files, write code, or run commands itself. If a task involves reading code, editing files, running tools, or researching anything, that work belongs in an agent.

**"Send an agent team"** means spawn agents in this order:
1. **Orchestration agent** — reads the task, breaks it down, and coordinates the rest
2. **Log reader agent** *(if needed)* — reads runtime logs to gather evidence before planning
3. **Planner agent** — designs the implementation approach
4. **Implementer agent** — writes the code
5. **Validator agent** — verifies the fix works and nothing regressed

When in doubt whether to do something inline or delegate, delegate.

## Lists

Whenever presenting a list of any kind, always use hierarchical numbered format: `1.` for top-level headers, `1.1` for items, `1.1.1` for sub-items. Never use bullet points or lettered lists.

**Agents should be self-sufficient.** When an agent encounters a problem, it should attempt to resolve it independently before reporting back. An agent should only return to the main session if: (a) the user needs to be made aware of something, or (b) a decision or input is required that only the user can provide.

## Token-Efficient File Operations

Prefer CLI tools over read/write tools whenever possible. Shell commands consume far fewer tokens than reading file content into context.

- **Search:** use `grep`/`Select-String`/`rg` — not Read + manual scan
- **Move/copy/rename:** use `mv`/`Copy-Item`/`Rename-Item` — not Read + Write + delete
- **Bulk replace:** use `sed`/`(Get-Content | ForEach-Object { ... } | Set-Content)` — not Read + Edit for large files
- **Directory listing:** use `ls`/`Get-ChildItem` — not Glob when a shell call suffices
- **Check existence:** use `Test-Path`/`[ -f ]` — not Read

Use Read/Write/Edit only when content must be reasoned about or precisely modified. Agents should apply this same principle — prefer `Bash`/`PowerShell` tool calls over file-content tools for mechanical operations.

## OS-Layer Development Values

When making architectural, design, or configuration decisions on the AIOS OS
layer itself, load and consult the values document:

    $HORIZON_DOCS/dev_values.md

Do **not** import this file at session start — read it on demand when a
decision benefits from it. This keeps session context lean. The values document
is the reference for resolving tradeoffs between security, token economy,
extensibility, documentation parity, and standardization.

## Commits

Always use `git commit -s` when creating commits in this repository. The DCO (Developer Certificate of Origin) requires a `Signed-off-by:` line in every commit message. Never create a commit without the `-s` flag.
