# =============================================================================
# Horizon AIOS - Bootstrap Script (PowerShell)
# Sets up a new machine with all required Horizon AIOS configuration.
# Safe to run multiple times (idempotent). Non-destructive by default.
#
# Usage:
#   .\bootstrap.ps1          # interactive
#   .\bootstrap.ps1 --yes   # non-interactive, accept all prompts
#   .\bootstrap.ps1 -y      # same as --yes
#
# Works on: Windows PowerShell 5.1+, PowerShell 7+
# =============================================================================

$ErrorActionPreference = "Stop"

# Parse --yes / -y flag
$YesAll = $args -contains "--yes" -or $args -contains "-y"

# -----------------------------------------------------------------------------
# Require Administrator — harden_aios.py (run below) needs elevated privileges
# to set filesystem ACLs.  Fail fast rather than let the user discover this
# mid-run at Section 9.
# -----------------------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host ""
    Write-Host "  [ERR] Bootstrap must be run as Administrator." -ForegroundColor Red
    Write-Host "  Right-click PowerShell and choose 'Run as administrator', then re-run:"
    Write-Host "    .\bootstrap.ps1" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# -----------------------------------------------------------------------------
# Resolve HORIZON_ROOT from script location
# Script lives at horizon_system/sbin/ - go up two levels to reach repo root.
# -----------------------------------------------------------------------------
$HORIZON_SYSTEM   = Split-Path $PSScriptRoot -Parent
$HORIZON_ROOT     = Split-Path $HORIZON_SYSTEM -Parent
$HORIZON_BIN      = Join-Path $HORIZON_SYSTEM "bin"
$HORIZON_ETC      = Join-Path $HORIZON_SYSTEM "ai_os_etc"
$HORIZON_DOCS     = Join-Path $HORIZON_SYSTEM "documentation"
$HORIZON_USRBIN   = Join-Path $HORIZON_ROOT "usrbin"
$HORIZON_PROJECTS = Join-Path $HORIZON_ROOT "Projects"
$HORIZON_LOGS     = Join-Path $HORIZON_SYSTEM "logs"
$HORIZON_SOUNDS   = Join-Path $HORIZON_SYSTEM "sounds"

$env:HORIZON_SYSTEM   = $HORIZON_SYSTEM
$env:HORIZON_ROOT     = $HORIZON_ROOT
$env:HORIZON_BIN      = $HORIZON_BIN
$env:HORIZON_ETC      = $HORIZON_ETC
$env:HORIZON_DOCS     = $HORIZON_DOCS
$env:HORIZON_USRBIN   = $HORIZON_USRBIN
$env:HORIZON_PROJECTS = $HORIZON_PROJECTS
$env:HORIZON_LOGS     = $HORIZON_LOGS
$env:HORIZON_SOUNDS   = $HORIZON_SOUNDS

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
$PassCount = 0
$FailCount = 0

function Banner($title) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "  $title"
    Write-Host "============================================================"
}

function Ok($msg)   { Write-Host "  [OK]   $msg" }
function Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Info($msg) { Write-Host "  [INFO] $msg" }
function Err($msg)  { Write-Host "  [ERR]  $msg" -ForegroundColor Red }

function PassCheck($msg) { Write-Host "  [PASS] $msg" -ForegroundColor Green; $script:PassCount++ }
function FailCheck($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red;   $script:FailCount++ }

# -----------------------------------------------------------------------------
# SECTION 1: Environment Variables
# -----------------------------------------------------------------------------
Banner "SECTION 1: Environment Variables"

Write-Host ""
Write-Host "Resolved paths:"
Write-Host "  HORIZON_ROOT    = $HORIZON_ROOT"
Write-Host "  HORIZON_BIN     = $HORIZON_BIN"
Write-Host "  HORIZON_ETC     = $HORIZON_ETC"
Write-Host "  HORIZON_DOCS    = $HORIZON_DOCS"
Write-Host "  HORIZON_LOGS    = $HORIZON_LOGS"
Write-Host "  HORIZON_SOUNDS  = $HORIZON_SOUNDS"

