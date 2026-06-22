# =============================================================================
# Horizon AIOS - Uninstall Script (PowerShell)
# Undoes everything bootstrap.ps1 does on this machine.
# Safe to run multiple times (idempotent). Non-destructive on user content.
#
# Usage:
#   .\uninstall.ps1 --dry-run # preview every action; change nothing (no elevation)
#   .\uninstall.ps1          # interactive — confirms each destructive step
#   .\uninstall.ps1 --yes   # non-interactive, accept all removals
#   .\uninstall.ps1 -y      # same as --yes
# Unknown arguments are rejected (exit 2) rather than silently ignored.
#
# Works on: Windows PowerShell 5.1+, PowerShell 7+
# Must be run as Administrator (same requirement as bootstrap).
#
# What this removes (mirrors bootstrap.ps1 section by section):
#   Section 2  — ~/.claude/CLAUDE.md redirect lines written by bootstrap
#   Section 3  — ~/.claude/skills/ junction and user-skill symlinks in skills_sbin/
#   Section 4  — $HORIZON_ROOT/handoffs/ and objectives/ (only if empty)
#   Section 5  — ~/.horizon/ tree (registry, active_env, wrappers), ~/.claude/settings.json
#   Section 5b — ~/.claude/projects junction (memory redirect); memory data left intact
#   Section 6  — .git/hooks/commit-msg, pre-commit; git core.hooksPath config
#   Section 7  — $HORIZON_BIN entry from Machine-scope PATH
#   Section 9  — $HORIZON_ETC/aios_local.conf, $HORIZON_SYSTEM/logs/ (only if empty)
#   Section 10 — brains-group ACEs removed from $HORIZON_SYSTEM subtrees
#                Advisory: 'brains' OS group left in place (may have brain members)
#
# What this does NOT remove (requires manual steps — see advisories printed below):
#   - Shell-profile line sourcing active_env.ps1 (user added this manually)
#   - Global git include.path pointing to harness_configs/git/gitconfig (user added manually)
#   - Optional sync schedule created by horizon_aios_setup_sync_schedule.py (separate opt-in)
#   - 'brains' OS group (may have brain OS users as members)
#   - Brain OS user accounts and their data (use horizon_aios_create_brain.py's remove flow)
#   - Python packages (watchdog, keyring) installed by the user
# =============================================================================

$ErrorActionPreference = "Stop"

# --- Parse arguments (reject unknown flags instead of silently dropping them) ---
function Show-Usage {
    Write-Host ""
    Write-Host "  Horizon AIOS uninstall — reverses the bootstrap footprint."
    Write-Host ""
    Write-Host "  Usage: .\uninstall.ps1 [--dry-run] [--yes]"
    Write-Host "    --dry-run        Preview every action; make no changes (no elevation needed)."
    Write-Host "    --yes, -y        Non-interactive; accept all removals without prompting."
    Write-Host "    --help, -h       Show this help and exit."
    Write-Host ""
}

$YesAll = $false
$DryRun = $false
foreach ($arg in $args) {
    switch ($arg) {
        "--yes"     { $YesAll = $true; break }
        "-y"        { $YesAll = $true; break }
        "--dry-run" { $DryRun = $true; break }
        "--help"    { Show-Usage; exit 0 }
        "-h"        { Show-Usage; exit 0 }
        default {
            Write-Host ""
            Write-Host "  [ERR] Unknown argument: $arg" -ForegroundColor Red
            Show-Usage
            exit 2
        }
    }
}

# --- Privilege check (a dry-run only previews, so it needs no elevation) ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin -and -not $DryRun) {
    Write-Host ""
    Write-Host "  [ERR] Uninstall must be run as Administrator (ACL removal requires elevation)." -ForegroundColor Red
    Write-Host "  Right-click PowerShell and choose 'Run as administrator', then re-run:"
    Write-Host "    .\uninstall.ps1" -ForegroundColor Cyan
    Write-Host "  Or preview without elevation:  .\uninstall.ps1 --dry-run" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}
