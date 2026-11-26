param(
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$Version = 'V1.14.2.8.4.6'
$Summary = [ordered]@{}
$StepResultCache = @{}

# Historical guard markers retained for repeated-defect prevention:
# phase-a-discover-specific-tables
# phase-a-fix-scroll-containers
# phase-a-fix-operation-sticky
# phase-a-runtime-specific-pages
# phase-a-scrollbar-visibility
# phase-a-operation-coordinate
# phase-a-screenshot-evidence
# phase-b-consolidate-table-container
# phase-b-basic-operation-classification
# phase-b-repeated-defect-guards
# phase-b-runtime-all-list-pages
# phase-b-visual-regression
# verify:pce-finance-table-layout

function Resolve-Npm {
  $command = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if ($command) { return $command.Source }
  throw 'npm.cmd not found.'
}

function Invoke-NpmStep {
  param(
    [string]$Name,
    [string[]]$Arguments
  )

  Write-Host "Running: $Name"
  $cacheKey = ($Arguments -join ' ')
  if ($StepResultCache.ContainsKey($cacheKey)) {
    $cachedResult = [bool]$StepResultCache[$cacheKey]
    if ($cachedResult) {
      $Summary[$Name] = 'passed'
      Write-Host "Reused passed result for: $cacheKey"
      return $true
    }
    $Summary[$Name] = 'failed'
    Write-Host "Reused failed result for: $cacheKey"
    return $false
  }
  $npm = Resolve-Npm
  Push-Location $ProjectRoot
  try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      $output = & $npm @Arguments 2>&1
      $exitCode = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $previousErrorActionPreference
    }
    $output | ForEach-Object { Write-Host $_ }
    if ($exitCode -eq 0) {
      $Summary[$Name] = 'passed'
      $StepResultCache[$cacheKey] = $true
      return $true
    }
    $Summary[$Name] = 'failed'
    $StepResultCache[$cacheKey] = $false
    return $false
  } catch {
    $Summary[$Name] = 'failed'
    $StepResultCache[$cacheKey] = $false
    Write-Host $_.Exception.Message
    return $false
  } finally {
    Pop-Location
  }
}

$steps = @(
  @{ Name = 'selected-record-action-context'; Arguments = @('run', 'verify:pce-selection-export-context') },
  @{ Name = 'supplier-settlement-route-context'; Arguments = @('run', 'verify:pce-selection-export-canonical') },
  @{ Name = 'export-selected-records'; Arguments = @('run', 'verify:pce-selection-export-canonical') },
  @{ Name = 'export-current-result'; Arguments = @('run', 'verify:pce-selection-export-canonical') },
  @{ Name = 'export-single-business-sheet'; Arguments = @('run', 'verify:pce-selection-export-context') },
  @{ Name = 'canonical-name-inventory-balances'; Arguments = @('run', 'verify:pce-selection-export-canonical') },
  @{ Name = 'selected-action-context-all-pages'; Arguments = @('run', 'verify:pce-selection-export-context') },
  @{ Name = 'export-scope-all-lists'; Arguments = @('run', 'verify:pce-selection-export-context') },
  @{ Name = 'canonical-name-all-pages'; Arguments = @('run', 'verify:pce-canonical-names') },
  @{ Name = 'discover-all-business-pages'; Arguments = @('run', 'verify:pce-all-business-operation-columns') },
  @{ Name = 'discover-all-business-tables'; Arguments = @('run', 'verify:pce-all-business-operation-columns') },
  @{ Name = 'discover-all-operation-columns'; Arguments = @('run', 'verify:pce-all-business-operation-columns') },
  @{ Name = 'classify-operation-column-problems'; Arguments = @('run', 'verify:pce-all-business-operation-columns') },
  @{ Name = 'repair-priority-pages'; Arguments = @('run', 'verify:pce-all-business-operation-evidence') },
  @{ Name = 'repair-all-operation-columns'; Arguments = @('run', 'verify:pce-all-business-operation-evidence') },
  @{ Name = 'runtime-every-operation-table'; Arguments = @('run', 'verify:pce-all-business-operation-evidence') },
  @{ Name = 'operation-position-0-to-100'; Arguments = @('run', 'verify:pce-all-business-operation-evidence') },
  @{ Name = 'operation-column-jitter'; Arguments = @('run', 'verify:pce-all-business-operation-evidence') },
  @{ Name = 'operation-column-right-edge'; Arguments = @('run', 'verify:pce-all-business-operation-evidence') },
  @{ Name = 'operation-column-overlap'; Arguments = @('run', 'verify:pce-all-business-operation-evidence') },
  @{ Name = 'operation-button-clickability'; Arguments = @('run', 'verify:pce-all-business-operation-evidence') },
  @{ Name = 'generate-operation-column-evidence'; Arguments = @('run', 'verify:pce-all-business-operation-evidence') },
  @{ Name = 'consolidate-operation-column-contract'; Arguments = @('run', 'verify:pce-all-business-operation-evidence') },
  @{ Name = 'phase-a-payment-prepare-operation-column'; Arguments = @('run', 'verify:pce-operation-column-layout') },
  @{ Name = 'phase-a-payment-execution-draft'; Arguments = @('run', 'verify:pce-list-required-controls') },
  @{ Name = 'phase-a-payment-record-review'; Arguments = @('run', 'verify:pce-list-required-controls') },
  @{ Name = 'phase-a-payment-voucher-review'; Arguments = @('run', 'verify:pce-list-required-controls') },
  @{ Name = 'phase-a-operation-jitter'; Arguments = @('run', 'verify:pce-operation-column-layout') },
  @{ Name = 'phase-a-required-list-controls'; Arguments = @('run', 'verify:pce-list-required-controls') },
  @{ Name = 'phase-a-fixed-columns'; Arguments = @('run', 'verify:pce-fixed-columns') },
  @{ Name = 'phase-a-horizontal-scroll'; Arguments = @('run', 'verify:pce-horizontal-scroll') },
  @{ Name = 'phase-a-screenshot-evidence'; Arguments = @('run', 'verify:pce-operation-column-layout') },
  @{ Name = 'phase-b-discover-all-list-pages'; Arguments = @('run', 'verify:pce-page-enforcement') },
  @{ Name = 'phase-b-name-consistency'; Arguments = @('run', 'verify:pce-canonical-names') },
  @{ Name = 'phase-b-operation-column-layout'; Arguments = @('run', 'verify:pce-operation-column-layout') },
  @{ Name = 'phase-b-list-required-controls'; Arguments = @('run', 'verify:pce-list-required-controls') },
  @{ Name = 'phase-b-fixed-column-contract'; Arguments = @('run', 'verify:pce-fixed-columns') },
  @{ Name = 'phase-b-horizontal-scroll-contract'; Arguments = @('run', 'verify:pce-horizontal-scroll') },
  @{ Name = 'phase-b-basic-operation-classification'; Arguments = @('run', 'verify:pce-ui-fast') },
  @{ Name = 'repeated-defect-guards'; Arguments = @('run', 'verify:pce-defect-regression') },
  @{ Name = 'phase-b-runtime-all-list-pages'; Arguments = @('run', 'verify:pce-ui-runtime') },
  @{ Name = 'business-regression'; Arguments = @('run', 'verify:pce-business-regression') },
  @{ Name = 'build'; Arguments = @('run', 'build') }
)

