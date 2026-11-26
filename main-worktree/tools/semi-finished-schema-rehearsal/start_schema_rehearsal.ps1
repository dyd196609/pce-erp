Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $packageRoot 'rehearsal_common.ps1')
$config = Read-RehearsalConfig $packageRoot
$statusContract = Read-RehearsalPackageStatusContract $packageRoot
$logRoot = Join-Path $packageRoot 'logs'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$attemptId = "start-$([DateTimeOffset]::Now.ToString('yyyyMMdd-HHmmss'))-$([guid]::NewGuid().ToString('N').Substring(0,8))"
$attemptLog = Join-Path $logRoot "$attemptId.json"
$attempt = [ordered]@{ contractVersion = $config.contractVersion; attemptId = $attemptId; startedAt = [DateTimeOffset]::Now.ToString('o'); status = 'BLOCKED'; steps = @(); error = '' }
$startedProcesses = [System.Collections.Generic.List[object]]::new()

function Add-Step([string]$Message) { $attempt.steps += [ordered]@{ at = [DateTimeOffset]::Now.ToString('o'); message = $Message }; Write-Host $Message }
function Stop-StartedProcesses {
    foreach ($record in @($startedProcesses) | Sort-Object { $_.pid } -Descending) {
        try { $null = Stop-RehearsalOwnedProcess $record $runId $false } catch { Write-Warning $_.Exception.Message }
    }
}

