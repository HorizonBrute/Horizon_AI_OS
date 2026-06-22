# Switching between AIOSs

Run two (or more) Horizon AIOS installs on one machine and switch which one your
local Claude config points at, without re-running bootstrap or hand-editing
config. Backed by `horizon_system/sbin/aios_switch.py`.

## What binds a machine to an AIOS

Five machine-global pointers otherwise hardcode a single `HORIZON_ROOT`:

| # | Pointer | Location |
|---|---------|----------|
| 1 | Env vars (`HORIZON_ROOT` + 8 derived) | your shell profile |
| 2 | CLAUDE.md redirect | `~/.claude/CLAUDE.md` |
| 3 | Skills junction/symlink | `~/.claude/skills/` |
| 4 | statusline + hooks | `~/.claude/settings.json` |
| 5 | Upstream sync schedule | OS scheduler (advisory) |

The switcher makes a switch a **pointer write**, not a re-stamp. Two pointers go
through an indirection layer so they never change on switch:

- **Env (#1)** — `~/.horizon/active_env.{ps1,sh}` is generated from the active
  AIOS. Your profile sources that one file; a switch regenerates it.
- **settings.json (#4)** — points once at stable wrappers `~/.horizon/bin/aios-exec.{ps1,sh}`
  that resolve the active AIOS at run time. A switch leaves settings.json alone.

Pointers #2 and #3 are rewritten directly on each switch. #5 is advisory: the
switcher prints the command to re-point auto-sync; it does not touch the
scheduler itself.

## The registry

`~/.horizon/aios_registry.json` (machine-local, never synced) records the known
AIOSs and which is active:

```json
{
  "version": 1,
  "active": "work",
  "aioses": {
    "work": { "root": "C:\\devroot",      "registered": "..." },
    "home": { "root": "D:\\horizon-home", "registered": "..." }
  }
}
```

It is **self-healing**: any command rebuilds it silently if missing, registering
the current tree (resolved from the script's own location) as the sole active
AIOS. Bootstrap also runs `aios_switch.py init` to create it on onboarding.

## Commands

```
aios_switch.py list                      # registered AIOSs (* = active)
aios_switch.py current                   # active name + root
aios_switch.py register <name> <path>    # add/replace a registration
aios_switch.py unregister <name>         # remove a registration (files untouched)
aios_switch.py switch <name>             # point local config at <name>
aios_switch.py switch <name> --dry-run   # show what would change, change nothing
aios_switch.py init                      # onboarding: registry + env + wrappers
```

`register` refuses to silently overwrite an existing name or an already-registered
root — it prompts (`--yes`/`-y` to force). `unregister` refuses to remove the
active AIOS.

## One-time setup

Add the profile snippet (see `templates/profile_snippet.{ps1,sh}`) so your shell
loads whichever AIOS is active:

```powershell
# PowerShell $PROFILE
if (Test-Path "$HOME\.horizon\active_env.ps1") { . "$HOME\.horizon\active_env.ps1" }
```
```bash
# ~/.bashrc, ~/.zshrc, …
[ -f "$HOME/.horizon/active_env.sh" ] && . "$HOME/.horizon/active_env.sh"
```

Bootstrap generates `active_env.*`, the wrappers, and a settings.json that points
at the wrappers. On an existing install, point statusLine + hooks at
`~/.horizon/bin/aios-exec.*` with actions `statusline`, `hook-stop`,
`hook-permission`, `hook-stopfailure` (compare with the templates under
`templates/claude_code/`).

## Switching

```
$ python aios_switch.py register home D:\horizon-home
$ python aios_switch.py switch home
```

After a switch:

- **Restart Claude Code** and **open a new shell.** Env-var changes do not reach
  already-running sessions.
- If you use auto-sync, run the printed `setup_sync_schedule.py` command to point
  it at the new AIOS.

## Verifying

`doctor.py` reports registry validity, that the active root is a real AIOS, and
that `active_env.*` + the wrappers are present.

## Notes & limits

- This switches the **operator's** config only. Brain users have their own
  profiles/ACLs per AIOS; switching the operator does not touch them.
- A target must be a valid AIOS root (`horizon_system/` with `ai_os_etc/` and
  `sbin/`); the switcher refuses to register or switch to anything else.
- The bash `active_env.sh` renders Windows paths with forward slashes for Git
  Bash compatibility; the primary Windows path is PowerShell.
