# Horizon AIOS — Philosophy and Conceptual Framework

This document captures the design philosophy and conceptual vocabulary behind Horizon AIOS. It is the "why" behind the architecture — readable by humans and AI alike, but not loaded into session context.

---

## 1. The Core Distinction: Brain vs. AI Operating System

The term "AI Operating System" is used inconsistently in the industry. Most products marketed as an "AI OS" are actually what Horizon calls a **Brain** — an expert system finely tuned and calibrated to do one class of things well: write media, manage a business workflow, produce code, perform a specific business function.

That framing maps more cleanly to "App" than "OS."

**Horizon's vocabulary:**

| Term | Definition |
|---|---|
| **Brain** | One atomic unit of an expert system. An agentic workflow given precise training and calibration to be an expert at one specific thing. A brain is an App — it runs inside the AIOS. Every brain includes a memory system; that is what makes it an expert rather than a stateless query processor. |
| **Memory System** | The memory subsystem owned and contained within a brain — entirely the brain author's choice. The AIOS does not implement or prescribe a memory technology; it provides only the secure, isolated directory where the brain's memory lives. A brain's self-contained memory is what makes it portable: when the directory moves, the expertise moves with it, regardless of harness or model. |
| **AI Operating System (AIOS)** | The collection of configuration, harnesses, security boundaries, logging, and coordination scaffolding that brains run on top of. The OS layer is not itself an expert system. It is the infrastructure that makes expert systems safe, auditable, and controllable. |
| **Second Brain** | The goal-state user experience: an ecosystem of brains that collectively runs life and business tasks — things that require some level of cognition but not the user's full attention. Tedious, repetitive, or high-volume cognitive work delegated to purpose-built expert systems. |

**Why this matters:** If you conflate Brain with AIOS, you build a single large system that is opaque, hard to audit, and difficult to contain. The separation enables: independent deployment of brains, per-brain access control, per-brain audit trails, and a stable shared OS layer that can be updated without disrupting individual brains.

**The harness is bound by the OS, not by itself.** Because the harness runs as the brain OS user, it cannot modify the AIOS-layer protections that govern it. This is an OS-enforced property: even a fully compromised harness cannot write to `$HORIZON_SYSTEM`, access `sbin/`, or escalate to the administrative context. The security boundary is maintained by the operating system independently of anything the harness does or is instructed to do. See `$HORIZON_ETC/security_invariants.md §5` for the full invariant.

---

## 2. The Second Brain: Goal State

The common implementation of "second brain" as knowledge management (notes, links, documents) is a narrow reading. In Horizon's framing, a second brain is the **ecosystem and operating system of the harness** — the infrastructure underneath a collection of apps (Brains) that collectively run life and business on the user's behalf.

The second brain goal state: multiple expert brains running in their own isolated contexts, each with precisely scoped tools and data access, collectively handling work the user finds flooring or tedious — and doing so in a way the user, and a security team, can inspect, audit, and trust.

---

## 3. The Security Team's Questions (Blue Team Answerability)

Every architectural decision in Horizon AIOS should be evaluable against the questions a security team would ask when approving any new application or infrastructure change:

1. **What is the agent doing?** — Audit trail; logged tool invocations and file access.
2. **How is it doing it?** — Defined, provisioned toolset; no capability beyond what was explicitly granted.
3. **How do we enforce it?** — OS-level filesystem permissions (not just app-layer promises). Explicit Deny ACLs, not just absence of grants.
4. **How do we prevent insider threat or unintended AI risk?** — Git commit enforcement, audit log immutability (brain cannot write to log directory), brain isolation (blast radius limited to own folder).
5. **What data does the agent have access to?** — Answerable per-brain from the provisioning record. Zero by default; explicit grants documented.
6. **What tooling does the agent have access to?** — Same model: zero by default; every tool provisioned to a brain must be explainable in one sentence tied to that brain's function.

The principle of least privilege is no longer sufficient as a statement of intent. It must be enforced at the OS layer. "The developer is smart enough not to delete the database" is not a security model. "The developer's brain cannot authenticate to the database because it holds no credential for it" is.

**What AIOS provides vs. what you must implement:**

AIOS answers questions 2–6 fully: provisioning records, zero-default access, explicit ACLs, credential containment. Question 1 — *what did the agent actually do during a session* — requires OS-level audit that AIOS cannot provide portably across all platforms and deployments. AIOS provides the log directory, the filesystem change monitor (`horizon_aios_monitor.py`), and the isolation boundary. Full session-level audit requires integration with the infrastructure your organization already runs.

