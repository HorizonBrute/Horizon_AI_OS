# Horizon AIOS — Sync Setup Reference

Auto-sync keeps your local AIOS installation up to date with an upstream git
remote. The sync is a fast-forward-only `git fetch` + `git merge --ff-only`
against the configured remote and branch. It will not run if you have
uncommitted changes, and it will not force-push or rebase — if histories have
diverged, it fails loudly and leaves you to resolve it manually.

---

## Config keys (`aios_local.conf`)

Copy `horizon_system/templates/aios_local.conf.template` to
`horizon_system/ai_os_etc/aios_local.conf` and set the following keys. The file
is git-ignored; never commit it.

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `SYNC_AIOS_FROM_REMOTE` | `yes` / `no` | `yes` | Master switch. Set to `no` to disable all syncing and prevent the scheduler from being installed. |
| `AIOS_SYNC_FREQ` | `hourly` / `daily` / `weekly` | `daily` | How often the scheduled task or cron job runs. |
| `AIOS_SYNC_TIME` | `HH:MM` (24h) | `03:00` | Time of day for daily and weekly schedules. Ignored for hourly. |
| `AIOS_REPO_REMOTE` | remote name or URL | `origin` | The git remote to fetch from. Use a remote name if it is already configured in the repo, or a full URL. |
| `AIOS_REPO_BRANCH` | branch name | `main` | Branch on the remote to sync from. |

---

## Installing the scheduled task / cron job

Run from `$HORIZON_SYSTEM/sbin/`:

```
python setup_sync_schedule.py
```

The script reads `aios_local.conf`, detects the platform, and installs the
appropriate automation:

- **Windows**: registers a Task Scheduler task named `HorizonAIOS_Sync` that
  runs `sbin/sync_aios_runner.ps1` at the configured frequency and time.
- **Linux / macOS**: appends a cron entry (marked `# HorizonAIOS_Sync`) to
  your user crontab.

Pass `--yes` to skip all interactive confirmation prompts (useful in unattended
bootstrap runs):

```
python setup_sync_schedule.py --yes
```

If the task or cron entry already exists, the script prompts before overwriting
(or auto-confirms with `--yes`).

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
logs/aios_sync.log
```
Every sync run appends timestamped `[OK]`, `[WARN]`, `[ERR]`, or `[INFO]`
entries. Start here when a sync fails silently.

**Run sync manually to see live output:**
```
python horizon_system/sbin/sync_aios.py
```
This runs the same logic the scheduler calls and prints directly to stdout in
addition to writing the log.

**Common failure causes:**

- `git fetch failed` — SSH key not loaded, wrong remote URL, or network issue.
  Run `ssh -T git@github.com` (or your remote host) to test SSH auth.

- `Uncommitted changes` — the sync refuses to run when tracked files are
  dirty. Commit or stash your changes first.

- `Fast-forward not possible` — your local branch has commits not on the
  remote, or the remote was force-pushed. Inspect with
  `git log origin/main..HEAD` and resolve manually.

- `aios_local.conf not found` — sync runs with defaults (remote=`origin`,
  branch=`main`). Copy the template to create the file:
  ```
  cp horizon_system/templates/aios_local.conf.template horizon_system/ai_os_etc/aios_local.conf
  ```

- Task runs but nothing happens on Windows — confirm the task is not in a
  "disabled" state in Task Scheduler and that the last run result is not
  `0x1` (Python not found) or `0x41301` (task is already running).