if ($DryRun) {
    Write-Host ""
    Write-Host "  [DRY-RUN] Previewing actions only — no changes will be made." -ForegroundColor Magenta
    if (-not $isAdmin) {
        Write-Host "  [DRY-RUN] Not elevated; a real uninstall must be run as Administrator." -ForegroundColor Magenta
    }
}

# --- Resolve paths (same logic as bootstrap.ps1) ---
$HORIZON_SYSTEM   = Split-Path $PSScriptRoot -Parent
$HORIZON_ROOT     = Split-Path $HORIZON_SYSTEM -Parent
$HORIZON_BIN      = Join-Path $HORIZON_SYSTEM "bin"
$HORIZON_ETC      = Join-Path $HORIZON_SYSTEM "ai_os_etc"
$HORIZON_LOGS     = Join-Path $HORIZON_SYSTEM "logs"
$HORIZON_SBIN     = Join-Path $HORIZON_SYSTEM "sbin"

# --- Helpers ---
function Banner($title) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "  $title"
    Write-Host "============================================================"
}
function Ok($msg)      { Write-Host "  [OK]      $msg" -ForegroundColor Green }
function Warn($msg)    { Write-Host "  [WARN]    $msg" -ForegroundColor Yellow }
function Info($msg)    { Write-Host "  [INFO]    $msg" }
function Advisory($msg){ Write-Host "  [MANUAL]  $msg" -ForegroundColor Cyan }
function Err($msg)     { Write-Host "  [ERR]     $msg" -ForegroundColor Red }
function Skip($msg)    { Write-Host "  [SKIP]    $msg" }
function Dry($msg)     { Write-Host "  [DRY]     would $msg" -ForegroundColor Magenta }

function Confirm($prompt) {
    if ($YesAll) { return $true }
    $answer = Read-Host "  $prompt [y/N]"
    return ($answer -eq "y" -or $answer -eq "Y")
}

# =============================================================================
# SECTION 2: ~/.claude/CLAUDE.md — remove lines written by bootstrap
# Bootstrap writes: the @ redirect line and the @ CLAUDE.aios-dev.md import line.
# We strip only those lines; any content the user added is preserved.
# If the file becomes empty (or whitespace-only) after stripping, remove it.
# =============================================================================
Banner "SECTION 2: ~/.claude/CLAUDE.md cleanup"

$ClaudeMd = Join-Path $HOME ".claude\CLAUDE.md"
if (Test-Path $ClaudeMd) {
    $lines = Get-Content $ClaudeMd
    $filtered = $lines | Where-Object {
        # Remove the main redirect line (@ pointing to $HORIZON_ROOT/.claude/CLAUDE.md)
        ($_ -notmatch [regex]::Escape($HORIZON_ROOT) -or $_ -notmatch "CLAUDE\.md") -and
        # Remove the dev-context import line (@ pointing to CLAUDE.aios-dev.md)
        $_ -notmatch "CLAUDE\.aios-dev\.md"
    }
    # Also strip blank lines left at the top after removal
    $trimmed = ($filtered | Where-Object { $_.Trim() -ne "" })
    if ($DryRun) {
        if ($trimmed.Count -eq 0) {
            Dry "delete ~/.claude/CLAUDE.md (would be empty after removing bootstrap lines)."
        } else {
            Dry "strip bootstrap redirect lines from ~/.claude/CLAUDE.md (user content preserved)."
        }
    } elseif ($trimmed.Count -eq 0) {
        if (Confirm "~/.claude/CLAUDE.md will be empty after removing bootstrap lines — delete it?") {
            Remove-Item $ClaudeMd -Force
            Ok "Deleted ~/.claude/CLAUDE.md (was only bootstrap content)."
        } else {
            Set-Content -Path $ClaudeMd -Value "" -Encoding UTF8
            Ok "Cleared bootstrap lines from ~/.claude/CLAUDE.md (file kept, now empty)."
        }
    } else {
        Set-Content -Path $ClaudeMd -Value ($trimmed -join "`n") -Encoding UTF8
        Ok "Removed bootstrap redirect lines from ~/.claude/CLAUDE.md (user content preserved)."
    }
} else {
    Skip "~/.claude/CLAUDE.md not found — nothing to remove."
}