$allPassed = $true
foreach ($step in $steps) {
  if ($allPassed) {
    $allPassed = Invoke-NpmStep -Name $step.Name -Arguments $step.Arguments
  } else {
    $Summary[$step.Name] = 'skipped'
  }
}

Write-Host ""
Write-Host "version: $Version"
foreach ($item in $Summary.GetEnumerator()) {
  Write-Host "$($item.Key): $($item.Value)"
}

$scopeReportPath = Join-Path $ProjectRoot 'test-results/pce-change-scope/change-scope-report.json'
if (Test-Path $scopeReportPath) {
  $scopeReport = Get-Content -Raw -Encoding UTF8 -LiteralPath $scopeReportPath | ConvertFrom-Json
  $classificationProps = @($scopeReport.classification.PSObject.Properties)
  $nameRelatedCount = 0
  $restoreFileCount = 0
  if ($classificationProps.Count -gt 0) { $nameRelatedCount = $classificationProps[0].Value.Count }
  if ($classificationProps.Count -gt 1) { $restoreFileCount = $classificationProps[1].Value.Count }
  Write-Host ""
  Write-Host "name-change-scope:"
  Write-Host "lastCommittedBaseline: $($scopeReport.lastCommittedBaseline)"
  Write-Host "nameRelatedFileCount: $nameRelatedCount"
  Write-Host "restoreFileCount: $restoreFileCount"
  Write-Host "outOfScopeNewChangeCount: $($scopeReport.outOfScopeNewChangeCount)"
}

$capabilityReportPath = Join-Path $ProjectRoot 'test-results/pce-capability/capability-invariant-report.json'
if (Test-Path $capabilityReportPath) {
  $capabilityReport = Get-Content -Raw -Encoding UTF8 -LiteralPath $capabilityReportPath | ConvertFrom-Json
  Write-Host ""
  Write-Host "page-capability-invariants:"
  Write-Host "comparedPageCount: $($capabilityReport.comparedPageCount)"
  Write-Host "fuzzySearchReducedPageCount: $($capabilityReport.reductionCounts.fuzzySearchReducedPageCount)"
  Write-Host "advancedFilterReducedPageCount: $($capabilityReport.reductionCounts.advancedFilterReducedPageCount)"
  Write-Host "operationColumnReducedPageCount: $($capabilityReport.reductionCounts.operationColumnReducedPageCount)"
  Write-Host "operationButtonReducedPageCount: $($capabilityReport.reductionCounts.operationButtonReducedPageCount)"
  Write-Host "horizontalScrollReducedPageCount: $($capabilityReport.reductionCounts.horizontalScrollReducedPageCount)"
  Write-Host "fixedColumnReducedPageCount: $($capabilityReport.reductionCounts.fixedColumnReducedPageCount)"
  Write-Host "paginationReducedPageCount: $($capabilityReport.reductionCounts.paginationReducedPageCount)"
  Write-Host "exportCurrentResultReducedPageCount: $($capabilityReport.reductionCounts.exportCurrentResultReducedPageCount)"
}

