# Horizon AIOS — Consistency Checks

A standing, machine-readable specification of what "consistent" means for this
project, plus the protocol for running an iterative validation pass against it.

Invoke it from any session with a prompt like:
> "Read `horizon_system/documentation/development_tools/consistency_checks.md` and run a consistency pass."

This file is **not** loaded into every session — it is run on demand — so it can
be thorough. Keep the checks themselves authoritative and durable; edit them as
the project's standards evolve.

---

## 1. How to run a consistency pass (the protocol)

A *pass* runs every applicable check once and produces a report. You then
remediate or surface findings and run another pass. Repeat until the report is
**100% clean** (every check PASS or justified N/A) **or** you are **blocked on a
user decision**.

1. **Scope.** Default scope is the whole repo. The invoking prompt may narrow it
   (e.g., "only the files changed this session", "only the statusline feature").
   State the scope at the top of every report.
2. **Run all in-scope checks (§3).** For each, gather *positive evidence* —
   cite `file:line`, a command and its output, or a quoted doc passage. Do not
   mark a check PASS without evidence. If you could not verify it, mark UNKNOWN,
   not PASS. No false greens.
3. **Classify each check:**
   - `PASS` — verified consistent, with evidence.
   - `FAIL` — verified inconsistent. Include the conflict and the fix.
   - `PARTIAL` — consistent in some places, not others. List the gaps.
   - `UNKNOWN` — could not verify within scope/tools. Say why.
   - `N/A` — not applicable to this scope. Justify.
4. **Remediate vs. surface.**
   - **Fix directly** when the correct resolution is unambiguous (a stale path,
     a renamed flag, a missing doc entry, a one-sided platform implementation).
   - **Stop and ask the user** when a finding requires a judgment call: a design
     trade-off, an authority conflict that isn't clearly resolved by §2, anything
     that changes intended behavior, or anything destructive/outward-facing.
     Collect such items into a single "Needs user input" list rather than
     guessing.
5. **Re-run.** After any fix, run a **full** new pass over the same scope — a fix
   can introduce new drift. Note what changed since the previous pass.
6. **Terminate** when either:
   - every in-scope check is PASS or justified N/A (**100% clean**), or
   - the only remaining findings are in "Needs user input" (**blocked**).
   Print a final summary with the pass count and the terminal state.

Never weaken or delete a check to make a pass go green. If a check itself is
wrong or outdated, flag that as a finding and ask before editing this file.

---

## 2. Authority hierarchy (tie-breaker for conflicts)

When two sources disagree, the higher one wins and the lower one is the defect to
fix. Always flag the conflict; never silently "average" them.

```
philosophy.md  ▶  dev_values.md  ▶  architecture_decisions.md  ▶  all other documentation  ▶  implementation
```

- `documentation/philosophy.md` — the why; highest authority.
- `documentation/dev_values.md` — engineering values; beats architecture.
- `documentation/build_decisions/architecture_decisions.md` — the ADR log; beats
  all other docs. Respect supersession: a decision marked SUPERSEDED must not be
  presented as current anywhere.
- All other documentation must align with the three above.
- Implementation must align with the documentation. Where implementation and a
  *lower* doc disagree but the implementation matches a *higher* authority, the
  lower doc is the defect.

If a higher authority is itself silent or ambiguous on a point in dispute, that
is a "Needs user input" item.

---

## 3. The checks

Each check has a stable ID. Cite evidence for every verdict. "Tools/scripts"
includes everything under `horizon_system/bin`, `horizon_system/sbin`,
`horizon_system/scripts`, skills, hooks, and templates.

### A. Documentation hierarchy & alignment
- **CC-A1 — Authority respected.** No lower-tier document contradicts a higher
  tier (per §2). Verify by spot-checking claims in other docs against philosophy,
  dev_values, and the ADR log.
- **CC-A2 — Philosophy alignment.** Every document is consistent with
  `philosophy.md`. Flag anything that violates a stated principle.
- **CC-A3 — Values alignment.** Implementations and docs honor `dev_values.md`
  (e.g., token economy for context-loaded files, stated security posture).
- **CC-A4 — ADR alignment & supersession.** Current behavior matches the
  non-superseded ADR entries; superseded decisions are not described as current
  anywhere in docs or code comments.

### B. Documentation ↔ implementation consistency
- **CC-B1 — Docs match code.** Every command, flag, env var, path, placeholder,
  config key, and described behavior in the docs exists and behaves that way in
  the implementation.
- **CC-B2 — Code is documented.** Every user-facing tool/script/skill/hook/config
  key in the code is documented somewhere discoverable (see CC-H1).
- **CC-B3 — No stale references.** No docs or comments reference removed/renamed
  files, old placeholders, old paths, or superseded mechanisms.
- **CC-B4 — Examples run.** Commands and code snippets in docs execute as written
  on at least one supported platform (note which). Substitution placeholders are
  current.

### C. Cross-platform (Linux, Windows, macOS)
- **CC-C1 — Parity exists.** Every platform-specific implementation has a working
  counterpart for the other supported platforms (e.g., a `.ps1` has a `.sh`
  peer; bootstrap, hooks, statusline, wrappers all cover Windows + Unix).
  This is an **explicit** check: enumerate the platform-specific assets and
  confirm each has full coverage.
- **CC-C2 — Instructions cover all OSes.** Setup/usage docs give correct
  Windows, Linux, and macOS instructions where they differ.
- **CC-C3 — No unguarded OS assumptions.** Path separators, shells, line endings,
  symlink/junction handling, and OS-only commands are guarded or abstracted, not
  hardcoded to one platform outside a platform branch.

### D. Deployment flexibility
- **CC-D1 — Single desktop.** The single-user desktop path works end-to-end and
  is the low-friction default (likely the earliest adopter).
