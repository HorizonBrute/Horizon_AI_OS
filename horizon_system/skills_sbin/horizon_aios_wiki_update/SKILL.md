---
name: horizon_aios_wiki_update
description: Author, expand, and re-index the Horizon AIOS operational wiki, keeping it shaped as a user story arc from first install through enterprise usage. Use when the user types /horizon_aios_wiki_update, asks to "add to the wiki", "grow the wiki", "update the wiki structure", "re-index the wiki", or when new source documentation has landed that needs wiki coverage.
tools: Agent, Read, Write, Edit, Glob, Grep, Bash
---

# Skill: /horizon_aios_wiki_update

**Model preference:** `#highcap` (authoring new wiki content requires synthesizing multiple source docs into cohesive prose and reasoning about narrative arc and user story progression).

Author, expand, and re-index the Horizon AIOS operational wiki at
`$HORIZON_DOCS/user_guides/using_your_aios.md`. Where `/horizon_aios_wiki_upkeep`
fixes facts, this skill grows structure — adding sections, updating the user story
arc, and keeping all dependent artifacts synchronized when the wiki changes.

**Note on placement:** This skill is a candidate for migration to the Dev Stack
(`skills_sbin/`) as the wiki approaches constitutional status — that is, as it
becomes the canonical user-facing reference that other documentation points to
rather than the reverse. The scaffolding is intentionally placed here while that
transition is pending.

---

## The User Story Arc

The wiki is organized as a progressive user story, not a flat reference. Every
section serves a reader at a specific stage of their journey. New content must be
placed where it fits the arc, not just appended. The arc:

| Stage | Reader question | Sections |
|---|---|---|
| Orientation | What is this system and can I trust it? | Security Model |
| First use | How do I create and configure a brain? | Building a Brain |
| Organizing work | Where does my code live relative to the AI layer? | Projects |
| Working across time | How do I preserve progress between sessions? | Handoffs and Objectives |
| Seeing it whole | What does this look like end-to-end? | Case Study |
| Configuration | How do I tune the system for my workflow? | BYOH / local.agents.md |
| Optimization | What is the cost of this and how do I control it? | Context Management |
| Safety | What do I commit and what do I keep private? | Gitignore / Local Config |
| Scale — org | How does my organization adopt this? | Enterprise Deployment |
| Scale — infra | How does this deploy in cloud / IaC / containers? | Containerization / IaC |
| Scale — IT | How does this integrate with existing infrastructure? | BYOH Infrastructure |

When adding a section, identify which stage it serves. Insert it where the reader
would encounter the question, not at the end.

---

## Arguments

`/horizon_aios_wiki_update [--add-section | --reindex | --survey | --full]`

- No argument / `--survey` — Read all source docs and the current wiki. Report what is missing from the wiki without writing anything. Ask the user which gaps to address before proceeding.
- `--add-section` — Enter the guided section-addition flow (Step 3).
- `--reindex` — Re-synchronize all dependent artifacts (wiki TOC, docs index, userguides skill, upkeep skill scope table) to match the current wiki without changing wiki content.
- `--full` — Survey + add all approved sections + reindex in one pass.

If the user provides a topic name or section title as a plain argument (e.g.,
`/horizon_aios_wiki_update "Agent Teams"`), treat it as `--add-section` with that
topic pre-filled.

---

## Step-by-step execution

### Step 1 — Inventory the current state

1.1 Read `$HORIZON_DOCS/user_guides/using_your_aios.md`. Extract all numbered
section headings (`## N. Title`) dynamically — do not rely on any hardcoded list.

1.2 Read `$HORIZON_DOCS/index.md`. Collect every document path listed there.

1.3 For each source doc in the index, determine whether it has meaningful coverage
in any wiki section. Build a gap list: source docs with no wiki coverage.

1.4 Run:
```bash
git log --since="60 days ago" --name-only --pretty=format: -- "$HORIZON_DOCS" "$HORIZON_ETC" \
  | grep -v "^$" | sort -u
```
Add any recently changed docs that appear in the gap list to a "high priority" set.

### Step 2 — Survey and propose (always runs first)

2.1 Present the gap list to the user:
```
Wiki coverage survey
  Current sections: <N> (list titles)
  Source docs with no wiki coverage:
    - <path> — <one-line purpose from index>
    [...]
  Recently changed docs in gap list (higher priority):
    - <path>
    [...]
  Proposed additions (arc placement):
    - "<Proposed section title>" — fits at stage <stage name>, after §<N>
    [...]
```

2.2 Ask: "Which of these should I add? (All / specific numbers / none — just reindex)"

