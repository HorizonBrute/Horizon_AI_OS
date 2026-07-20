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

# Capture script-level args (inside functions $args refers to the function's
# own args, so snapshot them here for the onboarding flags below).
$ScriptArgs = $args

# Parse --yes / -y flag
$YesAll = $ScriptArgs -contains "--yes" -or $ScriptArgs -contains "-y"

# -----------------------------------------------------------------------------
# Onboarding flags (SECTION 10 - secure-by-onboarding: humans group + lanes)
#   --profile server|workstation   deployment profile (gates human enrollment)
#   --humans <name|sid> [<...>]    human accounts to enroll into horizon_humans
#   --add-human <name|sid>         enroll one human and exit (management mode)
# A human may be an account NAME or a raw SID - cloud/AzureAD identities surface
# as SIDs (e.g. a Windows 365 cloud user), and Add-LocalGroupMember takes either.
# -----------------------------------------------------------------------------
$ProfileVal  = $null
$AddHumanVal = $null
$HumansList  = @()
# Nightly maintenance (doctor report + harden re-assert) is installed by default;
# -NoNightly opts out. Recorded in the deployment marker (nightly_maintenance).
$NightlyMaintenance = $true
for ($i = 0; $i -lt $ScriptArgs.Count; $i++) {
    switch ($ScriptArgs[$i]) {
        "--profile"   { if ($i + 1 -lt $ScriptArgs.Count) { $ProfileVal  = $ScriptArgs[$i + 1]; $i++ } }
        "--add-human" { if ($i + 1 -lt $ScriptArgs.Count) { $AddHumanVal = $ScriptArgs[$i + 1]; $i++ } }
        "--humans"    { while ($i + 1 -lt $ScriptArgs.Count -and $ScriptArgs[$i + 1] -notlike "-*") { $HumansList += $ScriptArgs[$i + 1]; $i++ } }
        "-NoNightly"  { $NightlyMaintenance = $false }
        "--no-nightly" { $NightlyMaintenance = $false }
    }
}

# AIOS-managed group for flesh-and-blood human operators.
$HUMANS_GROUP      = "horizon_humans"
$HUMANS_GROUP_DESC = "Horizon.AIOS Actual Humans"

# -----------------------------------------------------------------------------
# Require Administrator - horizon_aios_harden.py (run below) needs elevated privileges
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
$HORIZON_SBIN     = Join-Path $HORIZON_SYSTEM "sbin"
$HORIZON_ETC      = Join-Path $HORIZON_SYSTEM "ai_os_etc"
$HORIZON_DOCS     = Join-Path $HORIZON_SYSTEM "documentation"
$HORIZON_USRBIN   = Join-Path $HORIZON_ROOT "usrbin"
$HORIZON_PROJECTS = Join-Path $HORIZON_ROOT "projects"
$HORIZON_LOGS     = Join-Path $HORIZON_SYSTEM "logs"
$HORIZON_SOUNDS   = Join-Path $HORIZON_SYSTEM "sounds"

$env:HORIZON_SYSTEM   = $HORIZON_SYSTEM
$env:HORIZON_ROOT     = $HORIZON_ROOT
$env:HORIZON_BIN      = $HORIZON_BIN
$env:HORIZON_SBIN     = $HORIZON_SBIN
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
# Onboarding helpers: horizon_humans group, human enrollment, deployment marker.
# add_human is a FUNCTION of onboarding (not a separate script) - see -add-human.
# -----------------------------------------------------------------------------
$DeployMarker = Join-Path $HORIZON_ROOT ".horizon_aios_deployment.json"

function Ensure-HumansGroup {
    if (-not (Get-LocalGroup -Name $HUMANS_GROUP -ErrorAction SilentlyContinue)) {
        New-LocalGroup -Name $HUMANS_GROUP -Description $HUMANS_GROUP_DESC | Out-Null
        Ok "Created group: $HUMANS_GROUP ($HUMANS_GROUP_DESC)"
    } else {
        Info "Group already exists: $HUMANS_GROUP"
    }
}

