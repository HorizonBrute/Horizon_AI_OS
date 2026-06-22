# Claude Code Settings Template

`settings.json` in this directory is the reference template for the Claude Code global settings file (`~/.claude/settings.json`). It wires up the three standard Horizon AIOS event hooks (Stop, PermissionRequest, StopFailure), the status line, and baseline UI preferences.

---

## What This Template Configures

statusLine and all hooks dispatch through the stable `aios-exec` wrapper
(`~/.horizon/bin/aios-exec.{ps1,sh}`), which resolves the *active* AIOS at run
time. This is what lets `aios switch <name>` repoint everything without ever
rewriting `settings.json`. Each entry passes the wrapper an action:

- `statusLine` — `aios-exec … statusline`: runs the active AIOS's context-alert status script in the status bar.
- `hooks.Stop` — `aios-exec … hook-stop`: logs the event and plays a completion sound (synchronous).
- `hooks.PermissionRequest` — `aios-exec … hook-permission`: logs and plays an alert sound when input is needed (async).
- `hooks.StopFailure` — `aios-exec … hook-stopfailure`: logs and plays a failure sound on error (async).
- `effortLevel`, `autoUpdatesChannel`, `theme`, `verbose` — baseline UI preferences; adjust to taste.
- `permissions.allow` — empty by default; populate with the permissions your workflow needs.

On Windows the wrapper uses `Media.SoundPlayer` — no external audio player dependency required. See `$HORIZON_DOCS/system/aios_switching.md` for the indirection model.

---

## Setup Instructions

This template must not be used directly. Copy it to `~/.claude/settings.json` and replace the placeholder string before use.

### Placeholder: `AIOS_EXEC_WRAPPER`

The template uses one placeholder: `AIOS_EXEC_WRAPPER` — replace with the absolute
path to the stable wrapper at `~/.horizon/bin/aios-exec.ps1` (Windows) or
`~/.horizon/bin/aios-exec.sh` (Unix). The path is AIOS-independent — it lives in
your home directory, not in any `$HORIZON_ROOT` — which is exactly why
`settings.json` never has to change when you switch AIOS. Inside the JSON string,
use **forward slashes** on Windows (`C:/Users/you/.horizon/bin/aios-exec.ps1`);
backslashes form invalid JSON escape sequences. `powershell.exe -File` accepts
forward slashes.

Generate the wrapper first with `python "$HORIZON_SYSTEM/sbin/horizon_aios_switch.py" init`.
The bootstrap script (`bootstrap.ps1` / `bootstrap.sh`, Section 5) runs `init` and
performs this substitution automatically when you copy the template.

### Quick substitution (PowerShell — manual)

```powershell
python "$env:HORIZON_SYSTEM\sbin\horizon_aios_switch.py" init   # generates ~/.horizon/bin/aios-exec.ps1
$wrapper  = ("$HOME\.horizon\bin\aios-exec.ps1") -replace '\\','/'   # forward slashes for JSON
$template = Get-Content "$env:HORIZON_SYSTEM\templates\claude_code\settings.json" -Raw
$template -replace 'AIOS_EXEC_WRAPPER', $wrapper | Set-Content "$env:USERPROFILE\.claude\settings.json" -Encoding utf8
```

Or substitute manually in any text editor. See `$HORIZON_DOCS/system/aios_switching.md`.

---

## Layer Ownership Reminder

This template is for `~/.claude/settings.json` (global layer). Do not copy hooks or statusLine into the devroot `$HORIZON_ROOT/.claude/settings.json` — that layer owns devroot-scoped permissions only. See `$HORIZON_ETC/ai_os_personalizations.md` Section 1 for the full layer ownership model.

---

## The Broken `settings.json.json`

The file `settings.json.json` (double extension) in this directory is a legacy artifact from initial setup. It contains an older bash-based hook format that predates the PowerShell Media.SoundPlayer approach. It can be deleted once you have confirmed your global `~/.claude/settings.json` is correctly configured from this template.
