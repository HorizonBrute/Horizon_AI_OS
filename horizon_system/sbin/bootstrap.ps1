# =============================================================================
# Horizon AIOS — Bootstrap Script (PowerShell)
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
# Resolve HORIZON_ROOT from script location
# Script lives at horizon_system/sbin/ — go up two levels to reach repo root.
# -----------------------------------------------------------------------------
$HORIZON_SYSTEM   = Split-Path $PSScriptRoot -Parent
$HORIZON_ROOT     = Split-Path $HORIZON_SYSTEM -Parent
$HORIZON_BIN      = Join-Path $HORIZON_SYSTEM "bin"
$HORIZON_ETC      = Join-Path $HORIZON_SYSTEM "ai_os_etc"
$HORIZON_DOCS     = Join-Path $HORIZON_SYSTEM "documentation"
$HORIZON_USRBIN   = Join-Path $HORIZON_ROOT "usrbin"
$HORIZON_PROJECTS = Join-Path $HORIZON_ROOT "Projects"
$HORIZON_KEYS     = Join-Path $HORIZON_ROOT "keys"

$env:HORIZON_SYSTEM   = $HORIZON_SYSTEM
$env:HORIZON_ROOT     = $HORIZON_ROOT
$env:HORIZON_BIN      = $HORIZON_BIN
$env:HORIZON_ETC      = $HORIZON_ETC
$env:HORIZON_DOCS     = $HORIZON_DOCS
$env:HORIZON_USRBIN   = $HORIZON_USRBIN
$env:HORIZON_PROJECTS = $HORIZON_PROJECTS
$env:HORIZON_KEYS     = $HORIZON_KEYS

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
Write-Host "  HORIZON_ROOT  = $HORIZON_ROOT"
Write-Host "  HORIZON_BIN   = $HORIZON_BIN"
Write-Host "  HORIZON_ETC   = $HORIZON_ETC"
Write-Host "  HORIZON_DOCS  = $HORIZON_DOCS"

Write-Host ""
Write-Host "Add the following to your PowerShell profile (`$PROFILE):"
Write-Host "  (Replace the HORIZON_ROOT value with your actual path if different)"
Write-Host ""
Write-Host "    `$env:HORIZON_ROOT     = `"$HORIZON_ROOT`""
Write-Host "    `$env:HORIZON_SYSTEM   = `"`$env:HORIZON_ROOT\horizon_system`""
Write-Host "    `$env:HORIZON_BIN      = `"`$env:HORIZON_SYSTEM\bin`""
Write-Host "    `$env:HORIZON_ETC      = `"`$env:HORIZON_SYSTEM\ai_os_etc`""
Write-Host "    `$env:HORIZON_DOCS     = `"`$env:HORIZON_SYSTEM\documentation`""
Write-Host "    `$env:HORIZON_USRBIN   = `"`$env:HORIZON_ROOT\usrbin`""
Write-Host "    `$env:HORIZON_PROJECTS = `"`$env:HORIZON_ROOT\Projects`""
Write-Host "    `$env:HORIZON_KEYS     = `"`$env:HORIZON_ROOT\keys`""
Write-Host ""
Write-Host "  Then reload your profile: . `$PROFILE"

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
        Ok "~/.claude/CLAUDE.md already contains an @ redirect — skipping."
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
        Warn "Not overwriting — update manually if needed."
    }
} else {
    Set-Content -Path $ClaudeMd -Value $ExpectedRedirect -Encoding UTF8
    Ok "Created ~/.claude/CLAUDE.md with @ redirect to repo CLAUDE.md."
}

# -----------------------------------------------------------------------------
# SECTION 3: Deploy skills
# -----------------------------------------------------------------------------
Banner "SECTION 3: Deploy skills"

# Skills live in horizon_system/skills_bin/<name>/SKILL.md (directory per skill).
# Deploy by copying each skill directory into ~/.claude/skills/.
$SkillsSrc = Join-Path $HORIZON_SYSTEM "skills_bin"
$SkillsDst = Join-Path $HOME ".claude\skills"

if (-not (Test-Path $SkillsSrc)) {
    Warn "Skills source directory not found: $SkillsSrc"
    Warn "Skipping skills deploy."
} else {
    if (-not (Test-Path $SkillsDst)) {
        New-Item -ItemType Directory -Path $SkillsDst -Force | Out-Null
    }

    $SkillCount   = 0
    $SkippedCount = 0

    Get-ChildItem -Path $SkillsSrc -Directory | ForEach-Object {
        $skillName = $_.Name
        $srcDir    = $_.FullName
        $dstDir    = Join-Path $SkillsDst $skillName

        if (Test-Path $dstDir) {
            # Compare SKILL.md content
            $srcMd = Get-Content (Join-Path $srcDir "SKILL.md") -Raw -ErrorAction SilentlyContinue
            $dstMd = Get-Content (Join-Path $dstDir "SKILL.md") -Raw -ErrorAction SilentlyContinue
            if ($srcMd -eq $dstMd) {
                Ok "  $skillName — already up to date, skipping."
                $SkippedCount++
            } else {
                Warn "  $skillName — destination differs from source."
                $answer = if ($YesAll) { "y" } else { Read-Host "    Overwrite $dstDir? [y/N]" }
                if ($answer -eq "y" -or $answer -eq "Y") {
                    Copy-Item $srcDir $dstDir -Recurse -Force
                    Ok "  $skillName — overwritten."
                    $SkillCount++
                } else {
                    Warn "  $skillName — skipped (keeping existing)."
                    $SkippedCount++
                }
            }
        } else {
            Copy-Item $srcDir $dstDir -Recurse
            Ok "  $skillName — deployed."
            $SkillCount++
        }
    }

    Info "Skills deploy complete: $SkillCount deployed, $SkippedCount skipped."
}