function Enroll-Human([string]$member) {
    # $member = account name OR raw SID (cloud/AzureAD identities are SIDs).
    try {
        Add-LocalGroupMember -Group $HUMANS_GROUP -Member $member -ErrorAction Stop
        Ok "Enrolled human into ${HUMANS_GROUP}: $member"
        return $true
    } catch {
        if ($_.Exception.Message -match "already a member") {
            Info "Already enrolled in ${HUMANS_GROUP}: $member"; return $true
        }
        Warn "Could not enroll '$member' into ${HUMANS_GROUP}: $($_.Exception.Message)"
        return $false
    }
}

function Read-DeploymentMarker {
    if (Test-Path $DeployMarker) {
        try { return (Get-Content $DeployMarker -Raw | ConvertFrom-Json) } catch { return $null }
    }
    return $null
}

function Write-DeploymentMarker([string]$profile, [string[]]$humans) {
    # Records profile + enrolled humans (incl. cloud SIDs) so re-runs and
    # create_brain/doctor agree. Holds a real personal SID -> gitignored (sec 6).
    $obj = [ordered]@{
        source       = "Horizon.AIOS"
        profile      = $profile
        humans_group = $HUMANS_GROUP
        humans       = @($humans)
        nightly_maintenance = [bool]$NightlyMaintenance
        updated_utc  = (Get-Date).ToUniversalTime().ToString("o")
    }
    ($obj | ConvertTo-Json) | Set-Content -Path $DeployMarker -Encoding UTF8
    Ok "Wrote deployment marker: $DeployMarker"
}

# --- Management mode: `bootstrap.ps1 --add-human <name|sid>` enrolls one human
#     and exits, without re-running the whole install. Administrator manages
#     membership from here after onboarding. ---
if ($AddHumanVal) {
    Banner "Add human operator to $HUMANS_GROUP"
    Ensure-HumansGroup
    if (Enroll-Human $AddHumanVal) {
        $existing = Read-DeploymentMarker
        $profile  = if ($existing -and $existing.profile) { $existing.profile } else { "workstation" }
        $humans   = @()
        if ($existing -and $existing.humans) { $humans += $existing.humans }
        if ($humans -notcontains $AddHumanVal) { $humans += $AddHumanVal }
        # Preserve a prior nightly_maintenance opt-out across --add-human re-runs.
        if ($existing -and ($existing.PSObject.Properties.Name -contains 'nightly_maintenance')) {
            $NightlyMaintenance = [bool]$existing.nightly_maintenance
        }
        Write-DeploymentMarker $profile $humans
        Info "Note: horizon_humans is Read-Only on brains/ by design (elevate to admin or change permissions to write there)."
        exit 0
    }
    exit 1
}

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
    Info "Docker mode: HORIZON_* env vars are set in the Dockerfile - no profile changes needed."
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
# We redirect the directory itself (symlink) so changes are live immediately.
# AIOS requires admin installation, so mklink /D (directory symlink) is valid.
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
                Warn "~/.claude/skills/ is a symlink but points elsewhere: $target"
                $answer = if ($YesAll) { "y" } else { Read-Host "  Replace symlink? [y/N]" }
                if ($answer -eq "y" -or $answer -eq "Y") {
                    [System.IO.Directory]::Delete($SkillsDst, $false)
                    New-Item -ItemType SymbolicLink -Path $SkillsDst -Target $SkillsSrc | Out-Null
                    Ok "Updated symlink: ~/.claude/skills/ -> skills_sbin/"
                } else {
                    Warn "Skipping skills redirect."
                }
            }
        } else {
            $contents = @(Get-ChildItem $SkillsDst -ErrorAction SilentlyContinue)
            if ($contents.Count -eq 0) {
                Remove-Item $SkillsDst
                New-Item -ItemType SymbolicLink -Path $SkillsDst -Target $SkillsSrc | Out-Null
                Ok "Created symlink: ~/.claude/skills/ -> skills_sbin/"
            } else {
                Warn "~/.claude/skills/ is a real directory with $($contents.Count) item(s)."
                Warn "Cannot auto-redirect. Manually empty or remove it, then re-run bootstrap."
            }
        }
    } else {
        New-Item -ItemType SymbolicLink -Path $SkillsDst -Target $SkillsSrc | Out-Null
        Ok "Created symlink: ~/.claude/skills/ -> skills_sbin/"
    }
}

