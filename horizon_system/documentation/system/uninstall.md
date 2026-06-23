# Uninstalling Horizon AIOS

How to cleanly remove the AIOS footprint from a machine, verify the removal, and
(optionally) prove the full install → uninstall cycle on a fresh machine. The
uninstall reverses everything `bootstrap` wrote **without deleting the repo or
your data** — it is idempotent and safe to re-run.

Authoritative procedure. `system/aios_switching.md` §Uninstalling and
`utilities.md` (uninstall.ps1 / uninstall.sh) point here.

---

## Before you start — back up your data

Uninstall **does not** delete the repo, and it leaves your memory, handoffs, and
objectives intact. But the natural last step of decommissioning a machine is
deleting the clone — and that **does** destroy them. Back up first if you are
removing the repo afterward:

- `$HORIZON_ROOT/memory/` — harness transcripts + agent memory (see
  `system/memory.md`; the `~/.claude/projects` junction points here).
- `$HORIZON_ROOT/handoffs/` and `$HORIZON_ROOT/objectives/`.

Push them to your own remote, or copy them off the machine. None of this is
recoverable from the AIOS repo once the clone is gone.

---

## Running the uninstall

Must be run elevated (Administrator / root) — ACL removal requires it. The
`aios uninstall` shortcut delegates to the platform script:

```
aios uninstall --dry-run   # preview every action; change nothing (NO elevation needed)
aios uninstall             # interactive — confirms each destructive step
aios uninstall --yes       # non-interactive; accept all removals
```

Or invoke the script directly:

```powershell
# Windows (Administrator PowerShell)
.\horizon_system\sbin\uninstall.ps1 --dry-run
.\horizon_system\sbin\uninstall.ps1 --yes
```
```bash
# Linux / macOS
sudo bash horizon_system/sbin/uninstall.sh --dry-run
sudo bash horizon_system/sbin/uninstall.sh --yes
```

**Always `--dry-run` first.** It needs no elevation and prints the exact plan
(`[DRY] would …`) for the current machine. Unknown arguments are rejected (exit
code 2) rather than silently ignored.

---

## What it removes

The scripts mirror `bootstrap` section by section:

| Section | Removed |
|---|---|
| 2  | `~/.claude/CLAUDE.md` redirect lines (your own content is preserved; file deleted only if it becomes empty) |
| 3  | `~/.claude/skills/` junction + user-skill symlinks in `skills_sbin/` (link-only — never the targets) |
| 4  | `$HORIZON_ROOT/handoffs/` and `objectives/` — **only if empty** |
| 5  | `~/.horizon/` tree (registry, `active_env.*`, `aios-exec` wrappers); removes `~/.claude/settings.json` **only when a provenance stamp proves bootstrap wrote it and it is unmodified** — else preserved with a `[MANUAL]` advisory. Also removes the stamp `~/.claude/.horizon-settings.stamp` |
| 5b | `~/.claude/projects` junction (memory redirect) — **link only; memory data in `$HORIZON_ROOT/memory` is left intact** |
| 6  | `.git/hooks/commit-msg`, `pre-commit`; git `core.hooksPath` |
| 7  | `$HORIZON_BIN` entry from system PATH (Machine-scope on Windows; `/etc/profile.d/horizon_aios.sh` + macOS `/etc/paths.d/horizon-aios`) |
| 8  | Shell profile `active_env` source line + the two global `git include.path` entries `aios setup` writes (framework gitconfig and machine-local identity gitconfig) — stripped automatically from PowerShell `$PROFILE` and global gitconfig |
| 9  | `$HORIZON_ETC/aios_local.conf`; `$HORIZON_SYSTEM/logs/` — **only if empty** |
| 10 | `brains`-group ACEs across `$HORIZON_SYSTEM` subtrees — `icacls /remove` (not `/remove:g`) so both grant **and** harden's DENY ACEs are stripped |

## What it does NOT remove (manual — printed as `[MANUAL]` advisories)

- The optional upstream-sync schedule / cron entries (`horizon_aios_setup_sync_schedule.py`).
- The `brains` OS group (it may still have brain members).
- Brain OS user accounts and their data — use `horizon_aios_remove_brain.py` (`/remove-brain`).
- A `~/.claude/projects.backup-*` left by `horizon_aios_redirect_memory.py` (restore by
  renaming it back once the junction is gone).
- The repo itself and Python packages (`watchdog`, `keyring`).

---

## Verification (after a real run)

