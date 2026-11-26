Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Import-RehearsalRequiredAssembly([string]$AssemblyName) {
    if ([string]::IsNullOrWhiteSpace($AssemblyName)) { throw 'REQUIRED_ASSEMBLY_NAME_MALFORMED' }
    try { Add-Type -AssemblyName $AssemblyName -ErrorAction Stop } catch { throw "REQUIRED_SYSTEM_ASSEMBLY_UNAVAILABLE: $AssemblyName / $($_.Exception.Message)" }
    $assembly = @([AppDomain]::CurrentDomain.GetAssemblies() | Where-Object { $_.GetName().Name -eq $AssemblyName }) | Select-Object -First 1
    if ($null -eq $assembly) { throw "REQUIRED_SYSTEM_ASSEMBLY_NOT_LOADED: $AssemblyName" }
    return $assembly
}

function Assert-RehearsalRequiredType([string]$TypeName) {
    if ([string]::IsNullOrWhiteSpace($TypeName)) { throw 'REQUIRED_TYPE_NAME_MALFORMED' }
    $type = $TypeName -as [type]
    if ($null -eq $type) { throw "REQUIRED_TYPE_UNAVAILABLE: $TypeName" }
    return $type
}

function Initialize-RehearsalHttpClientDependency {
    $assembly = Import-RehearsalRequiredAssembly 'System.Net.Http'
    $type = Assert-RehearsalRequiredType 'System.Net.Http.HttpClient'
    $probe = $null
    try { $probe = [Activator]::CreateInstance($type) } catch { throw "HTTPCLIENT_INSTANTIATION_FAILED: $($_.Exception.Message)" } finally { if ($null -ne $probe) { $probe.Dispose() } }
    return [pscustomobject]@{
        systemNetHttpAssemblyLoad = 'PASS'
        httpClientTypeResolution = 'PASS'
        httpClientInstantiation = 'PASS'
        assemblyFullName = $assembly.FullName
        assemblyLocation = $assembly.Location
        typeFullName = $type.FullName
        processId = $PID
        powerShellVersion = $PSVersionTable.PSVersion.ToString()
        powerShellEdition = $PSVersionTable.PSEdition
        clrVersion = $PSVersionTable.CLRVersion.ToString()
        processArchitecture = if ([Environment]::Is64BitProcess) { 'x64' } else { 'x86' }
    }
}

function New-RehearsalHttpClient {
    $null = Initialize-RehearsalHttpClientDependency
    return [System.Net.Http.HttpClient]::new()
}

function Read-RehearsalConfig([string]$PackageRoot) {
    $manifestPath = Join-Path $PackageRoot 'REHEARSAL_MANIFEST.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "MANIFEST_MISSING: $manifestPath" }
    try { $config = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json } catch { throw "MANIFEST_JSON_MALFORMED: $($_.Exception.Message)" }
    if ($null -eq $config -or $config -isnot [psobject]) { throw 'MANIFEST_ROOT_MALFORMED' }
    $statusProperty = $config.PSObject.Properties['packageStatus']
    if ($null -eq $statusProperty) { throw 'PACKAGE_STATUS_MISSING' }
    if ($null -eq $statusProperty.Value) { throw 'PACKAGE_STATUS_NULL' }
    if ($statusProperty.Value -isnot [string]) { throw 'PACKAGE_STATUS_MALFORMED' }
    if ([string]::IsNullOrWhiteSpace($statusProperty.Value)) { throw 'PACKAGE_STATUS_EMPTY' }
    return $config
}