if ($env:AIOS_DEPLOY_MODE -eq "docker") {
    Info "Docker mode: HORIZON_* env vars are set in the Dockerfile — no profile changes needed."
} else {
    Write-Host ""
    Write-Host "Add ONE line to your PowerShell profile (`$PROFILE) to load the active AIOS:"
    Write-Host "  (Section 5 generates this file; the AIOS switcher regenerates it on switch.)"
    Write-Host ""
    Write-Host "    . `"`$HOME\.horizon\active_env.ps1`""
    Write-Host ""
    Write-Host "  This sets HORIZON_ROOT + all derived vars for whichever AIOS is active,"
    Write-Host "  so 'aios switch <name>' repoints your shell without editing your profile."
    Write-Host "  Then reload your profile: . `$PROFILE"
}

# -----------------------------------------------------------------------------
# SECTION 2: ~/.claude/CLAUDE.md stub
# -----------------------------------------------------------------------------
Banner "SECTION 2: ~/.claude/CLAUDE.md stub"

$ClaudeHomeDir    = Join-Path $HOME ".claude"
$ClaudeMd         = Join-Path $ClaudeHomeDir "CLAUDE.md"
$RepoCLAUDEMd     = Join-Path $HORIZON_ROOT ".claude\CLAUDE.md"
$ExpectedRedirect = "@$RepoCLAUDEMd"

if (-not (Test-Path $ClaudeHomeDir)) {
    New-Item -ItemType Directory -Path $ClaudeHomeDir -Force | Out-Null
}

if (Test-Path $ClaudeMd) {
    $content = Get-Content $ClaudeMd -Raw
    if ($content -match "@" -and $content -match "CLAUDE\.md") {
        Ok "~/.claude/CLAUDE.md already contains an @ redirect - skipping."
        if ($content.Trim() -ne $ExpectedRedirect) {
            Warn "Existing redirect may point somewhere else:"
            Warn "  Current:  $($content.Trim())"
            Warn "  Expected: $ExpectedRedirect"
            Warn "If this is wrong, update ~/.claude/CLAUDE.md manually."
        }
    } else {
        Warn "~/.claude/CLAUDE.md exists but does not contain an @ redirect."
        Warn "  Current content: $($content.Trim())"
        Warn "  Expected:        $ExpectedRedirect"
        Warn "Not overwriting - update manually if needed."
    }
} else {
    Set-Content -Path $ClaudeMd -Value $ExpectedRedirect -Encoding UTF8
    Ok "Created ~/.claude/CLAUDE.md with @ redirect to repo CLAUDE.md."
}

# Owner-only AIOS development context: import the dev directives into the owner
# stub. Brains never import this (their brain_CLAUDE.md.template omits it), so
# AIOS-development rules stay out of brain/runtime context.
$DevContextImport = "@$HORIZON_ROOT\.claude\CLAUDE.aios-dev.md"
$stubContent = if (Test-Path $ClaudeMd) { Get-Content $ClaudeMd -Raw } else { "" }
if ($stubContent -notmatch [regex]::Escape("CLAUDE.aios-dev.md")) {
    Add-Content -Path $ClaudeMd -Value "" -Encoding UTF8
    Add-Content -Path $ClaudeMd -Value $DevContextImport -Encoding UTF8
    Ok "Added owner-only AIOS development context import to ~/.claude/CLAUDE.md."
} else {
    Ok "~/.claude/CLAUDE.md already imports AIOS development context."
}

# -----------------------------------------------------------------------------
# SECTION 3: Redirect ~/.claude/skills/ to skills_sbin/
# Primary user is AIOS root - all skills live in skills_sbin/.
# We redirect the directory itself (junction) so changes are live immediately.
# Windows directory junctions do not require administrator rights.
# -----------------------------------------------------------------------------
Banner "SECTION 3: Skills redirect"

