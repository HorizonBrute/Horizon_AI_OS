# Horizon AIOS — System Configuration Reference

This document describes the complete configuration architecture of Horizon AIOS: what each file controls, how the system is structured, where paths are sensitive, and how all components fit together. It is the authoritative reference for understanding and maintaining the system.

---

## Presumptions / Dependencies

The following conditions must be true for Horizon AIOS to function correctly. This section is the authoritative list of what the system assumes about the environment it runs in.

**Software**

P.1 **Git 2.9 or later** — `core.hooksPath` (introduced in 2.9) is how the pre-commit hook is wired without placing files in `.git/hooks/`. Versions earlier than 2.9 silently ignore this config key and the hook will never run.

P.2 **Claude Code CLI** — the application the AIOS config layer targets. All settings, hooks, and statusline configuration are specific to Claude Code's configuration schema. Must be installed before the bootstrap is run.

P.3 **PowerShell** — required on Windows only. The Windows statusline script (`statusline-context-alerts.ps1`) and the `play_sound.sh` Windows branch both invoke PowerShell, which is built-in on Windows 5.1+. On Linux and macOS, `play_sound.sh` uses native audio commands and the bash statusline script is dispatched instead — `pwsh` is not required on those platforms.

P.4 **GPG** — commit signing is enabled globally (`commit.gpgsign = true` in `harness_configs/git/gitconfig`). A GPG key must be present in the local keyring before the first commit to any repo on the machine. The key fingerprint is stored in the portable gitconfig and must be updated per-machine during setup. `aios setup` decouples the first commit from `--yes`: it is off by default; pass `--first-commit` to create it in the same pass (requires a working GPG key), or run `git commit -s` manually later.

P.5 **SSH client** — all remote Git operations use SSH. No HTTPS remote URLs exist in this system. The `gh` CLI is not installed and not used.

**Authentication**