Advisory "If you added '. `$HOME\.horizon\active_env.ps1' to your PowerShell `$PROFILE, remove that line manually."

# =============================================================================
# SECTION 3: ~/.claude/skills/ junction and user-skill symlinks in skills_sbin/
# Bootstrap creates a junction from ~/.claude/skills/ → skills_sbin/.
# horizon_aios_register_user_skills.py creates symlinks inside skills_sbin/ pointing to usr_skills/.
# =============================================================================
Banner "SECTION 3: Skills junction and user-skill symlinks"

$SkillsDst    = Join-Path $HOME ".claude\skills"
$SkillsSbin   = Join-Path $HORIZON_SYSTEM "skills_sbin"
$UsrSkillsDir = Join-Path $HORIZON_ROOT "usrbin\usr_skills"

# Remove user-skill symlinks from skills_sbin/ (created by horizon_aios_register_user_skills.py)
if (Test-Path $SkillsSbin) {
    $staleLinks = Get-ChildItem $SkillsSbin -ErrorAction SilentlyContinue | Where-Object {
        ($_.LinkType -eq "SymbolicLink" -or $_.LinkType -eq "Junction") -and
        ($_.Target -like "*usr_skills*" -or $_.Target -like "*usrbin*")
    }
    foreach ($link in $staleLinks) {
        if ($DryRun) {
            Dry "remove user-skill symlink: $($link.Name)"
        } else {
            [System.IO.Directory]::Delete($link.FullName, $false)
            Ok "Removed user-skill symlink: $($link.Name)"
        }
    }
    if ($staleLinks.Count -eq 0) {
        Skip "No user-skill symlinks found in skills_sbin/."
    }
}

# Remove the ~/.claude/skills/ junction itself
if (Test-Path $SkillsDst) {
    $item = Get-Item $SkillsDst -ErrorAction SilentlyContinue
    if ($item.LinkType -eq "Junction" -or $item.LinkType -eq "SymbolicLink") {
        if ($DryRun) {
            Dry "remove ~/.claude/skills/ junction."
        } else {
            [System.IO.Directory]::Delete($SkillsDst, $false)
            Ok "Removed ~/.claude/skills/ junction."
        }
    } else {
        Warn "~/.claude/skills/ is a real directory (not a junction) — skipping removal."
        Warn "  If it was not created by bootstrap, manage it manually."
    }
} else {
    Skip "~/.claude/skills/ not found — nothing to remove."
}

# =============================================================================
# SECTION 4: handoffs/ and objectives/ directories
# Only removed if empty — they may contain user data.
# =============================================================================
Banner "SECTION 4: Handoffs and objectives directories"

foreach ($dirName in @("handoffs", "objectives")) {
    $dirPath = Join-Path $HORIZON_ROOT $dirName
    if (Test-Path $dirPath) {
        $contents = @(Get-ChildItem $dirPath -Recurse -ErrorAction SilentlyContinue)
        if ($contents.Count -eq 0) {
            if ($DryRun) {
                Dry "remove empty directory: $dirPath"
            } else {
                Remove-Item $dirPath -Force
                Ok "Removed empty directory: $dirPath"
            }
        } else {
            Warn "$dirPath contains $($contents.Count) item(s) — not removed."
            Advisory "Review and remove $dirPath manually if no longer needed."
        }
    } else {
        Skip "$dirPath not found — nothing to remove."
    }
}

