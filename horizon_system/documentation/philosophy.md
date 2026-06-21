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
| **Memory System** | The memory subsystem owned and contained within a brain. Calibration documents, few-shot examples, retrieval stores, conversation history, domain knowledge — all live inside the brain's directory. The memory system is what makes a brain portable: when it travels, the brain's expertise travels with it regardless of harness or model. |
| **AI Operating System (AIOS)** | The collection of configuration, harnesses, security boundaries, logging, and coordination scaffolding that brains run on top of. The OS layer is not itself an expert system. It is the infrastructure that makes expert systems safe, auditable, and controllable. |
| **Second Brain** | The goal-state user experience: an ecosystem of brains that collectively runs life and business tasks — things that require some level of cognition but not the user's full attention. Tedious, repetitive, or high-volume cognitive work delegated to purpose-built expert systems. |

**Why this matters:** If you conflate Brain with AIOS, you build a single large system that is opaque, hard to audit, and difficult to contain. The separation enables: independent deployment of brains, per-brain access control, per-brain audit trails, and a stable shared OS layer that can be updated without disrupting individual brains.

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

---

## 4. Lean Into Existing IT Infrastructure

Horizon AIOS is not a security framework. It is a configuration layer that redirects existing security frameworks toward AI workloads.

- **User isolation** is done by the OS (NTFS ACLs / POSIX permissions), not by AIOS code.
- **Audit logging** uses the OS filesystem and optionally `auditd` / Windows Security Audit — tools the security team already knows.
- **Credential containment** uses the OS filesystem (per-brain directory permissions on `$HORIZON_KEYS`), not a custom secrets store.
- **Centralized logging** follows the standard log taxonomy the ops team already has tooling for.
- **Access control** is enforced by `icacls` / `chmod` — not reimplemented.

The goal: when a security team asks "how does this work?", the answer should be "the same way everything else works — OS users, filesystem ACLs, and centralized logs." Not "we built a custom isolation layer."

---

## 5. Infrastructure as Code and Containerization

Horizon AIOS must be deployable as infrastructure, not just installed by hand.

**Deployment models, all first-class:**

1. **Bare metal / native OS** — bootstrap scripts provision env vars, directories, permissions, brain accounts. Current primary model.
2. **Docker container (AIOS as container)** — the entire AIOS layer runs in a container. Brains run as sub-containers or OS users within. Enables consistent deployment across machines.
3. **Docker container (per-brain)** — each brain runs in its own container managed by the AIOS. AIOS is the orchestrator; Docker adds network and process isolation on top of OS-level account isolation.

**IaC compatibility requirements:**
- No hardcoded paths in any committed file — all paths are env vars (`$HORIZON_ROOT`, `$HORIZON_SYSTEM`, etc.).
- Bootstrap scripts are the single source of truth for setup — cloning the repo + running bootstrap produces a working AIOS.
- Brain provisioning is a single script invocation (`create_brain.py`) — not a sequence of manual steps.
- Configuration is file-driven — the entire AIOS state can be recreated from the repo + a local config file.

Docker does not replace OS-level user isolation — it extends it. A Dockerized brain still runs as a non-root user inside the container. The container boundary adds network isolation and process isolation; the OS user boundary limits filesystem access.

---

## 6. Memory Systems Are Part of the Brain

An expert system cannot function without memory. Memory is not an optional add-on — it is what makes a brain an expert rather than a stateless query processor.

**Memory belongs inside the brain, not in the AIOS layer.**

The AIOS provides no shared memory system. Each brain owns its own memory subsystem, scoped entirely within its directory boundary. This is intentional:

- A brain's memory is part of its expert function — it is as specialized as its toolset.
- Placing memory in the brain (not in the OS layer) enforces the isolation model: a brain's accumulated knowledge cannot leak to other brains any more than its files can.
- The AIOS provides the *structure* (the brain's home directory) and the *security model* (filesystem permissions) but not the memory implementation. The brain chooses what memory system to use.

**Memory as the portability layer:**

A brain's memory system is what enables the BYOH principle at the brain level. When memory (training data, calibration documents, context stores, vector indices, conversation history) is consolidated within the brain rather than tied to a specific harness or API:

- The brain's knowledge and expert context travel with it when the underlying harness changes.
- Swapping the frontier model, the API provider, or the toolchain does not require rebuilding the brain's expertise from scratch.
- The brain is model-agnostic and harness-agnostic because its memory is portable.

Without a self-contained memory system, a brain is tightly coupled to whatever harness or model it happened to train on. With one, it is a portable expert that can be brought to any harness, any frontier model, any API endpoint, any network topology — independently.

**What this means in practice:**

- Brain directories hold memory artifacts: calibration documents, few-shot examples, retrieved context stores, conversation logs, domain-specific knowledge files.
- Memory tooling (vector databases, embedding pipelines, retrieval scripts) is provisioned inside the brain's directory, not shared across brains via the AIOS.
- The AIOS provides the secure container; the brain provides the contents. The container is standardized; the contents are specialized.

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

Any workflow or knowledge base set up in AIOS-standard format is portable across harnesses. The same brain configuration should work whether the harness is Claude Code today or something else tomorrow. Harness-specific configuration lives in `$HORIZON_BIN/harness_configs/<vendor>/` and extends — but never replaces — the cross-harness core.

---

## 7. Evaluation: Current Implementation Against These Values

### Aligned

| Value | How the current implementation delivers it |
|---|---|
| BYOH / Harness independence | `agents.md` + CLAUDE.md conventions; `harness_configs/` separation; explicit design constraint in `dev_values.md` §6 |
| Lean into existing IT infra | OS user accounts for brain isolation; NTFS ACLs / `icacls`; no custom access control layer |
| Least privilege, enforced | Zero-default access posture; explicit Deny ACEs on `sbin`; `create_brain.py` provisions the minimum; every tool grant requires a one-sentence justification |
| Audit trail | `monitor_aios.py` writes to `$HORIZON_ROOT/logs/`; log dir has Deny ACE for brain users; documented in `security_invariants.md` §8 |
| Credential containment | Per-brain subdirectories in `$HORIZON_KEYS`; no brain has default key access; scoped read-only grants |
| IaC-ready paths | All paths are env vars; no hardcoded values in committed files |
| Reproducible bootstrap | `bootstrap.ps1` / `bootstrap.sh` cover setup end-to-end |
| Brain isolation | Separate OS user accounts; own folder only by default; blast radius limited |

### Gaps

| Value | Gap | Priority |
|---|---|---|
| IaC / Containerization | No Dockerfile or Docker Compose template exists. The AIOS is described as container-compatible but no deployment artifact exists. | Medium |
| Blue Team Answerability | The "what is the agent doing / how / why" framing is implicit in the security model but never stated as explicit design goals in a user-facing document. An auditor reading the repo would need to piece this together. | Medium |
| Brain vs. AIOS conceptual vocabulary | `security_invariants.md` uses "brain" without defining it. The distinction between Brain (expert app) and AIOS (OS layer) is not explained anywhere in the existing docs. A contributor or auditor must infer this from context. | High — this document addresses it |
| Second Brain as goal state | Not articulated in any existing document. The user experience objective is missing. | Low (strategy doc; doesn't block implementation) |
| Per-brain provisioning record | `create_brain.py` provisions brains correctly but there is no generated audit artifact (e.g., a machine-readable manifest of what each brain was provisioned with). An auditor cannot inspect "what does brain X have access to?" without running filesystem queries. | Medium |
| Docker-aware bootstrap | `bootstrap.ps1` / `bootstrap.sh` are native-OS only. No container-aware bootstrap variant exists. | Low (future work) |