function Read-RehearsalPackageStatusContract([string]$PackageRoot) {
    $contractPath = Join-Path $PackageRoot 'PACKAGE_STATUS_CONTRACT.json'
    if (-not (Test-Path -LiteralPath $contractPath -PathType Leaf)) { throw "PACKAGE_STATUS_CONTRACT_MISSING: $contractPath" }
    try { $contract = Get-Content -Raw -LiteralPath $contractPath | ConvertFrom-Json } catch { throw "PACKAGE_STATUS_CONTRACT_MALFORMED: $($_.Exception.Message)" }
    if ($contract.schemaVersion -ne 'PCE-LAUNCHER-PACKAGE-STATUS-CONTRACT-V1') { throw 'PACKAGE_STATUS_CONTRACT_VERSION_UNSUPPORTED' }
    if ($contract.comparison -ne 'ordinal-exact') { throw 'PACKAGE_STATUS_COMPARISON_NOT_EXACT' }
    if ($contract.rehearsalEntry.acceptedPackageStatus -isnot [string] -or [string]::IsNullOrWhiteSpace($contract.rehearsalEntry.acceptedPackageStatus)) { throw 'PACKAGE_STATUS_ACCEPTED_VALUE_MALFORMED' }
    if ($contract.rehearsalEntry.requiresExplicitUserAuthorization -ne $true) { throw 'PACKAGE_STATUS_USER_AUTHORIZATION_GATE_MISSING' }
    return $contract
}

function Assert-RehearsalEntryStatus($Config, $StatusContract) {
    $actual = $Config.packageStatus
    $expected = $StatusContract.rehearsalEntry.acceptedPackageStatus
    if (-not [string]::Equals($actual, $expected, [System.StringComparison]::Ordinal)) {
        throw "PACKAGE_NOT_READY_FOR_USER_AUTHORIZED_REHEARSAL: $actual"
    }
    return $true
}

function Test-RehearsalPortAvailable([int]$Port) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse('127.0.0.1'), $Port)
    try { $listener.Start(); return $true } catch { return $false } finally { try { $listener.Stop() } catch {} }
}

function Throw-RehearsalProcessIdentityInvalid([string]$Detail) {
    throw "RUN_MANIFEST_PROCESS_IDENTITY_INVALID: $Detail"
}

function Get-RehearsalRequiredProperty($Value, [string]$Name) {
    if ($null -eq $Value) { Throw-RehearsalProcessIdentityInvalid "object missing while reading $Name" }
    if ($Value -is [System.Collections.IDictionary]) {
        if (-not $Value.Contains($Name)) { Throw-RehearsalProcessIdentityInvalid "required field missing: $Name" }
        return $Value[$Name]
    }
    $property = $Value.PSObject.Properties[$Name]
    if ($null -eq $property) { Throw-RehearsalProcessIdentityInvalid "required field missing: $Name" }
    return $property.Value
}

function Resolve-RehearsalExecutablePath([string]$Executable) {
    if ([string]::IsNullOrWhiteSpace($Executable)) { Throw-RehearsalProcessIdentityInvalid 'executable must be a non-empty string' }
    try {
        if (-not [System.IO.Path]::IsPathRooted($Executable)) { Throw-RehearsalProcessIdentityInvalid "executable must be absolute: $Executable" }
        $resolved = [System.IO.Path]::GetFullPath($Executable)
    } catch {
        if ($_.Exception.Message -like 'RUN_MANIFEST_PROCESS_IDENTITY_INVALID:*') { throw }
        Throw-RehearsalProcessIdentityInvalid "executable path malformed: $Executable"
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) { Throw-RehearsalProcessIdentityInvalid "executable does not exist: $resolved" }
    return $resolved
}

