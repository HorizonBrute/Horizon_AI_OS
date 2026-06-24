---
name: skill-creation
description: Create a new AIOS skill with correct structure and registration. Use when the user asks to create, add, or scaffold a new skill (user-callable or admin-only).
tools: Read, Write, Edit, Glob, Grep
---

# Skill: /skill-creation

**Model preference:** `#midcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Create a new AIOS skill with the required directory structure, frontmatter, and index registration. Enforce this skill before writing any new skill file in this project.

---

## Directory structure

Skills live in one of three locations depending on access tier:

| Directory | Access | How it reaches Claude Code |
|---|---|---|
| `$HORIZON_SYSTEM/skills_sbin/<name>/` | Owner only (privileged) | `~/.claude/skills/` is a symlink → `skills_sbin/` — live immediately |
| `$HORIZON_SYSTEM/skills_bin/<name>/` | All brains (group-readable) | Brain users' `~/.claude/skills/` is a symlink → `skills_bin/` — live immediately |
| `$HORIZON_USRBIN/usr_skills/<name>/` | Owner only; **machine-local, gitignored, never synced** | `horizon_aios_register_user_skills.py` symlinks it into `skills_sbin/` — surfaces flat alongside OS skills |

**OS skills vs user skills:** `skills_bin`/`skills_sbin` are OS-level — tracked, shared, and overwritable by an upstream sync. `usr_skills` is for personal skills you do not want in the OS repo or at risk from sync. They register cohesively (same flat namespace) but live separately.

Each skill is a **directory** containing exactly one required file: `SKILL.md`.

```
skills_bin/
  <skill-name>/
    SKILL.md        ← required
    (any supporting files, e.g. templates/, examples/)
```

---

## SKILL.md frontmatter

Every `SKILL.md` must begin with YAML frontmatter. Required fields:

```yaml
---
name: <skill-name>           # matches directory name; used as /slash-command
description: <one sentence>  # when to invoke this skill; used by agent routing
tools: <comma-separated>     # tools this skill uses (e.g. Read, Write, Bash, Grep)
---
```

Optional fields: `model`, `isolation`.

---

## Step-by-step: creating a new skill

### Step 1 — Choose the tier

1.1 Is this a personal/machine-local skill that should NOT enter the OS repo (and should survive upstream syncs)?
- Yes → `usr_skills` (user tier). Skip to the user-tier flow at the end of Step 2.
- No → continue to 1.2.

1.2 Is the skill safe for all brain users (group members) to invoke?
- Yes → `skills_bin`
- No (admin/owner-only, touches privileged paths or user accounts) → `skills_sbin`

### Step 2 — Create the skill directory and file

2.1 Create the directory:
```
$HORIZON_SYSTEM/skills_bin/<skill-name>/
```
or
```
$HORIZON_SYSTEM/skills_sbin/<skill-name>/
```

2.2 Create `SKILL.md` inside it. Start with the frontmatter block. Then write:
- **When to invoke** — the trigger phrases and contexts
- **Step-by-step execution** — numbered steps the executing agent follows
- **Notes for the executing agent** — caveats, pitfalls, invariants to check

2.3 Name the skill with a lowercase hyphenated slug that matches the intended `/slash-command` name.

2.4 Add the **model-preference callout** as the first body line, immediately after the `# Skill:` heading (blank line before and after):

```
**Model preference:** `#GROUP` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).
```

Choose the group from the skill's dominant work: security/privileged/destructive → `#highcap`; research/fetch/analysis → `#investigate`; authoring/summarizing → `#midcost`; mechanical/read-only/reporting → `#lowcost`; trivial/latency-bound → `#fast`; debugging/coding → `#debug`. **If you cannot determine it confidently, default to `#midcost`** and note it for later review with `/model-prefs-assign`. The callout MUST be in the body — frontmatter is stripped before the model sees the skill, so a frontmatter field would never be read.

**User-tier flow (`usr_skills`):** if you chose the user tier in Step 1.1:
- Create `$HORIZON_USRBIN/usr_skills/<skill-name>/SKILL.md` (same frontmatter and body rules).
- Register it: run `python "$HORIZON_SYSTEM/sbin/horizon_aios_register_user_skills.py"` (or invoke `/resync-user-skills`). This symlinks it into `skills_sbin/` so it loads flat.
- Do **not** touch any index or commit anything — user skills are machine-local and gitignored. Skip Steps 3 and the commit; go to Step 4.

### Step 3 — Update the index (OS skills only)

3.1 Open the index for the chosen tier:
- `$HORIZON_SYSTEM/skills_bin/index.md`
- `$HORIZON_SYSTEM/skills_sbin/index.md`

3.2 Add a row to the table:

```markdown
| <skill-name> | `/<skill-name>` | `#<group>` | <one-line purpose> |
```

The "Model group" column value must match the callout you chose in Step 2.4.

3.3 **If the tier is `skills_sbin`**, also add the new skill to the whitelist in `$HORIZON_SYSTEM/skills_sbin/.gitignore` (two lines: `!<skill-name>/` and `!<skill-name>/**`). That file ignores everything by default so user-skill symlinks stay out of git; a new OS skill must be explicitly re-included or it will be untracked.

3.4 The index update, the `.gitignore` whitelist update (sbin), and the SKILL.md creation must be in the **same commit**.

### Step 4 — Deploy (automatic via symlink)

No manual copy needed. `~/.claude/skills/` is a symlink to `skills_sbin/` (primary user) or `skills_bin/` (brain users). Skills are live immediately on disk.

4.1 Restart Claude Code after creating a new skill — skills are loaded at session start.

### Step 5 — Verify

5.1 Check that `$HORIZON_SYSTEM/skills_sbin/<skill-name>/SKILL.md` (or `skills_bin/`) exists.
5.2 Start a new Claude Code session and verify the skill appears (type `/<skill-name>`).

---

## Checklist

- [ ] Directory created at correct tier (`skills_bin`, `skills_sbin`, or `usr_skills`)
- [ ] `SKILL.md` has valid YAML frontmatter with `name`, `description`, `tools`
- [ ] `name` in frontmatter matches directory name
- [ ] `description` is specific enough for agent routing (not just "does X")
- [ ] Body has the **Model preference** callout (group chosen by Step 2.4, or `#midcost` default); index "Model group" column matches
- [ ] **OS skill:** `index.md` updated in the same commit; if `skills_sbin`, `.gitignore` whitelist updated too
- [ ] **User skill:** registered via `horizon_aios_register_user_skills.py` / `/resync-user-skills`; nothing committed
- [ ] Claude Code restarted to load the new skill (symlink is live; restart is sufficient)

---

## Notes for the executing agent

- Never create a flat `<skill-name>.md` file directly in `skills_bin/` or `skills_sbin/`. The directory-per-skill structure is required — bootstrap and horizon_aios_doctor.py both check for it.
- User-skill symlinks appear inside `skills_sbin/` but must never be committed; the `skills_sbin/.gitignore` whitelist keeps them out of git. If a new OS skill is missing from that whitelist it will be silently untracked — always update it when adding an sbin skill.
- The `name` frontmatter field is what Claude Code uses to register the `/slash-command`. It must exactly match the directory name.
- If the user already has the skill deployed at `~/.claude/skills/` from a previous run, bootstrap will prompt before overwriting (or auto-overwrite with `--yes`).