# -----------------------------------------------------------------------------
# SECTION 4: Create handoffs directory
# -----------------------------------------------------------------------------
Banner "SECTION 4: Handoffs directory"

$HandoffsDir = Join-Path $HORIZON_ROOT "handoffs"

if (Test-Path $HandoffsDir) {
    Ok "Handoffs directory already exists: $HandoffsDir"
} else {
    New-Item -ItemType Directory -Path $HandoffsDir -Force | Out-Null
    Ok "Created handoffs directory: $HandoffsDir"
}

# -----------------------------------------------------------------------------
# SECTION 5: ~/.claude/settings.json
# -----------------------------------------------------------------------------
Banner "SECTION 5: ~/.claude/settings.json"

$SettingsDst      = Join-Path $HOME ".claude\settings.json"
$SettingsTemplate = Join-Path $HORIZON_SYSTEM "templates\claude_code\settings.json"

if (Test-Path $SettingsDst) {
    Info "~/.claude/settings.json already exists."
    Info "Review $SettingsTemplate and merge any new entries manually."
    Info "See $HORIZON_DOCS\getting_started\ReadMeToSetupYourSystem.md Step 8 for the hard-link approach."
} else {
    if (Test-Path $SettingsTemplate) {
        Write-Host ""
        Write-Host "  No ~/.claude/settings.json found."
        Write-Host "  The template is at: $SettingsTemplate"
        $answer = if ($YesAll) { "y" } else { Read-Host "  Copy template to ~/.claude/settings.json? [y/N]" }
        if ($answer -eq "y" -or $answer -eq "Y") {
            $templateContent = Get-Content $SettingsTemplate -Raw
            $substituted = $templateContent -replace [regex]::Escape("HORIZON_BIN_PATH"), $HORIZON_BIN -replace [regex]::Escape("HORIZON_SYSTEM_PATH"), $HORIZON_SYSTEM
            Set-Content -Path $SettingsDst -Value $substituted -Encoding UTF8
            Ok "Copied template to ~/.claude/settings.json (HORIZON_BIN_PATH substituted)."
            Warn "Review ~/.claude/settings.json — some paths may still need manual adjustment."
            Warn "See $HORIZON_DOCS\getting_started\ReadMeToSetupYourSystem.md Step 8 for path substitution details."
        } else {
            Info "Skipping settings.json — create it manually from the template."
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
} else {
    Info "$HORIZON_ROOT is not a git repository — skipping git hooks config."
}

# -----------------------------------------------------------------------------
# SECTION 7: Verification
# -----------------------------------------------------------------------------
Banner "SECTION 7: Verification"

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

# Check 2: handoff skill deployed (directory with SKILL.md)
$handoffSkill = Join-Path $HOME ".claude\skills\handoff\SKILL.md"
if (Test-Path $handoffSkill) {
    PassCheck "~/.claude/skills/handoff/SKILL.md exists"
} else {
    FailCheck "~/.claude/skills/handoff/SKILL.md not found"
}

# Check 3: handoffs directory exists
$handoffsPath = Join-Path $HORIZON_ROOT "handoffs"
if (Test-Path $handoffsPath) {
    PassCheck "`$HORIZON_ROOT/handoffs/ exists"
} else {
    FailCheck "`$HORIZON_ROOT/handoffs/ not found"
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
# SECTION 8: Local Config and Sync Schedule
# -----------------------------------------------------------------------------
Banner "SECTION 8: Local Config and Sync Schedule"

Write-Host ""
Write-Host "=== Section 8: Local Config and Sync Schedule ===" -ForegroundColor Cyan

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
    Write-Host "aios_local.conf already exists — skipping template copy." -ForegroundColor Green
}

# Ensure logs directory exists
$logsDir = Join-Path $HORIZON_SYSTEM "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    Write-Host "Created logs/ directory." -ForegroundColor Green
}

$setupSched = if ($YesAll) { $true } else { (Read-Host "Set up daily auto-sync from upstream? [y/N]") -match '^[Yy]' }
if ($setupSched) {
    $schedScript = Join-Path $HORIZON_SYSTEM "sbin\setup_sync_schedule.py"
    python $schedScript $(if ($YesAll) { "--yes" })
} else {
    Write-Host "Skipped. Run later: python $HORIZON_SYSTEM\sbin\setup_sync_schedule.py"
}
