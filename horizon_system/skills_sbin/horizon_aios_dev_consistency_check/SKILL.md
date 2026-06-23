---
name: horizon_aios_dev_consistency_check
description: Run an iterative documentation/implementation consistency validation pass against the AIOS consistency-check standard, fixing unambiguous drift and surfacing decisions until 100% clean or blocked on user input. Use when asked to run a consistency pass/check, validate AIOS standards, or verify docs and implementation are consistent (e.g. after a feature lands).
tools: Read, Grep, Glob, Bash, Edit, Write
---

# Skill: /horizon_aios_dev_consistency_check

**Model preference:** `#midcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Run a consistency validation pass over the Horizon AIOS repo using the standing
standard at `$HORIZON_DOCS/development_tools/consistency_checks.md`. That file —
not this one — is the single source of truth for the checks (IDs `CC-*`), the
authority hierarchy, the run protocol, and the report format. This skill is the
invocation entry point that runs it.

---

## When to invoke

- "run a consistency pass/check", "validate AIOS standards", "check docs vs
  implementation are consistent", "verify the AIOS is internally consistent".
- After a feature or docs change lands, to confirm no drift was introduced.

## Run this as a subagent (do this first)

A consistency pass reads broadly across docs and code, so running it inline bloats
the invoking session's context. **When invoked, delegate the work to a
general-purpose subagent** rather than doing it in the main session (this follows
the agent delegation model in `agents.md` — the main session orchestrates,
subagents do the file-heavy work). Only run inline if subagents are unavailable.

How to delegate:
1. Spawn a general-purpose subagent (the harness's Agent/Task tool,
   `subagent_type: general-purpose`). Subagents start cold — give it enough scope
   and context to be self-sufficient.
2. Instruct it: "read `$HORIZON_DOCS/development_tools/consistency_checks.md` and
   run its protocol over <scope>; fix unambiguous drift, collect judgment calls
   into 'Needs user input', report each pass in the §4 format; **do not commit**."
3. The subagent runs the iterate-until-clean-or-blocked loop and returns its
   report; the main session relays it and brings any "Needs user input" items to
   the user.

For a full-repo pass you may fan out subagents by check group (A–I) or by area and
have the main session synthesize one report, then re-run until clean or blocked.

## Execution

1. **Read** `$HORIZON_DOCS/development_tools/consistency_checks.md` in full.
2. **Determine scope** from the user's prompt (default: the whole repo; may be
   narrowed, e.g. "only this session's changes"). State the scope up front.
3. **Run the protocol** in §1 of that file:
   - Execute every in-scope check (`CC-*`). Gather *positive evidence* for each
     verdict — `file:line`, a command + its output, or a quoted passage. No false
     greens: anything unverified is `UNKNOWN`, never `PASS`.
   - **Fix** unambiguous drift directly (stale paths, renamed flags, missing index
     entries, one-sided platform implementations).
   - **Surface** judgment calls into a single "Needs user input" list — design
     trade-offs, authority conflicts not resolved by §2, behavior changes, or
     anything destructive/outward-facing. Do not guess.
   - **Re-run a full pass** after any fix (a fix can introduce new drift).
   - **Terminate** at 100% clean (all PASS or justified N/A) or when blocked on
     user input.
4. **Report** each pass in the §4 format. Keep a running tally of pass count and
   the terminal state.

## Notes for the executing agent

- Never weaken or delete a check to make a pass go green. If a check itself is
  wrong/outdated, flag it as a finding and ask before editing
  `consistency_checks.md` (§1 rule).
- Apply the authority hierarchy (§2) to conflicts: `philosophy ▶ dev_values ▶
  architecture_decisions ▶ other docs ▶ implementation`. A lower doc that
  contradicts a higher authority is the defect.
- Cross-platform (Group C) and onboarding/offboarding (CC-I3) require
  *enumerating* the platform-specific assets and confirming parity — verify it,
  do not infer it.
- CC-G4 (doc index) and CC-G5 (token economy of context-loaded files) often pair
  with `/horizon_aios_documentation_index_update`; run or recommend it when CC-G4
  fails.
- Commit fixes only if the user asks (DCO sign-off per repo rules); otherwise
  leave changes in the working tree and report.
