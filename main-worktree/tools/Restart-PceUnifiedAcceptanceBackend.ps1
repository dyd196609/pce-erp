[CmdletBinding()]
param()

# Active work-system release: refuse root-only backend restart before any process action.
throw 'The active work-system daily release requires its fixed full Start/Stop path. Root-only backend restart is disabled; no process was stopped.'
return


$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $sourceRoot 'backend'
$pythonPath = Join-Path $backendRoot 'venv\Scripts\python.exe'
$databasePath = 'D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3'
$runtimeRoot = Join-Path $sourceRoot '.pce-runtime\unified-development'
$statePath = Join-Path $runtimeRoot 'runtime.json'
$state = Get-Content -LiteralPath $statePath -Encoding utf8 | ConvertFrom-Json
$backendPort = 8075

if ($state.profile -ne 'PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE') { throw 'Runtime state is not the unified non-production acceptance profile.' }
if ([IO.Path]::GetFullPath($state.database) -ne [IO.Path]::GetFullPath($databasePath)) { throw 'Runtime state does not identify the approved acceptance database.' }

$listener = Get-NetTCPConnection -State Listen -LocalPort $backendPort -ErrorAction Stop
if (@($listener).Count -ne 1 -or $listener.OwningProcess -ne [int]$state.backend.pid) {
  throw "$backendPort listener does not match runtime state; refusing to stop an unknown process."
}
$listenerProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($state.backend.pid)"
$launcherProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($state.backend.launcherPid)"
$expectedCommand = "manage.py runserver 127.0.0.1:$backendPort --noreload"
if (-not $listenerProcess -or $listenerProcess.CommandLine -notlike "*$expectedCommand*") { throw "$backendPort listener command violates the acceptance startup contract." }
if (-not $launcherProcess -or $launcherProcess.CommandLine -notlike "*$expectedCommand*") { throw "$backendPort launcher command violates the acceptance startup contract." }

$env:PCE_DATABASE_PATH = $databasePath
$env:PCE_DATABASE_IDENTITY = 'PDE-OPERABLE-ACCEPTANCE-20260912'
$env:PCE_NON_PRODUCTION_ACCEPTANCE = '1'
$env:DJANGO_SETTINGS_MODULE = 'pce_backend.settings'
$env:PYTHONPATH = Join-Path $backendRoot 'venv\Lib\site-packages'
$env:PCE_RUNTIME_PROFILE = 'PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE'
$env:PCE_ENVIRONMENT_LABEL = 'PDE-OPERABLE-ACCEPTANCE-20260912 (non-production acceptance)'
$env:PCE_ACCEPTANCE_IDENTITY = 'PDE-OPERABLE-ACCEPTANCE-20260912'
& $pythonPath (Join-Path $backendRoot 'scripts\verify_unified_development_target.py')
if ($LASTEXITCODE -ne 0) { throw 'Acceptance database preflight failed; existing backend was not stopped.' }
$env:PCE_RUNTIME_LAUNCHER_VERIFIED = '1'

Stop-Process -Id ([int]$state.backend.pid) -Force
Stop-Process -Id ([int]$state.backend.launcherPid) -Force -ErrorAction SilentlyContinue

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backendOut = Join-Path $runtimeRoot "backend-$stamp.stdout.log"
$backendErr = Join-Path $runtimeRoot "backend-$stamp.stderr.log"
$backend = Start-Process -FilePath $pythonPath -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru `
  -ArgumentList @('manage.py','runserver',"127.0.0.1:$backendPort",'--noreload') `
  -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr

$backendReady = $false
foreach ($attempt in 1..40) {
  if ($backend.HasExited) { throw "Backend failed to start; inspect $backendErr" }
  try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$backendPort/api/users/" -UseBasicParsing -TimeoutSec 2
    if ($response.StatusCode -eq 200 -and $response.Content -match 'pce_emp107') { $backendReady = $true; break }
  } catch {}
  Start-Sleep -Milliseconds 250
}
if (-not $backendReady) {
  if (-not $backend.HasExited) { Stop-Process -Id $backend.Id -Force }
  throw "$backendPort did not return the acceptance account fingerprint in time."
}

$newListener = Get-NetTCPConnection -State Listen -LocalPort $backendPort -ErrorAction Stop
$state.backend.pid = [int]$newListener.OwningProcess
$state.backend.launcherPid = [int]$backend.Id
$state.startedAt = (Get-Date).ToString('o')
$state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding utf8

Write-Host "$backendPort acceptance backend reloaded: launcher PID $($backend.Id), listener PID $($newListener.OwningProcess)."
Write-Host "5173 remains on PID $($state.frontend.pid)."