function Assert-RehearsalProcessIdentity($Record, [string]$ExpectedRunId) {
    $role = Get-RehearsalRequiredProperty $Record 'role'
    if ($role -isnot [string] -or [string]::IsNullOrWhiteSpace($role)) { Throw-RehearsalProcessIdentityInvalid 'role must be a non-empty string' }
    $pidValue = Get-RehearsalRequiredProperty $Record 'pid'
    if (($pidValue -isnot [int] -and $pidValue -isnot [long]) -or [long]$pidValue -le 0) { Throw-RehearsalProcessIdentityInvalid "$role pid must be a positive integer" }
    $parentPid = Get-RehearsalRequiredProperty $Record 'parentPid'
    if (($parentPid -isnot [int] -and $parentPid -isnot [long]) -or [long]$parentPid -le 0) { Throw-RehearsalProcessIdentityInvalid "$role parentPid must be a positive integer" }
    $executableValue = Get-RehearsalRequiredProperty $Record 'executable'
    if ($executableValue -isnot [string]) { Throw-RehearsalProcessIdentityInvalid "$role executable must be a string" }
    $executable = Resolve-RehearsalExecutablePath $executableValue
    $commandLine = Get-RehearsalRequiredProperty $Record 'commandLine'
    if ($commandLine -isnot [string] -or [string]::IsNullOrWhiteSpace($commandLine)) { Throw-RehearsalProcessIdentityInvalid "$role commandLine must be a non-empty string" }
    $startTime = Get-RehearsalRequiredProperty $Record 'startTime'
    $startTimeUtc = Get-RehearsalRequiredProperty $Record 'startTimeUtc'
    try {
        $parsedStart = [DateTimeOffset]::ParseExact([string]$startTime, 'o', [Globalization.CultureInfo]::InvariantCulture)
        $parsedStartUtc = [DateTimeOffset]::ParseExact([string]$startTimeUtc, 'o', [Globalization.CultureInfo]::InvariantCulture)
    } catch { Throw-RehearsalProcessIdentityInvalid "$role startTime/startTimeUtc must use round-trip format" }
    if ($parsedStart.UtcDateTime.Ticks -ne $parsedStartUtc.UtcDateTime.Ticks) { Throw-RehearsalProcessIdentityInvalid "$role startTime fields disagree" }
    $ownedByRunId = Get-RehearsalRequiredProperty $Record 'ownedByRunId'
    $recordRunId = Get-RehearsalRequiredProperty $Record 'runId'
    if ($ownedByRunId -isnot [string] -or -not [string]::Equals($ownedByRunId, $ExpectedRunId, [StringComparison]::Ordinal)) { Throw-RehearsalProcessIdentityInvalid "$role owner marker mismatch" }
    if ($recordRunId -isnot [string] -or -not [string]::Equals($recordRunId, $ExpectedRunId, [StringComparison]::Ordinal)) { Throw-RehearsalProcessIdentityInvalid "$role runId mismatch" }
    $hostValue = Get-RehearsalRequiredProperty $Record 'host'
    if ($hostValue -isnot [string] -or [string]::IsNullOrWhiteSpace($hostValue)) { Throw-RehearsalProcessIdentityInvalid "$role host must be a non-empty string" }
    $workingDirectory = Get-RehearsalRequiredProperty $Record 'workingDirectory'
    if ($workingDirectory -isnot [string] -or [string]::IsNullOrWhiteSpace($workingDirectory) -or -not [System.IO.Path]::IsPathRooted($workingDirectory)) { Throw-RehearsalProcessIdentityInvalid "$role workingDirectory must be absolute" }
    $port = Get-RehearsalRequiredProperty $Record 'port'
    if (($port -isnot [int] -and $port -isnot [long]) -or [long]$port -lt 1 -or [long]$port -gt 65535) { Throw-RehearsalProcessIdentityInvalid "$role port must be in 1..65535" }
    return [pscustomobject]@{ role = $role; pid = [int]$pidValue; executable = $executable; startTimeUtc = $parsedStartUtc.UtcDateTime; port = [int]$port }
}

function Assert-RehearsalRunManifest($Run) {
    $runId = Get-RehearsalRequiredProperty $Run 'runId'
    if ($runId -isnot [string] -or [string]::IsNullOrWhiteSpace($runId)) { Throw-RehearsalProcessIdentityInvalid 'runId must be a non-empty string' }
    $processes = Get-RehearsalRequiredProperty $Run 'processes'
    if ($null -eq $processes -or @($processes).Count -lt 1) { Throw-RehearsalProcessIdentityInvalid 'processes must contain at least one owned process' }
    $roles = @{}
    foreach ($record in @($processes)) {
        $identity = Assert-RehearsalProcessIdentity $record $runId
        if ($roles.ContainsKey($identity.role)) { Throw-RehearsalProcessIdentityInvalid "duplicate role: $($identity.role)" }
        $roles[$identity.role] = $true
    }
    foreach ($requiredRole in @('backend', 'frontend')) { if (-not $roles.ContainsKey($requiredRole)) { Throw-RehearsalProcessIdentityInvalid "required process role missing: $requiredRole" } }
    return $true
}

