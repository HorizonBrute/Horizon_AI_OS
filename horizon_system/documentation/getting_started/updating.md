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
   python horizon_system/sbin/backup_user_data.py        # memory/handoffs/objectives -> your remote
   ```
2. Pull upstream — **fast-forward-only**:
   ```bash
   python horizon_system/sbin/sync_aios.py
   #   equivalently: git fetch upstream && git merge --ff-only upstream/<branch>
   ```
3. If it reports already up to date, you're done. Your user-space files
   (`aios_local.conf`, `.gitignore.user`, `memory/`, `handoffs/`, `objectives/`,
   `~/.horizon/`, `~/.claude/`, `brains/`, `*.local.*`) were never touched —
   upstream doesn't own them.

## If the update REFUSES (fast-forward not possible)

A refusal is a feature, not a failure: it means your local branch **diverged**
from upstream — almost always because a *framework* file (`horizon_system/**`,
the tracked `.gitignore`, a template) was edited locally. Don't force it. Instead:

1. See what diverged:
   ```bash
   git fetch upstream
   git log --oneline upstream/<branch>..HEAD     # your local-only commits
   git status
   ```
2. Move your customization into the **override layer** so it survives every future
   update — `aios_overrides.md` (project), `aios_local.conf` (machine),
   `.gitignore.user` (ignores), `settings.local.json` (permissions),
   `CLAUDE.local.md` (instructions) — then restore the framework file:
   ```bash
   git checkout -- <the framework file you edited>
   python horizon_system/sbin/sync_aios.py
   ```
3. Or, if the local change is intentional and you accept the maintenance cost,
   merge manually and resolve conflicts:
   ```bash
   git merge upstream/<branch>
   ```
   (`.gitignore` is set to `merge=union` in `.gitattributes`, so ignore-list
   edits combine instead of conflicting.)

## After updating

1. If templates or structure changed, re-run bootstrap (idempotent):
   ```bash
   ./horizon_system/sbin/bootstrap.ps1      # Windows (Administrator)
   sudo bash horizon_system/sbin/bootstrap.sh   # Linux/macOS
   ```
2. Verify health: `python horizon_system/sbin/doctor.py`.
3. **Restart Claude Code** and open a new shell so it reloads config.

## Rolling back a bad update

Updates never touch your gitignored data (`memory/`, `handoffs/`, `objectives/`),
so a rollback is safe:

```bash
git reflog                       # find the commit from just before the update
git reset --hard <that-commit>
```

## Automating it

`sync_aios.py` can run on a schedule (cron / Task Scheduler) via
`setup_sync_schedule.py`; configure cadence in `aios_local.conf`
(`SYNC_AIOS_FROM_REMOTE`, `AIOS_SYNC_FREQ`, `AIOS_REPO_REMOTE`, `AIOS_REPO_BRANCH`).
See `$HORIZON_DOCS/sync_setup.md`.
