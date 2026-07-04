# Horizon AIOS — Sync Setup Reference

Auto-sync keeps your local AIOS installation aligned with upstream through a
two-lane model that mirrors the framework-vs-user-space ownership split.

- Official / upstream lane ("stay synced"): pulls the canonical Horizon AIOS
  system layer and is authoritative. Its scope is every path EXCEPT `projects/`,
  `usrbin/`, and `brains/`. It OVERWRITES your local copy of those official paths
  via a scoped hard-restore (`git fetch`, then `git checkout <remote>/<branch> --
  <official paths>`), and commits the result. Local edits to official paths are
  discarded by design -- move any customization into the override layer instead
  (see `system/distribution_and_updates.md`).
- Personal lane ("updates optional, local wins"): its scope is exactly
  `projects/`, `usrbin/`, and `brains/`. Local always wins. By default it keeps
  local and pulls nothing. You can opt in to a fast-forward-only advance, or use
  the `--force-personal` danger flag to overwrite personal paths from the
  personal remote.

The path partition is the boundary the whole model rests on: anything not
explicitly personal-owned is treated as official and may be overwritten by the
official lane. The personal lane runs first, then the official lane. Setting
`SYNC_AIOS_FROM_REMOTE=no` disables both lanes. Nothing force-pushes to a remote;
all activity is logged.

Because these commits are automated machine housekeeping (not human
contributions), the sync bypasses the DCO `commit-msg` hook with `--no-verify` --
see "Automated commits and the DCO hook" below.

---

## Config keys (`aios_local.conf`)

Copy `horizon_system/templates/aios_local.conf.template` to
`horizon_system/ai_os_etc/aios_local.conf` and set the following keys. The file
is git-ignored; never commit it.

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `SYNC_AIOS_FROM_REMOTE` | `yes` / `no` | `yes` | Master switch. Set to `no` to disable both lanes and prevent the scheduler from being installed. |
| `AIOS_SYNC_FREQ` | `hourly` / `daily` / `weekly` | `daily` | How often the scheduled task or cron job runs. |
| `AIOS_SYNC_TIME` | `HH:MM` (24h) | `03:00` | Time of day for daily and weekly schedules. Ignored for hourly. |
| `AIOS_OFFICIAL_REMOTE` | remote name or URL | `origin` | Official lane: the canonical Horizon AIOS remote to fetch the system layer from. |
| `AIOS_OFFICIAL_BRANCH` | branch name | `main` | Official lane: branch on the official remote to sync from. |
| `AIOS_PERSONAL_REMOTE` | remote name or URL | `` (empty) | Personal lane: your own remote for `projects/`, `usrbin/`, `brains/`. Empty means the personal lane is skipped entirely. |
| `AIOS_PERSONAL_BRANCH` | branch name | `main` | Personal lane: branch on the personal remote. |
| `SYNC_PERSONAL_FROM_REMOTE` | `yes` / `no` | `no` | Personal lane opt-in. `no` keeps local and pulls nothing. `yes` allows a fast-forward-only advance of the personal paths (never a rewrite; a diverged branch is left as-is). Overwrite still requires `--force-personal`. |

**Deprecated (back-compat) keys:** `AIOS_REPO_REMOTE` and `AIOS_REPO_BRANCH`
are the pre-two-lane single-remote keys. They are still honored: when the new
`AIOS_OFFICIAL_*` keys are absent, the sync maps `AIOS_REPO_REMOTE` /
`AIOS_REPO_BRANCH` onto the official lane. Prefer the `AIOS_OFFICIAL_*` names in
new configs.

---

## Running sync manually

```
python $HORIZON_SYSTEM/sbin/horizon_aios_sync.py                 # both lanes
python $HORIZON_SYSTEM/sbin/horizon_aios_sync.py --lane official # official only
python $HORIZON_SYSTEM/sbin/horizon_aios_sync.py --lane personal # personal only
python $HORIZON_SYSTEM/sbin/horizon_aios_sync.py --force-personal # DANGER: overwrite personal paths
```

- `--lane official | personal | both` selects which lane(s) to run (default
  `both`).
- `--force-personal` overwrites your local `projects/`, `usrbin/`, and `brains/`
  from the personal remote. This is the deliberate, logged override to the
  local-wins default; use it only when you intend to discard local personal
  changes.

---

## Automated commits and the DCO hook

Both lanes finish by creating a commit for the paths they changed (official:
`chore(sync): pull official AIOS update from ...`; forced personal:
`chore(sync): FORCE-pull personal paths from ...`). The repo ships a DCO
`commit-msg` hook that rejects any commit whose message lacks a `Signed-off-by:`
line -- the sign-off requirement for human contributions.

An automated sync commit is machine housekeeping, not a human contribution, so
the sync passes `git commit --no-verify` to bypass that hook. This is the one
deliberate exception to the DCO policy. Without it, every scheduled sync would be
rejected by the hook and abort, leaving official paths overwritten in the working
tree but never committed -- a dirty tree that re-overwrites on each run. Human
commits still sign off normally (`git commit -s`); only the sync's own commits
skip the hook.

---

## Installing the scheduled task / cron job

Run from `$HORIZON_SYSTEM/sbin/`:

```
python horizon_aios_setup_sync_schedule.py
```

The script reads `aios_local.conf`, detects the platform, and installs the
appropriate automation:

- **Windows**: registers a Task Scheduler task named `HorizonAIOS_Sync` that
  runs `sbin/horizon_aios_sync_runner.ps1` at the configured frequency and time.
- **Linux / macOS**: appends a cron entry (marked `# HorizonAIOS_Sync`) to
  your user crontab.

Pass `--yes` to skip all interactive confirmation prompts (useful in unattended
bootstrap runs):