# =============================================================================
# SECTION 5: ~/.horizon/ tree and ~/.claude/settings.json
# Bootstrap creates:
#   ~/.horizon/aios_registry.json
#   ~/.horizon/active_env.ps1
#   ~/.horizon/bin/aios-exec.ps1
#   ~/.horizon/bin/aios-exec.sh  (also written on Windows by horizon_aios_switch.py)
# And optionally:
#   ~/.claude/settings.json (copied from template)
# =============================================================================
Banner "SECTION 5: ~/.horizon/ tree and ~/.claude/settings.json"

$HorizonDir = Join-Path $HOME ".horizon"

if (Test-Path $HorizonDir) {
    if ($DryRun) {
        Dry "remove entire ~/.horizon/ directory (registry, active_env, wrappers)."
    } elseif (Confirm "Remove entire ~/.horizon/ directory (registry, active_env, wrappers)?") {
        Remove-Item $HorizonDir -Recurse -Force
        Ok "Removed ~/.horizon/."
    } else {
        Skip "Skipping ~/.horizon/ removal."
    }
} else {
    Skip "~/.horizon/ not found — nothing to remove."
}

$SettingsJson = Join-Path $HOME ".claude\settings.json"
if (Test-Path $SettingsJson) {
    Warn "~/.claude/settings.json exists."
    Warn "  Bootstrap may have created this from the template."
    if ($DryRun) {
        Dry "remove ~/.claude/settings.json."
    } elseif (Confirm "Remove ~/.claude/settings.json?") {
        Remove-Item $SettingsJson -Force
        Ok "Removed ~/.claude/settings.json."
    } else {
        Skip "Keeping ~/.claude/settings.json — remove manually if needed."
    }
} else {
    Skip "~/.claude/settings.json not found — nothing to remove."
}

# =============================================================================
# SECTION 5b: ~/.claude/projects memory redirect (reverses bootstrap 5c)
# Bootstrap junctions ~/.claude/projects → $HORIZON_ROOT/memory via
# horizon_aios_redirect_memory.py so the harness's per-project memory lives in the AIOS.
# We remove only the JUNCTION — never the memory target's contents (that data
# lives in $HORIZON_ROOT/memory, part of the repo). Mirrors the Section 3
# skills-junction removal: link-only delete, not confirm-gated.
# =============================================================================
Banner "SECTION 5b: ~/.claude/projects memory redirect"

$ProjectsLink = Join-Path $HOME ".claude\projects"
if (Test-Path $ProjectsLink) {
    $projItem = Get-Item $ProjectsLink -Force -ErrorAction SilentlyContinue
    if ($projItem -and ($projItem.LinkType -eq "Junction" -or $projItem.LinkType -eq "SymbolicLink")) {
        if ($DryRun) {
            Dry "remove ~/.claude/projects junction (memory redirect); memory data in `$HORIZON_ROOT/memory left intact."
        } else {
            [System.IO.Directory]::Delete($ProjectsLink, $false)
            Ok "Removed ~/.claude/projects junction (memory redirect) — memory data left intact."
        }
    } else {
        Warn "~/.claude/projects is a real directory (not a junction) — leaving as-is."
        Warn "  If bootstrap created it, manage it manually."
    }
} else {
    Skip "~/.claude/projects not found — nothing to remove."
}

# Advise about any pre-redirect backup horizon_aios_redirect_memory.py left behind
$ClaudeHome  = Join-Path $HOME ".claude"
$ProjBackups = @()
if (Test-Path $ClaudeHome) {
    $ProjBackups = @(Get-ChildItem $ClaudeHome -Directory -Filter "projects.backup-*" -ErrorAction SilentlyContinue)
}
foreach ($b in $ProjBackups) {
    Advisory "A pre-redirect harness-memory backup remains: $($b.FullName)"
}
if ($ProjBackups.Count -gt 0) {
    Advisory "  To restore it: with the junction removed (above), rename a backup back to ~/.claude/projects."
}

