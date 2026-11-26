Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $packageRoot 'rehearsal_common.ps1')

$results = [System.Collections.Generic.List[object]]::new()
function Add-Result([string]$Name, [bool]$Passed, [string]$Detail) {
    $results.Add([pscustomobject]@{ name = $Name; passed = $Passed; detail = $Detail })
    if (-not $Passed) { throw "HTTPCLIENT_DEPENDENCY_TEST_FAILED: $Name / $Detail" }
}
function Assert-FailsClosed([string]$Name, [scriptblock]$Action, [string]$ExpectedPrefix) {
    try { & $Action; Add-Result $Name $false 'unexpected success' } catch { Add-Result $Name ($_.Exception.Message.StartsWith($ExpectedPrefix, [StringComparison]::Ordinal)) $_.Exception.Message }
}

$pathBefore = [Environment]::GetEnvironmentVariable('PATH', 'Process')
$modulePathBefore = [Environment]::GetEnvironmentVariable('PSModulePath', 'Process')
$assemblyBefore = @([AppDomain]::CurrentDomain.GetAssemblies() | Where-Object { $_.GetName().Name -eq 'System.Net.Http' })
Add-Result 'Windows PowerShell 5.1 exact host' ($PSVersionTable.PSEdition -eq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and (Get-Process -Id $PID).Path -eq 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe') ((Get-Process -Id $PID).Path)
Add-Result 'clean process assembly initially unloaded' ($assemblyBefore.Count -eq 0) "count=$($assemblyBefore.Count)"

$first = Initialize-RehearsalHttpClientDependency
Add-Result 'assembly bootstrap' ($first.systemNetHttpAssemblyLoad -eq 'PASS' -and $first.assemblyFullName.StartsWith('System.Net.Http,')) $first.assemblyFullName
Add-Result 'HttpClient type resolution' ($first.httpClientTypeResolution -eq 'PASS' -and $first.typeFullName -eq 'System.Net.Http.HttpClient') $first.typeFullName
Add-Result 'HttpClient instantiation' ($first.httpClientInstantiation -eq 'PASS') $first.httpClientInstantiation
$second = Initialize-RehearsalHttpClientDependency
Add-Result 'bootstrap idempotent' ($second.httpClientInstantiation -eq 'PASS') $second.httpClientInstantiation
Add-Result 'already-loaded assembly repeat' (@([AppDomain]::CurrentDomain.GetAssemblies() | Where-Object { $_.GetName().Name -eq 'System.Net.Http' }).Count -eq 1) 'single loaded identity'
Assert-FailsClosed 'assembly load failure fails closed' { Import-RehearsalRequiredAssembly 'PCE.Definitely.Unavailable.Assembly' } 'REQUIRED_SYSTEM_ASSEMBLY_UNAVAILABLE:'
Assert-FailsClosed 'malformed assembly fails closed' { Import-RehearsalRequiredAssembly ' ' } 'REQUIRED_ASSEMBLY_NAME_MALFORMED'
Assert-FailsClosed 'unavailable type fails closed' { Assert-RehearsalRequiredType 'PCE.Definitely.Unavailable.Type' } 'REQUIRED_TYPE_UNAVAILABLE:'
Assert-FailsClosed 'malformed type fails closed' { Assert-RehearsalRequiredType '' } 'REQUIRED_TYPE_NAME_MALFORMED'

$precheckSource = [IO.File]::ReadAllText((Join-Path $packageRoot 'precheck_schema_rehearsal.ps1'))
$mainSource = [IO.File]::ReadAllText((Join-Path $packageRoot 'start_schema_rehearsal.ps1'))
Add-Result 'Precheck uses shared bootstrap' $precheckSource.Contains('Initialize-RehearsalHttpClientDependency') 'shared function call'
Add-Result 'Main Launcher uses shared bootstrap' ($mainSource.Contains('Initialize-RehearsalHttpClientDependency') -and $mainSource.Contains('New-RehearsalHttpClient')) 'shared init and factory'
$bootstrapIndex = $mainSource.IndexOf('Initialize-RehearsalHttpClientDependency', [StringComparison]::Ordinal)
$processIndex = $mainSource.IndexOf('Start-Process', [StringComparison]::Ordinal)
$readinessIndex = $mainSource.IndexOf('New-RehearsalHttpClient', [StringComparison]::Ordinal)
Add-Result 'dependency precedes process/readiness' ($bootstrapIndex -ge 0 -and $processIndex -gt $bootstrapIndex -and $readinessIndex -gt $processIndex) "$bootstrapIndex/$processIndex/$readinessIndex"
Add-Result 'same-process dependency evidence' ($first.processId -eq $PID -and $second.processId -eq $PID) "pid=$PID"
Add-Result 'no PowerShell 7 dependency' ($first.powerShellEdition -eq 'Desktop' -and $first.powerShellVersion.StartsWith('5.1.')) "$($first.powerShellEdition)/$($first.powerShellVersion)"
Add-Result 'no process environment mutation' ([string]::Equals($pathBefore, [Environment]::GetEnvironmentVariable('PATH', 'Process'), [StringComparison]::Ordinal) -and [string]::Equals($modulePathBefore, [Environment]::GetEnvironmentVariable('PSModulePath', 'Process'), [StringComparison]::Ordinal)) 'PATH and PSModulePath unchanged'
Add-Result 'system GAC dependency only' ($first.assemblyLocation -like 'C:\Windows\Microsoft.Net\assembly\GAC_MSIL\System.Net.Http\*') $first.assemblyLocation

$summary = [ordered]@{ contractVersion = 'PCE-PS51-HTTPCLIENT-DEPENDENCY-TEST-V1'; total = $results.Count; passed = @($results | Where-Object passed).Count; failed = @($results | Where-Object { -not $_.passed }).Count; results = @($results) }
$summary | ConvertTo-Json -Depth 8
if ($summary.failed -ne 0) { exit 1 }
