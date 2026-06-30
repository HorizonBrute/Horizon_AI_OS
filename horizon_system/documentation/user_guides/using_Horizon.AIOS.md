# Using Your Horizon AIOS — Operational Wiki

This wiki bridges the gap between initial setup and daily operation. It assumes AIOS is installed and running. If it is not, start with `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md`.

---

## Table of Contents

1. [The Security Model](#1-the-security-model)
2. [Building and Configuring a Brain](#2-building-and-configuring-a-brain)
3. [Projects — Purpose and Practical Patterns](#3-projects--purpose-and-practical-patterns)
4. [Session Continuity — Handoffs and Objectives](#4-session-continuity--handoffs-and-objectives)
5. [Case Study — The Developer Brain](#5-case-study--the-developer-brain)
6. [Bring Your Own Harness and local.agents.md](#6-bring-your-own-harness-and-localagentsmd)
7. [Model Preferences and Agent Teams](#7-model-preferences-and-agent-teams)
8. [Understanding and Managing Context](#8-understanding-and-managing-context)
9. [The Terseness Contract](#9-the-terseness-contract)
10. [Gitignore, Local Config, and What Not to Commit](#10-gitignore-local-config-and-what-not-to-commit)
11. [Enterprise Deployment](#11-enterprise-deployment)
12. [Containerization, Cloud, and Infrastructure as Code](#12-containerization-cloud-and-infrastructure-as-code)
13. [Bring Your Own Infrastructure — Integrated Identity and Existing Security](#13-bring-your-own-infrastructure--integrated-identity-and-existing-security)

---

## 1. The Security Model

### 1.1 The Core Principle

Horizon AIOS is not a security framework — it is a configuration layer that redirects existing OS security mechanisms toward AI workloads. The security model's governing question is the one a security team asks when approving any new application: *What is the agent doing? How? With what access? And how do we enforce it?*

AIOS answers all of these from the OS layer. There is no custom security engine. The enforcements are the same mechanisms your IT infrastructure already knows:

- **User isolation** — OS user accounts and NTFS ACLs / POSIX permissions
- **Access control** — `icacls` (Windows) / `chmod` (Unix), not reimplemented
- **Audit logging** — the AIOS filesystem monitor writing JSON-line events, compatible with any SIEM
- **Credential containment** — OS-native credential stores (Windows Credential Manager / macOS Keychain / Linux Secret Service)

See `$HORIZON_DOCS/philosophy.md` §§3–4 for the full "Blue Team Answerability" treatment.

### 1.2 Brains in the Security Model

A **brain** is a separate OS user account scoped to its own directory subtree. This is not a metaphor — the brain user is a real local account with a generated 64-character password stored in the OS keystore, never printed anywhere.

The security model for a brain at provisioning time:

| What | Enforcement |
|---|---|
| Full access to its own workspace (`brains/<name>/`) | `brains_group` ACL grants full control; no other account has access |
| Read + execute on `$HORIZON_BIN` and `skills_bin` | `brains` group grant — the "can use AIOS tooling" gate |
| Explicit Deny on `sbin`, `skills_sbin`, and `logs` | Non-inherited Deny ACE — cannot be overridden by any Allow |
| Cannot write to the AIOS system layer | Deny ACE on `$HORIZON_SYSTEM`; OS-enforced regardless of what the harness says |

The critical property: **even a fully compromised harness cannot escalate past the OS boundary.** The Deny ACEs are not app-layer promises. They are OS-level restrictions that the harness runs inside — not controls the harness can modify.

A brain's access to data and tooling is zero by default. Every grant must be explicit and is answerable from the provisioning record (`.aios_provision.json` in the brain's folder).

For isolation verification commands, see `$HORIZON_DOCS/security/brain_isolation_test.md`. To re-apply the ACL model after structural changes, run `/harden`.

### 1.3 Bring Your Own Harness in the Security Model

BYOH means the harness — Claude Code, Codex, Ollama, or any tool that reads `agents.md` — is a guest inside the AIOS layer, not the layer itself. A brain's harness is configured to point at the AIOS but runs as the brain OS user, so it is bounded by the brain's OS permissions.

Harness-specific configuration lives in `$HORIZON_SYSTEM/harness_configs/<vendor>/` and extends — but never replaces — the cross-harness core. The security invariants (ACLs, isolation boundaries, credential containment) have no harness dependency. Swapping the harness does not change what the brain can reach.

The implication: **the security model is the same regardless of which harness the brain runs.** A brain running Claude Code and a brain running Codex have the same filesystem restrictions. The harness governs what the AI can do within those bounds; the OS governs what the account can touch.

See `$HORIZON_DOCS/philosophy.md` §7 (BYOH) and `$HORIZON_ETC/security_invariants.md` §5 (the harness-is-bounded-by-the-OS invariant).

---

## 2. Building and Configuring a Brain

### 2.1 Provisioning

Brain provisioning is a single elevated command:

```bash
# Windows (Administrator PowerShell)
python "$env:HORIZON_SYSTEM\sbin\horizon_aios_create_brain.py" <brain-name>

# Linux / macOS
sudo python "$HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py" <brain-name>
```

Or use the `/create-brain` skill from an owner session. The script creates the OS user account, the `brains` group (if absent), a per-brain group, the workspace folder with correct ACLs, and a shell profile that loads the `HORIZON_*` environment variables on login. A `.aios_provision.json` manifest is written into the brain's folder.

After provisioning, the brain user's `~/.claude/` is already pointed at `brains/<name>/.claude/` — the harness is wired to AIOS at provisioning time, not separately. There is no additional "connect harness to AIOS" step.

Brain names must match `^[a-z][a-z0-9_]{1,31}$`. Use descriptive names that reflect the brain's function: `code_reviewer`, `inbox_triage`, `research_assistant`.

### 2.2 The Brain's Home Directory

The brain's workspace lives at `$HORIZON_ROOT/brains/<name>/`. This is the brain's entire world by default. Inside it:

```
brains/<name>/
  .claude/
    CLAUDE.md          # brain identity, persona, scope — edit this after provisioning
    settings.json      # harness-layer permissions (defense-in-depth only; real isolation is the ACLs)
    skills -> $HORIZON_SYSTEM/skills_bin/   # symlink; brain sees group-readable skills only
  .aios_provision.json  # provisioning manifest; do not delete
  memory/               # the brain's memory system — your design, your choice
  projects -> ...        # optional: symlinks to project folders
  tools/                 # optional: scripts, MCP configs, credentials the brain needs
```

### 2.3 Building the Memory System

**The AIOS does not implement a memory system.** The `brains/<name>/` directory is a secure, isolated container. What you put inside it is your decision entirely.

Common patterns:

- **File-based memory** — Markdown documents, calibration files, few-shot examples, domain knowledge. The simplest form. The brain's `CLAUDE.md` tells it where to look and what the files mean.
- **Vector index** — a ChromaDB, FAISS, or similar index stored in a subdirectory. The brain has a retrieval script in `tools/` that wraps it.
- **Structured knowledge base** — SQLite database, JSON knowledge store, or any format the brain's tooling can query.
- **Conversation history** — the harness writes transcripts to `brains/<name>/.claude/projects/` automatically (via the `~/.claude/projects` redirect). These are available to the brain across sessions.

The memory system is what makes the brain an expert rather than a stateless query processor. When the brain's expertise is consolidated in self-contained artifacts within its directory — not embedded in a specific harness or model fine-tuning — the brain is portable: swap the harness, swap the model, move to another machine, and the expertise travels with the directory.

See `$HORIZON_DOCS/philosophy.md` §6 for the design rationale and `$HORIZON_DOCS/system/memory.md` for how harness transcripts are redirected.

### 2.4 Giving the Brain Access to Tooling

**Bring the tooling to the brain — don't expect the brain to range for it.**

Tools are delivered into the brain's boundary, externally provisioned. Every tool the brain holds is auditable and revocable. The provisioning question: "What tooling does this brain have?" is answerable from what was brought to it.

Practical provisioning:

1.1 **Scripts and CLI tools** — place in `brains/<name>/tools/`. These are files the brain's OS user owns and can execute. Keep them deterministic. The brain coordinates the tool; the tool does the computation.

1.2 **MCP servers** — MCP configuration lives in the brain's harness settings (`brains/<name>/.claude/settings.local.json`) under the `mcpServers` key. Since the brain's `~/.claude` symlinks to `brains/<name>/.claude/`, MCP servers configured there are available only to that brain.

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    }
  }
}
```

Scope MCP server paths to what the brain actually needs. An MCP server that exposes the full filesystem defeats the isolation model.

1.3 **Credentials** — store in the OS-native credential store via `horizon_aios_brain_credential.py`, or place credential files inside `brains/<name>/`. Never store credentials in committed files or environment variables that could leak.

1.4 **Network access** — the brain OS user has the same network access as any local account by default. To restrict it, apply OS-level firewall rules or network policies per account. AIOS does not manage network access; that is a standard IT infrastructure concern.

1.5 **Filesystem access beyond the brain's home** — grant access to additional paths explicitly. On Windows: `icacls <path> /grant <brain-name>:(OI)(CI)RX`. On Unix: add the brain user to a group that owns the target directory, or set ACLs with `setfacl`. Document every grant in the brain's provisioning record.

### 2.5 Running the Harness as the Brain User

The harness must run as the brain OS user — not as the owner — to enforce the isolation boundary. The harness reads configuration from `~/.claude/`, and the brain's `~/.claude/` is symlinked to its workspace, so the harness automatically gets the brain's context when launched as the brain.

**Interactive use:**

```powershell
# Windows — launch Claude Code as the brain
runas /user:<brain-name> claude

# Linux / macOS — switch to the brain user and launch
su - <brain-name>
claude
```

On Windows, the brain's password can be retrieved (as Administrator) for `runas`:
```powershell
python "$env:HORIZON_SYSTEM\sbin\horizon_aios_brain_credential.py" get <brain-name> --show
```

**Automated / unattended use:**

For scheduled tasks or daemons, provision the brain with a logon right:

```bash
python $HORIZON_SYSTEM/sbin/horizon_aios_create_brain.py <brain-name> --automation scheduled
```

Then register a Windows Task Scheduler task or Linux cron job whose user account is the brain. The task launches the harness directly (`claude -p "<prompt>"`). Because the task runs as the brain user, all isolation guarantees apply — the scheduled harness cannot access anything the brain's ACLs deny it.

See `$HORIZON_DOCS/deployment/brain_automation.md` for the full three-tier logon rights model (none / scheduled / daemon) and `$HORIZON_DOCS/deployment/desktop.md` for the complete wiring walkthrough.

---

## 3. Projects — Purpose and Practical Patterns

### 3.1 What Projects Are

A project is any folder inside `$HORIZON_ROOT` that you choose to work in. AIOS gives it no special treatment by default — it just inherits the full AIOS Claude Code environment automatically, with no per-project wiring.

What makes a folder a project (in the meaningful sense) is that it has its own independent Git history:

```bash
mkdir "$HORIZON_ROOT/my-project"
cd "$HORIZON_ROOT/my-project"
git init
```

From this point, the folder is invisible to the OS repo. Git does not descend into subdirectories with their own `.git`. The OS repo tracks AIOS config; this project tracks its own source code, history, and remotes.

No `.gitignore` entry is needed. The pre-commit hook handles any edge case where files were tracked before `git init` was run.

### 3.2 Why Separate Development Tooling from Code Repos

The AIOS layer (with all its configuration, skills, hooks, and harness settings) lives in the OS repo at `$HORIZON_ROOT`. Code projects live in nested repos. The separation serves several purposes:

- **Audit isolation** — the AIOS monitor watches the OS layer for unexpected changes. Code repositories under their own git histories have different change patterns and are out of scope by default. You can extend the monitor's watch to specific project paths if you want to audit them.
- **Brain containment** — a brain given access to a project folder can read and write within it, but the AIOS layer remains protected by its own ACLs regardless of what the brain does inside the project.
- **Config hygiene** — AI development tooling (CLAUDE.md files, skills, model preferences, hooks) lives in the OS repo. Code lives in project repos. When you update the OS layer, code projects are unaffected. When code project files change, the OS layer is unaffected.
- **Harness portability** — a project folder can be moved, shared, or synced independently. The AIOS layer stays on the machine.

### 3.3 Practical Patterns for Project Folders

Projects inside `$HORIZON_ROOT` are just directories. The OS provides standard filesystem semantics. This means you can use them however it makes sense for your workload:

**Code repositories.** The most common case. Each project is a git repo. The developer works inside it; the AIOS environment applies automatically.

```
$HORIZON_ROOT/
  my-api/         # git repo — the backend
  my-frontend/    # git repo — the frontend
  shared-libs/    # git repo — shared code
```

**NTFS directory symlinks.** A project folder can be a directory symlink (Windows) or symlink (Unix/macOS) pointing to a directory elsewhere on the machine or on a network share. From the AIOS and the brain's perspective, it looks like a normal folder. AIOS requires admin installation, so `mklink /D` (and `New-Item -ItemType SymbolicLink`) are available.

```powershell
# Windows — directory symlink to a network share or local path (run as administrator)
New-Item -ItemType SymbolicLink -Path "$env:HORIZON_ROOT\my-project" -Target "\\fileserver\share\my-project"
```

**Cloud-synced storage.** OneDrive, Google Drive, Dropbox, or cloud provider storage (AWS S3 via rclone, GCP Storage via Cloud Drive, Azure Storage via Azure File Sync) can be mounted or synced at a project folder path. The AIOS sees a local folder; the sync is handled by the OS and the cloud provider's tools. For what to exclude from sync, see `$HORIZON_DOCS/cloud_sync_exclusions.md`.

**Brain access points.** When you provision a brain to work on a project, you grant the brain's OS user access to the project folder and optionally create a symlink inside the brain's workspace pointing to it:

```bash
# Grant access
icacls "$HORIZON_ROOT\my-project" /grant <brain-name>:(OI)(CI)RX

# Optionally, link from inside the brain workspace (run as administrator)
New-Item -ItemType SymbolicLink -Path "$HORIZON_ROOT\brains\<brain-name>\my-project" `
  -Target "$HORIZON_ROOT\my-project"
```

The brain navigates to its symlink. From its perspective, the project folder is inside its home directory — its harness context starts there, and the AIOS environment applies.

### 3.4 Project-Level AIOS Overrides

To customize AIOS behavior for a specific project, drop an `aios_overrides.md` at the project root:

```bash
cp "$HORIZON_SYSTEM/templates/aios_overrides.md" "$HORIZON_ROOT/my-project/aios_overrides.md"
```

This can override `handoffs_dir`, `objectives_dir`, `project_display_name`, and other per-project settings. It does not affect the OS-layer security model or the brain isolation boundary.

Project-specific AI instructions go in `$HORIZON_ROOT/my-project/.claude/CLAUDE.md`. Claude Code loads these on top of the global CLAUDE.md when working inside that project.

---

## 4. Session Continuity — Handoffs and Objectives

### 4.1 The Problem They Solve

Every Claude Code session starts fresh. Context that mattered in the previous session is gone. For short tasks this is fine. For multi-session work — a complex feature, a weeks-long investigation, an evolving project — you need a way to carry state forward without manually re-explaining it every time.

Horizon AIOS provides two complementary tools for this: **handoffs** (point-in-time session state) and **objectives** (durable, evolving goals).

### 4.2 /handoff

A handoff is a structured Markdown document that captures where a session ended and where the next one should pick up. Run `/handoff` at the end of any significant session.

The handoff document contains:
- What was accomplished in this session
- What decisions were made and why
- What is deferred or blocked
- The recommended entry point for the next session
- A link to the active objective (if one exists)

Handoffs write to `$HORIZON_ROOT/handoffs/` by default (configurable per project via `aios_overrides.md`). At the start of a new session on the same topic, read the most recent handoff to restore context.

**Usage:**
```
/handoff
```

Claude will ask clarifying questions if needed, then write the document. No flags or arguments are required for a basic handoff. The skill is owner-only (`skills_sbin/`).

### 4.3 /objective

An objective is a durable goal document that persists across many sessions and many handoffs. Where a handoff captures a moment in time, an objective captures the sustained intent — what you are ultimately trying to accomplish and why.

Objectives live in `$HORIZON_ROOT/objectives/` (configurable). They are plain Markdown files numbered sequentially. Handoffs reference objectives by number, so the goal survives even as the tactical details evolve across sessions.

**Creating an objective:**
```
/objective create "Migrate the authentication system to JWT by end of Q3"
```

**Listing objectives:**
```
/objective
```

**Referencing in a handoff:** When you run `/handoff` with an active objective in context, the handoff links back to it automatically. Future sessions can open the objective to understand the broader goal before reading the tactical handoff.

**Updating an objective:**
```
/objective update 1 "Migrate auth to JWT; RS256 algorithm confirmed, refresh token scope still open"
```

Objectives are point-of-truth documents — not status dashboards. They record the goal and its key constraints. Daily status belongs in handoffs.

### 4.4 Starting a New Session from a Handoff

When you start a session on a topic that has a handoff, pass the handoff filename directly at the start of the conversation:

```
C:\Users\you\horizon\handoffs\2026-06-22_141500_my-project.md
```

The agent reads the handoff silently into context — it does not reprint the document, which would bloat context and bury the useful output. Instead, it gives you a 2–4 line orientation: what was being worked on and where to start. You do not need to re-explain context.

If the handoff references an active objective, load it directly:

```
/objective 3
```

The objective provides the durable goal; the handoff provides the tactical state. Together they restore full context in seconds.

### 4.5 The Objective-Handoff Chain

For sustained work spanning more than a couple of sessions, use handoffs and objectives together:

1. **Create an objective** at the start of the engagement: `/objective create "Migrate the authentication system to JWT by Q3"`
2. **Run `/handoff` at the end of each session.** With an active objective in context, the handoff links to it automatically — the handoff's `Objective:` field carries the number, name, and file path.
3. **Start the next session** by reading the handoff. Its `Objective:` field points to the objective file. Reading the objective restores the durable goal; reading the handoff restores the tactical state.
4. **Update the objective** when something significant changes: `/objective update 1 "JWT migration: RS256 algorithm confirmed, refresh token scope still open"`

The chain persists as long as you run `/handoff` at the end of each session. The objective link carries forward automatically across as many sessions as the work takes.

---

## 5. Case Study — The Developer Brain

This case study illustrates how a developer builds a brain for code review and development assistance, and how the day-to-day workflow operates.

### 5.1 The Setup

**Goal:** Separate AI development tooling from the development environment itself. The brain holds all code conventions, review logic, and scripting. The code lives in project folders. The developer uses the brain to assist with their development work, and automated agentic flows use the brain to monitor PRs.

**Brain name:** `code_review`

**Project folders:**
- `$HORIZON_ROOT/backend-api/` — the primary backend code repo
- `$HORIZON_ROOT/frontend/` — the frontend repo

### 5.2 Provisioning the Brain

```powershell
# Windows, Administrator PowerShell
python "$env:HORIZON_SYSTEM\sbin\horizon_aios_create_brain.py" code_review --automation scheduled
```

The `--automation scheduled` flag grants the `SeBatchLogonRight` so a Task Scheduler task can run the harness as `code_review` without a user being logged in. This is used for the PR-monitoring agentic flow.

### 5.3 Configuring the Brain's Workspace

After provisioning, the brain's workspace at `$HORIZON_ROOT/brains/code_review/` receives:

**1. Code conventions and requirements (`brains/code_review/conventions/`)**

The developer drops all their coding conventions, style guides, architecture decision records, and review checklists as Markdown files here. These become the brain's domain knowledge.

```
brains/code_review/
  conventions/
    style_guide.md
    api_design_principles.md
    test_requirements.md
    security_checklist.md
    architecture_decisions.md
```

**2. Brain identity (`brains/code_review/.claude/CLAUDE.md`)**

Edit the Role section of the provisioned template:

```markdown
## Role
You are the code review brain for [developer name]. Your expertise covers:
- This codebase's conventions — see `$BRAIN_HOME/conventions/`
- API design patterns documented in `conventions/api_design_principles.md`
- Security requirements in `conventions/security_checklist.md`

When reviewing code, always apply the full conventions set. When assisting with
development, your working context is the project the user names at session start.
```

**3. Granting project access**

```powershell
# Grant the brain read access to both project folders
icacls "$env:HORIZON_ROOT\backend-api" /grant "code_review:(OI)(CI)RX"
icacls "$env:HORIZON_ROOT\frontend" /grant "code_review:(OI)(CI)RX"

# Create navigation symlinks inside the brain workspace (optional but convenient; run as administrator)
New-Item -ItemType SymbolicLink -Path "$env:HORIZON_ROOT\brains\code_review\backend-api" `
  -Target "$env:HORIZON_ROOT\backend-api"
New-Item -ItemType SymbolicLink -Path "$env:HORIZON_ROOT\brains\code_review\frontend" `
  -Target "$env:HORIZON_ROOT\frontend"
```

**4. Model preferences for the automated PR flow**

The agentic PR-monitoring flow does status checks — a task that does not need a powerful model. In `brains/code_review/.claude/` (or in the OS-level extend file), configure the PR-check flows to use a token-conscious group:

In the brain's `CLAUDE.md` or in the agentic prompt that drives the scheduled task:
```
Use #lowcost for PR status checks and summaries. Use #highcap when doing
a full review pass with security checklist application.
```

Or in the model-prefs extend file (see `/model-prefs`):
```
## Task-Class Routing
- pr status checks, inbox triage, summaries -> #lowcost
- full code review, security audit          -> #highcap
```

### 5.4 The Automated PR-Monitoring Flow

The scheduled task runs daily (or on a trigger) as the `code_review` OS user. It launches the harness with a non-interactive prompt:

```powershell
# Registered in Task Scheduler, runs as code_review user
claude -p "Check the status of open PRs in backend-api. For each PR: summarize the change, flag any that have been open more than 3 days without activity, and note any that touch the auth module. Write the summary to $BRAIN_HOME/reports/pr_status_$(date +%Y%m%d).md"
```

Because the task runs as `code_review`, it:
- Has read access to `backend-api/` (explicitly granted)
- Has write access to `brains/code_review/` (its own workspace)
- Cannot touch the AIOS system layer (Deny ACE enforced by OS)
- Cannot access the owner's memory or other brains (isolation boundary)

The harness runs with the brain's `CLAUDE.md` loaded — it knows the codebase conventions without the developer re-explaining them.

### 5.5 The Interactive Development Workflow

When the developer sits down to work, they log into their own user account (not the brain). They open Claude Code, which runs as themselves. When they want to use the brain for development assistance:

```powershell
runas /user:code_review claude
```

Claude opens in the `code_review` user context, with the brain's full conventions and memory loaded. The developer tells it which codebase they are working on:

> "I'm working on the backend-api today. Specifically I'm implementing the new rate-limiting middleware."

The brain navigates to `backend-api/` (via the symlink in its workspace), loads the relevant conventions, and assists with development. All agentic work — file reads, writes (within the project folder), searches — happens within the brain's permission boundary. Any files the brain creates or modifies land in the project folder, which is where the developer's git history tracks them.

At the end of the session, the developer runs `/handoff` to capture where the implementation stands. If there is an active objective ("Implement rate limiting for the v2 API"), the handoff links back to it.

### 5.6 Why This Works

- **Conventions stay with the brain.** The developer does not re-paste style guides or architecture docs into every conversation. They live in the brain's workspace, loaded at session start.
- **Code stays in project repos.** The brain has access to read the code and write to the project folder, but the project's git history is independent. The developer's normal git workflow is unchanged.
- **Automated flows run as the brain.** The scheduled PR check is a real OS-level isolation boundary — not a software promise. The PR-checking process cannot access anything outside its provisioned scope.
- **Token cost is managed.** Routine agentic flows use `#lowcost`. Full review passes escalate to `#highcap`. The cost is proportionate to the task's reasoning requirement.

---

## 6. Bring Your Own Harness and local.agents.md

### 6.1 What BYOH Means in Practice

BYOH means the AIOS does not prescribe which AI system you use. You bring the harness (Claude Code, Codex, Ollama, or anything that can read `agents.md`), the model (any the harness supports), and the tooling (MCP servers, scripts, APIs).

The AIOS provides the structure: the standard directory layout, the cross-harness agent instruction conventions (`agents.md`), the security model, and the configuration management layer. These have no harness dependency.

The current implementation is fully wired for Claude Code. Other harnesses (Codex, Ollama, LM Studio) have stubs in `$HORIZON_SYSTEM/harness_configs/` but are not yet fully integrated. See `$HORIZON_DOCS/philosophy.md` §9 for the honest current-state assessment.

### 6.2 The Configuration Chain

Agent instructions load in a specific order, from most global to most local. Understanding this chain is how you configure a brain or a project without touching the shared OS layer:

```
~/.claude/CLAUDE.md              ← thin stub; points at the OS repo
  ↓ @-imports
$HORIZON_ROOT/.claude/CLAUDE.md  ← project harness entry; imports root CLAUDE.md
  ↓ @-imports
$HORIZON_ROOT/CLAUDE.md          ← AIOS-wide rules; imports agents.md
  ↓ @-imports
$HORIZON_ROOT/agents.md          ← cross-harness agent instructions
  ↓ @-imports
horizon_aios_agents.md           ← OS-layer agent config (skills, orchestration, session-start)
  ↓ @-imports
local.agents.md                  ← machine-local overrides (gitignored)
```

For a brain, the chain adds its workspace-root config at the innermost level:
```
brains/<name>/CLAUDE.md          ← thin entry; @-imports the files below
  ↓ @-imports
brains/<name>/brain_invariants.md ← brain hard rules
brains/<name>/brain_core.md       ← brain identity, persona, role, knowledge, scope
```

### 6.3 local.agents.md — The Primary Configuration Seam

`local.agents.md` is the gitignored override file at the end of the `agents.md` chain. It is the right place for any instruction that:
- Is specific to this machine or this owner's preferences
- Should not ship to other users or machines
- Overrides or extends shipped behavior

`aios setup` creates it from the template at `$HORIZON_ROOT/local.agents.md` and `$HORIZON_ROOT/.claude/local.agents.md`. Edit it directly. It is never overwritten by syncs or updates.

**Examples of what belongs in `local.agents.md`:**

```markdown
# Local Agent Instructions

## Git
- When the user says "commit", always commit AND push. Do not stop at the local commit.

## Session Behavior
- This machine is the code review workstation. Default the working project to backend-api
  unless the user specifies otherwise.

## Developer Identity
- Owner: Jane Smith. GitHub: @jsmith. GPG key fingerprint: ABCD1234...
```

Keep it short. `local.agents.md` loads into context every session. Every line costs tokens.

### 6.4 Adding Support for a New Harness

To add a new harness to the AIOS:

1.1 Create `$HORIZON_SYSTEM/harness_configs/<harness-name>/` for runtime config (hooks, sounds map, README).
1.2 Create `$HORIZON_SYSTEM/templates/<harness-name>/` for setup templates copied at bootstrap.
1.3 Add an equivalent to the Claude Code settings.json template for the new harness's config format.
1.4 Wire hooks to the sounds system in `$HORIZON_SYSTEM/sounds/`.
1.5 Document the harness in `$HORIZON_DOCS/`.

The brain model, ACL layer, and OS-level isolation are reusable as-is. The work is in the integration scaffolding, not the OS layer.

See `$HORIZON_ETC/ai_os_personalizations.md` §3 for the full harness addition protocol and `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md` → "Adding a New AI Harness."

---

## 7. Model Preferences and Agent Teams

### 7.1 Model Preferences — Routing Work to the Right Model

The model-preference layer lets you control which model handles different kinds of work — without changing your interactive session model. There is no resolver script, no engine, no env-var wiring. The mechanism is in-context instruction: you write a configuration file, the AIOS loads it each session, and the acting model honors it when spawning agents or delegating tasks.

**Model groups** are the core abstraction: named lists of models that define the capability tier for a class of work. The shipped groups:

| Group | Intended use |
|---|---|
| `#lowcost` | Routine, mechanical work — status checks, summaries, formatting |
| `#midcost` | Standard development and writing tasks |
| `#highcap` | Complex reasoning, cross-document synthesis, architecture decisions |
| `#investigate` | Research-heavy tasks requiring deep comprehension |
| `#debug` | Debugging passes, root cause analysis |
| `#fast` | Latency-sensitive operations where speed matters more than depth |

The system selects the first runnable member of the group in your current runtime. Members that do not match your runtime (e.g., an Ollama model in a Claude Code session) are silently skipped — so you can define groups that include both Anthropic and local models and the right one is used automatically based on what is available.

**What the preference layer governs.** Your interactive session model is set by the harness at launch and is not changed by this configuration. What it governs — for the first time — is the model used for spawned agents and delegated tasks. Routine delegated work runs on a cheap model; complex delegated work escalates automatically. Cost becomes proportionate to task reasoning requirements, decided by your configuration rather than left to defaults.

**Task-class routing** directs entire categories of work to the right tier automatically:

```
## Task-Class Routing
- pr status checks, inbox triage, summaries -> #lowcost
- full code review, security audit          -> #highcap
```

**Setting up model preferences:**

Run `/model-prefs` to configure interactively, or set up the extend file manually:

```bash
# Linux / macOS
cp "$HORIZON_ETC/horizon_aios_model_prefs.local.template.md" \
   "$HORIZON_ETC/horizon_aios_model_prefs.local.md"
```

```powershell
# Windows
Copy-Item "$env:HORIZON_ETC\horizon_aios_model_prefs.local.template.md" `
          "$env:HORIZON_ETC\horizon_aios_model_prefs.local.md"
```

All choices go in this gitignored file — never in the OS-tracked base spec, which a sync would overwrite. Run `/model-catalog-refresh` to fetch current model IDs and pricing before filling in group members.

Configuration cascades by scope: OS-global < project root < brain workspace, most-specific wins. A brain or project can override the global config by dropping its own extend file in its directory.

See `$HORIZON_DOCS/system/model_preferences.md` for the full member grammar, scope cascade, and configuration walkthrough.

### 7.2 Agent Teams — Structured Multi-Agent Workflows

Agent teams let you define coordinated multi-agent workflows with specific roles, model assignments, and loop constructs — invoked by name rather than assembled from scratch each time.

A team definition specifies:
- **Roles** — the participants, their charters, and their model groups
- **Loop constructs** — loop-back conditions, pass/fail criteria, and iteration caps that govern when agents hand off to each other

Four starter teams ship with the AIOS and are ready to use immediately:

| Team | Purpose |
|---|---|
| Investigate & Fix | Diagnose a problem then apply the fix |
| Full Team | Full lifecycle for a sizable or ambiguous task (default for "send an agent team") |
| Review & Fix | Audit a diff then apply findings |
| Explore & Summarize | Fan out across a codebase or question then distill |

**Using a team:**

Name the team at the start of a task that fits its pattern:

```
Use the Review & Fix team on the changes in this PR.
```

```
Send an Investigate & Fix team — the auth middleware is rejecting valid tokens intermittently.
```

**Defining your own team:**

Create or edit `local.agent_teams.md` in any scope. The innermost scope wins. Example:

```markdown
### security-review-team
Independent security audit of changed code.

1. Auditor A (`#investigate`, parallel) — injection risks and input validation
2. Auditor B (`#investigate`, parallel) — credential and secrets handling
3. Synthesizer (`#highcap`, wait) — consolidated findings with remediation priority
```

Run `/agent-teams` to manage team definitions interactively. See `$HORIZON_DOCS/system/agent_teams.md` for the full invocation pattern, scope cascade, and loop/retry grammar.

### 7.3 Loop / Retry Constructs

A role in an agent team can declare a **Loop** to re-run an earlier role with feedback until a pass condition is met or an iteration cap is reached. Declare it inline below the role:

> **Loop:** on `<condition>`, return feedback to `"<role name>"` and re-run from there; repeat until `<pass condition>` or `<max>` iterations, then `<action at cap>`.

Four things a looping role must specify:

1. **Condition** — what counts as a failure and triggers another pass (e.g., "validation fails").
2. **Loop-back target** — the earlier role to re-run, by name (preferred over step number so renumbering never breaks the target).
3. **Max iterations** — a hard cap that bounds cost and guarantees termination.
4. **Cap action** — what to do if the cap is hit without passing: `report-failure` (stop and surface outstanding failures) or `proceed` (continue with a caveat). Prefer `report-failure`.

The `full-team` Validator is the canonical example: if it fails, it returns specific feedback to the Implementer and re-runs from there — up to 3 iterations, then stops and reports rather than proceeding with broken output.

### 7.4 Conditional Roles

A role may be marked conditional by appending a flag inside its model-group parenthetical:

- `(#group, if needed)` — the acting model runs the role only when it judges the role adds value for the task; otherwise it skips to the next.
- `(#group, if asked)` — the role runs only when the user explicitly requests it (e.g., "…and validate it"); skipped by default.

Conditions combine with loops: a conditional looping role loops only on runs where it actually executes.

The `full-team` Log-reader is an example: `(#lowcost, if needed)` — skipped for tasks that need no runtime evidence.

### 7.5 SAILL — Standardized AI Loop Language

The conditional and loop flags above are part of **SAILL** (Standardized AI Loop Language) — a small, vendor-neutral vocabulary for expressing *how* a team runs, not just who is in it. A SAILL-annotated team definition is portable: the same notation is readable by a human, the acting model, and the `resolve_agent_teams.py` tooling.

**The full flag vocabulary** is cataloged in `$HORIZON_ETC/agent_team_flags.md`, loaded every session. Current flags:

| Flag | Form | Meaning |
|---|---|---|
| `if needed` | inline | Run only if it adds value; else skip |
| `if asked` | inline | Run only when the user explicitly requests it; else skip |
| `ask user` | inline | Pause and wait for the user's input, decision, or approval before continuing |
| `parallel` | inline | Run concurrently with adjacent `parallel` roles |
| `wait` | inline | Wait for the preceding `parallel` group to finish (sync point) |
| `Loop` | annotation | Re-run an earlier role with feedback until pass/cap (see §7.3) |

**Extending the flag vocabulary:** add your own flags in `local.agent_team_flags.md` (gitignored, any scope) or via `/agent-teams`. The resolver parses flags generically — a new term works as soon as it appears in the file. List the current vocabulary at any time:

```bash
resolve_agent_teams.py --flags
```

Do not add new flags to `$HORIZON_ETC/agent_team_flags.md` directly; that file is synced from upstream. Use `local.agent_team_flags.md` for machine- or project-local extensions and propose community-useful terms upstream.

### 7.6 Agent Team Skills

Three owner skills support the agent-team and SAILL workflow end-to-end:

| Skill | What it does |
|---|---|
| `/agent-teams` | Lists teams in effect for the current path; creates or edits team definitions at any scope (OS, project, brain, subfolder); adds custom SAILL flags |
| `/test-agent-teams` | End-to-end self-test: spawns each role of every defined team, each echoes a nonce + role name + charter + actual model; reports per-team PASS/FAIL for resolution and model routing |
| `/convert-prompt-to-saill` | Converts a natural-language prompt into a SAILL agent-team flow (roles, model groups, flags, sub-team boxes, loops, `-context-` values); outputs the SAILL block with a gloss, then offers to save or run it |

Use `/test-agent-teams` after defining or modifying a team to confirm that roles resolve to the expected models before you invoke the team on real work. Use `/convert-prompt-to-saill` ad hoc to turn any workflow you can describe in plain language into SAILL, then feed that output into `/agent-teams` to populate a custom agent team — the on-ramp from "a workflow in my head" to standardized SAILL to a reusable named team (verify it with `/test-agent-teams`).

See `$HORIZON_DOCS/system/agent_teams.md` for the full SAILL spec, scope cascade, and team-definition grammar.

---

## 8. Understanding and Managing Context

### 8.1 What Context Is and Why It Costs

Every Claude Code session pays a fixed token cost before you type anything. The harness assembles a system prompt from files on disk. Every byte in those files is billed on every session — whether Claude uses it or not.

The practical implication: the larger your auto-loaded context, the more every session costs. The AIOS baseline (excluding user-global `~/.claude/CLAUDE.md`) is approximately 3,660 tokens at the AIOS root. This is the fixed cost of running the OS layer. Everything you add on top of this is your cost to manage. Run `python $HORIZON_BIN/context_cost.py $HORIZON_ROOT` for the current number — it drifts as files are edited.

### 8.2 What Gets Loaded in Any Given Directory

Claude Code loads `CLAUDE.md` files from `~/.claude/` down to the current working directory — all of them, stacked. Then it resolves all `@`-imports recursively.

The files loaded in a standard AIOS session starting at `$HORIZON_ROOT`:

| File | Purpose | ~Tokens |
|---|---|---|
| `~/.claude/CLAUDE.md` | User-global; points at the OS repo | varies |
| `$HORIZON_ROOT/.claude/CLAUDE.md` | Thin entry; imports root CLAUDE.md | 7 |
| `$HORIZON_ROOT/CLAUDE.md` | AIOS-wide rules; imports agents.md | ~7 |
| `$HORIZON_ROOT/agents.md` | Cross-harness instructions | ~291 |
| `horizon_aios_agents.md` | OS-layer agent config | ~777 |
| `horizon_aios_model_prefs.md` | Model preference spec | ~1367 |
| `agent_teams.md` | Agent team definitions | ~1012 |
| `agent_team_flags.md` | Role-flag vocabulary | ~198 |
| `local.agents.md` | Machine-local overrides | varies |

Run `/context-cost` or `python $HORIZON_BIN/context_cost.py $HORIZON_ROOT` for current numbers — counts drift as files are edited. The AIOS baseline (excluding user-global) is approximately 3,660 tokens.

If you start a session inside `$HORIZON_ROOT/my-project/`, any `CLAUDE.md` in `my-project/` or `my-project/.claude/` is added on top. If you are running as a brain, the brain's `CLAUDE.md` is the innermost layer.

### 8.3 Measuring Context Overhead

To see exactly what is loaded in any directory and how much it costs:

```bash
python "$HORIZON_SYSTEM/bin/context_cost.py" [path]
```

Or run `/context-cost` inside a Claude Code session (available to brains and owner alike).

Output: per-file KB, word count, and estimated token count, plus a total. Thresholds:
- ≥ 1,000 tokens: note (moderate — review before adding more)
- ≥ 2,000 tokens: warning (high — trim before adding more)

Run `context_cost.py` after adding or modifying any `CLAUDE.md` or `@`-import. Confirm the overhead stayed in budget before committing.

### 8.4 The @-Import Rule — Unconditional Loading

A critical misconception: `@file` in `CLAUDE.md` does not lazy-load. The harness inlines the file's full content into the system prompt before the session starts, unconditionally. Writing "only load if needed" on the same line as an `@`-import does not help — those words become part of the already-loaded content.

For content you want available only when needed: **do not `@`-import it**. Instead, tell Claude in prose where to find it:

```markdown
If you need the API design principles, read `$BRAIN_HOME/conventions/api_design_principles.md`.
```

That costs a few tokens in the always-loaded context. The file itself costs nothing until Claude reads it mid-conversation.

Only `CLAUDE.md` and `CLAUDE.local.md` trigger `@`-import resolution. `agents.md` `@`-references are passed to Claude as plain text — the harness does not inline them.

See `$HORIZON_DOCS/authoring/claude_md_authoring.md` for the full authoring reference and `$HORIZON_DOCS/context_loading.md` for the complete loading mechanics.

### 8.5 Per-Layer Configuration Guide

| Layer | Edit when | Keep |
|---|---|---|
| `~/.claude/CLAUDE.md` | User-global preferences that apply across all projects | Minimal — it loads in every session including unrelated projects |
| `$HORIZON_ROOT/.claude/CLAUDE.md` | Never — thin entry point only | One line: `@$HORIZON_ROOT/CLAUDE.md` |
| `$HORIZON_ROOT/agents.md` | AIOS-wide cross-harness instructions | Rules that apply to every session in every project |
| `local.agents.md` | Machine-local overrides | Short — loads every session |
| `brains/<name>/CLAUDE.md` (+ `brain_core.md` / `brain_invariants.md`) | Brain persona, scope, memory pointers | Short — loads every brain session |
| `my-project/.claude/CLAUDE.md` | Project-specific context | Only what Claude cannot derive from the code |

### 8.6 Health Check

To verify the full AIOS installation and configuration is correct:

```bash
# From a Claude Code session
/doctor

# From the command line
python "$HORIZON_SYSTEM/sbin/horizon_aios_doctor.py"
```

This checks env vars, the skills symlink, git hooks, the AIOS registry, and the Deny ACLs on `sbin`, `skills_sbin`, and `logs`.

To verify documentation integrity (canon structure, doc index, cross-references):

```bash
# From a Claude Code session
/doc-check

# From the command line
python "$HORIZON_SYSTEM/sbin/horizon_aios_doc_integrity.py"
```

This checks that required canon files are present, all docs are indexed, and cross-references resolve. Exits 0 if clean (warnings are expected for gitignored local configs).

---

## 9. The Terseness Contract

### 9.1 What It Is

The **Terseness Contract** is a set of authoring rules that governs every file loaded unconditionally into every AIOS session — the always-loaded chain. Because each byte in those files is billed on every session for every user and every brain, verbosity in them is a cost imposed on all interactions the AIOS will ever have.

The always-loaded files subject to strict terseness enforcement are `agents.md` and `horizon_aios_agents.md`. Files such as `agent_teams.md`, `agent_team_flags.md`, and `horizon_aios_model_prefs.md` are in the always-loaded chain but are explicitly excluded from terseness enforcement — their content scope is the operator's prerogative. The authoritative index of which files are tracked, excluded, or advisory is `$HORIZON_DOCS/terseness_contract_index.md`.

### 9.2 The Seven Criteria

A file in the always-loaded chain passes the Terseness Contract if, and only if:

1. **Every line earns its keep.** Removing it would break the file's function or leave a required instruction unspecified.
2. **Instructions are imperative, not discursive.** Tell the model what to do. Rationale belongs in `dev_values.md` or `philosophy.md`.
3. **No rationale that belongs elsewhere.** If the "why" is in a higher-authority doc, cut the prose and use a pointer.
4. **No inline examples when a pointer suffices.** "See `$HORIZON_DOCS/X.md`" is cheaper than an inline example.
5. **No redundancy with sibling always-loaded files.** If another indexed file already says it, one copy is the defect.
6. **No commented-out content.** Dead lines and `# TODO` prose still cost tokens.
7. **@-imports only for always-needed files.** @-importing a large reference doc "for convenience" is a fail. Use a prose pointer instead.

### 9.3 Checking Compliance

Run the terseness check from any owner session:

```
/terseness-check
```

The skill evaluates each tracked file in the index against the seven criteria and reports `PASS` or `FAIL` per criterion per file. Files in the Excluded section of the index are skipped entirely — no `FAIL`, `ADVISORY`, or `NOTED` findings are generated for them. Files in the gitignored / user-controlled section are checked and reported as `ADVISORY` — the user bears the cost of their own verbosity, so fixes are not applied without prompting.

Run `/terseness-check` after adding or modifying any always-loaded file or @-import. Confirm all tracked files pass before committing.

### 9.4 The Terseness Contract Index

The authoritative file list with loading paths and per-file constraints is:

```
$HORIZON_DOCS/terseness_contract_index.md
```

Update it whenever a file is added to or removed from the always-loaded chain (a new @-import in any indexed file, or a new CLAUDE.md layer inserted into the harness loading path). The index is the contract's scope boundary — if a file is not listed, it is not subject to the strict contract (though always-loaded files added without updating the index will be caught on the next `/terseness-check` pass as a gap finding).

---

## 10. Gitignore, Local Config, and What Not to Commit

### 10.1 The Two-Gitignore Model

AIOS uses two gitignore mechanisms that serve different purposes:

**`.gitignore`** — tracked, committed, ships with every clone. Contains patterns for OS-layer artifacts that should never be tracked on any machine (build outputs, temp files, the generated `active_env` files, `memory/`, `handoffs/`).

**`.gitignore.user`** — machine-local, gitignored itself, never committed. Contains patterns specific to this machine and this user's personal exclusions. Only `.gitignore.user.template` (the empty starting template) is tracked.

The pre-commit hook syncs `.gitignore.user` to `.git/info/exclude` on every commit. To add a personal exclusion pattern:

```
# Edit $HORIZON_ROOT/.gitignore.user
MyPersonalNotes/
scratch/
RedTeam/
```

The pattern takes effect on the next commit — no manual sync step. The file is machine-local and does not travel with a clone.

### 10.2 What Is Never Committed

These files are gitignored and must stay that way:

| File / Directory | What it holds |
|---|---|
| `local.agents.md` (all instances) | Machine-local agent instructions; overrides shipped content |
| `settings.local.json` | Machine-specific permission overrides |
| `horizon_aios_model_prefs.local.md` | Your private model groups and routing rules |
| `memory/` | Harness transcripts and agent memory (never publish) |
| `handoffs/` | Session handoff documents |
| `objectives/` | Durable objectives |
| `usrbin/usr_skills/` | Machine-local personal skills |
| `brains/<name>/` | Brain workspaces (sensitive — personal credentials, memory) |
| `$HORIZON_SYSTEM/logs/` | Audit and event logs |
| `aios_local.conf` | Local sync and log configuration |
| `~/.claude/settings.json` | Global settings (points at machine-specific wrapper paths) |
| `ai_os_etc/git_identity.local.gitconfig` | Machine-local git identity |

### 10.3 Protecting Configuration Points — The Clobber Hazard

An upstream sync (`git pull` / `aios sync`) will update the OS layer. The files it can overwrite are tracked files: `agents.md`, `horizon_system/`, the shipped templates.

What it **cannot** overwrite: anything gitignored. This is why your customizations belong in the gitignored seam files:

- Override `agents.md` behavior → use `local.agents.md`
- Override model preferences → use the gitignored `extend.md`
- Override permissions → use `settings.local.json`
- Override session behavior per-machine → use `local.agents.md`

Never put machine-specific or personal configuration into the tracked files. A sync will clobber it, and other users' clones will break.

If you want to ship a configuration change to all users (or to your own other machines), it belongs in the tracked files. If you want it only on this machine, it belongs in the gitignored files.

### 10.4 Checking What a Sync Would Overwrite

Before pulling:

```bash
git fetch origin
git diff HEAD..origin/master -- agents.md .claude/CLAUDE.md horizon_system/
```

Review the diff. If the upstream changed a file you have also customized, the update applies cleanly because your customizations are in the gitignored seam files — not in the tracked files. This is the purpose of the `local.agents.md` / `extend.md` pattern.

See `$HORIZON_DOCS/system/distribution_and_updates.md` for the full framework vs. user-space model and `$HORIZON_DOCS/getting_started/updating.md` for the step-by-step update procedure.

---

---

## 11. Enterprise Deployment

### 11.1 The Model: Organization Fork, Employee Clone

The Horizon AIOS distribution model is designed for downstream customization without merge conflicts. An enterprise maps directly onto this model:

```
Official upstream (HorizonBrute/Horizon_AI_OS)
  ↓ fork
Organization repo (your-org/Horizon_AI_OS)    ← org-controlled; org policy lives here
  ↓ clone
Employee machine                               ← employee customizations in gitignored seam files
```

The organization forks the official upstream repo into their own Git infrastructure (GitHub Enterprise, GitLab, Bitbucket, Azure DevOps). That fork becomes the authoritative source of truth for the organization. Employees clone from the org fork, not from the official upstream. The org controls what ships to every employee; the official upstream controls what the org chooses to pull in.

### 11.2 Where Organization Policy Lives

The framework/user-space split that protects individual user customizations from being clobbered by syncs works identically at the org level:

| File / Layer | Who owns it | How the org enforces it |
|---|---|---|
| `agents.md` | Org (in the fork) | Org policy committed here ships to every clone |
| `horizon_system/` | Org (in the fork) | Security templates, hook scripts, ACL defaults — all controlled |
| `horizon_system/ai_os_etc/security_invariants.md` | Org (in the fork) | The org's authoritative security posture |
| `horizon_system/templates/` | Org (in the fork) | The brain template, settings.json template, profile templates |
| `local.agents.md` | Employee (gitignored) | Machine-local only; org cannot ship this |
| `settings.local.json` | Employee (gitignored) | Machine-local only; org cannot ship this |
| `brains/`, `memory/` | Employee (gitignored) | Never reaches the org repo |

The org commits policy directly into the tracked framework files in their fork. Employees who sync get the updated policy automatically. Employees' gitignored customizations are never touched.

**What belongs in the org's fork:**
- Organization-wide agent instructions in `agents.md` (approved tools, prohibited actions, required session behaviors)
- Standardized brain templates in `horizon_system/templates/` that reflect the org's compliance requirements
- Security invariant documents that encode the org's control posture
- Approved skill sets in `skills_bin/` and `skills_sbin/`
- Model-preference routing that reflects the org's approved models and cost policy
- Hook scripts that write to the org's SIEM or compliance logging infrastructure

### 11.3 Pulling Upstream Updates into the Org Fork

The org maintains the fork like any upstream-tracking fork:

```bash
# In the org fork repo (run by whoever manages the AIOS distribution)
git remote add upstream git@github.com:HorizonBrute/Horizon_AI_OS.git
git fetch upstream
git merge upstream/master   # or rebase; review before merging

# After review and any org-specific adjustments:
git push origin master      # employees sync from here
```

The org can choose how aggressively to track upstream — immediate, quarterly, or only for specific security patches. The org's changes to tracked files (org policy additions to `agents.md`, etc.) merge with upstream changes normally. As long as the org has not duplicated content that lives in the user-space seam files, merges are clean by construction.

### 11.4 Centralized Deployment and Force Install

For managed machines, the org can distribute and install the AIOS through standard enterprise software deployment mechanisms:

**Windows (Intune / SCCM / Group Policy):**
1.1 Package the clone + bootstrap as a deployment script. Intune Win32 app wraps `git clone <org-fork-url> C:\devroot && powershell -File C:\devroot\horizon_system\sbin\bootstrap.ps1`.
1.2 The bootstrap runs as the logged-in user for the Claude Code wiring steps, and as SYSTEM for the ACL hardening steps (the bootstrap detects this and handles the split automatically).
1.3 Use a managed GPO to set `HORIZON_ROOT` as a machine-level environment variable, removing the need for users to configure it.
1.4 Deploy the org's approved `settings.json` template through the bootstrap — it is already templated for this.

**Linux (Ansible / Chef / Puppet / Salt):**

```yaml
# Ansible playbook excerpt
- name: Clone AIOS from org fork
  git:
    repo: "git@git.your-org.com:aios/Horizon_AI_OS.git"
    dest: /opt/aios
    version: main

- name: Run AIOS bootstrap
  command: bash /opt/aios/horizon_system/sbin/bootstrap.sh --yes
  become: true
```

After the play runs, the system has a fully configured AIOS installation with org-approved configuration. User-specific customization happens afterward through the gitignored seam files.

### 11.5 Multi-Operator and Team Environments

On a shared server or in a team environment where multiple humans operate the same AIOS installation:

1.1 **Each human operator gets their own OS user account.** Do not share owner accounts. The global `~/.claude/settings.json` (hooks, statusLine) is per OS home directory — it must stay per-operator.
1.2 **Each operator runs bootstrap under their own account.** Bootstrap installs each operator's personal `~/.claude/` from the org's template. The devroot `.claude/settings.json` (permissions only) is shared across all operators — that is intentional.
1.3 **Brains are AI agent accounts, not human accounts.** A team member who needs to interact with a brain does so by running the harness as that brain user, not by sharing the brain's OS account.
1.4 **The `$HORIZON_ROOT` repo can be shared storage or separate clones.** Shared storage keeps all operators on the same AIOS version automatically; separate clones give each operator independent upgrade control. Both models work.

See `$HORIZON_DOCS/deployment/server.md` → "Multi-Operator Server Pattern" for the full treatment.

### 11.6 Sync Schedule and Drift Prevention

To keep employee machines current with the org fork without requiring manual pulls:

```bash
# Employees add the org fork as their origin (done at clone time):
git clone git@git.your-org.com:aios/Horizon_AI_OS.git C:\devroot

# horizon_aios_sync.py (fast-forward-only) can be scheduled:
python "$HORIZON_SYSTEM/sbin/horizon_aios_sync.py"
```

The sync script is fast-forward-only by design. If an employee has edited a tracked framework file (violating the user-space principle), the sync refuses rather than silently overwriting. That refusal is the signal to move the change into the correct gitignored seam file. The org can schedule this via Windows Task Scheduler or Linux cron as a background maintenance task.

See `$HORIZON_DOCS/system/distribution_and_updates.md` for the complete framework vs. user-space model.

---

## 12. Containerization, Cloud, and Infrastructure as Code

### 12.1 Why AIOS Is IaC-Friendly

Horizon AIOS is, at its core, a set of files and filesystem ACL rules. There are no daemons that must be running, no databases to migrate, no external state to synchronize. The entire system state is:

1.1 The repository contents (cloned from git — reproducible)
1.2 The bootstrap outputs (symlinks, wrappers, `active_env.*` — generated by `bootstrap.{ps1,sh}`)
1.3 The ACL assignments on the filesystem (applied by `horizon_aios_harden.py` and `horizon_aios_create_brain.py`)
1.4 The OS user accounts for brains (provisioned by `horizon_aios_create_brain.py`)
1.5 The credentials in the OS keystore (managed by `horizon_aios_brain_credential.py`)

This maps directly to standard IaC patterns: declare the desired state, apply it, verify it.

### 12.2 Docker

The AIOS ships Docker templates in `$HORIZON_SYSTEM/templates/docker/`:
- `Dockerfile` — Ubuntu-based image; runs bootstrap as root before switching to the `aios` user; brains are OS users within the container
- `docker-compose.yml` — single AIOS service with named volumes for `logs`, `handoffs`, `objectives`, and an optional host-path bind for `brains/`
- `.dockerignore` — excludes `memory/`, `handoffs/`, `brains/`, and `logs/` from the build context

```bash
# Build and run
docker build -f horizon_system/templates/docker/Dockerfile -t horizon-aios .
docker compose -f horizon_system/templates/docker/docker-compose.yml up -d

# Open a Claude Code session inside the container
docker exec -it horizon-aios claude
```

**Mutable state** (logs, handoffs, objectives, brain workspaces) is volume-mounted. The AIOS layer itself is baked into the image. After an AIOS update, rebuild the image; volumes persist unchanged.

**Brain isolation in Docker:** The default model runs all brains as OS users inside a single AIOS container — the same isolation model as a native OS deployment. For environments that require container-level isolation per brain, mount each brain's directory as a writable volume in a separate container definition. The AIOS audit log volume must not be mounted into any brain container.

See `$HORIZON_DOCS/deployment/docker.md` for the full reference.

### 12.3 Cloud VM Provisioning (Terraform / Pulumi / cloud-init)

Because AIOS setup is a clone + bootstrap, it maps to any cloud provisioning tool that can run a shell script on a new VM:

**Terraform + cloud-init (AWS EC2 example):**

```hcl
resource "aws_instance" "aios_server" {
  ami           = "ami-ubuntu-22-04"
  instance_type = "t3.medium"

  user_data = <<-EOF
    #!/bin/bash
    apt-get update && apt-get install -y git python3 python3-pip
    pip3 install watchdog
    git clone git@git.your-org.com:aios/Horizon_AI_OS.git /opt/aios
    bash /opt/aios/horizon_system/sbin/bootstrap.sh --yes
    # Provision brains
    python3 /opt/aios/horizon_system/sbin/horizon_aios_create_brain.py inbox_triage \
      --automation scheduled
  EOF

  tags = { Name = "aios-server" }
}
```

**Terraform + Pulumi on Azure / GCP:** The same pattern — a VM resource with a `custom_data` / `metadata startup-script` block that runs the bootstrap. The AIOS has no cloud-provider dependencies; it runs on any Linux or Windows VM.

**Ansible for configuration management:**

```yaml
- hosts: aios_servers
  become: true
  tasks:
    - name: Clone org AIOS fork
      git:
        repo: "git@git.your-org.com:aios/Horizon_AI_OS.git"
        dest: /opt/aios
        version: main
        key_file: /root/.ssh/deploy_key

    - name: Bootstrap AIOS
      command: bash /opt/aios/horizon_system/sbin/bootstrap.sh --yes

    - name: Provision brain accounts
      command: >
        python3 /opt/aios/horizon_system/sbin/horizon_aios_create_brain.py
        {{ item }} --automation scheduled
      loop: "{{ brain_names }}"
      vars:
        brain_names:
          - inbox_triage
          - code_review
          - data_pipeline
```

### 12.4 Kubernetes

Kubernetes is the right orchestration layer when you need multiple AIOS instances at scale, per-brain pod isolation, or cloud-native autoscaling of brain workloads.

**Pattern 1 — AIOS-in-a-pod, brains as OS users (matches Docker model):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aios-server
spec:
  template:
    spec:
      containers:
      - name: aios
        image: your-org/horizon-aios:latest
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000           # the 'aios' OS user baked into the image
        volumeMounts:
        - name: aios-logs
          mountPath: /opt/aios/horizon_system/logs
        - name: brain-workspaces
          mountPath: /opt/aios/brains
      volumes:
      - name: aios-logs
        persistentVolumeClaim:
          claimName: aios-logs-pvc
      - name: brain-workspaces
        persistentVolumeClaim:
          claimName: aios-brains-pvc
```

**Pattern 2 — One pod per brain (stronger isolation boundary):**

Each brain runs in its own pod with a `securityContext.runAsUser` matching the brain's UID (provisioned at image build time). The AIOS system directory is mounted read-only from a shared volume; the brain's workspace is a dedicated writable volume. The audit log volume is mounted only into the administrative pod, never into brain pods.

```yaml
# Brain pod template
containers:
- name: brain-inbox-triage
  image: your-org/horizon-aios:latest
  securityContext:
    runAsUser: 1001               # inbox_triage UID
  volumeMounts:
  - name: aios-system
    mountPath: /opt/aios/horizon_system
    readOnly: true                # brain cannot modify the AIOS layer
  - name: inbox-triage-workspace
    mountPath: /opt/aios/brains/inbox_triage
                                  # writable; brain-scoped only
```

This mirrors the OS-level isolation model at the container boundary.

### 12.5 Container Registry and Image Management

The standard image management workflow for an org:

1.1 The org's CI pipeline builds `horizon-aios:latest` from the org fork on every merge to `main`.
1.2 The image bakes in the AIOS layer (cloned repo + bootstrap). Brains are provisioned at container start time via an entrypoint script, or pre-provisioned in the image if the brain roster is stable.
1.3 Mutable state (logs, handoffs, brain workspaces, credentials) lives in volumes — never in the image.
1.4 An AIOS update = a new image build. Volumes are unaffected. Rollback = pin to the previous image tag.

### 12.6 Secrets Management in Cloud Environments

The AIOS brain credential system uses OS-native keystores (`horizon_aios_brain_credential.py`). In containerized or cloud environments, the OS keystore is often not available. The operator-owned integration pattern:

- **Kubernetes Secrets** — inject the brain's API key as an environment variable via a `secretKeyRef`. The brain's entrypoint script exports it.
- **HashiCorp Vault** — use the Vault agent sidecar to write secrets to an in-memory tmpfs volume that the brain reads at startup.
- **AWS Secrets Manager / Azure Key Vault / GCP Secret Manager** — use the cloud provider's secret store SDK or a secrets CSI driver to mount secrets into the brain pod.

The AIOS does not prescribe a cloud secrets solution. `horizon_aios_brain_credential.py` is the local-machine path; cloud environments use whatever secret management the organization already operates.

---

## 13. Bring Your Own Infrastructure — Integrated Identity and Existing Security

### 13.1 The Core Principle

Horizon AIOS is not a security framework. It does not implement its own identity model, its own access control engine, or its own audit pipeline. It is an AI-focused application layer that runs inside existing OS infrastructure using the same mechanisms IT has always used.

This means everything your organization already operates for security and identity management applies to AIOS out of the box:

- **File system ACLs** — NTFS (Windows) / POSIX permissions (Linux/macOS). Same `icacls`, same `chmod`. AIOS sets them; your IT team can audit and verify them with the same tools they use for everything else.
- **OS user accounts** — same local accounts (or domain accounts — see §11.2). Same user management tooling, same password policy, same account lifecycle.
- **Audit logging** — same OS audit infrastructure (`auditd`, Windows Security Event Log). AIOS writes to it; your SIEM ingests it.
- **Network controls** — same firewall rules, same network segmentation. Brain OS accounts are subject to the same network policy as any service account.

The security team's question "how does this work?" has a simple answer: **the same way everything else works**.

### 13.2 Active Directory and Integrated Identity Providers

The AIOS security model is built on OS user accounts and filesystem group memberships. If those accounts and groups are managed by an identity provider — Active Directory, Azure AD/Entra ID, LDAP, FreeIPA — the model works identically. The ACLs reference group names; where those groups come from is the OS's concern, not AIOS's.

**Windows domain-joined machines with Active Directory:**

The two AIOS group primitives are:
- `brains` — shared group; all brain accounts are members; grants `RX` on `$HORIZON_BIN` and `skills_bin`
- `<brain-name>_group` — per-brain group; the brain account and the owner are members; grants full control on the brain's workspace

These can be AD security groups rather than local groups. The brain OS account can be a domain account rather than a local account:

```powershell
# Create the brain as a domain account (domain admin required)
New-ADUser -Name "brain_inbox_triage" -AccountPassword (Read-Host -AsSecureString) `
  -Enabled $true -Path "OU=AIBrains,DC=your-org,DC=com"

# Add to the brains AD group
Add-ADGroupMember -Identity "aios-brains" -Members "brain_inbox_triage"

# The icacls grants in horizon_aios_create_brain.py reference group names —
# pass the domain-qualified group name to match your AD group:
#   icacls $HORIZON_BIN /grant "YOUR-ORG\aios-brains:(OI)(CI)RX"
```

Group Policy applies to brain accounts the same way it applies to any domain account. Password policies, logon hour restrictions, audit policies — all enforced by the domain controller without any AIOS involvement.

**Linux with SSSD / PAM (AD or LDAP):**

When a Linux machine is joined to Active Directory via SSSD, domain users and groups are available to `chmod` and `chown` by their domain names. The AIOS bootstrap and `horizon_aios_create_brain.py` use standard POSIX group membership and permission commands — they work with SSSD-resolved groups without modification.

**Azure AD / Entra ID managed devices:**

On Intune-managed Windows machines with Azure AD join, local group membership and NTFS ACLs function normally. The `brains` local group and per-brain groups are machine-local (not synced to Azure AD), which is appropriate — they are machine-local security boundaries. Azure AD conditional access policies apply to interactive logons; the brain's non-interactive scheduled-task logon (`SeBatchLogonRight`) is governed by local security policy, not Azure AD, which is the correct separation.

### 13.3 SIEM and Security Monitoring Integration

AIOS produces two audit streams:

**Stream 1 — AIOS filesystem monitor** (`horizon_aios_monitor.py`): JSON-lines written to `$HORIZON_SYSTEM/logs/horizon_aios_monitor/monitor_YYYYMMDD.log`. Events: file created, modified, deleted, moved in the AIOS system directories. One record per event, self-describing with `source: "Horizon.AIOS"` and `horizon_root` for multi-install attribution.

Any standard log shipper can tail this directory and forward to your SIEM without transformation:

| Tool | Configuration |
|---|---|
| Elastic Filebeat | `type: filestream`, `paths: [".../monitor_*.log"]`, `parsers: [{ndjson: {}}]` |
| Fluent Bit | `[INPUT] tail` on `monitor_*.log`, `[FILTER] parser = json` |
| Splunk UF | Monitor stanza on the directory, `sourcetype=_json` |
| Vector | `sources.aios.type = "file"`, decode as JSON |
| NXLog | `im_file` on the directory, `xm_json` to parse |

Filter on `source="Horizon.AIOS"` to isolate AIOS integrity events.

**Stream 2 — OS-level audit (write-access detection)**: The AIOS monitor detects file writes. For unauthorized read detection, use your OS's existing audit infrastructure — it does not require AIOS involvement:

- **Windows**: Security Audit → Object Access Auditing via Group Policy. Set audit ACEs on brain folders. Events land in the Security Event Log, forwarded to your SIEM via Windows Event Forwarding.
- **Linux**: `auditd` with `IN_ACCESS` rules: `auditctl -w /opt/aios/brains/brain_name -p rwxa -k brain_activity`. Forward via `auditd → rsyslog → your log aggregator`.
- **macOS**: BSM / OpenBSM via `audit(8)`, configured in `/etc/security/audit_control`.

AIOS gives you the structure and the log location. The integration with your SIEM is yours — it plugs directly into whatever audit infrastructure you already operate, using the same configuration you use for every other application.

### 13.4 Group Policy and System-Level Controls

Because brain accounts are real OS accounts, every system-level control that applies to service accounts applies to brains:

**Windows Group Policy:**
- Password complexity and rotation policies apply automatically to brain accounts
- Account lockout thresholds apply (relevant for the scheduled-task credential)
- Software restriction policies and AppLocker rules apply — you can limit which executables the brain account can run to just the harness binary and its dependencies
- Windows Defender Application Control (WDAC) policies apply per-user

**Linux PAM and login restrictions:**
- `/etc/security/access.conf` — restrict which terminals or SSH hosts a brain account can log in from
- PAM modules for two-factor authentication can be applied selectively to brain accounts
- `pam_limits.conf` — CPU, memory, and file descriptor limits per brain account

**Network segmentation:**
- Brain accounts can be assigned to specific network zones. If the brain only needs to reach the AI API endpoint and a specific internal data source, firewall rules can enforce that precisely — same as any service account.
- On Windows domain environments, Windows Firewall rules can be scoped per-user via Group Policy.

### 13.5 What AIOS Adds — and What It Doesn't

| Concern | Who handles it | AIOS's role |
|---|---|---|
| OS user account lifecycle | IT / IDP / HR workflow | None — brain accounts are OS accounts like any other |
| Password policy | Group Policy / PAM / IDP | None — brain passwords follow the same policy |
| Network access control | Firewall / network team | None — brain accounts are standard service accounts |
| SIEM and log aggregation | Security team / existing SIEM | Provides the log location and format; integration is the operator's |
| Filesystem ACL model | OS (NTFS / POSIX) | Sets and enforces the specific ACEs for brain isolation |
| Brain workspace isolation | OS (ACL model above) | Provisions the structure; verifiable with standard OS tools |
| Credential storage | OS keystore | Stores brain passwords in the native credential store |
| Audit of AI-layer file changes | AIOS filesystem monitor | Writes JSON-line events to `logs/`; SIEM integration is operator-owned |
| Session-level AI audit (reads) | OS audit infrastructure | Provides the boundary; audit integration is operator-owned |

AIOS is the AI-focused application. Everything else — identity, access governance, network controls, security monitoring, compliance reporting — stays in the infrastructure your organization already runs and already trusts. The AIOS does not require you to trust a new security model. It requires you to apply the one you already have to a new class of workload.

---

## Reference Pointers

| Topic | Document |
|---|---|
| Full setup guide | `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md` |
| Philosophy and conceptual vocabulary | `$HORIZON_DOCS/philosophy.md` |
| Security invariants (authoritative) | `$HORIZON_ETC/security_invariants.md` |
| Brain isolation test | `$HORIZON_DOCS/security/brain_isolation_test.md` |
| Audit logging and SIEM integration | `$HORIZON_DOCS/security/audit_logging.md` |
| Brain automation (scheduled / daemon) | `$HORIZON_DOCS/deployment/brain_automation.md` |
| Desktop deployment | `$HORIZON_DOCS/deployment/desktop.md` |
| Server / headless deployment | `$HORIZON_DOCS/deployment/server.md` |
| Docker deployment | `$HORIZON_DOCS/deployment/docker.md` |
| Distribution, updates, and backups | `$HORIZON_DOCS/system/distribution_and_updates.md` |
| Context loading mechanics | `$HORIZON_DOCS/context_loading.md` |
| CLAUDE.md authoring rules | `$HORIZON_DOCS/authoring/claude_md_authoring.md` |
| Model preferences | `$HORIZON_DOCS/system/model_preferences.md` |
| Agent teams and SAILL (full spec) | `$HORIZON_DOCS/system/agent_teams.md` |
| Memory and transcript redirect | `$HORIZON_DOCS/system/memory.md` |
| Skills reference | `$HORIZON_DOCS/skills.md` |
| System configuration reference | `$HORIZON_DOCS/system/system_configuration_reference.md` |
| File structure invariants (authoritative) | `$HORIZON_ETC/file_structure_invariants.md` |
| Updating AIOS | `$HORIZON_DOCS/getting_started/updating.md` |
| Cloud sync exclusions | `$HORIZON_DOCS/cloud_sync_exclusions.md` |
| Terseness Contract (authoritative index) | `$HORIZON_DOCS/terseness_contract_index.md` |
| Agent team flags / SAILL vocabulary | `$HORIZON_ETC/agent_team_flags.md` |