function ConvertTo-RehearsalCommandLine([string]$Executable, [string[]]$Arguments) {
    $tokens = @($Executable) + @($Arguments)
    return (($tokens | ForEach-Object { '"' + ([string]$_).Replace('"', '\"') + '"' }) -join ' ')
}

function New-RehearsalProcessIdentity([string]$Role, $Process, [string]$Executable, [string[]]$Arguments, [string]$WorkingDirectory, [int]$Port, [string]$RunId) {
    $resolvedExecutable = Resolve-RehearsalExecutablePath $Executable
    if ($null -eq $Process -or $Process.Id -le 0) { Throw-RehearsalProcessIdentityInvalid "$Role process was not started" }
    $start = $Process.StartTime.ToUniversalTime().ToString('o')
    $record = [ordered]@{
        role = $Role; pid = [int]$Process.Id; parentPid = [int]$PID; executable = $resolvedExecutable
        commandLine = ConvertTo-RehearsalCommandLine $resolvedExecutable $Arguments
        startTime = $start; startTimeUtc = $start; ownedByRunId = $RunId; runId = $RunId
        host = [Environment]::MachineName; workingDirectory = [System.IO.Path]::GetFullPath($WorkingDirectory); port = $Port
    }
    $null = Assert-RehearsalProcessIdentity $record $RunId
    return $record
}

function Test-RehearsalProcessOwnsListener([int]$ProcessId, [int]$Port) {
    $lines = & "$env:SystemRoot\System32\netstat.exe" -ano -p tcp
    if ($LASTEXITCODE -ne 0) { Throw-RehearsalProcessIdentityInvalid 'listener ownership enumeration failed' }
    $pattern = '^\s*TCP\s+\S+:' + [regex]::Escape([string]$Port) + '\s+\S+\s+LISTENING\s+' + [regex]::Escape([string]$ProcessId) + '\s*$'
    return @($lines | Where-Object { $_ -match $pattern }).Count -gt 0
}

function Stop-RehearsalOwnedProcess($Record, [string]$ExpectedRunId, [bool]$RequirePortOwnership = $true) {
    $identity = Assert-RehearsalProcessIdentity $Record $ExpectedRunId
    try { $process = Get-Process -Id $identity.pid -ErrorAction Stop } catch [Microsoft.PowerShell.Commands.ProcessCommandException] { return 'NOT_RUNNING' }
    $actualStart = $process.StartTime.ToUniversalTime()
    if ($actualStart.Ticks -ne $identity.startTimeUtc.Ticks) { Throw-RehearsalProcessIdentityInvalid "$($identity.role) start time ownership mismatch for PID $($identity.pid)" }
    $actualExecutableValue = $process.Path
    if ($actualExecutableValue -isnot [string]) { Throw-RehearsalProcessIdentityInvalid "$($identity.role) actual executable unavailable for PID $($identity.pid)" }
    $actualExecutable = Resolve-RehearsalExecutablePath $actualExecutableValue
    if (-not [string]::Equals($actualExecutable, $identity.executable, [StringComparison]::OrdinalIgnoreCase)) { Throw-RehearsalProcessIdentityInvalid "$($identity.role) executable ownership mismatch for PID $($identity.pid)" }
    if ($RequirePortOwnership) {
        if (-not (Test-RehearsalProcessOwnsListener $identity.pid $identity.port)) { Throw-RehearsalProcessIdentityInvalid "$($identity.role) port ownership mismatch for PID $($identity.pid) on $($identity.port)" }
    }
    Stop-Process -Id $identity.pid -Force -ErrorAction Stop
    try { $process.WaitForExit(10000) | Out-Null } catch {}
    if (Get-Process -Id $identity.pid -ErrorAction SilentlyContinue) { Throw-RehearsalProcessIdentityInvalid "$($identity.role) exact cleanup did not terminate PID $($identity.pid)" }
    return 'STOPPED'
}

