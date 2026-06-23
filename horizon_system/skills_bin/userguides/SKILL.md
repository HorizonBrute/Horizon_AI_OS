---
name: userguides
description: Browse the Horizon AIOS operational wiki. Bare /userguides spawns one Haiku agent per section to summarize all sections in parallel, then presents the summaries in order. /userguides <N> displays the full text of section N. Use when the user types /userguides, asks for a wiki overview, or wants to read a specific wiki section.
tools: Agent, Read, Bash
---

# Skill: /userguides

**Model preference:** `#lowcost` (summaries via Haiku agents; section display is a file read).

Browse the Horizon AIOS operational wiki at `$HORIZON_DOCS/user_guides/using_your_aios.md`.

---

## Arguments

`/userguides [N]`

- No argument — summarize all sections in parallel using one Haiku agent per section, then present summaries in order.
- `N` — integer section number; display the full text of that section from the wiki.

---

## Wiki Section Map (informational — kept current by /horizon_aios_wiki_update --reindex)

At the time this skill was last indexed, the wiki contained these sections. Always
read the actual file to get the live section list — do not treat this table as
authoritative at runtime.

| N | Title |
|---|---|
| 1 | The Security Model |
| 2 | Building and Configuring a Brain |
| 3 | Projects — Purpose and Practical Patterns |
| 4 | Session Continuity — Handoffs and Objectives |
| 5 | Case Study — The Developer Brain |
| 6 | Bring Your Own Harness and local.agents.md |
| 7 | Model Preferences and Agent Teams |
| 8 | Understanding and Managing Context |
| 9 | Gitignore, Local Config, and What Not to Commit |
| 10 | Enterprise Deployment |
| 11 | Containerization, Cloud, and Infrastructure as Code |
| 12 | Bring Your Own Infrastructure — Integrated Identity and Existing Security |

---

## Step-by-step execution

### Both branches — Step 0: discover live section count

Before branching, read `$HORIZON_DOCS/user_guides/using_your_aios.md` and scan for
all `## N.` headings (where N is an integer). Collect them as an ordered list:
`[(N, title), ...]`. This is the authoritative section list for this invocation.
The section map table above is informational only.

---

### Branch A — No argument (full summary run)

**Step A.1 — Extract each section's text**

Using the live section list from Step 0, extract each section's text. Each section
runs from its own `## N. Title` heading up to (but not including) the next `## N+1.`
heading, or the `## Reference Pointers` block, whichever comes first.

**Step A.2 — Spawn one Haiku agent per section, all in parallel**

Launch one agent per section in a single message (one tool-call block). Count and
agent count both come from the live section list — not from any hardcoded number.
For each agent:

- `model: haiku`
- `description`: `Summarize wiki section <N>`
- Prompt (fill in `<N>`, `<title>`, `<section_text>`):

```
Summarize the following section of the Horizon AIOS operational wiki in 3–5 concise
sentences. Focus on what a reader needs to understand, not on restating structure.
Return only the summary — no preamble, no heading.

---

## <N>. <title>

<section_text>
```

**Step A.3 — Collect results and present in order**

Wait for all agents. Present summaries in section order, each preceded by a bold
title line:

```
**<N>. <title>**
<summary text>

---
```

After all summaries: `Full wiki: $HORIZON_DOCS/user_guides/using_your_aios.md`

---

### Branch B — Section number argument

**Step B.1 — Validate the argument**

Parse the argument as an integer N. Check it against the live section list from
Step 0. If N is not in the list, respond:

`Section <N> does not exist. The wiki currently has <total> sections (1–<total>).
Run /userguides with no argument for a summary of all sections.`

Then stop.

**Step B.2 — Extract and display the section**

Extract the text from `## <N>.` through (but not including) the next `## <N+1>.`
heading or `## Reference Pointers`, whichever comes first. Display the full
extracted text verbatim, preserving all Markdown formatting.

Footer: `— Section <N> of <total> | Full wiki: $HORIZON_DOCS/user_guides/using_your_aios.md`

---

## Notes for the executing agent

- `$HORIZON_DOCS` resolves to `$HORIZON_SYSTEM/documentation`. If unset, substitute the absolute path.
- Always read the wiki file fresh. Never rely on an in-context copy or the section map table above.
- The live section count drives everything: agent spawn count in Branch A, validation range in Branch B, footer total in Branch B. All three must agree with what was actually read from the file.
- In Branch A, all agent calls must be in one message. Do not issue them sequentially.
- Section boundaries: `## N. Title` headings only. `## Table of Contents`, `## Reference Pointers`, and any other unnumbered `##` headings are not wiki sections.
- The section map table in this file is kept current by `/horizon_aios_wiki_update --reindex`. If it is stale, it does not affect runtime behavior — the file read is what matters.
