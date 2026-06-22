---
name: resync-user-skills
description: Rebuild the owner's aggregated skill view — per-skill junctions linking skills_bin (brain tier) and usr_skills (machine-local) into skills_sbin so they load alongside the owner's OS skills. Use when the user types /resync-user-skills, adds or removes a skill, or after an upstream sync may have wiped the links.
tools: Bash
---

# Skill: /resync-user-skills

The owner's `~/.claude/skills` points at `skills_sbin`, so brain-tier skills (`$HORIZON_SYSTEM/skills_bin/`) and machine-local skills (`$HORIZON_USRBIN/usr_skills/`) are surfaced to the owner by a per-skill junction `skills_sbin/<name>` → source, which appears flat through the existing `~/.claude/skills` junction. Brains are unaffected (their view points at `skills_bin` only).

Those junctions are not tracked by git, so an upstream sync that refreshes `skills_sbin` can drop them. This skill rebuilds them from whatever currently exists in the sources — the source of truth. It is idempotent and never shadows a real OS skill.

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
- A source skill whose name collides with a real OS skill is skipped, not linked, to avoid shadowing. Surface that message so the user can rename.
- This does not create or edit skills — only links existing ones into the owner view. To author a skill, use `/skill-creation`.
