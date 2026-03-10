param(
    [switch]$Once,
    [int]$PollSeconds = 2
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$coordRoot = Join-Path $repoRoot ".claude\coord"
$eventsPath = Join-Path $coordRoot "events.jsonl"
$statusPath = Join-Path $coordRoot "STATUS.md"
$tasksRoot = Join-Path $coordRoot "TASKS"
$reportsRoot = Join-Path $coordRoot "REPORTS"
$reviewRoot = Join-Path $coordRoot "REVIEW"

function Read-Events {
    param([string]$Path)

    $items = @()
    $seq = 0
    if (-not (Test-Path $Path)) {
        return $items
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed) { continue }
        $seq += 1
        try {
            $event = ($trimmed | ConvertFrom-Json)
            Add-Member -InputObject $event -NotePropertyName "_seq" -NotePropertyValue $seq -Force
            $items += $event
        } catch {
            $items += [pscustomobject]@{
                ts = ""
                actor = "watcher"
                wave = "UNKNOWN"
                type = "parse_error"
                status = "BLOCKED"
                summary = "Invalid JSON line in events.jsonl"
                _seq = $seq
            }
        }
    }
    return $items
}

function Get-LatestWaveState {
    param([object[]]$Events)

    $byWave = @{}
    foreach ($event in $Events) {
        if (-not $event.wave) { continue }
        $wave = [string]$event.wave
        if (-not $byWave.ContainsKey($wave)) {
            $byWave[$wave] = @()
        }
        $byWave[$wave] += $event
    }

    $rows = @()
    foreach ($wave in ($byWave.Keys | Sort-Object)) {
        $latest = $byWave[$wave] | Sort-Object @{ Expression = { $_._seq } } | Select-Object -Last 1
        $rows += [pscustomobject]@{
            Wave = $wave
            Status = [string]$latest.status
            Actor = [string]$latest.actor
            Type = [string]$latest.type
            Timestamp = [string]$latest.ts
            Summary = [string]$latest.summary
        }
    }
    return $rows
}

function Find-ExistingFile {
    param(
        [string]$Root,
        [string]$Wave
    )

    if (-not (Test-Path $Root)) { return $null }
    return Get-ChildItem $Root -File | Where-Object { $_.BaseName -like "$Wave*" } | Select-Object -First 1
}

function Render-Status {
    $events = Read-Events -Path $eventsPath
    $rows = Get-LatestWaveState -Events $events
    $generatedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")

    $lines = @()
    $lines += "# Coordination Status"
    $lines += ""
    $lines += "Generated: $generatedAt"
    $lines += ""

    if ($rows.Count -eq 0) {
        $lines += "No waves tracked yet."
        Set-Content -Path $statusPath -Value $lines -Encoding UTF8
        return
    }

    $current = $rows | Sort-Object Wave | Select-Object -Last 1
    $lines += "## Current Wave"
    $lines += ""
    $lines += "- Wave: $($current.Wave)"
    $lines += "- Status: $($current.Status)"
    $lines += "- Last actor: $($current.Actor)"
    $lines += "- Last event: $($current.Type)"
    $lines += "- Updated: $($current.Timestamp)"
    $lines += "- Summary: $($current.Summary)"
    $lines += ""
    $lines += "## Waves"
    $lines += ""
    $lines += "| Wave | Status | Actor | Event | Updated | Task | Report | Review |"
    $lines += "|------|--------|-------|-------|---------|------|--------|--------|"

    foreach ($row in $rows) {
        $task = Find-ExistingFile -Root $tasksRoot -Wave $row.Wave
        $report = Find-ExistingFile -Root $reportsRoot -Wave $row.Wave
        $review = Find-ExistingFile -Root $reviewRoot -Wave $row.Wave

        $taskRef = if ($task) { ".claude/coord/TASKS/$($task.Name)" } else { "-" }
        $reportRef = if ($report) { ".claude/coord/REPORTS/$($report.Name)" } else { "-" }
        $reviewRef = if ($review) { ".claude/coord/REVIEW/$($review.Name)" } else { "-" }

        $lines += "| $($row.Wave) | $($row.Status) | $($row.Actor) | $($row.Type) | $($row.Timestamp) | $taskRef | $reportRef | $reviewRef |"
    }

    $blocked = $rows | Where-Object { $_.Status -in @("BLOCKED", "REJECTED") }
    if ($blocked.Count -gt 0) {
        $lines += ""
        $lines += "## Attention"
        $lines += ""
        foreach ($row in $blocked) {
            $lines += "- $($row.Wave): $($row.Status) - $($row.Summary)"
        }
    }

    Set-Content -Path $statusPath -Value $lines -Encoding UTF8
}

Render-Status

if ($Once) {
    exit 0
}

Write-Host "[coord-watch] Watching $coordRoot every $PollSeconds second(s)..."
$lastSignature = ""

while ($true) {
    Start-Sleep -Seconds $PollSeconds
    $signature = ""
    if (Test-Path $eventsPath) {
        $file = Get-Item $eventsPath
        $signature = "{0}|{1}" -f $file.Length, $file.LastWriteTimeUtc.Ticks
    }
    if ($signature -ne $lastSignature) {
        Render-Status
        $lastSignature = $signature
    }
}
