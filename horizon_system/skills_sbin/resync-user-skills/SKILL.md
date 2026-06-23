---
name: resync-user-skills
description: Report the skill inventory and whether the owner's aggregated view (skills_bin + usr_skills linked into skills_sbin) is in sync with the filesystem and this session, then heal any drift by rebuilding the links. Use when the user types /resync-user-skills, asks what skills they have or whether skills are in sync, adds/removes a skill, or after an upstream sync may have wiped the links.
tools: Bash
---

# Skill: /resync-user-skills

**Model preference:** `#lowcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

The owner's `~/.claude/skills` points at `skills_sbin`, so brain-tier skills (`$HORIZON_SYSTEM/skills_bin/`) and machine-local skills (`$HORIZON_USRBIN/usr_skills/`) are surfaced to the owner by a per-skill junction `skills_sbin/<name>` → source, which appears flat through the existing `~/.claude/skills` junction. Brains are unaffected (their view points at `skills_bin` only).

Those junctions are not tracked by git, so an upstream sync that refreshes `skills_sbin` can drop them. This skill rebuilds them from whatever currently exists in the sources — the source of truth. It is idempotent and never shadows a real OS skill.

---

## When to invoke

`/resync-user-skills`, or when the user asks what skills they have / whether skills are in sync, or after adding/removing a skill, or after a sync.

---

## Step-by-step execution

This skill answers three things: what skills exist on disk, whether the owner view matches them, and whether *this session* has them loaded — then heals any drift.

1. **Check filesystem sync (read-only):**
   ```
   python "$HORIZON_SYSTEM/sbin/horizon_aios_register_user_skills.py" --check
   ```
   This reports each source skill (`skills_bin` + `usr_skills`) as `[OK]` (linked), `[DRIFT]` (missing/incorrect/stale link), or `[SHADOW]` (blocked by a real OS skill). Exit 0 = in sync; exit 1 = drift.

2. **Heal if drift:** if step 1 reported drift (exit 1), run the script without `--check` to rebuild the links, then report what changed (`[LINK]`/`[STALE]`):
   ```
   python "$HORIZON_SYSTEM/sbin/horizon_aios_register_user_skills.py"
   ```
   If in sync, skip this — no changes needed.

3. **Compare disk vs this session.** The `--check` output is the on-disk truth; compare it to the skills actually available in your current session:
   - On disk but **not** available this session → newly added; tell the user to restart Claude Code to load it (the watcher picks up edits to existing skills live, but a brand-new top-level skill dir needs a restart).
   - Available this session but **not** on disk → stale session (skill was removed); a restart clears it.
   - Otherwise report that the session matches disk.

4. Summarize: the skill inventory by tier, the sync result (in sync / healed N), and any restart needed.

---

## Notes for the executing agent

- The script is the single source of truth for the linking logic (Windows junction / Unix symlink, idempotency, stale-pruning, collision guard). Do not reimplement linking by hand — just run it.
- A source skill whose name collides with a real OS skill is skipped, not linked, to avoid shadowing. Surface that message so the user can rename.
- This does not create or edit skills — only links existing ones into the owner view. To author a skill, use `/skill-creation`.