- **CC-D2 — Server / multi-user.** Multi-user server deployment is supported and
  documented (shared install, per-user/brain scoping).
- **CC-D3 — Virtualization / containerization.** Docker (and VM) deployment is
  supported and documented; image-based config refresh is accounted for.
- **CC-D4 — IaC & orchestration.** Setup/teardown is scriptable, idempotent, and
  non-interactive (honors `--yes`/env-driven config) so it works under
  infrastructure-as-code and orchestrators (e.g., Ansible).
- **CC-D5 — Modes documented.** Each deployment mode above has a deployment doc
  and they do not contradict each other.

### E. Enterprise + single-user duality (blue-team)
- **CC-E1 — Enterprise foundations.** Audit logging, least-privilege/ACLs,
  credential hygiene, and tamper-awareness are present and foundational, not
  bolted on.
- **CC-E2 — Single-user simplicity.** Sane defaults make a single-user install
  easy; enterprise features do not block or complicate the simple path.
- **CC-E3 — Defensive posture.** The project adheres to a blue-team philosophy:
  secure defaults, auditability, no detection-evasion or offensive-by-default
  behavior.

### F. No AI-harness vendor lock-in
- **CC-F1 — Harness-swappable.** Harness-specific wiring is isolated (e.g.,
  `harness_configs/`, templates) so harnesses (Claude Code, Codex, Ollama-based,
  etc.) are swappable, not hardcoded into core logic.
- **CC-F2 — Configurable & extensible.** Adding or reconfiguring a harness is a
  documented, template-driven extension point.
- **CC-F3 — User controls brain data.** The user dictates how data inside brains
  is stored, used, and exposed; nothing forces a single vendor's data model.

### G. Documentation completeness & form
- **CC-G1 — User-forward & clear.** Docs are written for the reader, unambiguous,
  and task-oriented.
- **CC-G2 — Machine-readable.** Consistent structure (headings, IDs, tables,
  fenced code) so docs are parseable by tools and agents.
- **CC-G3 — Complete coverage.** Every capability and tool the AIOS provides is
  documented. Missing concepts are a FAIL, not an omission.
- **CC-G4 — Indexed & referenceable.** All documentation is registered in a
  documentation index and can be referenced by its index entry. No doc is
  orphaned (absent from the index), and every index entry resolves to a real
  file. New docs are added to the index in the same change.
- **CC-G5 — Token economy for context-loaded files.** Every file that is
  *regularly loaded into context* — e.g., `agents.md`, `CLAUDE.md`, the invariant
  docs under `ai_os_etc/`, and anything pulled in via an `@`-import — is highly
  conscious of token overhead: direct, non-redundant, no content that belongs in
  an on-demand doc instead. Verbosity in these files is a FAIL because it costs
  tokens every session. (Aligns with `dev_values.md` token economy.)
- **CC-G6 — Dependency list.** Documentation provides a current, explicit list of
  external dependencies required to run the AIOS — language runtimes (Python,
  PowerShell, bash), `git`, OS features (directory junctions/symlinks, ACL
  tooling), and any optional tools — with minimum versions where they matter. A
  dependency introduced by code is added to this list in the same change.

### H. Tool discoverability
- **CC-H1 — Findable with usage.** Every tool/script/skill is locatable from the
  documentation (an index or catalog) together with how to invoke it and its
  options. No "orphan" tools that exist only in the source tree.

### I. Onboarding & offboarding (all platforms)
- **CC-I1 — Easy onboarding.** Installing/bootstrapping the AIOS is available as
  tooling and clearly documented.
- **CC-I2 — Clean offboarding.** Uninstall/teardown (config, links, registry,
  scheduled tasks, brains/ACLs as applicable) is available as tooling and
  clearly documented, leaving the host clean.
- **CC-I3 — Cross-platform onboarding/offboarding.** This is an **explicit**
  check: both onboarding and offboarding are verified to be easy on **every**
  supported platform (Linux, Windows, macOS). For each OS, confirm the tooling
  exists and works and the documented steps are correct — neither path may be
  Windows-only or Unix-only. (Pairs with Group C.)
- **CC-I4 — System-change summary.** Documentation provides an explicit,
  accurate summary of the system changes onboarding makes, so an operator knows
  exactly what will be modified before running anything:
  - **Onboarding a new AIOS:** files/dirs created (`~/.claude/*`, `~/.horizon/*`,
    `handoffs/`, `objectives/`, `logs/`), profile/env changes, the AIOS registry,
    scheduled tasks, and ACL hardening.
  - **Onboarding a new brain:** the OS user account + group membership, the brain
    home directory, the ACLs applied, and the harness config written for the
    brain.
  Offboarding documents the reverse (ties to CC-I2). The documented change set
  must match what the tooling actually does.

---

## 4. Report format

Produce a report shaped like this each pass:

```
# Consistency Pass <N> — <scope> — <date>

Summary: <P> PASS · <F> FAIL · <PA> PARTIAL · <U> UNKNOWN · <NA> N/A
State:   <CLEAN | REMEDIATING | BLOCKED ON USER>

## Findings (FAIL / PARTIAL / UNKNOWN only)
- [CC-B3] FAIL — <one line>. Evidence: <file:line / output>. Fix: <action or "see user input">.
- ...

## Fixed this pass
- <file> — <what changed> (resolves CC-XX)

## Needs user input
- <CC-XX> — <the decision required and the options>

## Verified clean (IDs)
CC-A1, CC-A2, ... (PASS/N-A with evidence on request)
```

Keep the running report terse: only FAIL/PARTIAL/UNKNOWN get prose; PASS/N-A are
listed by ID. The goal is a tight signal of what is wrong and what was done,
pass over pass, until clean or blocked.
