---
name: skill-creation
description: Create a new AIOS skill with correct structure and registration. Use when the user asks to create, add, or scaffold a new skill (user-callable or admin-only).
tools: Read, Write, Edit, Glob, Grep
---

# Skill: /skill-creation

Create a new AIOS skill with the required directory structure, frontmatter, and index registration. Enforce this skill before writing any new skill file in this project.

---

## Directory structure

Skills live in one of two locations depending on access tier:

| Directory | Env var | Access | Deploy target |
|---|---|---|---|
| `$HORIZON_SYSTEM/skills_bin/<name>/` | `$HORIZON_SYSTEM/skills_bin` | All brains (group-readable) | `~/.claude/skills/<name>/` |
| `$HORIZON_SYSTEM/skills_sbin/<name>/` | `$HORIZON_SYSTEM/skills_sbin` | Owner only (privileged) | Deploy manually; not auto-deployed by bootstrap |

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

1.1 Is this skill safe for all brain users (group members) to invoke?
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

### Step 3 — Update the index

3.1 Open the index for the chosen tier:
- `$HORIZON_SYSTEM/skills_bin/index.md`
- `$HORIZON_SYSTEM/skills_sbin/index.md`

3.2 Add a row to the table:

```markdown
| <skill-name> | `/<skill-name>` | <one-line purpose> |
```

3.3 The index update and the SKILL.md creation must be in the **same commit**.

### Step 4 — Deploy (skills_bin only)

4.1 Copy the skill directory to `~/.claude/skills/`:
```bash
cp -r "$HORIZON_SYSTEM/skills_bin/<skill-name>" ~/.claude/skills/
```
Or re-run bootstrap to deploy all skills:
```bash
bash "$HORIZON_SYSTEM/sbin/bootstrap.sh"     # Linux/macOS
& "$env:HORIZON_SYSTEM\sbin\bootstrap.ps1"   # Windows
```

4.2 Restart Claude Code after deploying a new skill (skills are loaded at session start).

### Step 5 — Verify

5.1 Check that `~/.claude/skills/<skill-name>/SKILL.md` exists.
5.2 Start a new Claude Code session and verify the skill appears (type `/<skill-name>`).

---

## Checklist

- [ ] Directory created at correct tier (`skills_bin` or `skills_sbin`)
- [ ] `SKILL.md` has valid YAML frontmatter with `name`, `description`, `tools`
- [ ] `name` in frontmatter matches directory name
- [ ] `description` is specific enough for agent routing (not just "does X")
- [ ] `index.md` updated in the same commit
- [ ] Skill deployed to `~/.claude/skills/` (skills_bin only)
- [ ] Claude Code restarted to load the new skill

---

## Notes for the executing agent

- Never create a flat `<skill-name>.md` file directly in `skills_bin/` or `skills_sbin/`. The directory-per-skill structure is required — bootstrap and doctor.py both check for it.
- The `name` frontmatter field is what Claude Code uses to register the `/slash-command`. It must exactly match the directory name.
- If the user already has the skill deployed at `~/.claude/skills/` from a previous run, bootstrap will prompt before overwriting (or auto-overwrite with `--yes`).