P.6 **SSH key pair** — a key pair must exist (default path: `~/.ssh/id_ed25519`) and the public key must be registered with your GitHub account (or your organization's remote host).

P.7 **GPG key in keyring** — a GPG key must be generated and importable by the local GPG agent. The full fingerprint must be entered in `horizon_system/harness_configs/git/gitconfig` under `[user] signingkey` as part of setup.

**Platform**

P.8 Horizon AIOS supports **Windows, Linux, and macOS**. Platform detection is handled at runtime by two dispatcher scripts; no per-machine configuration branching is required.

P.8.1 **Sound playback** — `horizon_system/sounds/play_sound.sh` detects `uname -s` and calls: `Media.SoundPlayer` via `powershell.exe` (Windows/Git Bash), `afplay` (macOS), or the first available player from `paplay` → `aplay` → `ffplay` → `mpg123` (Linux). All hooks in `settings.json` call this script via `bash`.

P.8.2 **Statusline** — `horizon_system/bin/statusline/statusline.sh` detects `uname -s` and pipes stdin to: `statusline-context-alerts.ps1` via `powershell.exe` (Windows), or `statusline-command.sh` via `bash` (Linux/macOS). Both scripts include context threshold audio alerts.

P.8.4 **Master mute** — set `sounds_enabled = false` in `horizon_system/sounds/aios_sounds.conf` to silence all AIOS event sounds everywhere (absolute kill switch). A per-project `aios_sounds.conf` may set the same key to mute only its own subtree. See file_structure_invariants §10.6.

P.8.3 **Linux audio dependency** — at least one of `paplay` (PulseAudio), `aplay` (ALSA), `ffplay` (ffmpeg), or `mpg123` must be installed for sounds to play on Linux. If none are found, `play_sound.sh` exits silently with no effect on Claude Code.

P.9 **Bootstrap requires elevated privileges**: Administrator on Windows (right-click PowerShell → Run as administrator) and sudo/root on Linux and macOS. This is required for `horizon_aios_harden.py` to apply filesystem ACLs that enforce brain isolation. See the Prerequisites section in ReadMeToSetupYourSystem.md.

P.10 **Developer Mode not required**.

**Runtime**

P.11 **`$HORIZON_ROOT` is written into machine-local config at setup time.** If the repo is moved or renamed, run `horizon_aios_relocate.py` (`$HORIZON_SYSTEM/sbin/`) to update all machine-local instance pointers automatically. See Section 3 (Path Dependencies Catalog) for the files that contain the embedded root. Framework files in the repo use env vars or derive their root from script location — they do not embed the absolute path and need no substitution.

P.12 **Audio output device** — the sound hooks assume an audio output device is available. If none is present, `Media.SoundPlayer` will throw silently (the hook exits without error and Claude Code is unaffected). Context threshold audio in the statusline script also fails silently via `Test-Path` guard.

P.13 **`~/.claude/` must exist** before bootstrap. Claude Code creates this directory on first launch. If the directory does not exist when bootstrap writes the CLAUDE.md redirect and settings.json into it, the step will fail. Launch Claude Code once, let it initialize, then proceed with setup.

P.14 **`.git/info/exclude` is hook-managed**. The pre-commit hook overwrites this file on every OS repo commit. Do not manually edit `.git/info/exclude` — edit `.gitignore.user` instead and commit to apply changes.

P.15 **OS repo `$HORIZON_ROOT` is not a project workspace**. The OS repo tracks config and assets only. It is not intended to hold source code, build outputs, or project-specific files directly. Those belong in project repos nested inside `$HORIZON_ROOT`.

---

## 1. Architecture Summary

Horizon AIOS is a portable, Git-versioned Claude Code operating system layer. The entire environment — Claude Code settings, hooks, sounds, statusline, AI behavior instructions, and git configuration — lives in one repository. Cloning to a new machine and running a bootstrap sequence reproduces the full environment identically.

1.1 **Two-layer model**

1.1.1 The **OS repo** (`$HORIZON_ROOT`) is a Git repository that tracks the AIOS config and asset layer. It is not a project repo — it does not track source code, build artifacts, or project-specific files. It tracks: `.claude/CLAUDE.md`, `.claude/settings.json`, `horizon_system/`, `.gitignore`, `.gitignore.user`. Machine-local runtime artifacts (`handoffs/`, `objectives/`, `usrbin/usr_skills/`) are gitignored.

1.1.2 **Project repos** are independent Git repositories placed inside `$HORIZON_ROOT`. Each project manages its own history, branches, and remotes. The OS repo does not track them and has no knowledge of their contents.

1.2 **Config inheritance — no wiring required**

Any folder inside `$HORIZON_ROOT` automatically receives the full AIOS Claude Code environment. Claude Code reads its global configuration from `~/.claude/`, which the bootstrap process redirects into the OS repo. This means every session — regardless of which subdirectory it opens in — loads the same hooks, sounds, statusline, permissions, and CLAUDE.md instructions. No per-project setup is needed.

1.3 **Project opt-out — `git init` is the mechanism**

To exclude a folder from OS repo tracking and give it its own Git history, run `git init` inside it. Git will not descend into subdirectories that have their own `.git` folder, so the contents become invisible to the OS repo immediately. The pre-commit hook handles the edge case where a folder was already tracked before being git-initted.

1.4 **Two-file bootstrap**

Claude Code hardcodes two global config lookup paths that cannot be changed. The bootstrap redirects both into the repository:

1.4.1 `~/.claude/CLAUDE.md` is created as a one-line file containing `@$HORIZON_ROOT\.claude\CLAUDE.md`. Claude Code resolves `@` includes, so the actual AI instructions come from the repository.

1.4.2 `~/.claude/settings.json` is created by copying the template `horizon_system\templates\claude_code\settings.json` and substituting the `AIOS_EXEC_WRAPPER` placeholder with the path to the machine-local `aios-exec` wrapper (`~/.horizon\bin\aios-exec.ps1`). It is a **separate file** from `$HORIZON_ROOT\.claude\settings.json` — the two have different owners (the global file owns hooks/statusLine; the devroot file owns devroot-scoped permissions only). Because the deployed file points at the wrapper, which resolves the active AIOS at run time, it is AIOS-independent and is not rewritten when you `aios switch`. (Earlier versions hard-linked the two files; that model is superseded — see `documentation/system/aios_switching.md`.)

1.5 **What is version-controlled**

1.5.1 `$HORIZON_ROOT\.claude\CLAUDE.md` — global AI instructions
1.5.2 `$HORIZON_ROOT\.claude\settings.json` — devroot-scoped permissions only (the global hooks/statusLine/theme live in the machine-local `~/.claude/settings.json`, copied from the template and not committed)
1.5.3 `$HORIZON_ROOT\horizon_system\` — sounds, statusline scripts, harness configs, git hooks, documentation
1.5.4 `$HORIZON_ROOT\.gitignore` — system ignore patterns
1.5.5 `$HORIZON_ROOT\.gitignore.user` — user personal ignore patterns

1.6 **What is never version-controlled**

1.6.1 `~/.claude/.credentials.json` — Claude API authentication token
1.6.2 `$HORIZON_ROOT\.claude\settings.local.json` — machine-local permission overrides
1.6.3 All Claude Code runtime directories: `~/.claude/cache/`, `sessions/`, `history.jsonl`, `daemon/`, `telemetry/`, `paste-cache/`, `shell-snapshots/`, `file-history/`, `session-env/`, `tasks/`, `jobs/`
1.6.4 SSH private keys (`~/.ssh/id_ed25519`) and GPG private keys
1.6.5 Any folder that has been `git init`'d (nested repos are invisible to the OS repo)
1.6.6 `$HORIZON_ROOT\handoffs\` — machine-local session handoff documents (gitignored)
1.6.7 `$HORIZON_ROOT\objectives\` — machine-local durable `/objective` goals (gitignored)
1.6.8 `$HORIZON_ROOT\usrbin\usr_skills\` — machine-local user skills, symlinked into `skills_sbin/` at runtime (gitignored)
1.6.9 `$HORIZON_SYSTEM\ai_os_etc\git_identity.local.gitconfig` — machine-local git identity (`user.name`/`user.email`/`user.signingkey`) written by `aios setup` and wired via global `include.path`; gitignored, never shows in `git status`
1.6.10 `$HORIZON_ROOT\local.agents.md` and `$HORIZON_ROOT\.claude\local.agents.md` — machine-local agent instruction overrides; gitignored (bare `local.agents.md` pattern); materialized from their `.template` siblings by `aios setup`; `@`-imported last by the sibling `agents.md` so local content wins. See `$HORIZON_ETC/file_structure_invariants.md` §12.6.

1.7 **Pre-commit hook responsibilities**

The hook at `horizon_system/harness_configs/git/hooks/pre-commit` runs before every OS repo commit and performs two operations:

1.7.1 Scans for subdirectories that have acquired a `.git` folder since they were last tracked. Any such directory is removed from the OS index with `git rm -r --cached` before the commit proceeds. This ensures that `git init`'ing a project folder always results in clean exclusion even if the folder was previously tracked.

1.7.2 Syncs `.gitignore.user` to `.git/info/exclude`. Git reads `.git/info/exclude` as a machine-local ignore file. By syncing the tracked `.gitignore.user` into it on every commit, personal ignore patterns are always current without any manual step.

1.8 **`.gitignore.user` personal layer**

`.gitignore.user` is a tracked file at `$HORIZON_ROOT`. It is separate from the system `.gitignore` so that personal exclusions (folders, file types, machine-specific items) are cleanly separated from OS-managed patterns. Changes to `.gitignore.user` take effect at the next commit, when the pre-commit hook syncs it to `.git/info/exclude`. The file is version-controlled and therefore portable across machines.

---

## 2. Git Repo Architecture

2.1 **OS repo structure**

The OS repo is initialized at `$HORIZON_ROOT` with `git init`. It uses GPG commit signing globally (`commit.gpgsign = true`). SSH is used for all remote operations — no HTTPS, no `gh` CLI.

2.2 **What the OS repo tracks**

2.2.1 `.claude/CLAUDE.md` and `.claude/settings.json` — the two versioned Claude Code config files. The global gitignore excludes `.claude/` entirely; the system `.gitignore` contains a surgical override to un-ignore only these two files:

```gitignore
!.claude/
.claude/*
!.claude/CLAUDE.md
!.claude/settings.json
```

2.2.2 `horizon_system/` — the full runtime asset and config directory tree.

2.2.3 `handoffs/` — session handoff markdown files.

2.2.4 `.gitignore` and `.gitignore.user` — both ignore layer files.

2.3 **Nested repo exclusion**

2.3.1 Git natively does not descend into subdirectories that have their own `.git` folder. Running `git init` in any subfolder is sufficient to exclude it from the OS repo going forward.

2.3.2 The pre-commit hook handles the edge case where a folder was tracked before being git-initted. It scans the full directory tree for nested `.git` directories, checks whether any tracked files belong to those directories, and runs `git rm -r --cached` on them if so. This happens transparently before every commit.

2.3.3 To exclude an entire parent directory (one that will contain multiple independent projects), run `git init` in the parent itself. Example: `git init "$HORIZON_ROOT/RedTeam"`. No remote is needed. The local `.git` is sufficient to trigger exclusion of the entire subtree.

2.4 **`.gitignore` layers**

Four ignore layers apply to the OS repo, in order from lowest to highest precedence:

2.4.1 `core.excludesFile` → `$HORIZON_ROOT\.gitignore_global` — machine-global baseline patterns (secrets, common noise). Applies to all repos on the machine, not just the OS repo.

2.4.2 `.git/info/exclude` — machine-local, not committed. Populated automatically by the pre-commit hook from `.gitignore.user`. Do not edit this file manually; edit `.gitignore.user` instead.

2.4.3 `$HORIZON_ROOT\.gitignore` — system-level OS repo patterns. Comprehensive coverage of secrets, Python, Node, Godot, .NET, AI/ML artifacts, OS noise. Includes the `.claude/` surgical override. Managed as part of the AIOS system.

2.4.4 `$HORIZON_ROOT\.gitignore.user` — user personal patterns. Edit this freely. Changes are applied via `.git/info/exclude` on the next commit.

2.5 **`core.hooksPath`**

Git's `core.hooksPath` is set to `./horizon_system/harness_configs/git/hooks` in the repo-local config (`.git/config`). This tells Git to use the hooks stored in the repository rather than `.git/hooks/`, making hook changes version-controlled and portable. This setting is machine-local (not committed) and must be set once per machine:

```bash
git config --local core.hooksPath ./horizon_system/harness_configs/git/hooks
```

2.6 **Pre-commit hook detail**

The hook at `horizon_system/harness_configs/git/hooks/pre-commit` is a bash script that:

2.6.1 Resolves the repo root with `git rev-parse --show-toplevel`.

2.6.2 Runs `find` from the repo root with `-mindepth 2 -name '.git' -type d` to locate all nested repos. For each, derives the relative path of the containing directory and checks `git ls-files` to see if anything from that directory is currently indexed.

2.6.3 If tracked files are found in a nested repo directory, runs `git rm -r --cached <dir>` and logs a message to the terminal.

2.6.4 Reads `$HORIZON_ROOT/.gitignore.user` and writes its full contents (with a sync timestamp header) to `$HORIZON_ROOT/.git/info/exclude`.

2.6.5 Exits 0 in all cases — the hook never blocks a commit. Removal of nested repos and ignore sync happen silently unless removals are detected.

---

## 3. Path Dependencies Catalog

Every file in the repository that contains a hardcoded path referencing `$HORIZON_ROOT` is listed here. When setting up a new machine, every entry must be updated to the new machine's root path before first use.

3.1 **`$HORIZON_ROOT\.claude\settings.json`** — permissions only; **no `$HORIZON_ROOT` path dependencies** to update per machine.

The committed devroot file owns permissions only. The global `~/.claude/settings.json` (copied from the template) references the machine-local `aios-exec` wrapper at `~/.horizon/bin/aios-exec.{ps1,sh}` — a home-relative path, not a `$HORIZON_ROOT` path. The wrapper resolves the active AIOS at run time, so statusLine and the hook sound paths need no per-machine substitution. Only the `AIOS_EXEC_WRAPPER` placeholder is substituted once at setup. See §1.4.2 and `documentation/system/aios_switching.md`.

3.2 **`$HORIZON_ROOT\horizon_system\bin\statusline\statusline-context-alerts.ps1`** (Windows path)

3.2.1 No hardcoded sound paths — sound resolution is delegated to `resolve_sound.py` via `$HORIZON_BIN`. The script derives `$HORIZON_BIN` from its own location (`$PSScriptRoot`), so no per-machine substitution is needed.

3.3 **`$HORIZON_ROOT/horizon_system/bin/statusline/statusline-command.sh`** (Linux/macOS path)

3.3.1 Threshold audio section references `play_sound.sh` and `horizon_system/sounds/claude_event_sounds/` via relative path from `$SCRIPT_DIR`. No absolute path — resolves correctly on any machine without substitution.

3.4 **`$HORIZON_ROOT\horizon_system\harness_configs\git\gitconfig`**

3.4.1 `[core] excludesfile` — path to `.gitignore_global` at the repository root. Controls machine-global git ignore patterns.

3.4.2 `[user]` block — name, email, and GPG signing key fingerprint. Must be updated to the new user's identity on each machine.

3.5 **`$HORIZON_ROOT/.claude/CLAUDE.md`**

3.5.1 `$HORIZON_ROOT/.claude/CLAUDE.md` — contains absolute `@` import paths to invariant docs.
Must be updated on each new machine to use the local `$HORIZON_ROOT` path.

---

## 4. `settings.json` Structure

This section describes the **global** Claude Code configuration file at `~/.claude/settings.json`, which is created by copying `horizon_system\templates\claude_code\settings.json` with the `AIOS_EXEC_WRAPPER` placeholder substituted. It is machine-local and not committed. It is a separate file from the committed `$HORIZON_ROOT\.claude\settings.json`, which owns devroot-scoped permissions only (see §1.4.2). statusLine and hooks dispatch through the `aios-exec` wrapper, which resolves the active AIOS at run time, so this file is AIOS-independent.

4.1 **`permissions`** — controls which tool calls Claude Code approves automatically without prompting.

4.1.1 `permissions.allow` — array of tool permission strings. Each entry matches a tool call pattern (e.g., `Bash(git add *)`, `Grep`). Matched calls are auto-approved.

4.1.2 `permissions.defaultMode` — set to `"acceptEdits"`. File edits (Read, Edit, Write) are auto-accepted; shell commands not in the allow list still prompt.

4.2 **`statusLine`** — configures the persistent statusline at the bottom of the Claude Code terminal.

4.2.1 `statusLine.type` — set to `"command"`. An external command produces the statusline string.

4.2.2 `statusLine.command` — invokes the `aios-exec` wrapper with the `statusline` action (`powershell.exe -NonInteractive -File '<wrapper>' statusline`). The wrapper sources the active AIOS's `active_env` and runs that AIOS's `statusline-context-alerts.ps1`. Claude Code pipes a JSON object to stdin; the wrapper forwards it and displays the script's stdout as the statusline.

4.3 **`hooks`** — shell commands executed by the Claude Code harness at lifecycle events. Hooks run outside Claude's context and fire regardless of session state.

4.3.1 `hooks.Stop` — fires when Claude finishes a turn successfully. Invokes `aios-exec … hook-stop`, which logs the event and plays the task-complete sound via `Media.SoundPlayer` (synchronous).

4.3.2 `hooks.PermissionRequest` — fires when Claude Code needs to prompt for a tool permission. Marked `async: true` so it does not block the prompt UI. Invokes `aios-exec … hook-permission`, which logs the event and plays the input-needed sound.

4.3.3 `hooks.StopFailure` — fires when Claude stops due to an API error or unrecoverable failure. Invokes `aios-exec … hook-stopfailure`, which logs the event and plays the api-error sound.

4.4 **`effortLevel`** — set to `"medium"`. Controls Claude's default reasoning depth. Valid values: `"low"`, `"medium"`, `"high"`.

4.5 **`theme`** — set to `"dark"`. Claude Code terminal color theme.

4.6 **`verbose`** — set to `true`. Shows additional tool call detail in the terminal.

---

## 5. CLAUDE.md Structure

`$HORIZON_ROOT\.claude\CLAUDE.md` is the global AI instruction file. It is loaded into every Claude Code session. `~/.claude/CLAUDE.md` contains only an `@include` pointing to this file.

5.1 **Agent delegation model** — instructs Claude that the main session is an orchestrator, not a worker. All file reading, code writing, and tool-heavy work should be delegated to subagents. The main session decomposes tasks, spawns agents, and synthesizes results.

5.1.1 Defines the agent team pattern for complex tasks: Orchestration agent → Log reader agent (if needed) → Planner agent → Implementer agent → Validator agent.

5.1.2 Agents should be self-sufficient and only return to the main session when the user needs to be informed or a decision requires user input.

5.2 **List formatting** — instructs Claude to always use hierarchical numbered format (`1.`, `1.1`, `1.1.1`). Never bullet points, never lettered lists.

5.3 To add or change global instructions: edit `$HORIZON_ROOT\.claude\CLAUDE.md` and commit. The change takes effect in the next Claude Code session.

---

## 6. Statusline Configuration

`$HORIZON_ROOT\horizon_system\bin\statusline\statusline-context-alerts.ps1` is the active statusline script. Claude Code invokes it on every statusline refresh, piping session data to stdin.

6.1 **Input** — Claude Code writes a JSON object to the script's stdin:

6.1.1 `context_window.used_percentage` — context usage as a float (0–100).

6.1.2 `session_id` — unique identifier for the current session. Used to track which audio thresholds have already fired.

6.1.3 `cwd` — current working directory path.

6.1.4 `model.display_name` — the active model's display name, rendered in the statusline.

6.2 **Output** — the script writes a single line to stdout. Claude Code displays it as the statusline. Format: `[dirname] <model> git:branch Context Window: [####--42%--] Estimated % To Compact: N%`

6.2.1 `[dirname]` — leaf name of the current working directory.

6.2.2 `<model>` — the active model's display name (`model.display_name`).

6.2.3 `git:branch` — current git branch, omitted if the directory is not a git repo.

6.2.4 `Context Window: [context bar]` — labeled 20-character bar overlaid with the usage percentage. `#` = used context, `-` = available.

6.2.5 `Estimated % To Compact: N%` — estimated remaining headroom before auto-compact, computed as `compact_threshold - used_percentage` (floored at 0; default `compact_threshold` = 80). The real auto-compact trigger point is not exposed in Claude Code's statusline JSON, so this is intentionally approximate; tune `compact_threshold` in `aios_statusline.conf`.

6.3 **Threshold audio system** — when context usage crosses 30, 40, 50, 60, 70, 80, or 90 percent, the script plays the corresponding `.wav` file from `horizon_system\sounds\claude_event_sounds\`. Each threshold fires at most once per session.

6.3.1 State is tracked in `$env:TEMP\claude_ctx_{session_id}.txt` containing the highest threshold fired so far.

6.3.2 The script checks `Test-Path` before playing. If the wav file is missing, it skips audio silently and continues rendering the statusline.

6.4 **Bash variant** — `horizon_system\bin\statusline\statusline-command.sh` is an alternative statusline script that adds cost estimation and ANSI color output. It is not currently wired into `settings.json` but can replace the PowerShell script by updating `statusLine.command`.

---

## 7. Adding a New Machine

To bring a new machine into Horizon AIOS, follow the full setup in `horizon_system\documentation\getting_started\ReadMeToSetupYourSystem.md`. The essential sequence is summarized here.

7.1 Clone the repository to the desired `$HORIZON_ROOT` path.

7.2 Run the two bootstrap commands:

```powershell
Set-Content -Path "$HOME\.claude\CLAUDE.md" -Value "@$HORIZON_ROOT\.claude\CLAUDE.md"
# Global settings.json is a template copy pointed at the aios-exec wrapper (not a hard link):
python "$HORIZON_SYSTEM\sbin\horizon_aios_switch.py" init
$wrapper = ("$HOME\.horizon\bin\aios-exec.ps1") -replace '\\','/'
Copy-Item "$HORIZON_SYSTEM\templates\claude_code\settings.json" "$HOME\.claude\settings.json"
(Get-Content "$HOME\.claude\settings.json") -replace "AIOS_EXEC_WRAPPER", $wrapper | Set-Content "$HOME\.claude\settings.json"
```

7.3 The machine-local settings.json uses the AIOS-independent `aios-exec` wrapper (set in step 7.2) — no per-machine path substitution is needed for it. Framework files in the repo derive their root from their own location. If you later move the cloned repo to a different path, run `horizon_aios_relocate.py --apply` to update all machine-local instance pointers (registry, active_env, CLAUDE.md redirect, aios_local.conf). The Path Dependencies Catalog (section 3) lists the files the tool updates.

7.4 Update `horizon_system\harness_configs\git\gitconfig` with the new machine's user identity (name, email, GPG key fingerprint) and the correct `excludesfile` path.

7.5 Apply the portable git config:

```bash
git config --global include.path "$HORIZON_ROOT/horizon_system/harness_configs/git/gitconfig"
```

7.6 Initialize the OS repo and wire the hooks:

```bash
cd "$HORIZON_ROOT"
git init
git config --local core.hooksPath ./horizon_system/harness_configs/git/hooks
git add .claude/CLAUDE.md .claude/settings.json horizon_system/ handoffs/ .gitignore .gitignore.user
git commit -m "Initial Horizon AIOS OS layer commit"
```

7.7 Create a fresh `settings.local.json` — do not copy from another machine:

```json
{
  "permissions": {
    "allow": []
  }
}
```

7.8 Add any personal ignore patterns to `.gitignore.user` and commit. The pre-commit hook syncs them to `.git/info/exclude` automatically.

7.9 Verify: launch Claude Code, confirm the statusline renders, confirm sounds fire on stop and permission request, and confirm `git log --show-signature -1` shows a valid GPG signature. Or run `horizon_aios_doctor.py --post-setup` to automate these post-install checks: it validates `commit.gpgsign` (the signed-commit / DCO requirement, P.4), checks the statusline dispatcher `statusline.sh` (P.8.2) rather than the `settings.json` wiring, and plays a test sound while respecting the `sounds_enabled` master/project mute switch in `aios_sounds.conf` (P.8.4) — a muted config is reported as a clean SKIP.