Recommended OS-level audit integrations (implement in your environment):

- **Linux:** `auditd` with `IN_ACCESS` rules on brain home directories and `$HORIZON_SYSTEM`. Rules like `auditctl -w /path/to/brains/brain_name -p rwxa -k brain_activity` capture reads, writes, executes, and attribute changes per brain. Pipe to your SIEM via `auditd` → `rsyslog` → your log aggregator.
- **macOS:** Basic Security Module (BSM) / OpenBSM via `audit(8)`. Configure `/etc/security/audit_control` to capture `fc` (file create), `fd` (file delete), `fw` (file write), `fr` (file read) classes for brain accounts.
- **Windows:** Security Audit → Object Access Auditing. Enable via Group Policy (`Computer Configuration → Windows Settings → Security Settings → Advanced Audit Policy → Object Access → Audit File System`). Set audit ACEs on brain folders using `icacls` or the Security tab. Events land in the Security Event Log and can be forwarded to your SIEM via Windows Event Forwarding.
- **Docker:** Mount the log volume to your host or a log aggregator sidecar. Add your preferred logging driver (`json-file`, `fluentd`, `awslogs`, etc.) in `docker-compose.yml`. OS-level audit inside a container requires `--cap-add AUDIT_READ` and `auditd` in the container, or relies on the host's audit subsystem if using Linux namespaces.

AIOS gives you the structure. The integration is yours to implement — it plugs directly into whatever audit and SIEM infrastructure your organization already operates.

---

## 4. Lean Into Existing IT Infrastructure

Horizon AIOS is not a security framework. It is a configuration layer that redirects existing security frameworks toward AI workloads.

- **User isolation** is done by the OS (NTFS ACLs / POSIX permissions), not by AIOS code.
- **Audit logging** uses the OS filesystem and optionally `auditd` / Windows Security Audit — tools the security team already knows.
- **Credential containment** uses OS-native credential stores accessed via `horizon_aios_brain_credential.py` in sbin, not a custom secrets store.
- **Centralized logging** follows the standard log taxonomy the ops team already has tooling for.
- **Access control** is enforced by `icacls` / `chmod` — not reimplemented.

The goal: when a security team asks "how does this work?", the answer should be "the same way everything else works — OS users, filesystem ACLs, and centralized logs." Not "we built a custom isolation layer."

---

## 5. Infrastructure as Code and Containerization

Horizon AIOS must be deployable as infrastructure, not just installed by hand.

**Deployment models, all first-class:**

1. **Desktop (native OS)** — the primary and most personal deployment. The user installs AIOS on their own machine via bootstrap scripts. Brains run as OS user accounts on the same machine. The AI harness (e.g., Claude Code desktop app) is launched by the user directly. This is the "run my life / run my business" model — always on, always local, tightly integrated with the user's workflow.

2. **Backend / server (native OS)** — same bootstrap as desktop, deployed on a remote or always-on server. Brains run as OS user accounts. Access is via SSH or remote session. Suitable for brains that run unattended (scheduled tasks, cron jobs, daemons) or for separating AI workloads from the user's desktop environment.

3. **Docker container (AIOS as container)** — the entire AIOS layer runs in a container. Brains run as OS users within the container, exactly as in the native OS model. Enables consistent deployment across machines, cloud environments, and CI/CD pipelines. This is the supported Docker deployment mode.

4. **Docker container (per-brain)** — each brain runs in its own container. This is outside AIOS scope and is a user implementation choice. BYOH applies here: if a brain's expert function requires container isolation, the brain author provisions and manages that container. The AIOS OS layer doesn't change; the brain's working directory and Claude configuration still live under `$HORIZON_ROOT/brains/<name>/`. The containerization of the brain itself is the author's engineering decision, not an AIOS feature.

The desktop model is the design reference: if a feature works correctly on a user's desktop machine, it will work in server and container deployments. If a feature only works in server or container mode, it is not a core AIOS feature — it is a deployment-specific extension.

**IaC compatibility requirements:**
- No hardcoded paths in any committed file — all paths are env vars (`$HORIZON_ROOT`, `$HORIZON_SYSTEM`, etc.).
- Bootstrap scripts are the single source of truth for setup — cloning the repo + running bootstrap produces a working AIOS.
- Brain provisioning is a single script invocation (`horizon_aios_create_brain.py`) — not a sequence of manual steps.
- Configuration is file-driven — the entire AIOS state can be recreated from the repo + a local config file.

