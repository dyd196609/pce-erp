[CmdletBinding()]
param()

# Active work-system release forwarding. Original body below is unreachable.
$pceActiveCore = 'C:\Users\DAODA\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
$pceActiveWrapper = 'D:\Dev-PCE\Source\work\dispatch-submit-readback-retention-20261028\active_runtime.ps1'
if (-not [IO.File]::Exists($pceActiveCore) -or -not [IO.File]::Exists($pceActiveWrapper)) { throw 'Active runtime entry missing; root fallback is prohibited' }
& $pceActiveCore -NoProfile -File $pceActiveWrapper -Mode Start -AuthorizedDailyRuntime
if ($LASTEXITCODE -ne 0) { throw 'Active runtime operation failed; root fallback is prohibited' }
return


$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $sourceRoot 'backend'
$frontendRoot = Join-Path $sourceRoot 'frontend'
$databasePath = 'D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3'
$pythonPath = Join-Path $backendRoot 'venv\Scripts\python.exe'
$npmPath = 'D:\Dev-PCE\nodejs\npm.cmd'
$runtimeRoot = Join-Path $sourceRoot '.pce-runtime\unified-development'
$statePath = Join-Path $runtimeRoot 'runtime.json'
$backendPort = 8075
$frontendPort = 5173

function Assert-PortFree([int]$Port) {
  $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  if ($listener) {
    throw "Port $Port is occupied by PID $($listener.OwningProcess -join ','). The unified launcher will not switch ports or replace a process."
  }
}

function Test-UnauthenticatedBoundary([string]$Uri) {
  try {
    $request = [System.Net.HttpWebRequest]::Create($Uri)
    $request.Method = 'GET'
    $request.Timeout = 2000
    $request.AllowAutoRedirect = $false
    $response = $request.GetResponse()
    try { return ([int]$response.StatusCode -eq 401) } finally { $response.Close() }
  } catch [System.Net.WebException] {
    if ($_.Exception.Response) {
      $statusCode = [int]$_.Exception.Response.StatusCode
      $_.Exception.Response.Close()
      return ($statusCode -eq 401)
    }
    return $false
  }
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw "Python runtime not found: $pythonPath" }
if (-not (Test-Path -LiteralPath $npmPath -PathType Leaf)) { throw "npm runtime not found: $npmPath" }
Assert-PortFree $backendPort
Assert-PortFree $frontendPort
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null

$env:PCE_DATABASE_PATH = $databasePath
$env:PCE_DATABASE_IDENTITY = 'PDE-OPERABLE-ACCEPTANCE-20260912'
$env:PCE_NON_PRODUCTION_ACCEPTANCE = '1'
$env:DJANGO_SETTINGS_MODULE = 'pce_backend.settings'
$env:PYTHONPATH = Join-Path $backendRoot 'venv\Lib\site-packages'
$env:PCE_RUNTIME_PROFILE = 'PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE'
$env:PCE_ENVIRONMENT_LABEL = 'PDE-OPERABLE-ACCEPTANCE-20260912 (non-production acceptance)'
$env:PCE_ACCEPTANCE_IDENTITY = 'PDE-OPERABLE-ACCEPTANCE-20260912'
$preflightJson = & $pythonPath (Join-Path $backendRoot 'scripts\verify_unified_development_target.py')
if ($LASTEXITCODE -ne 0) { throw 'Acceptance database preflight failed.' }
$preflight = $preflightJson | ConvertFrom-Json
$env:PCE_RUNTIME_LAUNCHER_VERIFIED = '1'

$backendOut = Join-Path $runtimeRoot 'backend.stdout.log'
$backendErr = Join-Path $runtimeRoot 'backend.stderr.log'
$backend = Start-Process -FilePath $pythonPath -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru `
  -ArgumentList @('manage.py','runserver',"127.0.0.1:$backendPort",'--noreload') `
  -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr

try {
  $backendReady = $false
  foreach ($attempt in 1..40) {
    if ($backend.HasExited) { throw "Backend failed to start; inspect $backendErr" }
    if (Test-UnauthenticatedBoundary "http://127.0.0.1:$backendPort/api/access-control/profile/") { $backendReady = $true; break }
    Start-Sleep -Milliseconds 250
  }
  if (-not $backendReady) { throw "$backendPort did not expose the expected unauthenticated API boundary in time." }
  $backendListenerPid = (Get-NetTCPConnection -State Listen -LocalPort $backendPort -ErrorAction Stop).OwningProcess

  $env:PCE_API_PROXY_TARGET = "http://127.0.0.1:$backendPort"
  $frontendOut = Join-Path $runtimeRoot 'frontend.stdout.log'
  $frontendErr = Join-Path $runtimeRoot 'frontend.stderr.log'
  $frontend = Start-Process -FilePath $npmPath -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru `
    -ArgumentList @('run','dev:unified-acceptance') `
    -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr

  $frontendReady = $false
  foreach ($attempt in 1..40) {
    if ($frontend.HasExited) { throw "Frontend failed to start; inspect $frontendErr" }
    if (Test-UnauthenticatedBoundary "http://localhost:$frontendPort/api/access-control/profile/") { $frontendReady = $true; break }
    Start-Sleep -Milliseconds 250
  }
  if (-not $frontendReady) { throw "$frontendPort did not proxy the expected unauthenticated API boundary to target $backendPort in time." }
  $frontendListenerPid = (Get-NetTCPConnection -State Listen -LocalPort $frontendPort -ErrorAction Stop).OwningProcess

  @{
    profile = 'PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE'
    contract = 'PCE-UNIFIED-DEVELOPMENT-RUNTIME-V2'
    frontend = @{ origin = "http://localhost:$frontendPort"; pid = $frontendListenerPid; launcherPid = $frontend.Id; proxyTarget = "http://127.0.0.1:$backendPort" }
    backend = @{ origin = "http://127.0.0.1:$backendPort"; pid = $backendListenerPid; launcherPid = $backend.Id; command = "manage.py runserver 127.0.0.1:$backendPort --noreload" }
    database = $databasePath
    databaseIdentity = 'PDE-OPERABLE-ACCEPTANCE-20260912'
    databaseSha256AtStart = $preflight.databaseSha256
    schemaContract = $preflight.schemaContract
    startedAt = (Get-Date).ToString('o')
  } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding utf8
  Write-Host "Unified non-production entry started: http://localhost:$frontendPort"
  Write-Host "Backend and proxy target: http://127.0.0.1:$backendPort"
  Write-Host "Runtime identity state: $statePath"
} catch {
  if ($frontendListenerPid) { Stop-Process -Id $frontendListenerPid -Force -ErrorAction SilentlyContinue }
  if ($backendListenerPid) { Stop-Process -Id $backendListenerPid -Force -ErrorAction SilentlyContinue }
  if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force }
  if (-not $backend.HasExited) { Stop-Process -Id $backend.Id -Force }
  throw
}
