---
name: horizon_aios_wiki_upkeep
description: Run a consistency pass between the Horizon AIOS operational wiki and the underlying source documentation, fixing unambiguous drift and surfacing decisions until clean. Use when the user types /horizon_aios_wiki_upkeep, asks to "update the wiki", "sync the wiki with the docs", or "check if the wiki is still accurate".
tools: Agent, Read, Write, Edit, Glob, Grep, Bash
---

# Skill: /horizon_aios_wiki_upkeep

**Model preference:** `#highcap` (cross-document consistency reasoning; drift detection requires full comprehension of both sources).

Keep `$HORIZON_DOCS/user_guides/using_your_aios.md` consistent with the underlying source documentation it synthesizes. The wiki is a synthesis layer — when source docs change, the wiki can drift. This skill finds and fixes that drift.

---

## When to invoke

- After any source documentation has been updated or added.
- After new AIOS features, scripts, or skills have been shipped that affect wiki content.
- Periodically as a health check, even without known changes.
- When the user notices the wiki contradicts something they just read in a source doc.

---

## Scope

**Wiki file:** `$HORIZON_DOCS/user_guides/using_your_aios.md`

**Section count:** Dynamic — read the actual `## N. Title` headings from the wiki
file at runtime. Do not rely on any hardcoded count. The scope table below is an
annotation layer that maps known sections to their source docs; it is kept current
by `/horizon_aios_wiki_update --reindex`. If the wiki has sections not listed here,
treat them as needing a source-doc mapping determination (Step 1.3).

**Source documents the wiki synthesizes:**

| Wiki section | Primary source(s) |
|---|---|
| 1 — Security Model | `$HORIZON_ETC/security_invariants.md`, `$HORIZON_DOCS/philosophy.md` §§3–4 |
| 2 — Building a Brain | `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md` (Adding a Brain), `$HORIZON_DOCS/deployment/desktop.md` |
| 3 — Projects | `$HORIZON_DOCS/getting_started/ReadMeToSetupYourSystem.md` (Project Isolation Pattern, Adding a New Project) |
| 4 — Handoffs and Objectives | `$HORIZON_DOCS/skills.md` (/handoff, /objective entries) |
| 5 — Case Study | `$HORIZON_DOCS/deployment/brain_automation.md`, `$HORIZON_DOCS/deployment/desktop.md` |
| 6 — BYOH and local.agents.md | `$HORIZON_DOCS/context_loading.md`, `$HORIZON_DOCS/philosophy.md` §7 |
| 7 — Model Preferences and Agent Teams | `$HORIZON_DOCS/system/model_preferences.md`, `$HORIZON_ETC/horizon_aios_model_prefs.md`, `$HORIZON_DOCS/system/agent_teams.md`, `$HORIZON_ROOT/agent_teams.md`, `$HORIZON_ETC/agent_team_flags.md` |
| 8 — Context Management | `$HORIZON_DOCS/context_loading.md`, `$HORIZON_DOCS/authoring/claude_md_authoring.md` |
| 9 — Gitignore | `$HORIZON_DOCS/system/distribution_and_updates.md` |
| 10 — Enterprise Deployment | `$HORIZON_DOCS/system/distribution_and_updates.md`, `$HORIZON_DOCS/deployment/server.md` |
| 11 — Containerization / IaC | `$HORIZON_DOCS/deployment/docker.md`, `$HORIZON_DOCS/philosophy.md` §5 |
| 12 — Bring Your Own Infrastructure | `$HORIZON_DOCS/philosophy.md` §§3–4, `$HORIZON_DOCS/security/audit_logging.md` |
| 13 — The Terseness Contract | `$HORIZON_DOCS/terseness_contract_index.md` |

**Out of scope:** The wiki's case study section is illustrative, not a mechanical
reflection of a source doc. Check it only for factual accuracy (commands that work,
paths that exist), not for completeness.

---

## Step-by-step execution

### Step 1 — Identify scope

1.1 Read `$HORIZON_DOCS/user_guides/using_your_aios.md`. Extract all numbered
section headings dynamically by scanning for `## N.` patterns. This is the
authoritative section list — not any hardcoded count in this file.

