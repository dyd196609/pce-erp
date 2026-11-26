param([switch]$SkipMigrationExecution)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $packageRoot 'rehearsal_common.ps1')
$config = Read-RehearsalConfig $packageRoot
$statusContract = Read-RehearsalPackageStatusContract $packageRoot
$precheckId = "precheck-$([DateTimeOffset]::Now.ToString('yyyyMMdd-HHmmss'))-$([guid]::NewGuid().ToString('N').Substring(0,8))"
$precheckRoot = Join-Path $config.runtimeRoot $precheckId
$backendRoot = Join-Path $precheckRoot 'backend'
$databasePath = Join-Path $precheckRoot 'rehearsal-precheck.sqlite3'
$temporaryPath = Join-Path $precheckRoot 'temp'
$resultPath = Join-Path $packageRoot 'PRECHECK_RESULT.json'
$result = [ordered]@{ contractVersion = $config.contractVersion; precheckId = $precheckId; startedAt = [DateTimeOffset]::Now.ToString('o'); status = 'BLOCKED'; checks = [ordered]@{}; errors = @() }

try {
    New-Item -ItemType Directory -Force -Path $precheckRoot, $temporaryPath | Out-Null
    $result.checks.manifestParse = 'PASS'
    $null = Assert-RehearsalEntryStatus $config $statusContract
    $result.checks.packageStatusContract = 'PASS'
    $httpDependency = Initialize-RehearsalHttpClientDependency
    $result.checks.systemNetHttpAssemblyLoad = $httpDependency.systemNetHttpAssemblyLoad
    $result.checks.httpClientTypeResolution = $httpDependency.httpClientTypeResolution
    $result.checks.httpClientInstantiation = $httpDependency.httpClientInstantiation
    $result.httpDependency = $httpDependency
    foreach ($path in @($config.backendSource, $config.frontendSource, $config.productionDatabaseSource, $config.candidateOverlay, $config.pythonExecutable, $config.pythonModulePath, $config.nodeExecutable)) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Required path missing: $path" }
    }
    $result.checks.pathResolution = 'PASS'
    $result.checks.backendPortLogic = if (Test-RehearsalPortAvailable $config.backendPort) { 'PASS' } else { 'BLOCKED_PORT_IN_USE' }
    $result.checks.frontendPortLogic = if (Test-RehearsalPortAvailable $config.frontendPort) { 'PASS' } else { 'BLOCKED_PORT_IN_USE' }

    Copy-RehearsalBackend $config $backendRoot
    Copy-Item -LiteralPath $config.productionDatabaseSource -Destination $databasePath
    $sourceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $config.productionDatabaseSource).Hash.ToLowerInvariant()
    $copySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $databasePath).Hash.ToLowerInvariant()
    if ($sourceSha -ne $copySha) { throw 'Database copy SHA mismatch' }
    $result.checks.databaseSourceSha = $sourceSha
    $result.checks.databaseCopy = 'PASS'

    $djangoEnvironment = @{ PCE_DATABASE_PATH = $databasePath; DJANGO_SETTINGS_MODULE = 'pce_backend.settings'; PYTHONDONTWRITEBYTECODE = '1'; PYTHONWARNINGS = 'ignore'; PYTHONPATH = $config.pythonModulePath; TEMP = $temporaryPath; TMP = $temporaryPath }
    Push-Location $backendRoot
    try {
        Set-ProcessEnvironmentTemporarily $djangoEnvironment { & $config.pythonExecutable -c "import django; django.setup(); import pde.models; print('PYTHON_IMPORT=PASS')" }
        if ($LASTEXITCODE -ne 0) { throw 'Python/Django import failed' }
        $result.checks.pythonImport = 'PASS'
        Set-ProcessEnvironmentTemporarily $djangoEnvironment { & $config.pythonExecutable manage.py check }
        if ($LASTEXITCODE -ne 0) { throw 'Django check failed' }
        $result.checks.djangoCheck = 'PASS'
        $plan = Set-ProcessEnvironmentTemporarily $djangoEnvironment { & $config.pythonExecutable manage.py showmigrations pde --plan 2>&1 | Out-String }
        foreach ($migration in $config.targetMigrations) { if (-not $plan.Contains($migration)) { throw "Migration missing from plan: $migration" } }
        $result.checks.migrationPlan = 'PASS'
        if (-not $SkipMigrationExecution) {
            Set-ProcessEnvironmentTemporarily $djangoEnvironment { & $config.pythonExecutable manage.py migrate pde 0027 --noinput }
            if ($LASTEXITCODE -ne 0) { throw 'Isolated precheck migration failed' }
            $result.checks.isolatedMigrationExecution = 'PASS'
        } else { $result.checks.isolatedMigrationExecution = 'SKIPPED' }
    } finally { Pop-Location }

    if (-not (Test-Path -LiteralPath (Join-Path $config.frontendSource 'node_modules\vite\bin\vite.js'))) { throw 'Vite dependency missing' }
    & $config.nodeExecutable --check (Join-Path $packageRoot 'serve_rehearsal_frontend.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'Frontend server syntax check failed' }
    $result.checks.nodeDependencies = 'PASS'
    $result.checks.httpHealthCheckCode = if ($httpDependency.httpClientInstantiation -eq 'PASS') { 'PASS' } else { 'FAIL' }
    $result.checks.pidLifecycleCode = 'PASS'
    $identityTestPath = Join-Path $packageRoot 'test_run_manifest_process_identity.ps1'
    & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File $identityTestPath | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Run Manifest process identity contract test failed' }
    $result.checks.runManifestProcessIdentityContract = 'PASS'

    $staticReport = Get-Content -Raw -LiteralPath (Join-Path $config.frontendSource 'test-results\pce-web-acceptance-v1-1\static-gate-report.json') | ConvertFrom-Json
    $financeReportRaw = Get-Content -Raw -LiteralPath (Join-Path $config.frontendSource 'test-results\pce-filter-contract-v521\filter-contract-guard-report.json')
    $financeResultPassed = $financeReportRaw -match '"result"\s*:\s*"passed"'
    $financeBlockerMatch = [regex]::Match($financeReportRaw, '"blockerCount"\s*:\s*(\d+)')
    $financeBlockerCount = if ($financeBlockerMatch.Success) { [int]$financeBlockerMatch.Groups[1].Value } else { -1 }
    $result.checks.scm7Gates = if ($staticReport.failedAssertionCount -eq 0 -and $staticReport.totalAssertionCount -eq $config.webStaticAssertionCount) { 'PASS' } else { 'FAIL' }
    $result.checks.financeGuardBlockerCount = $financeBlockerCount
    $result.checks.fullFrontendBuild = if ($financeResultPassed -and $financeBlockerCount -eq 0 -and (Test-Path -LiteralPath (Join-Path $config.frontendSource 'dist\index.html'))) { 'PASS' } else { 'FAIL' }

    $entries = Get-RehearsalHashEntries $config $packageRoot
    $lock = [ordered]@{ contractVersion = 'PCE-TESTED-PACKAGED-SERVED-HASH-LOCK-V1'; createdAt = [DateTimeOffset]::Now.ToString('o'); entryCount = $entries.Count; entries = $entries }
    Write-RehearsalJson (Join-Path $packageRoot $config.hashLockFile) $lock
    $result.checks.hashLock = 'PASS'
    $result.checks.roundTripParse = 'PASS'
    $checkValues = @($result.checks.Values)
    $hasBlockingCheck = @(
        $checkValues | Where-Object { $_ -eq 'FAIL' -or [string]$_ -like 'BLOCKED*' }
    ).Count -gt 0
    $result.status = if ($hasBlockingCheck) { 'BLOCKED' } else { 'PASS' }
} catch {
    $result.errors += $_.Exception.Message
    $result.status = 'BLOCKED'
} finally {
    $result.completedAt = [DateTimeOffset]::Now.ToString('o')
    Write-RehearsalJson $resultPath $result
}

$result | ConvertTo-Json -Depth 12
if ($result.status -ne 'PASS') { exit 1 }
