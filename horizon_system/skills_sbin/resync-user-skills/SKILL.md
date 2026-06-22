---
name: resync-user-skills
description: Rebuild the junctions that register machine-local user skills (in $HORIZON_USRBIN/usr_skills) into skills_sbin so they load alongside OS skills. Use when the user types /resync-user-skills, adds or removes a user skill, or after an upstream sync may have wiped the links.
tools: Bash
---

# Skill: /resync-user-skills

User skills are machine-local and gitignored, living in `$HORIZON_USRBIN/usr_skills/<name>/SKILL.md`. They are surfaced to Claude Code by a per-skill junction at `$HORIZON_SYSTEM/skills_sbin/<name>` → the user skill, which appears flat through the existing `~/.claude/skills` junction.

Those junctions are not tracked by git, so an upstream sync that refreshes `skills_sbin` can drop them. This skill rebuilds them from whatever currently exists in `usr_skills` — the source of truth. It is idempotent and never touches real OS skills.

---

## When to invoke

`/resync-user-skills`, or after adding/removing a user skill, or after a sync.

---

## Step-by-step execution

1. Run the registration script:
   ```
   python "$HORIZON_SYSTEM/sbin/register_user_skills.py"
   ```
   (Add `--dry-run` first if the user wants a preview without making changes.)

2. Report its output to the user — which skills were linked (`[LINK]`), pruned (`[STALE]`), or skipped (`[SKIP]`), and the final count.

3. If any skill was newly linked, tell the user it should appear within the session; if it does not show under `/<name>`, a Claude Code restart picks up brand-new top-level entries.

---

## Notes for the executing agent

- The script is the single source of truth for the linking logic (Windows junction / Unix symlink, idempotency, stale-pruning, collision guard). Do not reimplement linking by hand — just run it.
- A user skill whose name collides with a real OS skill is skipped, not linked, to avoid shadowing. Surface that message so the user can rename.
- This does not create or edit user skills — only registers existing ones. To author a user skill, use `/skill-creation` (user tier).
