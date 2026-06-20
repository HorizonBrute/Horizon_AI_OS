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
# -----------------------------------------------------------------------------
$HORIZON_BIN    = $PSScriptRoot
$HORIZON_ROOT   = Split-Path $HORIZON_BIN -Parent
$HORIZON_ETC    = Join-Path $HORIZON_BIN "ai_os_etc"
$HORIZON_DOCS   = Join-Path $HORIZON_BIN "documentation"

$env:HORIZON_ROOT  = $HORIZON_ROOT
$env:HORIZON_BIN   = $HORIZON_BIN
$env:HORIZON_ETC   = $HORIZON_ETC
$env:HORIZON_DOCS  = $HORIZON_DOCS

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
Write-Host "    `$env:HORIZON_ROOT = `"$HORIZON_ROOT`""
Write-Host "    `$env:HORIZON_BIN  = `"`$env:HORIZON_ROOT\horizon_bin`""
Write-Host "    `$env:HORIZON_ETC  = `"`$env:HORIZON_BIN\ai_os_etc`""
Write-Host "    `$env:HORIZON_DOCS = `"`$env:HORIZON_BIN\documentation`""
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

$SkillsSrc = Join-Path $HORIZON_BIN "skills"
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

    Get-ChildItem -Path $SkillsSrc -Filter "*.md" | ForEach-Object {
        $srcFile = $_.FullName
        $filename = $_.Name
        $dstFile = Join-Path $SkillsDst $filename

        if (Test-Path $dstFile) {
            $srcContent = Get-Content $srcFile -Raw
            $dstContent = Get-Content $dstFile -Raw
            if ($srcContent -eq $dstContent) {
                Ok "  $filename — already up to date, skipping."
                $SkippedCount++
            } else {
                Warn "  $filename — destination differs from source."
                $answer = if ($YesAll) { "y" } else { Read-Host "    Overwrite $dstFile? [y/N]" }
                if ($answer -eq "y" -or $answer -eq "Y") {
                    Copy-Item $srcFile $dstFile -Force
                    Ok "  $filename — overwritten."
                    $SkillCount++
                } else {
                    Warn "  $filename — skipped (keeping existing)."
                    $SkippedCount++
                }
            }
        } else {
            Copy-Item $srcFile $dstFile
            Ok "  $filename — copied."
            $SkillCount++
        }
    }

    Info "Skills deploy complete: $SkillCount copied, $SkippedCount skipped."
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
$SettingsTemplate = Join-Path $HORIZON_BIN "templates\claude_code\settings.json"

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
            $substituted = $templateContent -replace [regex]::Escape("HORIZON_BIN_PATH"), $HORIZON_BIN
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
$HooksPath = "./horizon_bin/harness_configs/git/hooks"

if (Test-Path $GitDir) {
    git -C $HORIZON_ROOT config core.hooksPath $HooksPath
    Ok "Set git core.hooksPath to: $HooksPath"

    # Install commit-msg hook (DCO sign-off enforcement)
    Copy-Item "$HORIZON_BIN\harness_configs\git\hooks\commit-msg" "$HORIZON_ROOT\.git\hooks\commit-msg" -Force
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

# Check 2: handoff.md deployed
$handoffMd = Join-Path $HOME ".claude\skills\handoff.md"
if (Test-Path $handoffMd) {
    PassCheck "~/.claude/skills/handoff.md exists"
} else {
    FailCheck "~/.claude/skills/handoff.md not found"
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
$confTemplate = Join-Path $HORIZON_BIN "templates\aios_local.conf.template"

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
$logsDir = Join-Path $HORIZON_ROOT "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    Write-Host "Created logs/ directory." -ForegroundColor Green
}

$setupSched = if ($YesAll) { $true } else { (Read-Host "Set up daily auto-sync from upstream? [y/N]") -match '^[Yy]' }
if ($setupSched) {
    $schedScript = Join-Path $HORIZON_BIN "setup_sync_schedule.py"
    python $schedScript $(if ($YesAll) { "--yes" })
} else {
    Write-Host "Skipped. Run later: python $HORIZON_BIN\setup_sync_schedule.py"
}