2.3 If `--survey` or no argument: stop here after the user responds with their
choice. Do not proceed to writing unless the user explicitly approves additions.

### Step 3 — Add approved sections (--add-section or after survey approval)

For each approved addition, run this sub-flow:

**3.1 — Gather source material**

Read all source docs relevant to the new section. If multiple docs apply, read
all of them.

**3.2 — Draft the section**

Write the section as prose, not a mirror of the source doc. The wiki is a synthesis:
- Lead with the reader's goal, not the feature's mechanics.
- Explain the why before the how.
- Use concrete examples over abstract descriptions.
- Cross-reference source docs at the end, not throughout.
- Keep the section to what a reader at that stage actually needs to know;
  save exhaustive detail for the source doc.

Follow the existing wiki's voice: second person, present tense, confident and direct.

**3.3 — Determine insertion point**

Based on the arc stage table above, identify where the section fits. It must
be inserted in arc order, not appended. Renumber subsequent sections if needed.

**3.4 — Present draft to user for approval**

Show the drafted section and proposed insertion point. Ask: "Does this look right?
I'll insert it at §<N+1>, shifting §<N+1> → §<N+2> and so on."

Wait for approval before writing.

**3.5 — Write the section**

Edit the wiki file to insert the approved section at the correct position.
If sections were renumbered, update all affected headings and the Table of Contents.

### Step 4 — Reindex all dependent artifacts

Run after any wiki content change, or when `--reindex` is passed directly.

**4.1 — Wiki Table of Contents**

Read the current wiki TOC block (under `## Table of Contents`). Rebuild it to
match the actual `## N. Title` headings in the file. Use the existing link format.

**4.2 — Documentation index**

Read `$HORIZON_DOCS/index.md`. Update the purpose summary in the wiki's entry
to reflect the current section list (comma-separated, concise).

**4.3 — /userguides skill section map**

Read `$HORIZON_SYSTEM/skills_bin/userguides/SKILL.md`. Update the `## Wiki Section Map`
table to match the current wiki sections exactly. The table is informational — the
skill reads the actual file at runtime — but keeping it current helps authors.
Also update any hardcoded section counts (e.g., "11 sections", "1–11") to the
new count.

**4.4 — /horizon_aios_wiki_upkeep skill scope table**

Read `$HORIZON_SYSTEM/skills_sbin/horizon_aios_wiki_upkeep/SKILL.md`. Update the
`## Scope` source-document table to include any new sections, mapping each to the
relevant source docs. For new sections, infer the sources from what was read in
Step 3.1. For renumbered sections, update the section numbers in the table.

**4.5 — Report**

```
Reindex complete.
  Wiki: <N> sections
  TOC: updated
  docs/index.md: updated
  userguides skill: section map updated (<old> → <new> sections)
  horizon_aios_wiki_upkeep skill: scope table updated
```

### Step 5 — Commit guidance

5.1 After all changes, list the modified files and suggest a commit message:

```
Files changed:
  M  horizon_system/documentation/user_guides/using_your_aios.md
  M  horizon_system/documentation/index.md
  M  horizon_system/skills_bin/userguides/SKILL.md
  M  horizon_system/skills_sbin/horizon_aios_wiki_update/SKILL.md
  M  horizon_system/skills_sbin/horizon_aios_wiki_upkeep/SKILL.md

Suggested commit: docs(wiki): add §<N> <title>; reindex wiki artifacts
```

Do not commit. The user commits.

---

## Notes for the executing agent

- The wiki's authority hierarchy: the user story arc > source doc completeness. A
  source doc with no wiki coverage is a gap only if a user at some stage of the arc
  would benefit from it. Not every doc warrants a wiki section.
- Authoring quality matters. Read multiple existing wiki sections before drafting a
  new one — match the voice, level of abstraction, and the balance of explanation
  vs. example.
- Reindex is cheap and safe. Run it whenever in doubt about whether artifacts are
  synchronized. It reads the actual wiki state; it does not interpret hardcoded maps.
- Section numbering is a presentation artifact. If a section is inserted mid-document,
  renumber all subsequent sections in the headings, in the TOC, and in the dependent
  skill artifacts. The arc ordering matters; the specific numbers do not.
- This skill does not verify factual accuracy of existing sections — that is
  `/horizon_aios_wiki_upkeep`. This skill grows and organizes; upkeep keeps it
  accurate.
- If a section grows large enough to warrant splitting into two, treat the split as
  an addition: draft each subsection, determine arc placement, get user approval,
  then write and reindex.
- The note about Dev Stack placement in the description is real. If this skill is
  moved into a Dev Stack context in the future, update the skill's own description
  and the relevant index files. The logic does not change; only the access tier does.