function Invoke-RobocopyChecked([string]$Source, [string]$Destination, [string[]]$ExtraArguments) {
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) { throw "Source directory missing: $Source" }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $arguments = @($Source, $Destination, '/E', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP') + $ExtraArguments
    & robocopy.exe @arguments | Out-Null
    if ($LASTEXITCODE -gt 7) { throw "Robocopy failed ($LASTEXITCODE): $Source -> $Destination" }
}

function Copy-RehearsalBackend($Config, [string]$Destination) {
    Invoke-RobocopyChecked $Config.backendSource $Destination @('/XD', 'venv', '__pycache__', '.pytest_cache', '/XF', 'db.sqlite3', '*.pyc')
    Invoke-RobocopyChecked $Config.candidateOverlay $Destination @('/XD', '__pycache__', '/XF', '*.pyc')
}

function Get-RehearsalHashEntries($Config, [string]$PackageRoot) {
    $roots = @(
        @{ Root = $Config.frontendSource; Includes = @('src', 'index.html', 'vite.config.js', 'package.json', 'package-lock.json', 'dist') },
        @{ Root = $Config.backendSource; Includes = @('pce_backend', 'pde', 'workflow_runtime', 'manage.py') },
        @{ Root = $Config.candidateOverlay; Includes = @('.') },
        @{ Root = $PackageRoot; Includes = @('START_SCHEMA_REHEARSAL.cmd', 'STOP_SCHEMA_REHEARSAL.cmd', 'start_schema_rehearsal.ps1', 'stop_schema_rehearsal.ps1', 'precheck_schema_rehearsal.ps1', 'rehearsal_common.ps1', 'serve_rehearsal_frontend.mjs', 'REHEARSAL_MANIFEST.json', 'PACKAGE_STATUS_CONTRACT.json', 'test_package_status_contract.ps1', 'test_httpclient_dependency.ps1', 'test_run_manifest_process_identity.ps1', 'README_FOR_USER.txt') }
    )
    $entries = [System.Collections.Generic.List[object]]::new()
    foreach ($definition in $roots) {
        foreach ($include in $definition.Includes) {
            $target = Join-Path $definition.Root $include
            if (-not (Test-Path -LiteralPath $target)) { throw "Hash target missing: $target" }
            $files = if (Test-Path -LiteralPath $target -PathType Container) {
                Get-ChildItem -LiteralPath $target -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/](node_modules|test-results|__pycache__|venv)[\\/]' }
            } else { @(Get-Item -LiteralPath $target) }
            foreach ($file in $files) {
                $entries.Add([pscustomobject]@{
                    path = $file.FullName
                    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
                    length = $file.Length
                })
            }
        }
    }
    return @($entries | Sort-Object path -Unique)
}

function Assert-RehearsalHashLock($Config, [string]$PackageRoot) {
    $lockPath = Join-Path $PackageRoot $Config.hashLockFile
    if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) { throw "Hash lock missing: $lockPath" }
    $lock = Get-Content -Raw -LiteralPath $lockPath | ConvertFrom-Json
    foreach ($entry in $lock.entries) {
        if (-not (Test-Path -LiteralPath $entry.path -PathType Leaf)) { throw "Locked file missing: $($entry.path)" }
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $entry.path).Hash.ToLowerInvariant()
        if ($actual -ne $entry.sha256) { throw "SOURCE_DRIFT: $($entry.path)" }
    }
    return $lock
}

function Set-ProcessEnvironmentTemporarily([hashtable]$Values, [scriptblock]$Action) {
    $before = @{}
    try {
        foreach ($key in $Values.Keys) { $before[$key] = [Environment]::GetEnvironmentVariable($key, 'Process'); [Environment]::SetEnvironmentVariable($key, [string]$Values[$key], 'Process') }
        return & $Action
    } finally {
        foreach ($key in $Values.Keys) { [Environment]::SetEnvironmentVariable($key, $before[$key], 'Process') }
    }
}

function Write-RehearsalJson([string]$Path, $Value) {
    $json = $Value | ConvertTo-Json -Depth 12
    [System.IO.File]::WriteAllText($Path, "$json`r`n", [System.Text.UTF8Encoding]::new($false))
    $null = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
}
