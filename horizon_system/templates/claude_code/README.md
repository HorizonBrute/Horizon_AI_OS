# Claude Code Settings Template

`settings.json` in this directory is the reference template for the Claude Code global settings file (`~/.claude/settings.json`). It wires up the three standard Horizon AIOS event hooks (Stop, PermissionRequest, StopFailure), the status line, and baseline UI preferences.

---

## What This Template Configures

- `statusLine` — runs the Horizon AIOS context-alert status script in the Claude Code status bar.
- `hooks.Stop` — plays a completion sound when Claude Code finishes a session (synchronous, blocks until done).
- `hooks.PermissionRequest` — plays an alert sound when Claude Code needs user input for a permission (async, non-blocking).
- `hooks.StopFailure` — plays a failure sound when Claude Code stops due to an error (async, non-blocking).
- `effortLevel`, `autoUpdatesChannel`, `theme`, `verbose` — baseline UI preferences; adjust to taste.
- `permissions.allow` — empty by default; populate with the permissions your workflow needs.

All hooks use `shell: powershell` and `Media.SoundPlayer` — no external audio player dependency required on Windows.

---

## Setup Instructions

This template must not be used directly. Copy it to `~/.claude/settings.json` and replace the placeholder string before use.

### Placeholder: `HORIZON_BIN_PATH`

Every occurrence of `HORIZON_BIN_PATH` must be replaced with the actual absolute path to your `$HORIZON_BIN` directory (i.e., the `horizon_bin` folder inside your $HORIZON_ROOT).

Example: if $HORIZON_ROOT is `C:\devroot`, then $HORIZON_BIN is `C:\devroot\horizon_bin`, and you replace every `HORIZON_BIN_PATH` with `C:\devroot\horizon_bin`.

Note: in the hook commands (which run as PowerShell strings), use backslashes. In the statusLine command, use forward slashes (PowerShell's `-File` flag accepts both, but forward slashes are more portable in JSON).

### Quick substitution (PowerShell)

```powershell
$horizonBin = "C:\devroot\horizon_bin"   # set to your actual $HORIZON_BIN
$template = Get-Content "$horizonBin\templates\claude_code\settings.json" -Raw
$result = $template -replace 'HORIZON_BIN_PATH', $horizonBin.Replace('\', '\\')
# For statusLine forward-slash path, do a second pass:
$result = $result -replace 'HORIZON_BIN_PATH\\\\', ($horizonBin.Replace('\', '/') + '/')
$result | Set-Content "$env:USERPROFILE\.claude\settings.json" -Encoding utf8
```

Or substitute manually in any text editor.

---

## Layer Ownership Reminder

This template is for `~/.claude/settings.json` (global layer). Do not copy hooks or statusLine into the devroot `$HORIZON_ROOT/.claude/settings.json` — that layer owns devroot-scoped permissions only. See `$HORIZON_ETC/ai_os_personalizations.md` Section 1 for the full layer ownership model.

---

## The Broken `settings.json.json`

The file `settings.json.json` (double extension) in this directory is a legacy artifact from initial setup. It contains an older bash-based hook format that predates the PowerShell Media.SoundPlayer approach. It can be deleted once you have confirmed your global `~/.claude/settings.json` is correctly configured from this template.