# Register machine-local user skills (usrbin/usr_skills -> skills_sbin symlinks).
# Best-effort: never abort bootstrap if python is missing or no user skills exist.
$RegScript = Join-Path $HORIZON_SYSTEM "sbin\horizon_aios_register_user_skills.py"
if (Test-Path $RegScript) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python $RegScript
        if ($LASTEXITCODE -eq 0) { Ok "Registered machine-local user skills." }
        else { Warn "horizon_aios_register_user_skills.py exited with code $LASTEXITCODE." }
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
# horizon_aios_switch.py and $HORIZON_DOCS/system/aios_switching.md.
# -----------------------------------------------------------------------------
Banner "SECTION 5: settings.json + AIOS indirection layer"

# 5a: AIOS registry + active_env + wrappers (idempotent; self-heals registry).
$SwitchScript = Join-Path $HORIZON_SYSTEM "sbin\horizon_aios_switch.py"
if (Test-Path $SwitchScript) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python $SwitchScript init
        if ($LASTEXITCODE -eq 0) { Ok "AIOS registry + indirection layer initialized." }
        else { Warn "horizon_aios_switch.py init exited with code $LASTEXITCODE." }
    } else {
        Warn "python not found - skipping AIOS registry init. Run later: python $SwitchScript init"
    }
} else {
    Warn "horizon_aios_switch.py not found at $SwitchScript - skipping AIOS registry init."
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

            # Provenance stamp: record the SHA-256 of the EXACT settings.json bytes we
            # just wrote. uninstall.ps1 Section 5 reads this to prove bootstrap created
            # settings.json and the user has not modified it since. We only write the
            # stamp on the branch where bootstrap actually CREATES settings.json (here);
            # a pre-existing user settings.json gets no stamp, so uninstall preserves it.
            # Contract (must match uninstall.ps1 reader byte-for-byte):
            #   path   : ~/.claude/.horizon-settings.stamp
            #   format : one line, lowercase SHA-256 hex of settings.json's on-disk bytes
            $SettingsStamp = Join-Path $HOME ".claude\.horizon-settings.stamp"
            $digest = (Get-FileHash -Path $SettingsDst -Algorithm SHA256).Hash.ToLower()
            Set-Content -Path $SettingsStamp -Value $digest -NoNewline -Encoding ascii
            Ok "Wrote provenance stamp ~/.claude/.horizon-settings.stamp (SHA-256 of settings.json)."
        } else {
            Info "Skipping settings.json - create it manually from the template."
        }
    } else {
        Warn "Template not found: $SettingsTemplate"
        Warn "Create ~/.claude/settings.json manually. See $HORIZON_DOCS\getting_started\ReadMeToSetupYourSystem.md Step 8."
    }
}

