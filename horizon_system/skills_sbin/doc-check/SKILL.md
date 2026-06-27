---
name: doc-check
description: Run the Horizon AIOS documentation integrity verifier — catches canon pointers to non-existent files, index tables missing on-disk skills, and stale cross-references after renames. Use when asked to check doc integrity, verify the docs are clean, run /doc-check, or after any rename or documentation change.
tools: Bash, Read, Edit
---

# Skill: /doc-check

**Model preference:** `#lowcost` (pure file reads and grep; no reasoning required).

Run `horizon_aios_doc_integrity.py` against the active AIOS install and interpret its findings. Three verifiers run by default: canon (agents.md paths), indexes (skills and docs index tables), and cross-references ($HORIZON_* paths in .md files).

---

## When to invoke

- The user types `/doc-check`
- After any rename, move, or deletion of a doc or skill
- After a documentation session that created new files
- Before pushing AIOS changes (invoked by the pre-flight gauntlet)
- When a future session hits a dead path and you want to find all broken references at once

---

## Step-by-step execution

### Step 1 — Confirm the working AIOS

1.1 The script reads `$HORIZON_ROOT`, `$HORIZON_SYSTEM`, `$HORIZON_DOCS`, `$HORIZON_ETC`, and `$HORIZON_BIN` from the environment. Confirm these are set:

```bash
echo "ROOT=$HORIZON_ROOT | SYSTEM=$HORIZON_SYSTEM | DOCS=$HORIZON_DOCS"
```

If any are empty, stop and ask the user to run the onboarding script (`horizon_aios_dev_onboard.ps1` or `source horizon_aios_dev_onboard.sh`) before continuing.

### Step 2 — Run the verifier

2.1 Default (all three verifiers):

```bash
python "$HORIZON_SYSTEM/sbin/horizon_aios_doc_integrity.py"
```

2.2 Single verifier (if the user wants to scope the run):

```bash
python "$HORIZON_SYSTEM/sbin/horizon_aios_doc_integrity.py" --canon
python "$HORIZON_SYSTEM/sbin/horizon_aios_doc_integrity.py" --indexes
python "$HORIZON_SYSTEM/sbin/horizon_aios_doc_integrity.py" --refs
```

2.3 Handoff mode (verify paths a session said it created):

```bash
python "$HORIZON_SYSTEM/sbin/horizon_aios_doc_integrity.py" --handoff "<path>"
```

### Step 3 — Interpret and act

Output format:
```
FAIL  canon       agents.md:3       $HORIZON_DOCS/security_architecture_invariants.md — file not found
WARN  index       skills_sbin       doctor — on disk but missing from index
FAIL  cross-ref   utilities.md:47   $HORIZON_ETC/aios_logging_dirs.md — file not found
```

**If exit 0 and "OK — no issues found":** report clean. Done.

**If WARNs only (exit 0):** Report each WARN. A WARN means an on-disk skill is missing from its index — not broken, but the index is stale. Offer to add the missing index entry (ask before writing; see Step 4).

**If FAILs (exit 1):** Categorize by type:

| Category | What it means | What to do |
|---|---|---|
| `canon` | agents.md declares a file that doesn't exist | Open the file that contains the reference and ask the user whether to fix the pointer or create the missing file |
| `index` (indexed but missing) | Index lists a skill/doc that doesn't exist on disk | Open the index file and remove or correct the stale entry |
| `cross-ref` | A .md file references a $HORIZON_* path that doesn't resolve | Open the referencing file at the reported line; update or remove the stale reference |
| `handoff` | A handoff's Files Changed table names a path that doesn't exist | Report — the session may not have committed its work |

For unambiguous fixes (e.g. a stale index entry pointing to a path that clearly was renamed based on context), proceed with the fix after confirming with the user. For ambiguous cases (path might be missing vs. misspelled vs. never created), show the user the finding and ask.

### Step 4 — Fix unambiguous index gaps (WARN only)

An on-disk skill that isn't in the index is a WARN. If the user asks to fix it (or passes `--fix`):

4.1 Identify the skill's model group from its `SKILL.md` body callout (`**Model preference:** \`#GROUP\``).
4.2 Identify its one-line purpose from the `description:` frontmatter field.
4.3 Add a row to the relevant `index.md`:
    ```
    | <skill-name> | `/<skill-name>` | `#<group>` | <purpose> |
    ```
4.4 Report the addition.

`--fix` flag (non-interactive): apply all unambiguous index gaps without prompting. Still report what was changed.

### Step 5 — Report

5.1 After acting on findings, re-run the verifier to confirm the working copy is clean.
5.2 Report: "doc-check clean" or list any remaining findings with a short summary.

---

## Notes for the executing agent

- Never reimplement the verifier's logic — the script is the authority. The skill's job is to invoke it and interpret the output.
- Cross-ref findings in fenced code blocks or examples may be intentional stale references (documentation of a moved file). Use context to distinguish genuine breakage from intentional historical references before touching them.
- The `--refs` verifier walks all .md files under `$HORIZON_SYSTEM` — it may take a few seconds on large installs. It skips `memory/`, `handoffs/`, `objectives/`, and `brains/` (user data, not system docs).
- If a canon FAIL targets a file the user just created but hasn't committed, it may not exist yet because it's in the dev working copy but not the active AIOS root. Confirm the env vars point to the right install.
