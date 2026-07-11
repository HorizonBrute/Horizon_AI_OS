# Distribution, Updates, and Backing Up Your Data

How to run Horizon AIOS as a downstream install: get upstream updates without
losing your customizations, and back up your own data to your own git — without
ever editing framework files.

## The one principle: framework vs. user-space

Horizon AIOS separates what **upstream owns** from what **you own**. As long as
you customize only through the user-space layer (never by editing framework
files), updates can never clobber your work — because upstream never writes your
files.

| | Owned by | On update |
|---|---|---|
| `horizon_system/**`, the tracked `.gitignore`, `templates/` | **Upstream** | replaced / merged in |
| `aios_overrides.md` (project), `aios_local.conf` (machine) | **You** | never touched |
| `.gitignore.user` → `.git/info/exclude` (via pre-commit hook) | **You** | never touched |
| `settings.local.json`, `CLAUDE.local.md` | **You** | never touched |
| `~/.horizon/`, `~/.claude/`, `memory/`, `handoffs/`, `objectives/`, `brains/` | **You / machine** | never touched (gitignored) |

**Rule:** customize via the override layers above; do **not** edit framework files.

## Getting updates

Use the fork-with-upstream model:

```bash
# once, after cloning:
git remote add upstream git@github.com:HorizonBrute/Horizon_AI_OS.git
git remote set-url origin <your-own-private-repo>     # your work + backups

# to update:
python horizon_system/sbin/horizon_aios_sync.py       # two-lane sync
#   or: git fetch upstream && git merge upstream/<branch>
```

`horizon_aios_sync.py` runs a **two-lane sync** built directly on the
framework-vs-user-space split above:

- **Official lane (framework).** Scope is every path EXCEPT `projects/`,
  `usrbin/`, and `brains/`. Upstream is authoritative here: the lane OVERWRITES
  your local copy of those framework paths with the upstream version (a scoped
  hard-restore -- `git fetch`, then `git checkout upstream/<branch> -- <framework
  paths>` -- committed automatically). Local edits to framework files are
  **discarded by design**. That is why you customize only through the override
  layer: an edit parked in a framework file is exactly what the official lane
  reclaims on the next run.
- **Personal lane (user-space).** Scope is exactly `projects/`, `usrbin/`, and
  `brains/`. **Local always wins** -- the lane never overwrites these unless you
  opt in to a fast-forward-only advance (`SYNC_PERSONAL_FROM_REMOTE=yes`, against
  your own personal remote) or force it with `--force-personal`.

`SYNC_AIOS_FROM_REMOTE=no` disables both lanes. For the full key list, lane
mechanics, and the automated-commit DCO exception, see
`$HORIZON_DOCS/sync_setup.md`.

## Protecting your configuration

- **General config:** covered by the table above. Never edit framework files;
  use `aios_overrides.md`, `aios_local.conf`, `.gitignore.user`,
  `settings.local.json`, `CLAUDE.local.md`. Updates then merge cleanly by
  construction.
- **`.gitignore` specifically:** it is upstream-owned. To *add* ignores, put them
  in **`.gitignore.user`** (synced to `.git/info/exclude` by the pre-commit
  hook) — never the tracked `.gitignore`. As a safety net, `.gitattributes` marks
  `.gitignore`/`.gitignore.user` `merge=union`, so if an edit does happen,
  upstream and local lines combine instead of conflicting.

## Backing up your data to your own remote

You may want `memory/` (conversation transcripts + agent memory), `handoffs/`,
and `objectives/` version-controlled on **your own** git for backup and
cross-machine awareness. These are gitignored by the framework, so do **not**
un-ignore them in `.gitignore` (that collides with every upstream update). Use:

```bash
# configure your OWN remote in aios_local.conf:
#   AIOS_BACKUP_REMOTE=<your remote>     (never the public upstream)
python horizon_system/sbin/horizon_aios_backup_user_data.py
#   or: horizon_aios_backup_user_data.py --remote <your-remote> --paths memory handoffs objectives
```

What it does:
- **Force-adds** the data paths into a temporary git index and commits a snapshot
  of **only** those paths — the working tree, the staging area, and the framework
  branch are never touched (safe to run from an active session).
- Pushes to a **per-machine branch** (`aios-backup/<hostname>` by default) on
  **your** remote. Per-machine branches never diverge, and another machine can
  `git fetch` + read that branch for cross-machine awareness.
- **Refuses** to push to the public Horizon upstream — that would publish your
  private transcripts. You must configure your own remote.
- **Self-supplies a commit identity** when none is configured — no global
  `git config user.name/user.email` is required; it falls back to
  `Horizon AIOS <horizon-aios@localhost>`. The only hard prerequisite is
  `AIOS_BACKUP_REMOTE` pointing at your own (non-upstream) remote.

It never edits the framework `.gitignore`, so upstream updates stay
conflict-free. Run it manually, or on a schedule (cron / Task Scheduler).

**To see another machine's data:** `git fetch <remote>` then inspect or check out
that machine's `aios-backup/<host>` branch.

## Removing the AIOS

`memory/`, `handoffs/`, and `objectives/` live inside `$HORIZON_ROOT` and are
gitignored. **Deleting the AIOS deletes them unless you backed them up first**
(see above, or `documentation/system/memory.md`). This is your responsibility —
the AIOS documents it but does not auto-rescue it.

## Quick start (downstream install)

1. Clone, then `git remote add upstream …` and point `origin` at your private repo.
2. Run bootstrap (`sbin/bootstrap.{ps1,sh}`).
3. Add personal ignores to `.gitignore.user` (never the framework `.gitignore`).
4. Set `AIOS_BACKUP_REMOTE` in `aios_local.conf`; run `horizon_aios_backup_user_data.py` (cron it).
5. Update with `horizon_aios_sync.py` whenever you want upstream changes.