# 5c: Redirect ~/.claude/projects into $HORIZON_ROOT/memory (owner harness memory).
# Migrates the Claude harness's per-project state into the AIOS so memory is
# owned by the OS layer. The script symlinks ~/.claude/projects -> $HORIZON_ROOT/
# memory, backing up any existing real directory first. Idempotent: re-running
# no-ops if already redirected, so it is safe to always call.
# NOTE: Have Claude Code closed when bootstrap runs - the script moves the live
# projects directory (it leaves a backup if one was present).
$RedirectMemoryScript = Join-Path $HORIZON_SYSTEM "sbin\horizon_aios_redirect_memory.py"
if (Test-Path $RedirectMemoryScript) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python $RedirectMemoryScript
        if ($LASTEXITCODE -eq 0) { Ok "~/.claude/projects redirected to `$HORIZON_ROOT/memory." }
        else { Warn "horizon_aios_redirect_memory.py exited with code $LASTEXITCODE." }
    } else {
        Warn "python not found - skipping memory redirect. Run later: python $RedirectMemoryScript"
    }
} else {
    Warn "horizon_aios_redirect_memory.py not found at $RedirectMemoryScript - skipping memory redirect."
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

# 6b: .gitignore.user - the pre-commit hook syncs this file into
# .git/info/exclude. Seed it from the template so a fresh install is
# doctor-clean (horizon_aios_doctor.py checks $HORIZON_ROOT/.gitignore.user).
# Idempotent: never overwrite an existing file (it holds user-local patterns).
$GitignoreUser     = Join-Path $HORIZON_ROOT ".gitignore.user"
$GitignoreTemplate = Join-Path $HORIZON_ROOT ".gitignore.user.template"
if (Test-Path $GitignoreUser) {
    Info ".gitignore.user already exists - skipping template copy."
} elseif (Test-Path $GitignoreTemplate) {
    Copy-Item $GitignoreTemplate $GitignoreUser
    Ok "Created .gitignore.user from template."
} else {
    Warn "Template not found: $GitignoreTemplate - create .gitignore.user manually."
}

# -----------------------------------------------------------------------------
# SECTION 7: System PATH + HORIZON_* Machine-scope environment
# Adds $HORIZON_SYSTEM\bin to the Machine-scope PATH so brain accounts and new
# shells can run AIOS commands without manually editing PATH.
# Removes any stale horizon_system\bin entry first (handles AIOS switching).
#
# Also registers HORIZON_ROOT + the derived vars at MACHINE scope so EVERY
# account on the box (brains, service accounts, new users) inherits them - not
# just the owner whose profile sources active_env. active_env still overrides
# in the owner's live shells (so 'aios switch' repoints without a restart);
# these Machine vars are the system-wide baseline.
# -----------------------------------------------------------------------------
Banner "SECTION 7: System PATH + HORIZON_* environment"

$MachinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$PathEntries = $MachinePath -split ";" | ForEach-Object { $_.TrimEnd('\').TrimEnd('/') }

# Remove stale entries: any path ending with horizon_system\bin (case-insensitive)
$Cleaned = $PathEntries | Where-Object {
    $_ -notmatch '(?i)horizon_system[/\\]bin$'
}

$BinPath = $HORIZON_BIN.TrimEnd('\')

if ($Cleaned -contains $BinPath) {
    Ok "System PATH already contains: $BinPath - no change needed."
} else {
    $NewPath = ($Cleaned + @($BinPath)) -join ";"
    [System.Environment]::SetEnvironmentVariable("Path", $NewPath, "Machine")
    Ok "Added to system PATH: $BinPath"
}

# Refresh current session PATH so the change is immediately visible
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
Ok "Refreshed session PATH."

# Register HORIZON_* at Machine scope (system-wide baseline for all accounts).
$MachineEnv = [ordered]@{
    HORIZON_SYSTEM   = $HORIZON_SYSTEM
    HORIZON_ROOT     = $HORIZON_ROOT
    HORIZON_BIN      = $HORIZON_BIN
    HORIZON_SBIN     = $HORIZON_SBIN
    HORIZON_ETC      = $HORIZON_ETC
    HORIZON_DOCS     = $HORIZON_DOCS
    HORIZON_USRBIN   = $HORIZON_USRBIN
    HORIZON_PROJECTS = $HORIZON_PROJECTS
    HORIZON_LOGS     = $HORIZON_LOGS
    HORIZON_SOUNDS   = $HORIZON_SOUNDS
}
try {
    foreach ($name in $MachineEnv.Keys) {
        [System.Environment]::SetEnvironmentVariable($name, $MachineEnv[$name], "Machine")
    }
    Ok "Registered HORIZON_* at Machine scope (inherited by all accounts)."
} catch {
    Warn "Could not set Machine-scope HORIZON_* env (need Administrator): $($_.Exception.Message)"
}

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

# Check 2: ~/.claude/skills/ is a symlink to skills_sbin/
$skillsItem = Get-Item (Join-Path $HOME ".claude\skills") -ErrorAction SilentlyContinue
if ($skillsItem -and ($skillsItem.LinkType -eq "Junction" -or $skillsItem.LinkType -eq "SymbolicLink")) {
    PassCheck "~/.claude/skills/ redirected to skills_sbin/ (symlink)"
} else {
    FailCheck "~/.claude/skills/ is not a symlink - skills redirect not set up"
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
    Warn "git user.name or user.email not set - DCO sign-off lines will be malformed."
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
        $schedScript = Join-Path $HORIZON_SYSTEM "sbin\horizon_aios_setup_sync_schedule.py"
        python $schedScript $(if ($YesAll) { "--yes" })
    } else {
        Write-Host "Skipped. Run later: python $HORIZON_SYSTEM\sbin\horizon_aios_setup_sync_schedule.py"
    }
}

# -----------------------------------------------------------------------------
# Nightly maintenance schedule (ON BY DEFAULT) - a nightly task (doctor report +
# harden re-assert) so routine drift self-corrects. Opt out with -NoNightly.
# Non-fatal: a skipped/failed schedule install does not fail bootstrap. Separate
# from the opt-in upstream-sync scheduler above.
# -----------------------------------------------------------------------------
$MaintSched = Join-Path $HORIZON_SYSTEM "sbin\horizon_aios_setup_maintenance_schedule.py"
if ($env:AIOS_DEPLOY_MODE -eq "docker") {
    Info "Docker mode: skipping nightly maintenance schedule (run maintenance at the container/host layer)."
} elseif (-not $NightlyMaintenance) {
    Info "Nightly maintenance schedule opted out (-NoNightly). Enable later: python $MaintSched --yes"
} elseif (-not (Test-Path $MaintSched)) {
    Warn "horizon_aios_setup_maintenance_schedule.py not found - skipping nightly maintenance setup."
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python $MaintSched --yes
    if ($LASTEXITCODE -eq 0) { Ok "Nightly maintenance schedule installed (doctor report + harden re-assert, ~03:00)." }
    else { Warn "Nightly maintenance schedule install did not complete. Run later: python $MaintSched --yes" }
} else {
    Warn "python not found - skipping nightly maintenance schedule. Run later: python $MaintSched --yes"
}

# -----------------------------------------------------------------------------
# SECTION 10: Onboarding - secure by implementation
# There is no separate "hardening step": onboarding IS the security boundary.
# It always (a) creates the brains + horizon_humans groups and applies the
# uniform ACL model via the horizon_aios_harden.py engine, then (b) asks whether
# this is a server or an active-use workstation and enrolls human operators into
# horizon_humans accordingly. The infrastructure (groups + ACLs) is built even
# with zero humans defined - an empty horizon_humans grants nobody, so a server
# reduces to "only owner/SYSTEM/Administrators write" with no separate code path.
# FATAL: engine failure exits non-zero - the ACL model is a security requirement.
# -----------------------------------------------------------------------------
Banner "SECTION 10: Onboarding (groups + ACL model + human enrollment)"

# (a) Apply the uniform ACL model. The engine creates both groups and sets every
#     ACE (root inheritance broken + re-granted; humans Full on the tree,
#     Read-Only on brains/; brains denied on sbin/skills_sbin/logs).
$HardenScript = Join-Path $HORIZON_SYSTEM "sbin\horizon_aios_harden.py"
if (Test-Path $HardenScript) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python $HardenScript
        if ($LASTEXITCODE -eq 0) { Ok "AIOS ACL model applied (brains + horizon_humans)." }
        else {
            Err "horizon_aios_harden.py exited with code $LASTEXITCODE - ACL model FAILED. The system is NOT secured."
            Err "Re-run bootstrap elevated and review the output before using this installation."
            exit 1
        }
    } else {
        Err "python not found - cannot run horizon_aios_harden.py. ACL model FAILED. The system is NOT secured."
        Err "Install Python 3.6+ and re-run bootstrap elevated: python $HardenScript"
        exit 1
    }
} else {
    Err "horizon_aios_harden.py not found at $HardenScript - ACL model FAILED. The system is NOT secured."
    exit 1
}

# (b) Deployment profile - gates human enrollment (NOT the ACLs; those are
#     uniform). Server: enroll nobody (horizon_humans stays empty -> only admins
#     write). Workstation: enroll the human operator accounts.
$existingMarker = Read-DeploymentMarker
if (-not $ProfileVal) {
    if ($YesAll) {
        # Non-interactive: reuse a prior choice, else default to the safer
        # superset (workstation keeps humans able to work without being admins).
        $ProfileVal = if ($existingMarker -and $existingMarker.profile) { $existingMarker.profile } else { "workstation" }
        Info "Non-interactive: deployment profile = $ProfileVal (override with --profile server|workstation)."
    } else {
        Write-Host ""
        Write-Host "  Is this primarily a SERVER, or an active-use WORKSTATION with human users?"
        Write-Host "    [S] Server      - no non-admin humans; horizon_humans stays empty (only admins write)"
        Write-Host "    [W] Workstation - enroll human operator accounts into horizon_humans"
        $ans = Read-Host "  Enter S or W [W]"
        $ProfileVal = if ($ans -match '^[Ss]') { "server" } else { "workstation" }
    }
}

# Assemble the human enrollment set: any prior marker humans + supplied --humans.
$humansToEnroll = @()
if ($existingMarker -and $existingMarker.humans) { $humansToEnroll += $existingMarker.humans }
if ($HumansList.Count -gt 0) { $humansToEnroll += $HumansList }

if ($ProfileVal -eq "workstation") {
    if ($humansToEnroll.Count -eq 0 -and -not $YesAll) {
        Write-Host ""
        Write-Host "  Enter the human account(s) to grant AIOS access - names or SIDs,"
        Write-Host "  space-separated. Cloud/AzureAD users appear as SIDs. Leave blank to skip."
        $raw = Read-Host "  Humans"
        if ($raw.Trim()) { $humansToEnroll += ($raw -split '[\s,]+' | Where-Object { $_ }) }
    }
    $humansToEnroll = @($humansToEnroll | Select-Object -Unique)
    Ensure-HumansGroup
    foreach ($h in $humansToEnroll) { Enroll-Human $h | Out-Null }
    if ($humansToEnroll.Count -eq 0) {
        Warn "Workstation profile but no humans enrolled yet. Add later: bootstrap.ps1 --add-human <name|sid>"
    } else {
        Info "horizon_humans has Full control of the tree but is Read-Only on brains/ (elevate/re-perm to write there)."
    }
} else {
    Info "Server profile: no humans enrolled. horizon_humans stays empty (only owner/SYSTEM/Administrators write)."
    $humansToEnroll = @($humansToEnroll | Select-Object -Unique)  # preserve any prior entries
}

Write-DeploymentMarker $ProfileVal $humansToEnroll

# -----------------------------------------------------------------------------
# SECTION 11: Filesystem monitor service (boot + hourly watchdog)
# Registers the audit monitor to start at reboot (AIOSMonitor) plus an hourly
# watchdog (AIOSMonitorWatchdog) that restarts it if the process has stopped.
# Optional but recommended - audit logging is the detection layer for prompt
# injection. Non-fatal: a skipped/failed monitor does not fail bootstrap.
# -----------------------------------------------------------------------------
Banner "SECTION 11: Filesystem monitor service"

$MonitorSetup = Join-Path $HORIZON_SYSTEM "sbin\horizon_aios_setup_monitor_service.py"
if (-not (Test-Path $MonitorSetup)) {
    Warn "horizon_aios_setup_monitor_service.py not found - skipping monitor service setup."
} elseif ($env:AIOS_DEPLOY_MODE -eq "docker") {
    Info "Docker mode: skipping monitor service (handle monitoring at the container layer)."
} else {
    $setupMon = if ($YesAll) { $true } else { (Read-Host "Install the filesystem monitor to start on boot + hourly watchdog? [y/N]") -match '^[Yy]' }
    if ($setupMon) {
        if (Get-Command python -ErrorAction SilentlyContinue) {
            if ($YesAll) { python $MonitorSetup install --yes } else { python $MonitorSetup install }
            if ($LASTEXITCODE -eq 0) {
                Ok "Filesystem monitor installed (AIOSMonitor at startup; hourly AIOSMonitorWatchdog restarts it if stopped)."
            } else {
                Warn "Monitor service install did not complete (exit $LASTEXITCODE). Run later (elevated): python $MonitorSetup install"
            }
        } else {
            Warn "python not found - skipping monitor service. Run later: python $MonitorSetup install"
        }
    } else {
        Info "Skipped. Enable later: python $MonitorSetup install"
    }
}