try {
    Add-Step 'Checking isolated rehearsal environment...'
    $null = Assert-RehearsalEntryStatus $config $statusContract
    $lock = Assert-RehearsalHashLock $config $packageRoot
    Add-Step 'Bootstrapping Windows PowerShell HTTP readiness dependency...'
    $httpDependency = Initialize-RehearsalHttpClientDependency
    if (-not (Test-RehearsalPortAvailable $config.backendPort)) { throw "PORT_IN_USE: $($config.backendPort)" }
    if (-not (Test-RehearsalPortAvailable $config.frontendPort)) { throw "PORT_IN_USE: $($config.frontendPort)" }
    if (-not (Test-Path -LiteralPath (Join-Path $config.frontendSource 'dist\index.html'))) { throw 'BUILT_FRONTEND_MISSING' }

    $runId = "schema-rehearsal-$([DateTimeOffset]::Now.ToString('yyyyMMdd-HHmmss'))-$([guid]::NewGuid().ToString('N').Substring(0,8))"
    $pythonExecutable = Resolve-RehearsalExecutablePath ([string]$config.pythonExecutable)
    $nodeExecutable = Resolve-RehearsalExecutablePath ([string]$config.nodeExecutable)
    $runRoot = Join-Path $config.runtimeRoot $runId
    $backendRoot = Join-Path $runRoot 'backend'
    $databasePath = Join-Path $runRoot 'rehearsal.sqlite3'
    $runLogRoot = Join-Path $runRoot 'logs'
    $temporaryPath = Join-Path $runRoot 'temp'
    New-Item -ItemType Directory -Force -Path $runLogRoot, $temporaryPath | Out-Null
    Copy-RehearsalBackend $config $backendRoot

    Add-Step 'Copying the production database baseline...'
    Copy-Item -LiteralPath $config.productionDatabaseSource -Destination $databasePath
    $sourceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $config.productionDatabaseSource).Hash.ToLowerInvariant()
    $copySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $databasePath).Hash.ToLowerInvariant()
    if ($sourceSha -ne $copySha) { throw 'DATABASE_COPY_SHA_MISMATCH' }

    Add-Step 'Applying schema migrations to the isolated copy...'
    $djangoEnvironment = @{ PCE_DATABASE_PATH = $databasePath; DJANGO_SETTINGS_MODULE = 'pce_backend.settings'; PYTHONDONTWRITEBYTECODE = '1'; PYTHONWARNINGS = 'ignore'; PYTHONPATH = $config.pythonModulePath; TEMP = $temporaryPath; TMP = $temporaryPath }
    Push-Location $backendRoot
    try {
        Set-ProcessEnvironmentTemporarily $djangoEnvironment { & $pythonExecutable manage.py migrate pde 0027 --noinput }
        if ($LASTEXITCODE -ne 0) { throw 'ISOLATED_MIGRATION_FAILED' }
        Set-ProcessEnvironmentTemporarily $djangoEnvironment { & $pythonExecutable manage.py check }
        if ($LASTEXITCODE -ne 0) { throw 'DJANGO_CHECK_FAILED' }
    } finally { Pop-Location }

    Add-Step 'Starting isolated backend on 8001...'
    $backendOut = Join-Path $runLogRoot 'backend.stdout.log'
    $backendErr = Join-Path $runLogRoot 'backend.stderr.log'
    $backendArguments = @('manage.py', 'runserver', "127.0.0.1:$($config.backendPort)", '--noreload')
    $backendProcess = Set-ProcessEnvironmentTemporarily $djangoEnvironment {
        Start-Process -FilePath $pythonExecutable -ArgumentList $backendArguments -WorkingDirectory $backendRoot -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru -WindowStyle Hidden
    }
    $backendRecord = New-RehearsalProcessIdentity 'backend' $backendProcess $pythonExecutable $backendArguments $backendRoot $config.backendPort $runId
    $startedProcesses.Add($backendRecord)

    Add-Step 'Starting isolated frontend on 5183...'
    $frontendOut = Join-Path $runLogRoot 'frontend.stdout.log'
    $frontendErr = Join-Path $runLogRoot 'frontend.stderr.log'
    $serverScript = Join-Path $packageRoot 'serve_rehearsal_frontend.mjs'
    $identityFile = Join-Path $packageRoot $config.hashLockFile
    $frontendArguments = @($serverScript, (Join-Path $config.frontendSource 'dist'), [string]$config.frontendPort, "http://127.0.0.1:$($config.backendPort)", $identityFile)
    $frontendProcess = Start-Process -FilePath $nodeExecutable -ArgumentList $frontendArguments -WorkingDirectory $config.frontendSource -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru -WindowStyle Hidden
    $frontendRecord = New-RehearsalProcessIdentity 'frontend' $frontendProcess $nodeExecutable $frontendArguments $config.frontendSource $config.frontendPort $runId
    $startedProcesses.Add($frontendRecord)

    Add-Step 'Running HTTP health checks...'
    $http = New-RehearsalHttpClient
    $backendReady = $false; $frontendReady = $false
    try {
        for ($index = 0; $index -lt 60 -and -not ($backendReady -and $frontendReady); $index++) {
            if (-not $backendReady) { try { $response = $http.GetAsync("http://127.0.0.1:$($config.backendPort)/api/scm/supplier-performance/").GetAwaiter().GetResult(); $backendReady = [int]$response.StatusCode -eq 200 } catch {} }
            if (-not $frontendReady) { try { $response = $http.GetAsync("http://127.0.0.1:$($config.frontendPort)/").GetAwaiter().GetResult(); $frontendReady = [int]$response.StatusCode -eq 200 } catch {} }
            if (-not ($backendReady -and $frontendReady)) { Start-Sleep -Milliseconds 500 }
        }
    } finally { $http.Dispose() }
    if (-not $backendReady) { throw 'BACKEND_HEALTH_CHECK_FAILED' }
    if (-not $frontendReady) { throw 'FRONTEND_HEALTH_CHECK_FAILED' }

    $runManifest = [ordered]@{
        contractVersion = $config.contractVersion; runId = $runId; status = 'READY'; readyAt = [DateTimeOffset]::Now.ToString('o')
        sourceDatabase = $config.productionDatabaseSource; sourceDatabaseSha256 = $sourceSha; rehearsalDatabase = $databasePath; rehearsalDatabaseInitialSha256 = $copySha
        targetMigrations = $config.targetMigrations; hashLockSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $identityFile).Hash.ToLowerInvariant(); httpDependency = $httpDependency
        backendUrl = "http://127.0.0.1:$($config.backendPort)"; frontendUrl = "http://127.0.0.1:$($config.frontendPort)"; processes = @($startedProcesses)
        productionMigrationRetryExecuted = $false; productionBusinessFactCreate = 0
    }
    $runManifestPath = Join-Path $runRoot 'RUN_MANIFEST.json'
    $null = Assert-RehearsalRunManifest $runManifest
    Write-RehearsalJson $runManifestPath $runManifest
    $roundTripRunManifest = Get-Content -Raw -LiteralPath $runManifestPath | ConvertFrom-Json
    $null = Assert-RehearsalRunManifest $roundTripRunManifest
    Write-RehearsalJson (Join-Path $packageRoot $config.latestRunFile) ([ordered]@{ runId = $runId; runManifestPath = $runManifestPath; status = 'READY' })
    $attempt.status = 'READY'; $attempt.runId = $runId; $attempt.runManifestPath = $runManifestPath
    Add-Step 'Isolated rehearsal environment is ready.'
    Write-RehearsalJson $attemptLog $attempt
    exit 0
} catch {
    Stop-StartedProcesses
    $attempt.error = $_.Exception.Message
    $attempt.status = 'BLOCKED'
    Add-Step 'Rehearsal startup was blocked; details were written to the log.'
    Write-RehearsalJson $attemptLog $attempt
    Write-Host "BLOCKED: $($attempt.error)"
    exit 1
}