AIOS Docker images are Linux-container based and run on Windows, macOS, and Linux hosts via the container runtime (Docker Desktop / WSL2 on Windows and macOS, Docker Engine on Linux). Native Windows containers are out of scope.

Docker does not replace OS-level user isolation — it extends it. A Dockerized brain still runs as a non-root user inside the container. The container boundary adds network isolation and process isolation; the OS user boundary limits filesystem access.

---

## 6. Memory Systems Are Part of the Brain — and Entirely the User's Choice

An expert system cannot function without memory. Memory is not an optional add-on — it is what makes a brain an expert rather than a stateless query processor.

**The AIOS does not implement a memory system. That is entirely the brain author's decision.**

The AIOS provides one thing relevant to memory: a secure, isolated directory for each brain where anything the brain author wants to store can live — calibration documents, few-shot examples, vector indices, conversation history, retrieval scripts, domain knowledge files, or any other memory technology the author chooses. The directory has filesystem permissions that enforce isolation. What goes inside it is not the AIOS's concern.

This is a deliberate non-decision:
- Memory implementations vary enormously in kind (file-based, vector DB, graph DB, retrieval pipelines, structured knowledge bases) and the right choice depends entirely on the brain's expert domain.
- Any memory system the AIOS prescribed would either be too constrained for some brains or too complex for simpler ones.
- The "bring your own memory" model is the same as the broader BYOH principle — the AIOS provides the container and the security; the author provides the specialization.

**Memory is what makes BYOH possible at the brain level.**

When a brain's expertise is consolidated in self-contained memory artifacts (files, databases, indices) within its directory — rather than embedded in a specific harness's configuration or tied to a specific model's fine-tuning — the brain becomes portable:

- Swap the harness → the memory stays.
- Swap the frontier model → the memory stays.
- Swap the API provider → the memory stays.
- Move to a different machine or container → the memory moves with the directory.

Without a self-contained memory system, a brain is coupled to its current toolchain. With one, it is a portable expert that can be brought to any harness, any frontier model, any API endpoint, any network topology — independently.

**The AIOS's role is only:**
- Providing the brain's home directory (the container for whatever memory the author implements).
- Enforcing filesystem isolation so memory cannot leak across brain boundaries.
- Nothing else. Memory architecture is entirely outside the AIOS layer.

---

## 7. Bring Your Own Harness, Model, and Tooling (BYOH)

Horizon AIOS is a harness-agnostic configuration layer. It standardizes how AI workloads are structured and controlled — not which AI is doing the work.

A user brings:
- Their harness (Claude Code, Codex, Ollama, or any tool that reads `agents.md`)
- Their model (any model the harness supports)
- Their tooling (MCP servers, scripts, APIs)

The AIOS provides:
- The standard file and directory layout
- The cross-harness agent instruction conventions (`agents.md`, CLAUDE.md)
- The security model (brain isolation, least privilege, audit trail)
- The configuration management layer (env vars, bootstrap, overrides)
- The hook taxonomy and log schema

Any workflow or knowledge base set up in AIOS-standard format is portable across harnesses. The same brain configuration should work whether the harness is Claude Code today or something else tomorrow. Harness-specific configuration lives in `$HORIZON_SYSTEM/harness_configs/<vendor>/` and extends — but never replaces — the cross-harness core.

---

## 8. Current Scope: Claude Code Only

Section 7 frames AIOS as harness-agnostic, and that is the intended architecture. The current implementation is not there yet. Every concrete artifact — hook scripts, `settings.json` templates, the bootstrap paths, the statusline integration, the skill directory conventions — is implemented against Claude Code specifically. No other harness has a working integration.

What is genuinely harness-neutral today: the conceptual model (brain isolation, the ACL boundary, the registry/switcher pattern, the provision record), the brain directory layout, and `agents.md` itself. `agents.md` is written in harness-neutral language deliberately — it should remain readable and actionable by any harness that supports an equivalent instruction file. The security model (OS users, explicit Deny ACLs, credential containment) has no Claude dependency and applies to any harness that runs as the brain OS user.

Three harnesses have been identified as future targets to explore — not committed roadmap items, but the next logical candidates once the BYOH aspiration moves from design principle to implementation:

