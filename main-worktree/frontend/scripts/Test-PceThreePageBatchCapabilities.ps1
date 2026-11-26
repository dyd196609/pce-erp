$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$summaryPath = Join-Path $root 'test-results\pce-semantic-batch-capability\summary.json'
$invariantPath = Join-Path $root 'test-results\pce-capability\capability-invariant-report.json'

if (-not (Test-Path -LiteralPath $summaryPath)) {
  throw "Missing three-page semantic batch capability evidence: $summaryPath"
}
if (-not (Test-Path -LiteralPath $invariantPath)) {
  throw "Missing global capability invariant evidence: $invariantPath"
}

$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$invariant = Get-Content -LiteralPath $invariantPath -Raw -Encoding UTF8 | ConvertFrom-Json

if ($summary.result -ne 'passed') { throw 'Three-page semantic batch capability gate did not pass.' }
if (-not $summary.checkpointImmutable) { throw 'qualified_inbound_completed checkpoint changed.' }
if (-not $invariant.invariantPassed) { throw 'Global capability invariant gate did not pass.' }
if (@($summary.pages).Count -ne 3) { throw 'Three-page semantic capability evidence count is incorrect.' }
if (@($summary.pages | Where-Object { $_.missingActionIds.Count -or $_.extraActionIds.Count -or $_.duplicateActionIds.Count }).Count) {
  throw 'Semantic batch actions contain missing, extra, or duplicate action IDs.'
}

[pscustomobject]@{
  version = 'V1.14.2.8.4.7.31'
  gate = 'three_page_semantic_batch_capability_minimal'
  pageCount = @($summary.pages).Count
  semanticActionCounts = @($summary.pages | ForEach-Object { "$($_.pageId):$($_.semanticActionCount)" })
  checkpointImmutable = $summary.checkpointImmutable
  globalInvariantPassed = $invariant.invariantPassed
  result = 'passed'
} | ConvertTo-Json -Depth 5
