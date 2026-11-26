Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $packageRoot 'rehearsal_common.ps1')

$results = [System.Collections.Generic.List[object]]::new()
function Add-TestResult([string]$Name, [bool]$Passed, [string]$Detail = '') {
    $results.Add([pscustomobject]@{ name = $Name; passed = $Passed; detail = $Detail })
    if (-not $Passed) { throw "PACKAGE_STATUS_CONTRACT_TEST_FAILED: $Name / $Detail" }
}
function Assert-Rejected([string]$Name, [scriptblock]$Action, [string]$ExpectedCode) {
    try { & $Action; Add-TestResult $Name $false 'unexpected acceptance' } catch {
        Add-TestResult $Name ($_.Exception.Message.StartsWith($ExpectedCode, [System.StringComparison]::Ordinal)) $_.Exception.Message
    }
}

$config = Read-RehearsalConfig $packageRoot
$contract = Read-RehearsalPackageStatusContract $packageRoot
$fixtureParent = Join-Path $config.runtimeRoot 'package-status-contract-tests'
$fixtureRoot = Join-Path $fixtureParent ([guid]::NewGuid().ToString('N'))
$resolvedParent = [IO.Path]::GetFullPath($fixtureParent)
$resolvedFixture = [IO.Path]::GetFullPath($fixtureRoot)
if (-not $resolvedFixture.StartsWith("$resolvedParent\", [System.StringComparison]::OrdinalIgnoreCase)) { throw 'TEST_FIXTURE_PATH_UNSAFE' }

try {
    New-Item -ItemType Directory -Force -Path $fixtureRoot | Out-Null
    Add-TestResult 'manifest canonical status' ([string]::Equals($config.packageStatus, 'READY_FOR_USER_AUTHORIZED_REHEARSAL', [System.StringComparison]::Ordinal)) $config.packageStatus
    Add-TestResult 'launcher accepts canonical rehearsal status' (Assert-RehearsalEntryStatus $config $contract) 'accepted'
    Assert-Rejected 'launcher rejects generic READY' { Assert-RehearsalEntryStatus ([pscustomobject]@{ packageStatus = 'READY' }) $contract } 'PACKAGE_NOT_READY_FOR_USER_AUTHORIZED_REHEARSAL:'
    Assert-Rejected 'launcher rejects blocked state' { Assert-RehearsalEntryStatus ([pscustomobject]@{ packageStatus = 'BLOCKED_PENDING_FULL_BUILD' }) $contract } 'PACKAGE_NOT_READY_FOR_USER_AUTHORIZED_REHEARSAL:'
    Assert-Rejected 'launcher rejects unknown state' { Assert-RehearsalEntryStatus ([pscustomobject]@{ packageStatus = 'SOMETHING_UNKNOWN' }) $contract } 'PACKAGE_NOT_READY_FOR_USER_AUTHORIZED_REHEARSAL:'
    Assert-Rejected 'launcher rejects production-authorization state' { Assert-RehearsalEntryStatus ([pscustomobject]@{ packageStatus = 'READY_FOR_SEPARATE_PRODUCTION_AUTHORIZATION' }) $contract } 'PACKAGE_NOT_READY_FOR_USER_AUTHORIZED_REHEARSAL:'
    Assert-Rejected 'state comparison is ordinal exact' { Assert-RehearsalEntryStatus ([pscustomobject]@{ packageStatus = 'ready_for_user_authorized_rehearsal' }) $contract } 'PACKAGE_NOT_READY_FOR_USER_AUTHORIZED_REHEARSAL:'

    $missingRoot = Join-Path $fixtureRoot 'missing'; New-Item -ItemType Directory -Force -Path $missingRoot | Out-Null
    [IO.File]::WriteAllText((Join-Path $missingRoot 'REHEARSAL_MANIFEST.json'), '{"contractVersion":"fixture"}', [Text.UTF8Encoding]::new($false))
    Assert-Rejected 'missing status rejects' { Read-RehearsalConfig $missingRoot } 'PACKAGE_STATUS_MISSING'
    $nullRoot = Join-Path $fixtureRoot 'null'; New-Item -ItemType Directory -Force -Path $nullRoot | Out-Null
    [IO.File]::WriteAllText((Join-Path $nullRoot 'REHEARSAL_MANIFEST.json'), '{"packageStatus":null}', [Text.UTF8Encoding]::new($false))
    Assert-Rejected 'null status rejects' { Read-RehearsalConfig $nullRoot } 'PACKAGE_STATUS_NULL'
    $malformedStatusRoot = Join-Path $fixtureRoot 'malformed-status'; New-Item -ItemType Directory -Force -Path $malformedStatusRoot | Out-Null
    [IO.File]::WriteAllText((Join-Path $malformedStatusRoot 'REHEARSAL_MANIFEST.json'), '{"packageStatus":{"value":"READY_FOR_USER_AUTHORIZED_REHEARSAL"}}', [Text.UTF8Encoding]::new($false))
    Assert-Rejected 'malformed status rejects' { Read-RehearsalConfig $malformedStatusRoot } 'PACKAGE_STATUS_MALFORMED'
    $malformedJsonRoot = Join-Path $fixtureRoot 'malformed-json'; New-Item -ItemType Directory -Force -Path $malformedJsonRoot | Out-Null
    [IO.File]::WriteAllText((Join-Path $malformedJsonRoot 'REHEARSAL_MANIFEST.json'), '{not-json', [Text.UTF8Encoding]::new($false))
    Assert-Rejected 'malformed manifest rejects' { Read-RehearsalConfig $malformedJsonRoot } 'MANIFEST_JSON_MALFORMED:'

    $contractText = [IO.File]::ReadAllText((Join-Path $packageRoot 'PACKAGE_STATUS_CONTRACT.json'))
    $contractRoundTrip = $contractText | ConvertFrom-Json | ConvertTo-Json -Depth 8 | ConvertFrom-Json
    Add-TestResult 'JSON schema round-trip' ($contractRoundTrip.schemaVersion -eq 'PCE-LAUNCHER-PACKAGE-STATUS-CONTRACT-V1' -and $contractRoundTrip.comparison -eq 'ordinal-exact') 'schema and comparison preserved'
    Add-TestResult 'producer consumer round-trip' ([string]::Equals($config.packageStatus, $contract.rehearsalEntry.acceptedPackageStatus, [System.StringComparison]::Ordinal)) 'manifest equals authority'

    $precheckSource = [IO.File]::ReadAllText((Join-Path $packageRoot 'precheck_schema_rehearsal.ps1'))
    $mainSource = [IO.File]::ReadAllText((Join-Path $packageRoot 'start_schema_rehearsal.ps1'))
    Add-TestResult 'precheck and main use same contract' ($precheckSource.Contains('Read-RehearsalPackageStatusContract') -and $precheckSource.Contains('Assert-RehearsalEntryStatus') -and $mainSource.Contains('Read-RehearsalPackageStatusContract') -and $mainSource.Contains('Assert-RehearsalEntryStatus')) 'shared common validator'
    $cmdSource = [IO.File]::ReadAllText((Join-Path $packageRoot 'START_SCHEMA_REHEARSAL.cmd'))
    $statusIndex = $mainSource.IndexOf('Assert-RehearsalEntryStatus', [System.StringComparison]::Ordinal)
    $copyIndex = $mainSource.IndexOf('Copy-RehearsalBackend', [System.StringComparison]::Ordinal)
    $startIndex = $mainSource.IndexOf('Start-Process', [System.StringComparison]::Ordinal)
    Add-TestResult 'command entry cannot bypass status check' ($cmdSource.Contains('start_schema_rehearsal.ps1') -and $statusIndex -ge 0 -and $copyIndex -gt $statusIndex -and $startIndex -gt $statusIndex) 'status gate precedes copy and process start'
} finally {
    if (Test-Path -LiteralPath $fixtureRoot) { Remove-Item -LiteralPath $fixtureRoot -Recurse -Force }
    if ((Test-Path -LiteralPath $fixtureParent) -and @(Get-ChildItem -LiteralPath $fixtureParent -Force).Count -eq 0) { Remove-Item -LiteralPath $fixtureParent -Force }
}

$summary = [ordered]@{ contractVersion = 'PCE-LAUNCHER-PACKAGE-STATUS-CONTRACT-TEST-V1'; total = $results.Count; passed = @($results | Where-Object passed).Count; failed = @($results | Where-Object { -not $_.passed }).Count; results = @($results) }
$summary | ConvertTo-Json -Depth 8
if ($summary.failed -ne 0) { exit 1 }