- **Ollama** — a local model runtime with no equivalent to Claude Code's hook system or `~/.claude/` config. The open question: whether a parallel config convention (e.g., Modelfile SYSTEM blocks) can carry enough of the AIOS context-loading and hook semantics to make brain isolation meaningful. A minimal stub exists under `harness_configs/ollama/`; it does not yet answer this question.
- **Codex** (OpenAI) — OpenAI's coding agent / CLI tooling. The open question: whether it has a config home analogous to `~/.claude/`, supports something equivalent to hooks, and can load AIOS context in the same way `@`-imports load it for Claude Code.
- **LM Studio** — a local model GUI with an OpenAI-compatible API. The open question: whether the API compatibility layer is sufficient to share Codex-style integration, or whether the desktop GUI model requires a separate harness config path.

For each of these, "adding harness support" would require at minimum: a parallel `settings_{harness}.json` template, equivalent hook scripts (or the best available substitute), a parallel bootstrap section, and a parallel `active_env` export in the switcher. The brain model, the ACL layer, and the registry are reusable as-is — they have no harness dependency. The work is in the integration scaffolding, not the OS layer.

---

## 9. Evaluation: Current Implementation Against These Values

### Aligned

| Value | How the current implementation delivers it |
|---|---|
| BYOH / Harness independence | `agents.md` + CLAUDE.md conventions; `harness_configs/` separation; explicit design constraint in `dev_values.md` §6 |
| Lean into existing IT infra | OS user accounts for brain isolation; NTFS ACLs / `icacls`; no custom access control layer |
| Least privilege, enforced | Zero-default access posture; explicit Deny ACEs on `sbin`; `horizon_aios_create_brain.py` provisions the minimum; every tool grant requires a one-sentence justification |
| Audit trail | `horizon_aios_monitor.py` writes to `$HORIZON_SYSTEM/logs/`; log dir has Deny ACE for brain users (set by `horizon_aios_harden.py`); documented in `security_invariants.md` §7 |
| Credential containment | OS-native credential stores via `horizon_aios_brain_credential.py` in sbin; no brain has default key access; scoped credential grants |
| IaC-ready paths | All paths are env vars; no hardcoded values in committed files |
| Reproducible bootstrap | `bootstrap.ps1` / `bootstrap.sh` cover setup end-to-end |
| Brain isolation | Separate OS user accounts; own folder only by default; blast radius limited |

### Gaps

| Value | Gap | Status |
|---|---|---|
| IaC / Containerization | ~~No Dockerfile or Docker Compose template exists.~~ | **Addressed** — `horizon_system/templates/docker/` contains Dockerfile, docker-compose.yml, and .dockerignore. `bootstrap_docker.sh` is the container-aware bootstrap. ACL hardening now runs as root before the `USER aios` switch. Per-brain containerization is outside AIOS scope (see §5). |
| Blue Team Answerability | AIOS logs lifecycle events (Stop/PermissionRequest/StopFailure) and AIOS-layer file changes, but not tool invocations or reads inside brain folders. Full session-level audit requires OS-level infrastructure integration. | **Addressed by design** — AIOS provides the boundary and the log location; §3 now documents concrete OS-level audit recommendations (Linux `auditd`, macOS BSM, Windows Security Audit, Docker logging drivers). Integration is the operator's responsibility, consistent with how every other application in their environment is audited. |
| Brain vs. AIOS conceptual vocabulary | The distinction between Brain (expert app) and AIOS (OS layer) was implicit. | **Addressed** — this document defines the vocabulary. |
| Second Brain as goal state | Not articulated in any existing document. | **Addressed** — §2 of this document. |
| Per-brain provisioning record | No generated audit artifact per brain. | **Addressed** — `horizon_aios_create_brain.py` Phase 5 writes `.aios_provision.json` to each brain's directory at provisioning time. Post-creation grants are not auto-recorded. |
| Docker-aware bootstrap | No container-aware bootstrap variant. | **Addressed** — `bootstrap_docker.sh` wraps `bootstrap.sh` with `AIOS_DEPLOY_MODE=docker`; `bootstrap_docker.ps1` is the equivalent wrapper for driving the build from a Windows host. Images are Linux containers (run on Windows/macOS/Linux via the container runtime). |
| Brain verification on Windows | `horizon_aios_create_brain.py` Phase 4 verifies brain folder existence on Windows but does not verify ACL correctness — it trusts that the `icacls` commands in Phase 3 succeeded. A failed `icacls` call raises an exception and aborts provisioning, so catastrophic failures are detected; partial ACL success is not re-checked. | **Open** — full ACL re-verification on Windows would require parsing `icacls` output, which adds significant complexity. Current posture: fail-loudly on error, trust-on-success. |
