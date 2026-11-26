Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $packageRoot 'rehearsal_common.ps1')
$passed = 0
$failed = 0
$results = @()

function Add-TestResult([string]$Name, [bool]$Pass, [string]$Detail = '') {
    if ($Pass) { $script:passed++ } else { $script:failed++ }
    $script:results += [pscustomobject]@{ name = $Name; result = if ($Pass) { 'PASS' } else { 'FAIL' }; detail = $Detail }
}
function Clone-Value($Value) { return ($Value | ConvertTo-Json -Depth 12 | ConvertFrom-Json) }
function Expect-Invalid([string]$Name, [scriptblock]$Action) {
    try { & $Action | Out-Null; Add-TestResult $Name $false 'accepted invalid identity' }
    catch { Add-TestResult $Name ($_.Exception.Message -like 'RUN_MANIFEST_PROCESS_IDENTITY_INVALID:*') $_.Exception.Message }
}
function Get-FreePort {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    try { $listener.Start(); return ([Net.IPEndPoint]$listener.LocalEndpoint).Port } finally { $listener.Stop() }
}

$testRoot = Join-Path $packageRoot (".identity-test-" + [guid]::NewGuid().ToString('N'))
$child = $null
try {
    New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
    $port = Get-FreePort
    $childScript = Join-Path $testRoot 'listener.ps1'
    [IO.File]::WriteAllText($childScript, "param([int]`$Port)`r`n`$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,`$Port)`r`ntry{`$listener.Start();[Console]::Out.WriteLine('READY');[Console]::Out.Flush();while(`$true){Start-Sleep -Seconds 1}}finally{`$listener.Stop()}`r`n", [Text.UTF8Encoding]::new($false))
    $out = Join-Path $testRoot 'child.out.log'
    $err = Join-Path $testRoot 'child.err.log'
    $powershell = Resolve-RehearsalExecutablePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $arguments = @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $childScript, '-Port', [string]$port)
    $child = Start-Process -FilePath $powershell -ArgumentList $arguments -WorkingDirectory $testRoot -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -WindowStyle Hidden
    for ($i=0; $i -lt 50 -and -not (Test-RehearsalProcessOwnsListener $child.Id $port); $i++) { Start-Sleep -Milliseconds 100 }
    if (-not (Test-RehearsalProcessOwnsListener $child.Id $port)) { throw 'controlled child did not own listener' }
    $runId = 'identity-test-' + [guid]::NewGuid().ToString('N')
    $backend = New-RehearsalProcessIdentity 'backend' $child $powershell $arguments $testRoot $port $runId
    $frontend = Clone-Value $backend
    $frontend.role = 'frontend'
    $manifest = [ordered]@{ contractVersion = 'TEST'; runId = $runId; processes = @($backend, $frontend) }
    $manifestPath = Join-Path $testRoot 'RUN_MANIFEST.json'
    Write-RehearsalJson $manifestPath $manifest
    $roundTrip = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json

    Add-TestResult 'valid frontend executable' ((Resolve-RehearsalExecutablePath $frontend.executable) -eq $powershell)
    $x=Clone-Value $frontend; $x.executable=$null; Expect-Invalid 'executable null' { Assert-RehearsalProcessIdentity $x $runId }
    $x=Clone-Value $frontend; $x.PSObject.Properties.Remove('executable'); Expect-Invalid 'executable missing' { Assert-RehearsalProcessIdentity $x $runId }
    $x=Clone-Value $frontend; $x.executable=''; Expect-Invalid 'executable empty' { Assert-RehearsalProcessIdentity $x $runId }
    $x=Clone-Value $frontend; $x.executable='   '; Expect-Invalid 'executable whitespace' { Assert-RehearsalProcessIdentity $x $runId }
    $x=Clone-Value $frontend; $x.executable='C:\does-not-exist\<bad>|.exe'; Expect-Invalid 'malformed executable path' { Assert-RehearsalProcessIdentity $x $runId }
    $x=Clone-Value $frontend; $x.executable='powershell.exe'; Expect-Invalid 'relative executable path' { Assert-RehearsalProcessIdentity $x $runId }
    $x=Clone-Value $frontend; $x.PSObject.Properties.Remove('pid'); Expect-Invalid 'PID missing' { Assert-RehearsalProcessIdentity $x $runId }
    $x=Clone-Value $frontend; $x.PSObject.Properties.Remove('startTime'); Expect-Invalid 'startTime missing' { Assert-RehearsalProcessIdentity $x $runId }
    $x=Clone-Value $frontend; $x.runId='wrong'; Expect-Invalid 'runId mismatch' { Assert-RehearsalProcessIdentity $x $runId }
    $x=Clone-Value $frontend; $x.ownedByRunId='wrong'; Expect-Invalid 'owner marker mismatch' { Assert-RehearsalProcessIdentity $x $runId }
    $x=Clone-Value $frontend; $badTime=[DateTimeOffset]::Parse($x.startTimeUtc).AddSeconds(2).UtcDateTime.ToString('o'); $x.startTime=$badTime; $x.startTimeUtc=$badTime; Expect-Invalid 'PID reused startTime mismatch' { Stop-RehearsalOwnedProcess $x $runId $false }
    $x=Clone-Value $frontend; $x.executable="$env:SystemRoot\System32\cmd.exe"; Expect-Invalid 'executable ownership mismatch' { Stop-RehearsalOwnedProcess $x $runId $false }
    $x=Clone-Value $frontend; $x.port=Get-FreePort; Expect-Invalid 'port ownership mismatch' { Stop-RehearsalOwnedProcess $x $runId $true }
    Add-TestResult 'valid backend identity' ((Assert-RehearsalProcessIdentity $backend $runId).role -eq 'backend')
    Add-TestResult 'valid frontend identity' ((Assert-RehearsalProcessIdentity $frontend $runId).role -eq 'frontend')
    Add-TestResult 'manifest write-read-schema round-trip' (Assert-RehearsalRunManifest $roundTrip)
    $invalidManifest=Clone-Value $roundTrip; $invalidManifest.processes[1].executable=$null
    Expect-Invalid 'STOP receives invalid Manifest' { Assert-RehearsalRunManifest $invalidManifest }
    $aliveBefore = $null -ne (Get-Process -Id $child.Id -ErrorAction SilentlyContinue)
    try { $null=Assert-RehearsalRunManifest $invalidManifest } catch {}
    $aliveAfter = $null -ne (Get-Process -Id $child.Id -ErrorAction SilentlyContinue)
    Add-TestResult 'invalid Manifest does NOT kill unknown process' ($aliveBefore -and $aliveAfter)
    $stopped = Stop-RehearsalOwnedProcess $backend $runId $true
    $finalAbsent = $null -eq (Get-Process -Id $child.Id -ErrorAction SilentlyContinue)
    Add-TestResult 'REAL PROCESS IDENTITY ROUND-TRIP' ($stopped -eq 'STOPPED' -and $finalAbsent)
} catch {
    $detail = $_.Exception.Message
    if (Test-Path -LiteralPath $err -PathType Leaf) { $detail += ' / child stderr: ' + (Get-Content -Raw -LiteralPath $err) }
    Add-TestResult 'test harness' $false $detail
} finally {
    if ($null -ne $child -and (Get-Process -Id $child.Id -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $child.Id -Force -ErrorAction SilentlyContinue
        try { $child.WaitForExit(5000) | Out-Null } catch {}
    }
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue }
}

$results | Format-Table -AutoSize
Write-Host "RUN_MANIFEST_PROCESS_IDENTITY_TESTS: $passed PASS / $failed FAIL / 0 SKIP"
if ($failed -ne 0) { exit 1 }