```
python horizon_aios_setup_sync_schedule.py --yes
```

If the task or cron entry already exists, the script prompts before overwriting
(or auto-confirms with `--yes`).

---

## Check sync status

To answer "is auto-sync installed, and when did it last succeed?", use the
read-only status mode instead of manually reading the sync log or the Task
Scheduler / cron last-result codes:

```
python $HORIZON_SYSTEM/sbin/horizon_aios_sync.py --status
```

It reports the platform, whether the schedule is INSTALLED, the last scheduler
run/result, the log file, and the last recorded sync outcome. It is read-only
and never triggers a sync.

**Exit-code contract** (stable, usable in monitoring scripts):

| Exit | Meaning |
|------|---------|
| `0` | Auto-sync is installed and the last run succeeded — or is installed with no run recorded yet. |
| `1` | Auto-sync is NOT installed. |
| `2` | Auto-sync is installed but the LAST RECORDED RUN FAILED. |

---

## SSH key prerequisites for unattended sync

The sync script runs `git fetch` over SSH. This requires that the SSH key for
the remote is accessible without interactive passphrase entry at the time the
scheduled job runs.

### Unix (Linux / macOS)

Option A — ssh-agent loaded at login (interactive sessions):
1. Add your key to `~/.ssh/config` with `AddKeysToAgent yes`.
2. On macOS, add `UseKeychain yes` to store the passphrase in Keychain.
3. The cron job will only work if it inherits an active agent socket, which
   typically means it only works in login-session cron, not system cron.

Option B — passphrase-free deploy key (recommended for reliable unattended sync):
1. Generate a new key with no passphrase: `ssh-keygen -t ed25519 -f ~/.ssh/aios_sync_deploy -N ""`
2. Register the public key as a read-only deploy key on your upstream remote.
3. Add a `Host` block in `~/.ssh/config` that maps the remote host to this key:
   ```
   Host github.com-aios-sync
       HostName github.com
       User git
       IdentityFile ~/.ssh/aios_sync_deploy
       IdentitiesOnly yes
   ```
4. Update `AIOS_REPO_REMOTE` in `aios_local.conf` to use the aliased host
   (e.g., `git@github.com-aios-sync:yourorg/aios.git`).

### Windows

**Default (logged-in) mode:** The scheduled task runs only when you are logged
in. If the OpenSSH Authentication Agent service is running and your key is
loaded in it, `git fetch` will succeed without further setup.

To verify the agent is running and your key is loaded:
```powershell
Get-Service ssh-agent
ssh-add -l
```

**Advanced: sync while not logged in**

See the next section.

---

## Windows advanced: syncing while not logged in

By default, the task is registered with `/RL HIGHEST` but only runs when the
user is logged in (no stored credentials). For an always-on workstation or
server where you want sync to run even when logged out:

1. **Create a passphrase-free deploy key** (see Unix Option B above — same key
   generation and remote registration steps apply).

2. **Configure the OpenSSH Authentication Agent service** to start
   automatically and load the deploy key at boot:
   ```powershell
   Set-Service ssh-agent -StartupType Automatic
   Start-Service ssh-agent
   ssh-add C:\Users\<you>\.ssh\aios_sync_deploy
   ```
   Keys added to the Windows OpenSSH agent persist across reboots when the
   service is set to Automatic.

3. **Modify the scheduled task** in Task Scheduler:
   - Open Task Scheduler → find `HorizonAIOS_Sync`.
   - General tab → select "Run whether user is logged on or not".
   - Click OK — Windows will prompt for your account credentials to store them
     in the Credential Manager. These are used only to launch the task process,
     not to authenticate to git.

4. **Test the task** by right-clicking it and choosing "Run", then checking the
   log file (see below).

---

## Removing the scheduled task / cron entry

**Windows** — delete the task from Task Scheduler UI, or:
```powershell
schtasks /Delete /TN HorizonAIOS_Sync /F
```

**Unix** — edit your crontab and remove the two lines added by the installer
(the `# HorizonAIOS_Sync` marker line and the cron line below it):
```
crontab -e
```

---

## Troubleshooting

**Check the log file:**
```
logs/horizon_aios_sync.log
```
Every sync run appends timestamped `[OK]`, `[WARN]`, `[ERR]`, or `[INFO]`
entries. Start here when a sync fails silently.

**Run sync manually to see live output:**
```
python horizon_system/sbin/horizon_aios_sync.py
```
This runs the same logic the scheduler calls and prints directly to stdout in
addition to writing the log.

**Common failure causes:**

- `git fetch failed` — SSH key not loaded, wrong remote URL, or network issue.
  Run `ssh -T git@github.com` (or your remote host) to test SSH auth.

- Official lane discarded a local edit -- expected, not a failure. The official
  lane OVERWRITES official paths (everything except `projects/`, `usrbin/`,
  `brains/`). If a local change to an official path vanished after a sync, move
  that customization into the override layer (see
  `system/distribution_and_updates.md`); the official lane is not the place to
  keep local edits.

- `Personal lane: local diverged` -- informational, not a failure. With
  `SYNC_PERSONAL_FROM_REMOTE=yes` the personal lane only fast-forwards; if your
  personal branch diverged from the remote it keeps local and skips. Use
  `--force-personal` only if you intend to discard local personal changes.

- `aios_local.conf not found` — sync runs with defaults (remote=`origin`,
  branch=`main`). Copy the template to create the file:
  ```
  cp horizon_system/templates/aios_local.conf.template horizon_system/ai_os_etc/aios_local.conf
  ```

- Task runs but nothing happens on Windows — confirm the task is not in a
  "disabled" state in Task Scheduler and that the last run result is not
  `0x1` (Python not found) or `0x41301` (task is already running).
