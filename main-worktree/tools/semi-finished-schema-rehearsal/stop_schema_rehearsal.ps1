Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $packageRoot 'rehearsal_common.ps1')
$config = Read-RehearsalConfig $packageRoot
$latestPath = Join-Path $packageRoot $config.latestRunFile
if (-not (Test-Path -LiteralPath $latestPath -PathType Leaf)) { Write-Host 'No isolated rehearsal run is available to stop.'; exit 0 }
$latest = Get-Content -Raw -LiteralPath $latestPath | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $latest.runManifestPath -PathType Leaf)) { throw "Run Manifest missing: $($latest.runManifestPath)" }
$run = Get-Content -Raw -LiteralPath $latest.runManifestPath | ConvertFrom-Json
$null = Assert-RehearsalRunManifest $run
$results = @()
foreach ($record in $run.processes) {
    $result = [ordered]@{ role = $record.role; pid = $record.pid; result = 'NOT_RUNNING' }
    $result.result = Stop-RehearsalOwnedProcess $record $run.runId $true
    $results += $result
}
$stopEvidence = [ordered]@{ contractVersion = $config.contractVersion; runId = $run.runId; stoppedAt = [DateTimeOffset]::Now.ToString('o'); results = $results }
$stopPath = Join-Path (Split-Path -Parent $latest.runManifestPath) 'STOP_RESULT.json'
Write-RehearsalJson $stopPath $stopEvidence
$stopReadback = Get-Content -Raw -LiteralPath $stopPath | ConvertFrom-Json
if ($stopReadback.runId -ne $run.runId -or @($stopReadback.results).Count -ne @($run.processes).Count) { throw 'STOP_RESULT_SCHEMA_INVALID' }
Write-Host 'Only the verified processes from this rehearsal run were stopped.'