$SkillsSrc = Join-Path $HORIZON_SYSTEM "skills_sbin"
$SkillsDst = Join-Path $HOME ".claude\skills"

if (-not (Test-Path $SkillsSrc)) {
    Warn "skills_sbin not found: $SkillsSrc - skipping skills redirect."
} else {
    if (Test-Path $SkillsDst) {
        $item = Get-Item $SkillsDst -ErrorAction SilentlyContinue
        if ($item.LinkType -eq "Junction" -or $item.LinkType -eq "SymbolicLink") {
            $target = $item.Target
            if ($target -eq $SkillsSrc) {
                Ok "~/.claude/skills/ already redirected to skills_sbin/ - OK."
            } else {
                Warn "~/.claude/skills/ is a junction but points elsewhere: $target"
                $answer = if ($YesAll) { "y" } else { Read-Host "  Replace junction? [y/N]" }
                if ($answer -eq "y" -or $answer -eq "Y") {
                    [System.IO.Directory]::Delete($SkillsDst, $false)
                    New-Item -ItemType Junction -Path $SkillsDst -Target $SkillsSrc | Out-Null
                    Ok "Updated junction: ~/.claude/skills/ → skills_sbin/"
                } else {
                    Warn "Skipping skills redirect."
                }
            }
        } else {
            $contents = @(Get-ChildItem $SkillsDst -ErrorAction SilentlyContinue)
            if ($contents.Count -eq 0) {
                Remove-Item $SkillsDst
                New-Item -ItemType Junction -Path $SkillsDst -Target $SkillsSrc | Out-Null
                Ok "Created junction: ~/.claude/skills/ → skills_sbin/"
            } else {
                Warn "~/.claude/skills/ is a real directory with $($contents.Count) item(s)."
                Warn "Cannot auto-redirect. Manually empty or remove it, then re-run bootstrap."
            }
        }
    } else {
        New-Item -ItemType Junction -Path $SkillsDst -Target $SkillsSrc | Out-Null
        Ok "Created junction: ~/.claude/skills/ → skills_sbin/"
    }
}

# Register machine-local user skills (usrbin/usr_skills -> skills_sbin junctions).
# Best-effort: never abort bootstrap if python is missing or no user skills exist.
$RegScript = Join-Path $HORIZON_SYSTEM "sbin\register_user_skills.py"
if (Test-Path $RegScript) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python $RegScript
        if ($LASTEXITCODE -eq 0) { Ok "Registered machine-local user skills." }
        else { Warn "register_user_skills.py exited with code $LASTEXITCODE." }
    } else {
        Warn "python not found - skipping user-skill registration. Run later: python $RegScript"
    }
}

# -----------------------------------------------------------------------------
# SECTION 4: Create handoffs and objectives directories
# -----------------------------------------------------------------------------
Banner "SECTION 4: Handoffs and objectives directories"

$HandoffsDir = Join-Path $HORIZON_ROOT "handoffs"

if (Test-Path $HandoffsDir) {
    Ok "Handoffs directory already exists: $HandoffsDir"
} else {
    New-Item -ItemType Directory -Path $HandoffsDir -Force | Out-Null
    Ok "Created handoffs directory: $HandoffsDir"
}

$ObjectivesDir = Join-Path $HORIZON_ROOT "objectives"

if (Test-Path $ObjectivesDir) {
    Ok "Objectives directory already exists: $ObjectivesDir"
} else {
    New-Item -ItemType Directory -Path $ObjectivesDir -Force | Out-Null
    Ok "Created objectives directory: $ObjectivesDir"
}

