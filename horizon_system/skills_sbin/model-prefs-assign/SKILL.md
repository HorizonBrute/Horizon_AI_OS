---
name: model-prefs-assign
description: Audit AIOS skills for their model-preference group callout and assign or refresh it — add a "Model preference" line to skills that lack one, change the group where behavior should differ, and keep the skill indexes' Model-group columns in sync. Use when the user types /model-prefs-assign, says "assign model groups to skills", "audit skills for model preference", "which skills are missing a model group", or after adding/changing skills.
tools: Read, Grep, Glob, Edit, Bash
---

# Skill: /model-prefs-assign

**Model preference:** `#midcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Maintenance tool for the per-skill model-preference callouts. Every AIOS skill
should declare, as a one-line BODY callout, which model group (`#lowcost`,
`#midcost`, `#highcap`, `#investigate`, `#debug`, `#fast`) its work should run on.
The callout must live in the body — frontmatter is stripped before the model sees
the skill, so a frontmatter field would never be read. This skill finds skills
missing or mis-assigned and fixes them, then syncs the index columns.

Group semantics live in `$HORIZON_ETC/horizon_aios_model_prefs.md` — read it first.

---

## Quick Reference

- **Purpose:** keep every AIOS skill labeled with an appropriate model group, and
  the skill indexes in sync.
- **Triggers:** "assign model groups to skills", "audit skills for model
  preference", "which skills are missing a model group", `/model-prefs-assign`.
- **Scope:** all SKILL.md under `$HORIZON_SYSTEM/skills_bin/` and
  `$HORIZON_SYSTEM/skills_sbin/` (owner-only; edits privileged skill files).

---

## The callout (exact format)

One line, inserted immediately after the `# Skill:` heading (blank line before and
after). Substitute the group:

`**Model preference:** \`#GROUP\` (per \`horizon_aios_model_prefs.md\`; overridable by a prompt directive).`

Never put the group in frontmatter — it will not reach context.

---

## Assigning a group — heuristics

Pick the group that matches the dominant nature of the skill's work:

1.1 `#highcap` — security-sensitive, privileged, or destructive OS changes; deep
    cross-referencing / judgment where a mistake is costly (e.g. brain
    provisioning, ACL hardening, consistency validation).
1.2 `#investigate` — research, live fetching, cross-source analysis, synthesis.
1.3 `#midcost` — structured authoring/summarization with moderate judgment (docs,
    handoffs, objectives, scaffolding).
1.4 `#lowcost` — mechanical, read-only, or report-only work with little reasoning.
1.5 `#fast` — trivial single actions where latency matters (e.g. launching a
    process).
1.6 `#debug` — step-by-step debugging / coding tasks.

When uncertain between two, prefer the cheaper group unless a mistake would be
costly (then round up). Always propose the assignment to the user before applying.

---

## Procedure

### Step 1 — Enumerate
1.1 Glob all `SKILL.md` under `skills_bin/` and `skills_sbin/`.

### Step 2 — Audit
2.1 For each, grep for a line matching `**Model preference:** #...`. Classify:
    **present** (record the group), **missing**, or **malformed** (wrong format,
    unquoted, or in frontmatter).
2.2 Produce an audit table: skill | tier | current group | status.

### Step 3 — Assign / refresh
3.1 For each missing/malformed skill, determine the group from the heuristics
    above based on the skill's own description and body.
3.2 If the user asked to MODIFY a specific skill's group, target that one.
3.3 Present the proposed changes (skill → group → reason) and get confirmation.
3.4 On confirm, Edit each SKILL.md: insert or correct the callout line after the
    `# Skill:` heading. Match each file's exact heading text. Do not touch
    frontmatter or other content.

### Step 4 — Sync the indexes
4.1 Ensure both `skills_bin/index.md` and `skills_sbin/index.md` have a
    "Model group" column, and that every row's value matches the skill's callout.
    Add/repair rows as needed.

### Step 5 — Report
5.1 List skills added, updated, and unchanged, and confirm index columns match.
5.2 Remind: changes to `skills_sbin/` are owner-tracked — commit them (with the
    index updates) in one commit; the gitignored `extend.md` is unaffected.

---

## Notes for the executing agent

- This edits privileged skill files — owner-only; never expose to brains.
- The callout is documentation the acting model reads when the skill runs; it does
  not enforce model selection, it directs it (in-context, per the BYO layer).
- New skills should ship the callout from creation — `skill-creation` is the place
  to enforce that; flag if a newly created skill lacks one.
- Keep each callout to exactly one line (token-aware). Do not restate group
  semantics in the skill — they live in the spec.
- Never hardcode paths; resolve `$HORIZON_SYSTEM` / `$HORIZON_ETC` from the env.
