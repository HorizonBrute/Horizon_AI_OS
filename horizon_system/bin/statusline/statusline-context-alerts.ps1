$raw = [Console]::In.ReadToEnd()
try { $json = $raw | ConvertFrom-Json } catch { Write-Output "ctx:?"; exit 0 }

$used_pct   = if ($json.context_window.used_percentage -ne $null) { [int]($json.context_window.used_percentage) } else { 0 }
$model      = if ($json.model.display_name -ne $null) { $json.model.display_name } else { "" }
$session_id = if ($json.session_id -ne $null) { $json.session_id } else { "unknown" }
$cwd        = if ($json.cwd -ne $null) { $json.cwd } else { (Get-Location).Path }
$HORIZON_BIN    = Split-Path $PSScriptRoot -Parent          # horizon_system/bin/
$HORIZON_SYSTEM = Split-Path $HORIZON_BIN -Parent           # horizon_system/
$HORIZON_ROOT   = Split-Path $HORIZON_SYSTEM -Parent        # repo root

# --- Load per-project statusline config ---
function Find-StatuslineConf($start) {
    $current = $start
    $root = $HORIZON_ROOT
    while ($true) {
        $candidate = Join-Path $current "aios_statusline.conf"
        if (Test-Path $candidate) { return $candidate }
        $parent = Split-Path $current -Parent
        if ($current -eq $root -or $parent -eq $current) { return $null }
        $current = $parent
    }
}

function Parse-Conf($path) {
    $result = @{}
    if (-not $path -or -not (Test-Path $path)) { return $result }
    foreach ($line in (Get-Content $path)) {
        $line = $line.Trim()
        if ($line -eq "" -or $line.StartsWith("#") -or $line -notmatch "=") { continue }
        $idx = $line.IndexOf("=")
        $k = $line.Substring(0, $idx).Trim()
        $v = $line.Substring($idx + 1).Trim()
        if ($k) { $result[$k] = $v }
    }
    return $result
}

$conf = Parse-Conf (Find-StatuslineConf $cwd)

$show_git         = $conf["show_git"] -ne "false"
$show_context_bar = $conf["show_context_bar"] -ne "false"
$bar_width        = if ($conf["bar_width"]) { [int]$conf["bar_width"] } else { 20 }
$project_name     = $conf["project_name"]
$raw_thresholds   = if ($conf["context_thresholds"]) { $conf["context_thresholds"] } else { "30,40,50,60,70,80,90" }
$thresholds       = @($raw_thresholds -split "," | ForEach-Object { [int]$_.Trim() } | Sort-Object)
# Approximate auto-compact trigger point (not exposed in statusline JSON; defaults to ~80%)
$compact_threshold = if ($conf["compact_threshold"]) { [int]$conf["compact_threshold"] } else { 80 }

# --- Working directory label ---
$dirname = if ($project_name) { $project_name } else { Split-Path $cwd -Leaf }

# --- Git branch ---
$git_branch = ""
if ($show_git) {
    try {
        $git_branch = (& git -C $cwd rev-parse --abbrev-ref HEAD 2>$null) -join ""
        $git_branch = $git_branch.Trim()
        if ($LASTEXITCODE -ne 0 -or $git_branch -eq "HEAD" -or $git_branch -eq "") { $git_branch = "" }
    } catch { $git_branch = "" }
}

# --- Audio threshold alerts (fires once per threshold per session) ---
$state_file = "$env:TEMP\claude_ctx_$session_id.txt"
$last_fired = 0
if (Test-Path $state_file) {
    $read_val = Get-Content $state_file -ErrorAction SilentlyContinue
    if ($read_val) { $last_fired = [int]$read_val }
}

$new_threshold = 0
foreach ($t in $thresholds) {
    if ($used_pct -ge $t -and $last_fired -lt $t) { $new_threshold = $t }
}

if ($new_threshold -gt 0) {
    $resolveScript = Join-Path $HORIZON_BIN "resolve_sound.py"
    $sound = & python $resolveScript "claude.context_$new_threshold" --harness claude_code --cwd $cwd 2>$null
    if ($sound -and (Test-Path $sound)) {
        $player = New-Object Media.SoundPlayer $sound
        $player.PlaySync()
    }
    Set-Content $state_file -Value $new_threshold
}

# --- Build context bar ---
if ($show_context_bar) {
    $filled = [int]([Math]::Round($used_pct / 100.0 * $bar_width))
    $filled = [Math]::Max(0, [Math]::Min($bar_width, $filled))
    $label = "$used_pct%"
    $label_len = $label.Length
    $label_start = [int](($bar_width - $label_len) / 2)
    $bar = ""
    for ($i = 0; $i -lt $bar_width; $i++) {
        if ($i -ge $label_start -and $i -lt ($label_start + $label_len)) {
            $bar += $label[$i - $label_start]
        } elseif ($i -lt $filled) { $bar += "#" }
        else { $bar += "-" }
    }
}

# --- % To Compact (remaining headroom before approximate auto-compact point) ---
$to_compact = [Math]::Max(0, $compact_threshold - $used_pct)

# --- Build statusline ---
$parts = @("[$dirname]")
if ($model -ne "") { $parts += $model }
if ($git_branch -ne "") { $parts += "git:$git_branch" }
if ($show_context_bar) { $parts += "Context Window: [$bar]" }
$parts += "Estimated % To Compact: $to_compact%"

Write-Output ($parts -join " ")
