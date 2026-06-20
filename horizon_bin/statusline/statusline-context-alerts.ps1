$raw = [Console]::In.ReadToEnd()
try { $json = $raw | ConvertFrom-Json } catch { Write-Output "ctx:?"; exit 0 }

if ($json.context_window.used_percentage -ne $null) {
    $used_pct = [int]($json.context_window.used_percentage)
} else {
    $used_pct = 0
}

if ($json.session_id -ne $null) {
    $session_id = $json.session_id
} else {
    $session_id = "unknown"
}

if ($json.cwd -ne $null) {
    $cwd = $json.cwd
} else {
    $cwd = (Get-Location).Path
}

# --- Working directory: basename only ---
$dirname = Split-Path $cwd -Leaf

# --- Git branch: run from cwd ---
$git_branch = ""
try {
    $git_branch = (& git -C $cwd rev-parse --abbrev-ref HEAD 2>$null) -join ""
    $git_branch = $git_branch.Trim()
    if ($LASTEXITCODE -ne 0 -or $git_branch -eq "HEAD" -or $git_branch -eq "") {
        $git_branch = ""
    }
} catch { $git_branch = "" }

# --- Audio threshold alerts (fires once per threshold per session) ---
$state_file = "$env:TEMP\claude_ctx_$session_id.txt"
$last_fired = 0
if (Test-Path $state_file) {
    $read_val = Get-Content $state_file -ErrorAction SilentlyContinue
    if ($read_val -ne $null) {
        $last_fired = [int]$read_val
    } else {
        $last_fired = 0
    }
}

$new_threshold = 0
foreach ($t in @(30, 40, 50, 60, 70, 80, 90)) {
    if ($used_pct -ge $t -and $last_fired -lt $t) { $new_threshold = $t }
}

if ($new_threshold -gt 0) {
    $wav = "C:\devroot\horizon_bin\sounds\claude_event_sounds\claude_at_${new_threshold}_statusline.wav"
    if (Test-Path $wav) {
        $player = New-Object Media.SoundPlayer $wav
        $player.PlaySync()
    }
    Set-Content $state_file -Value $new_threshold
}

# --- Build context bar ---
$bar_width = 20
$filled = [int]([Math]::Round($used_pct / 100.0 * $bar_width))
if ($filled -gt $bar_width) { $filled = $bar_width }
if ($filled -lt 0) { $filled = 0 }

$label = "$used_pct%"
$label_len = $label.Length
$label_start = [int](($bar_width - $label_len) / 2)

$bar = ""
for ($i = 0; $i -lt $bar_width; $i++) {
    if ($i -ge $label_start -and $i -lt ($label_start + $label_len)) {
        $bar += $label[$i - $label_start]
    } elseif ($i -lt $filled) {
        $bar += "#"
    } else {
        $bar += "-"
    }
}

# --- Build statusline ---
$parts = @("[$dirname]")
if ($git_branch -ne "") { $parts += "git:$git_branch" }
$parts += "[$bar]"

Write-Output ($parts -join " ")