# -----------------------------------------------------------------------------
# SECTION 5: settings.json + AIOS indirection layer
# Initializes the machine-local AIOS registry (~/.horizon/) and generates the
# active_env snippet + aios-exec wrappers, then wires settings.json at the
# stable wrapper so switching AIOS never rewrites settings.json. See
# aios_switch.py and $HORIZON_DOCS/system/aios_switching.md.
# -----------------------------------------------------------------------------
Banner "SECTION 5: settings.json + AIOS indirection layer"

# 5a: AIOS registry + active_env + wrappers (idempotent; self-heals registry).
$SwitchScript = Join-Path $HORIZON_SYSTEM "sbin\aios_switch.py"
if (Test-Path $SwitchScript) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python $SwitchScript init
        if ($LASTEXITCODE -eq 0) { Ok "AIOS registry + indirection layer initialized." }
        else { Warn "aios_switch.py init exited with code $LASTEXITCODE." }
    } else {
        Warn "python not found - skipping AIOS registry init. Run later: python $SwitchScript init"
    }
} else {
    Warn "aios_switch.py not found at $SwitchScript - skipping AIOS registry init."
}

# 5b: settings.json points at the stable, AIOS-independent wrapper. Use forward
# slashes so the path is valid inside JSON (backslashes form invalid JSON escape
# sequences); powershell.exe -File accepts forward slashes on Windows.
$AiosExecWrapper  = (Join-Path $HOME ".horizon\bin\aios-exec.ps1") -replace '\\', '/'
$SettingsDst      = Join-Path $HOME ".claude\settings.json"
$SettingsTemplate = Join-Path $HORIZON_SYSTEM "templates\claude_code\settings.json"

if (Test-Path $SettingsDst) {
    Info "~/.claude/settings.json already exists."
    Info "To use the AIOS switcher, point statusLine + hooks at the wrapper:"
    Info "  $AiosExecWrapper  (actions: statusline, hook-stop, hook-permission, hook-stopfailure)"
    Info "Compare with $SettingsTemplate and merge manually."
} else {
    if (Test-Path $SettingsTemplate) {
        Write-Host ""
        Write-Host "  No ~/.claude/settings.json found."
        Write-Host "  The template is at: $SettingsTemplate"
        $answer = if ($YesAll) { "y" } else { Read-Host "  Copy template to ~/.claude/settings.json? [y/N]" }
        if ($answer -eq "y" -or $answer -eq "Y") {
            $templateContent = Get-Content $SettingsTemplate -Raw
            $substituted = $templateContent -replace [regex]::Escape("AIOS_EXEC_WRAPPER"), $AiosExecWrapper
            Set-Content -Path $SettingsDst -Value $substituted -Encoding UTF8
            Ok "Copied template to ~/.claude/settings.json (pointed at aios-exec wrapper)."
            Info "settings.json now resolves the active AIOS at run time - switching never rewrites it."
        } else {
            Info "Skipping settings.json - create it manually from the template."
        }
    } else {
        Warn "Template not found: $SettingsTemplate"
        Warn "Create ~/.claude/settings.json manually. See $HORIZON_DOCS\getting_started\ReadMeToSetupYourSystem.md Step 8."
    }
}

# -----------------------------------------------------------------------------
# SECTION 6: Git hooks path
# -----------------------------------------------------------------------------
Banner "SECTION 6: Git hooks"

$GitDir    = Join-Path $HORIZON_ROOT ".git"
$HooksPath = "./horizon_system/harness_configs/git/hooks"

if (Test-Path $GitDir) {
    git -C $HORIZON_ROOT config core.hooksPath $HooksPath
    Ok "Set git core.hooksPath to: $HooksPath"

    # Install commit-msg hook (DCO sign-off enforcement)
    Copy-Item "$HORIZON_SYSTEM\harness_configs\git\hooks\commit-msg" "$HORIZON_ROOT\.git\hooks\commit-msg" -Force
    Ok "Installed commit-msg hook (DCO sign-off enforcement)."
    Copy-Item "$HORIZON_SYSTEM\harness_configs\git\hooks\pre-commit" "$HORIZON_ROOT\.git\hooks\pre-commit" -Force
    Ok "Installed pre-commit hook."
} else {
    Info "$HORIZON_ROOT is not a git repository - skipping git hooks config."
}