1.2 For any section whose number does not appear in the scope table above, infer its
primary source docs from the section title and content before proceeding.

1.3 Ask the user: "Do you know which source docs changed, or should I do a full pass across all sections?"

- If the user names specific sections or source docs → check only those sections in Step 2.
- If unknown or full pass requested → proceed to Step 2 for all sections found in 1.1.

1.4 Optionally, run `git log --since="30 days ago" --name-only -- "$HORIZON_DOCS" "$HORIZON_ETC"` to surface recently changed source docs as a hint. Do not rely on git log as the sole check — it only shows committed changes.

### Step 2 — Delegate section checks in parallel

Spawn one #investigate agent per section being checked (all in a single message for parallel execution). Each agent receives:

- The wiki section text (extracted from the wiki file)
- The content of the relevant source documents (listed in the Scope table above)
- This instruction:

```
You are checking a wiki section against its source documentation for consistency.

Wiki section text:
<wiki section text>

Source documentation:
<source doc content>

Check for:
1. Factual drift — claims in the wiki that contradict the current source docs (wrong commands,
   wrong paths, wrong behavior descriptions, removed features, changed defaults).
2. Coverage gaps — significant content in the source docs that the wiki section is missing
   and that a reader of this section would benefit from knowing.
3. Stale references — file paths, script names, or command flags that no longer exist.
4. Outdated examples — code blocks that would no longer work as written.

For each issue found, report:
- Issue type (drift / gap / stale reference / outdated example)
- The specific claim or gap
- What the source doc says instead
- Whether it is unambiguous (safe to fix automatically) or a judgment call (needs user input)

If no issues are found, report: CLEAN
```

### Step 3 — Process results

3.1 Collect all agent reports. Group findings by:
- **Unambiguous fixes** — factual errors, stale paths, wrong commands; safe to apply without user input.
- **Judgment calls** — coverage gaps, tone/emphasis changes, restructuring suggestions; require user decision.

3.2 Present a summary to the user:
```
Wiki upkeep pass complete.

Unambiguous fixes (<N> found): [list each briefly]
Judgment calls (<N> found): [list each briefly, with options]
Clean sections: [list section numbers]
```

3.3 Apply all unambiguous fixes directly — edit `$HORIZON_DOCS/user_guides/using_your_aios.md` using Edit. For each fix, report the change in one line: `Fixed §<N>: <what changed>`.

3.4 For each judgment call, present it to the user with a clear question and 2–3 options. Wait for the user's decision before making any change. Apply their choice, then report: `Applied §<N>: <what changed>`.

### Step 4 — Re-run until clean

4.1 After all fixes are applied, run the section checks again for any section that had issues.

4.2 Repeat until all sections report CLEAN or all remaining issues are explicitly deferred by the user.

4.3 Final report:
```
Wiki upkeep complete. All sections clean.
  Applied <N> fixes.
  Deferred <N> items (user decision).
```
Or, if items remain:
```
Wiki upkeep pass complete. <N> items remain open:
  [list deferred items with their status]
```

### Step 5 — Update the documentation index if needed

5.1 If the wiki file's index entry in `$HORIZON_DOCS/index.md` is stale (wrong title or outdated purpose summary), update it.

5.2 If new sections were added to the wiki during this pass, update the section map in `$HORIZON_SYSTEM/skills_bin/userguides/SKILL.md` to reflect the new count and titles.

---

## Notes for the executing agent

- The wiki is a synthesis, not a mirror. It synthesizes multiple source docs into a practical guide. A gap in the wiki is only an issue if the missing content would materially help a reader of that section — not every detail in every source doc needs to appear in the wiki.
- Prefer Edit over Write for wiki changes. Surgical edits preserve surrounding context and reduce the risk of accidental formatting changes.
- Do not restructure the wiki unless the user explicitly requests it. Fix facts; do not rewrite prose.
- The skill's own section map (the table above) must stay current. If source docs for a section change significantly, update that row.
- If a source doc referenced in the Scope table no longer exists, surface that as a finding — the wiki may need to be updated and the scope table corrected.
- This skill is sbin (owner-only) because it writes to tracked documentation. Brains must not modify wiki or documentation files.
