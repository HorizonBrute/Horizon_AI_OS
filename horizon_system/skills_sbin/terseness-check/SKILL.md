---
name: terseness-check
description: Evaluate every file in the Terseness Contract Index for context overhead — flags verbose prose, redundant rationale, unnecessary examples, and misplaced content that should be on-demand. Reports FAIL/ADVISORY findings with file:line evidence and concrete cut suggestions. Use when asked to check context overhead, run a terseness pass, or when the consistency check delegates CC-T2.
tools: Read, Grep, Glob, Bash
---

# Skill: /terseness-check

**Model preference:** `#highcap` (judgment-heavy; needs to distinguish operative from
decorative prose accurately).

Evaluate every tracked file in the Terseness Contract Index against the seven
terseness criteria defined there. Gitignored files get `ADVISORY` findings only.

---

## Source of truth

Read these before evaluating anything:

1. `$HORIZON_DOCS/terseness_contract_index.md` — the canonical file list and all
   seven terseness criteria.
2. Each file in the **Tracked** table, in order.

---

## Evaluation protocol

For each tracked file:

1. Read the file in full.
2. Apply all seven criteria from the index. For each violation found:
   - Cite `file:line` (or a line range).
   - Quote the offending content (one line or the opening phrase of a block).
   - State which criterion it violates (1–7).
   - Propose a concrete fix: cut, move to an on-demand doc with a pointer, or
     collapse to one line.
3. Classify: `PASS` (no violations) or `FAIL` (one or more violations with evidence).

For each gitignored / user-controlled file (if it exists on disk):

1. Read it. If absent, skip — `N/A (not present)`.
2. Apply the same criteria but classify findings as `ADVISORY`, not `FAIL`.
   Do not auto-fix advisory findings; surface them for the user.

---

## Report format

```
# Terseness Check — <date>

Summary: <P> PASS · <F> FAIL · <A> ADVISORY · <NA> N/A

## FAIL findings
- [<file>:<line>] Criterion <N> — <one-line description>.
  Offending: "<quoted content>"
  Fix: <cut | move to <doc> with pointer | collapse to: "<replacement>">

## ADVISORY findings (gitignored / user-controlled)
- [<file>:<line>] Criterion <N> — <description>. Fix: <suggestion>.

## PASS
<file list>

## N/A (absent gitignored files)
<file list>
```

Keep the report tight: one finding block per violation, no commentary beyond the
fix. If a file is clean, list it under PASS — do not write prose about it.

---

## Auto-fix scope

Fix `FAIL` findings directly (Edit the file) only if **all three** are true:
1. The fix is a pure removal or collapse (no new content written).
2. The content being removed contains no operative instruction.
3. The fix does not change meaning for any other always-loaded file.

Surface for user confirmation before fixing if any of those conditions is uncertain.
Never auto-fix `ADVISORY` findings.

---

## When invoked by the consistency check

The `/horizon_aios_dev_consistency_check` skill delegates CC-T2 to this skill.
When called that way, return the full terseness report and map each `FAIL` finding
to `CC-T2 FAIL`. `ADVISORY` findings map to `CC-T2 ADVISORY` in the consistency
pass report.