# =============================================================================
# SECTION 6: Git hooks and core.hooksPath
# Bootstrap installs .git/hooks/commit-msg and .git/hooks/pre-commit (copies)
# and sets git config core.hooksPath for the OS repo.
# =============================================================================
Banner "SECTION 6: Git hooks and core.hooksPath"

$GitDir = Join-Path $HORIZON_ROOT ".git"
if (Test-Path $GitDir) {
    # Remove the installed hook copies
    foreach ($hook in @("commit-msg", "pre-commit")) {
        $hookPath = Join-Path $HORIZON_ROOT ".git\hooks\$hook"
        if (Test-Path $hookPath) {
            if ($DryRun) {
                Dry "remove .git/hooks/$hook."
            } else {
                Remove-Item $hookPath -Force
                Ok "Removed .git/hooks/$hook."
            }
        } else {
            Skip ".git/hooks/$hook not found."
        }
    }

    # Unset core.hooksPath from local git config
    $currentHooksPath = git -C $HORIZON_ROOT config --local core.hooksPath 2>$null
    if ($currentHooksPath) {
        if ($DryRun) {
            Dry "unset git config core.hooksPath (currently: $currentHooksPath)."
        } else {
            git -C $HORIZON_ROOT config --local --unset core.hooksPath
            Ok "Unset git config core.hooksPath (was: $currentHooksPath)."
        }
    } else {
        Skip "git core.hooksPath not set in local config — nothing to unset."
    }
} else {
    Skip "$HORIZON_ROOT is not a git repository — skipping git hooks cleanup."
}

Advisory "If you set 'include.path' in your global gitconfig to point at harness_configs/git/gitconfig, remove that line manually."

# =============================================================================
# SECTION 7: Machine-scope PATH — remove HORIZON_BIN entry
# Bootstrap adds $HORIZON_BIN to the Machine-scope PATH.
# =============================================================================
Banner "SECTION 7: Machine-scope PATH"

$MachinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$PathEntries = $MachinePath -split ";" | ForEach-Object { $_.TrimEnd('\').TrimEnd('/') }
$BinPath     = $HORIZON_BIN.TrimEnd('\')

# Remove all entries that look like any horizon_system\bin (handles path variations)
$Cleaned = $PathEntries | Where-Object {
    $_ -notmatch '(?i)horizon_system[/\\]bin$'
}

if ($Cleaned.Count -lt $PathEntries.Count) {
    if ($DryRun) {
        $removed = $PathEntries | Where-Object { $_ -match '(?i)horizon_system[/\\]bin$' }
        Dry "remove horizon_system\bin entries from Machine-scope PATH: $($removed -join ', ')"
    } else {
        $NewPath = ($Cleaned | Where-Object { $_ -ne "" }) -join ";"
        [System.Environment]::SetEnvironmentVariable("Path", $NewPath, "Machine")
        Ok "Removed horizon_system\bin entries from Machine-scope PATH."
        # Refresh current session
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path", "User")
        Ok "Refreshed session PATH."
    }
} else {
    Skip "No horizon_system\bin entry found in Machine-scope PATH."
}

# =============================================================================
# SECTION 9: aios_local.conf and logs/ directory
# Bootstrap copies $HORIZON_ETC/aios_local.conf from template.
# Bootstrap creates $HORIZON_SYSTEM/logs/.
# =============================================================================
Banner "SECTION 9: aios_local.conf and logs/ directory"

$LocalConf = Join-Path $HORIZON_ETC "aios_local.conf"
if (Test-Path $LocalConf) {
    if ($DryRun) {
        Dry "remove $LocalConf (machine-local config)."
    } elseif (Confirm "Remove $LocalConf (machine-local config)?") {
        Remove-Item $LocalConf -Force
        Ok "Removed aios_local.conf."
    } else {
        Skip "Keeping aios_local.conf — remove manually if needed."
    }
} else {
    Skip "aios_local.conf not found — nothing to remove."
}

if (Test-Path $HORIZON_LOGS) {
    $logContents = @(Get-ChildItem $HORIZON_LOGS -Recurse -ErrorAction SilentlyContinue)
    if ($logContents.Count -eq 0) {
        if ($DryRun) {
            Dry "remove empty logs/ directory ($HORIZON_LOGS)."
        } else {
            Remove-Item $HORIZON_LOGS -Force
            Ok "Removed empty logs/ directory."
        }
    } else {
        Warn "logs/ contains $($logContents.Count) item(s) — not removed."
        Advisory "Review and remove $HORIZON_LOGS manually if logs are no longer needed."
    }
} else {
    Skip "logs/ directory not found — nothing to remove."
}

Advisory "If you set up a sync schedule with horizon_aios_setup_sync_schedule.py, remove the scheduled tasks manually:"
Advisory "  schtasks /Delete /TN 'HorizonAIOS_Sync' /F"
Advisory "  schtasks /Delete /TN 'HorizonAIOS_MaintainLogs' /F"

# =============================================================================
# SECTION 10: Revert brains-group ACEs on $HORIZON_SYSTEM
# We remove ACEs that horizon_aios_harden.py added; we do NOT remove the brains group
# itself because it may have brain OS user members.
# On Windows this uses icacls to strip the brains group from each directory.
# =============================================================================
Banner "SECTION 10: Remove brains-group ACEs"

$BrainsGroup = "brains"
$DirsToClean = @(
    $HORIZON_SYSTEM,
    $HORIZON_BIN,
    (Join-Path $HORIZON_SYSTEM "skills_bin"),
    $HORIZON_SBIN,
    (Join-Path $HORIZON_SYSTEM "skills_sbin"),
    $HORIZON_LOGS
)

$groupExists = $false
try {
    $null = Get-LocalGroup -Name $BrainsGroup -ErrorAction Stop
    $groupExists = $true
} catch {}

if ($groupExists) {
    foreach ($dir in $DirsToClean) {
        if (Test-Path $dir) {
            if ($DryRun) {
                Dry "remove brains-group ACEs from: $dir  (icacls /remove:g $BrainsGroup /T)"
            } else {
                # /remove:g removes all ACEs (grant and deny) for the group
                $result = icacls $dir /remove:g $BrainsGroup /T /C /Q 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Ok "Removed brains-group ACEs from: $dir"
                } else {
                    Warn "icacls returned non-zero for $dir — some ACEs may remain."
                    Warn "  $result"
                }
            }
        } else {
            Skip "$dir not found — skipping ACE removal."
        }
    }
    Advisory "The 'brains' OS group was left in place — it may have brain OS user members."
    Advisory "  To remove it: Remove-LocalGroup -Name 'brains'"
    Advisory "  Only do this after removing all brain OS user accounts."
} else {
    Skip "brains group does not exist — no ACEs to remove."
}

# =============================================================================
# SUMMARY
# =============================================================================
if ($DryRun) {
    Banner "Dry run complete — no changes were made"
    Write-Host ""
    Write-Host "  Re-run without --dry-run (as Administrator) to apply these actions."
    Write-Host ""
    exit 0
}

Banner "Uninstall complete"
Write-Host ""
Write-Host "  Horizon AIOS bootstrap footprint removed from this machine."
Write-Host ""
Write-Host "  Manual steps still required (see [MANUAL] advisories above):"
Write-Host "    1. Remove the active_env.ps1 source line from your PowerShell `$PROFILE"
Write-Host "    2. Remove the 'include.path' from your global gitconfig (if set)"
Write-Host "    3. Remove the sync scheduled task (if you set one up)"
Write-Host "    4. Remove the 'brains' OS group (if no brain accounts remain)"
Write-Host "    5. Remove any brain OS user accounts (use horizon_aios_create_brain.py remove flow)"
Write-Host ""
