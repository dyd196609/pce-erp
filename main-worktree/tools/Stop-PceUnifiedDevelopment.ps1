[CmdletBinding()]
param()

# Active work-system release forwarding. Original body below is unreachable.
$pceActiveCore = 'C:\Users\DAODA\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
$pceActiveWrapper = 'D:\Dev-PCE\Source\work\dispatch-submit-readback-retention-20261028\active_runtime.ps1'
if (-not [IO.File]::Exists($pceActiveCore) -or -not [IO.File]::Exists($pceActiveWrapper)) { throw 'Active runtime entry missing; root fallback is prohibited' }
& $pceActiveCore -NoProfile -File $pceActiveWrapper -Mode Stop -AuthorizedDailyRuntime
if ($LASTEXITCODE -ne 0) { throw 'Active runtime operation failed; root fallback is prohibited' }
return


$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$statePath = Join-Path $sourceRoot '.pce-runtime\unified-development\runtime.json'
if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
  throw "Unified launcher runtime state not found: $statePath"
}
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if ($state.contract -ne 'PCE-UNIFIED-DEVELOPMENT-RUNTIME-V2') {
  throw 'Runtime state is not the current unified contract; refusing stale PIDs.'
}
if ($state.backend.origin -ne 'http://127.0.0.1:8075' -or $state.frontend.origin -ne 'http://localhost:5173') {
  throw 'Runtime state ports do not match the unified contract; refusing unknown processes.'
}
$backendListeners = @(Get-NetTCPConnection -State Listen -LocalPort 8075 -ErrorAction SilentlyContinue)
$frontendListeners = @(Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue)
if ($backendListeners.OwningProcess -notcontains [int]$state.backend.pid) {
  throw '8075 listener does not match runtime state; refusing unknown process.'
}
if ($frontendListeners.OwningProcess -notcontains [int]$state.frontend.pid) {
  throw '5173 listener does not match runtime state; refusing unknown process.'
}
$backendProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($state.backend.pid)"
$frontendProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($state.frontend.pid)"
if (-not $backendProcess -or $backendProcess.CommandLine -notlike '*manage.py runserver 127.0.0.1:8075 --noreload*') {
  throw '8075 command does not match the unified startup contract.'
}
if (-not $frontendProcess -or $frontendProcess.CommandLine -notlike '*vite*--host localhost*--port 5173*--mode unified-acceptance*') {
  throw '5173 command does not match the unified startup contract.'
}
foreach ($entry in @($state.frontend, $state.backend)) {
  foreach ($id in @($entry.pid, $entry.launcherPid)) {
    if (-not $id) { continue }
    $process = Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue
    if ($process) { Stop-Process -Id $process.Id -Force }
  }
}
Remove-Item -LiteralPath $statePath -Force
Write-Host 'Stopped only the unified non-production processes recorded by the launcher.'