# -----------------------------------------------------------------------------
# SECTION 7: System PATH
# Adds $HORIZON_SYSTEM\bin to the Machine-scope PATH so brain accounts and new
# shells can run AIOS commands without manually editing PATH.
# Removes any stale horizon_system\bin entry first (handles AIOS switching).
# -----------------------------------------------------------------------------
Banner "SECTION 7: System PATH"

$MachinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$PathEntries = $MachinePath -split ";" | ForEach-Object { $_.TrimEnd('\').TrimEnd('/') }

# Remove stale entries: any path ending with horizon_system\bin (case-insensitive)
$Cleaned = $PathEntries | Where-Object {
    $_ -notmatch '(?i)horizon_system[/\\]bin$'
}

$BinPath = $HORIZON_BIN.TrimEnd('\')

if ($Cleaned -contains $BinPath) {
    Ok "System PATH already contains: $BinPath — no change needed."
} else {
    $NewPath = ($Cleaned + @($BinPath)) -join ";"
    [System.Environment]::SetEnvironmentVariable("Path", $NewPath, "Machine")
    Ok "Added to system PATH: $BinPath"
}

# Refresh current session PATH so the change is immediately visible
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
Ok "Refreshed session PATH."

# -----------------------------------------------------------------------------
# SECTION 8: Verification
# -----------------------------------------------------------------------------
Banner "SECTION 8: Verification"

Write-Host ""

# Check 1: ~/.claude/CLAUDE.md contains @ redirect
$claudeMdPath = Join-Path $HOME ".claude\CLAUDE.md"
if ((Test-Path $claudeMdPath)) {
    $c = Get-Content $claudeMdPath -Raw
    if ($c -match "@" -and $c -match "CLAUDE\.md") {
        PassCheck "~/.claude/CLAUDE.md contains @ redirect"
    } else {
        FailCheck "~/.claude/CLAUDE.md is missing or does not contain @ redirect"
    }
} else {
    FailCheck "~/.claude/CLAUDE.md not found"
}

# Check 2: ~/.claude/skills/ is a junction/symlink to skills_sbin/
$skillsItem = Get-Item (Join-Path $HOME ".claude\skills") -ErrorAction SilentlyContinue
if ($skillsItem -and ($skillsItem.LinkType -eq "Junction" -or $skillsItem.LinkType -eq "SymbolicLink")) {
    PassCheck "~/.claude/skills/ redirected to skills_sbin/ (junction)"
} else {
    FailCheck "~/.claude/skills/ is not a junction - skills redirect not set up"
}

# Check 3: handoffs directory exists
$handoffsPath = Join-Path $HORIZON_ROOT "handoffs"
if (Test-Path $handoffsPath) {
    PassCheck "`$HORIZON_ROOT/handoffs/ exists"
} else {
    FailCheck "`$HORIZON_ROOT/handoffs/ not found"
}

# Check 4: objectives directory exists
$objectivesPath = Join-Path $HORIZON_ROOT "objectives"
if (Test-Path $objectivesPath) {
    PassCheck "`$HORIZON_ROOT/objectives/ exists"
} else {
    FailCheck "`$HORIZON_ROOT/objectives/ not found"
}

# Check 5: git user.name and user.email set (required for DCO sign-off)
$gitUserName  = git config user.name 2>$null
$gitUserEmail = git config user.email 2>$null
if (-not $gitUserName -or -not $gitUserEmail) {
    Warn "git user.name or user.email not set — DCO sign-off lines will be malformed."
    Warn "  Fix: git config --global user.name `"Your Name`""
    Warn "       git config --global user.email `"you@example.com`""
} else {
    PassCheck "git user.name and user.email are set"
}

Write-Host ""
Write-Host "------------------------------------------------------------"
Write-Host "  Bootstrap complete: $PassCount passed, $FailCount failed"
Write-Host "------------------------------------------------------------"

if ($FailCount -gt 0) {
    Write-Host ""
    Warn "Some checks failed. Review the output above and resolve manually."
    Warn "See $HORIZON_DOCS\getting_started\ReadMeToSetupYourSystem.md for step-by-step instructions."
    exit 1
}

Write-Host ""
Ok "All checks passed. Horizon AIOS is bootstrapped on this machine."
Write-Host ""

# -----------------------------------------------------------------------------
# SECTION 9: Local Config and Sync Schedule
# -----------------------------------------------------------------------------
Banner "SECTION 9: Local Config and Sync Schedule"

$localConf = Join-Path $HORIZON_ETC "aios_local.conf"
$confTemplate = Join-Path $HORIZON_SYSTEM "templates\aios_local.conf.template"

if (-not (Test-Path $localConf)) {
    Write-Host "aios_local.conf not found."
    $copyConf = if ($YesAll) { $true } else { (Read-Host "Copy template to aios_local.conf? [y/N]") -match '^[Yy]' }
    if ($copyConf) {
        Copy-Item $confTemplate $localConf
        Write-Host "Created $localConf from template. Edit it to customize your settings." -ForegroundColor Green
    } else {
        Write-Host "Skipped. Run manually: Copy-Item $confTemplate $localConf"
    }
} else {
    Write-Host "aios_local.conf already exists - skipping template copy." -ForegroundColor Green
}

# Ensure logs directory exists at canonical location ($HORIZON_SYSTEM/logs/)
$logsDir = Join-Path $HORIZON_SYSTEM "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    Write-Host "Created logs/ directory." -ForegroundColor Green
}

if ($env:AIOS_DEPLOY_MODE -eq "docker") {
    Info "Docker mode: skipping sync schedule setup (refresh via image rebuild or pull)."
} else {
    $setupSched = if ($YesAll) { $true } else { (Read-Host "Set up daily auto-sync from upstream? [y/N]") -match '^[Yy]' }
    if ($setupSched) {
        $schedScript = Join-Path $HORIZON_SYSTEM "sbin\setup_sync_schedule.py"
        python $schedScript $(if ($YesAll) { "--yes" })
    } else {
        Write-Host "Skipped. Run later: python $HORIZON_SYSTEM\sbin\setup_sync_schedule.py"
    }
}

# -----------------------------------------------------------------------------
# SECTION 10: Harden AIOS layer ACLs (brains group)
# Enforces security_invariants.md §2/§3/§5 — brains denied on sbin/skills_sbin/
# logs, granted RX on bin/skills_bin, no write elsewhere in $HORIZON_SYSTEM.
# FATAL: harden_aios.py failure exits bootstrap non-zero — ACL hardening is a
# security requirement, not a best-effort step.
# -----------------------------------------------------------------------------
Banner "SECTION 10: Harden AIOS layer ACLs"

$HardenScript = Join-Path $HORIZON_SYSTEM "sbin\harden_aios.py"
if (Test-Path $HardenScript) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python $HardenScript
        if ($LASTEXITCODE -eq 0) { Ok "AIOS layer hardened (brains-group ACLs applied)." }
        else {
            Err "harden_aios.py exited with code $LASTEXITCODE — ACL hardening FAILED. The system is NOT secured."
            Err "Re-run bootstrap elevated and review harden_aios.py output before using this installation."
            exit 1
        }
    } else {
        Err "python not found — cannot run harden_aios.py. ACL hardening FAILED. The system is NOT secured."
        Err "Install Python 3.6+ and re-run bootstrap elevated: python $HardenScript"
        exit 1
    }
} else {
    Err "harden_aios.py not found at $HardenScript — ACL hardening FAILED. The system is NOT secured."
    exit 1
}
