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
