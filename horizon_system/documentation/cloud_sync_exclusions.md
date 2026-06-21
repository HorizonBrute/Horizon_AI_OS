# Cloud Sync Exclusions for Horizon AIOS

If you use Horizon AIOS without git, or alongside a cloud sync service (OneDrive,
Google Drive, Dropbox), you need to configure your sync tool to exclude sensitive
and large files the same way `.gitignore` does for git.

**Recommendation: Do not place `$HORIZON_ROOT` inside a synced folder.**

The safest approach is to keep your AIOS root outside the OneDrive, Google Drive,
or Dropbox folder entirely. Cloud sync + a developer repo is a common source of
file corruption, credential leaks, and sync conflicts.

If you must sync AIOS, configure the exclusions below.

---

## Dropbox

Dropbox supports a `.dropboxignore` file (similar syntax to `.gitignore`).
Place it at the root of your Dropbox-synced directory.

A pre-populated template is at `$HORIZON_SYSTEM/templates/dropboxignore.template`.
Copy it to `.dropboxignore` at your Dropbox root and adjust as needed:

```
cp $HORIZON_SYSTEM/templates/dropboxignore.template ~/.dropbox/.dropboxignore
# or wherever your Dropbox root is
```

**Supported since:** Dropbox desktop 131.4.4602 (2021). On older clients,
use the Dropbox CLI: `dropbox.py exclude add <folder>`.

---

## OneDrive (Windows)

OneDrive does not support a `.onedriveignore` file. Options:

**Option A — Selective Sync (recommended):**
1. Right-click the OneDrive tray icon → Settings → Account → Choose Folders
2. Uncheck any folder you want to exclude from sync

**Option B — Attribute-based exclusion (PowerShell):**
Mark a folder as "offline-only" so OneDrive skips it:
```powershell
# Exclude a specific folder from OneDrive sync
attrib +U "C:\path\to\folder" /S /D
```
Note: this marks the folder as a "dehydrated" placeholder. Test on a
non-critical folder first.

**Option C — Move $HORIZON_ROOT outside the OneDrive folder:**
The cleanest solution. Example: keep AIOS at `C:\devroot` (not in
`C:\Users\<you>\OneDrive\devroot`).

---

## Google Drive for Desktop

Google Drive for Desktop does not support an ignore file.

Options:
1. Use the "Sync options" panel in Google Drive for Desktop to select which
   folders to sync (excludes folders at the root level only).
2. Keep `$HORIZON_ROOT` outside the Google Drive folder.
3. Use `.gdriveignore` if you are using the open-source `drive` CLI tool
   (not the official Google Drive for Desktop client).

---

## What to Exclude

Regardless of which sync service you use, the following categories must not
be synced (they contain secrets or are too large):

- `horizon_system/ai_os_etc/aios_local.conf` — machine-local credentials and paths
- `brains/` — all brain session data and any secrets they hold
- `logs/` — log content (scaffold is fine, content is not)
- `handoffs/` — session-local conversation continuity data
- `.gitignore.user` — machine-local folder patterns
- Any file matching patterns in `.gitignore` (secrets, credentials, ML weights)

See `.gitignore` for the full list of excluded patterns.