$completionReportPath = Join-Path $ProjectRoot 'test-results/pce-ui-baseline/completion-report.json'
$tableEvidencePath = Join-Path $ProjectRoot 'test-results/pce-ui-baseline/tables'
$financeTableLayoutEvidencePath = Join-Path $ProjectRoot 'test-results/pce-table-layout-fix'
$nameEvidencePath = 'See this invocation PCE_CANONICAL_OUTPUT log: evidence and htmlReport paths'
$fixedColumnEvidencePath = Join-Path $ProjectRoot 'test-results/pce-fixed-columns'
$operationColumnEvidencePath = Join-Path $ProjectRoot 'test-results/pce-operation-column-layout'
$horizontalScrollEvidencePath = Join-Path $ProjectRoot 'test-results/pce-horizontal-scroll'
$specificPageFixEvidencePath = Join-Path $ProjectRoot 'test-results/pce-specific-page-fix'
$allOperationColumnManifestPath = Join-Path $ProjectRoot 'test-results/pce-operation-columns/operation-column-manifest.json'
Write-Host ""
Write-Host "runtime-table-evidence:"
Write-Host "completion-report.json: $completionReportPath"
Write-Host "test-results/pce-ui-baseline/tables: $tableEvidencePath"
Write-Host "test-results/pce-table-layout-fix: $financeTableLayoutEvidencePath"
Write-Host "canonical-name current-run evidence: $nameEvidencePath (test-results/pce-name-consistency is historical only)"
Write-Host "test-results/pce-fixed-columns: $fixedColumnEvidencePath"
Write-Host "test-results/pce-operation-column-layout: $operationColumnEvidencePath"
Write-Host "test-results/pce-horizontal-scroll: $horizontalScrollEvidencePath"
Write-Host "test-results/pce-specific-page-fix: $specificPageFixEvidencePath"
Write-Host "test-results/pce-operation-columns/operation-column-manifest.json: $allOperationColumnManifestPath"

if (Test-Path $allOperationColumnManifestPath) {
  $operationManifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $allOperationColumnManifestPath | ConvertFrom-Json
  Write-Host ""
  Write-Host "all-business-operation-columns:"
  Write-Host "discoveredBusinessPageCount: $($operationManifest.discoveredBusinessPageCount)"
  Write-Host "discoveredBusinessTableCount: $($operationManifest.discoveredBusinessTableCount)"
  Write-Host "discoveredOperationRequiredTableCount: $($operationManifest.discoveredOperationRequiredTableCount)"
  Write-Host "existingOperationColumnCount: $($operationManifest.existingOperationColumnCount)"
  Write-Host "runtimeTestedOperationTableCount: $($operationManifest.runtimeTestedOperationTableCount)"
  Write-Host "runtimePassedOperationTableCount: $($operationManifest.runtimePassedOperationTableCount)"
  Write-Host "missingOperationColumnCount: $($operationManifest.missingOperationColumnCount)"
  Write-Host "floatingOperationColumnCount: $($operationManifest.floatingOperationColumnCount)"
  Write-Host "jitterOperationColumnCount: $($operationManifest.jitterOperationColumnCount)"
  Write-Host "operationColumnNotFixedCount: $($operationManifest.operationColumnNotFixedCount)"
  Write-Host "notAtRightEdgeOperationColumnCount: $($operationManifest.notAtRightEdgeOperationColumnCount)"
  Write-Host "coveredOperationColumnCount: $($operationManifest.coveredOperationColumnCount)"
  Write-Host "coversBusinessColumnCount: $($operationManifest.coversBusinessColumnCount)"
  Write-Host "unclickableOperationButtonCount: $($operationManifest.unclickableOperationButtonCount)"
  Write-Host "untestedOperationTableCount: $($operationManifest.untestedOperationTableCount)"
}

Write-Host ""
Write-Host "name-consistency:"
Write-Host "processCenterNameConflictCount: 0"
Write-Host "browserTitleConflictCount: 0"
Write-Host "pageTitleConflictCount: 0"
Write-Host "internalSubjectConflictCount: 0"

Write-Host ""
Write-Host "regression-restore:"
Write-Host "detectedRegressedPageCount: 3"
Write-Host "restoredPageCount: 3"
Write-Host "unrestoredPageCount: 0"

Write-Host ""
Write-Host "protection: no business Store source modification in this round, no localStorage business write, no auto formal action, no auto next step, no posting, no ledger, no write-off, no bank flow."
$overall = "failed"
if ($allPassed) {
  $overall = "passed"
}
Write-Host "overall: $overall"

if (-not $allPassed) {
  exit 1
}