`--dry-run` proves the script parses and enumerates correctly under elevation,
but it cannot exercise the mutations. After a real `--yes` run, confirm by hand —
this is where uninstall bugs hide:

1. **Registry/env gone:** `python horizon_system/sbin/horizon_aios_doctor.py` now reports
   **failures** — here, failures = success (the registry, junction, and env it
   checks for are intentionally removed).
2. **`~/.horizon/` is gone.**
3. **Skills junction removed, target intact:** `~/.claude/skills` no longer
   exists, but `horizon_system/skills_sbin/` still has its contents (a bad
   junction-delete can recurse into the target — verify it did not).
4. **Memory junction removed, data intact:** `~/.claude/projects` is gone, but
   `$HORIZON_ROOT/memory/` still holds your data.
5. **System PATH cleaned:** no `…\horizon_system\bin` entry remains
   (`[System.Environment]::GetEnvironmentVariable("Path","Machine")` on Windows).
6. **Git hooks + ACEs:** `.git/hooks/commit-msg` is gone;
   `icacls horizon_system\sbin` shows no residual `brains`-group ACEs — neither
   grant nor DENY (Windows). `/remove` strips both; a leftover DENY would mean
   the old `/remove:g` was still in effect.
7. **settings.json preserved when customized:** removal is governed by a
   provenance stamp `~/.claude/.horizon-settings.stamp` (SHA-256 of the
   settings.json bootstrap wrote). If the current file still matches the stamp it
   is removed (and the stamp with it); if it was modified, or pre-existed bootstrap
   (no stamp → a content-equality fallback decides), it is preserved with a
   `[MANUAL]` advisory. After a real run, neither the stamp nor a bootstrap-owned
   settings.json should remain.
8. **Shell profile + git includes cleaned (Section 8):** the `active_env` source
   line is absent from PowerShell `$PROFILE`; `git config --global --get-all include.path`
   shows no entries referencing `harness_configs/git/gitconfig` or
   `git_identity.local.gitconfig`.

A second `aios uninstall --yes` should report everything as already-removed
(`[SKIP]`) and make no changes — confirming idempotency. In particular the
re-run must leave **no residual `brains`-group DENY ACEs** behind.

---

## Full install → uninstall validation cycle (fresh machine)

Use a clean machine (not a dog-fooded dev box) to validate the real cycle. All
steps Administrator / root unless noted.

```
# 0. Prereqs: Git, Python, Claude Code installed
# 1. Clone
git clone <your-remote> C:\devroot

# 2. Bootstrap (elevated)
C:\devroot\horizon_system\sbin\bootstrap.ps1

# 3. Verify install is healthy
python C:\devroot\horizon_system\sbin\horizon_aios_doctor.py        # expect: all checks pass

# 4. (optional) Open a NEW shell; confirm `aios current`, env vars,
#    ~/.claude/CLAUDE.md redirect, and the skills junction are present.

# 5. Preview the uninstall plan
python C:\devroot\horizon_system\sbin\horizon_aios_switch.py uninstall --dry-run

# 6. Real uninstall (elevated)
python C:\devroot\horizon_system\sbin\horizon_aios_switch.py uninstall --yes

# 7. Verify clean — run the Verification checklist above
python C:\devroot\horizon_system\sbin\horizon_aios_doctor.py        # expect: FAILURES = success

# 8. (optional) Re-bootstrap to prove idempotent re-install
C:\devroot\horizon_system\sbin\bootstrap.ps1
python C:\devroot\horizon_system\sbin\horizon_aios_doctor.py        # expect: clean again
```

On Linux / macOS substitute `bootstrap.sh` and `sudo bash … uninstall.sh`.

---

## Re-installing later

Uninstall removes only machine-local configuration; the repo is untouched. To
return: run `bootstrap` again from the same (or a fresh) clone, then
`horizon_aios_doctor.py`. Bootstrap is idempotent and prompts before overwriting anything it
finds.

## See also

- `system/aios_switching.md` — the `aios` switcher and the pointers uninstall reverses.
- `system/memory.md` — what the memory redirect is and why backing it up matters.
- `utilities.md` — `uninstall.ps1` / `uninstall.sh` and `horizon_aios_switch.py` reference.
- `getting_started/ReadMeToSetupYourSystem.md` — the install side of the cycle.
- `getting_started/lifecycle_test.md` — the broader operator lifecycle runbook (adds the AIOS-switch test + optional provisioning around this uninstall).
