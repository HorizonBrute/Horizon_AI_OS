# How to Update Horizon AIOS

The step-by-step procedure for pulling upstream Horizon AIOS changes into your
install without losing your customizations or data. For *why* this works (the
framework vs. user-space model), see
`$HORIZON_DOCS/system/distribution_and_updates.md`.

## One-time setup: remotes

You track Horizon AIOS as `upstream` and keep your own work + backups on `origin`:

```bash
git remote add upstream git@github.com:HorizonBrute/Horizon_AI_OS.git
git remote set-url origin <your-own-private-repo>      # your fork / backup repo
```

## Updating (the normal path)

1. *(Recommended)* Back up your data first:
   ```bash
   python horizon_system/sbin/horizon_aios_backup_user_data.py        # memory/handoffs/objectives -> your remote
   ```
2. Pull upstream -- **two-lane sync**:
   ```bash
   python horizon_system/sbin/horizon_aios_sync.py
   ```
   The **official lane** overwrites every framework path (everything except
   `projects/`, `usrbin/`, `brains/`) with the upstream version and commits it.
   The **personal lane** leaves `projects/`, `usrbin/`, and `brains/` alone unless
   you opt in. See `$HORIZON_DOCS/sync_setup.md` for lane mechanics and config
   keys.
3. If it reports already up to date, you're done. Your user-space files
   (`aios_local.conf`, `.gitignore.user`, `memory/`, `handoffs/`, `objectives/`,
   `~/.horizon/`, `~/.claude/`, `brains/`, `*.local.*`) were never touched --
   upstream doesn't own them.

## If a local framework change disappeared after updating

This is expected, not a bug. The official lane is authoritative and **overwrites**
framework paths (`horizon_system/**`, the tracked `.gitignore`, templates, and
other non-personal paths) with the upstream version -- it does not stop to ask.
If a change you made to a framework file vanished after a sync, it was reclaimed
by design. To keep the customization across every future update, move it into the
**override layer**:

1. Recover your change from git history if needed:
   ```bash
   git log -p -- <the framework file you edited>   # find your prior version
   ```
2. Re-express it in the **override layer** so the official lane never touches it
   again -- `aios_overrides.md` (project), `aios_local.conf` (machine),
   `.gitignore.user` (ignores), `settings.local.json` (permissions),
   `CLAUDE.local.md` (instructions).
3. If the change genuinely belongs in the framework, contribute it upstream
   rather than carrying it locally; the official lane will otherwise reclaim it on
   every run.

For personal paths (`projects/`, `usrbin/`, `brains/`), the personal lane keeps
local by default. If you opted in with `SYNC_PERSONAL_FROM_REMOTE=yes` and your
personal branch **diverged** from its remote, the lane keeps local and skips
rather than rewriting; `--force-personal` is the deliberate override that
overwrites personal paths (and discards local personal changes).

## After updating

1. If templates or structure changed, re-run bootstrap (idempotent):
   ```bash
   ./horizon_system/sbin/bootstrap.ps1      # Windows (Administrator)
   sudo bash horizon_system/sbin/bootstrap.sh   # Linux/macOS
   ```
2. Verify health: `python horizon_system/sbin/horizon_aios_doctor.py`.
3. **Restart Claude Code** and open a new shell so it reloads config.

## Rolling back a bad update

Updates never touch your gitignored data (`memory/`, `handoffs/`, `objectives/`),
so a rollback is safe:

```bash
git reflog                       # find the commit from just before the update
git reset --hard <that-commit>
```

## Automating it

`horizon_aios_sync.py` can run on a schedule (cron / Task Scheduler) via
`horizon_aios_setup_sync_schedule.py`; configure cadence and lanes in
`aios_local.conf` (`SYNC_AIOS_FROM_REMOTE`, `AIOS_SYNC_FREQ`, `AIOS_SYNC_TIME`,
`AIOS_OFFICIAL_REMOTE`, `AIOS_OFFICIAL_BRANCH`, and the optional personal-lane
keys `AIOS_PERSONAL_REMOTE` / `AIOS_PERSONAL_BRANCH` / `SYNC_PERSONAL_FROM_REMOTE`).
See `$HORIZON_DOCS/sync_setup.md`.
