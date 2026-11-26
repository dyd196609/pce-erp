function Write-RunnerJson([string]$Path, $Value) {
    $text = ConvertTo-Json -InputObject $Value -Depth 90
    $temp = $Path + '.pending'
    [IO.File]::WriteAllText($temp, $text, [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temp -Destination $Path -Force
}
function Get-RunnerFileHash([string]$LiteralPath, [string]$Algorithm='SHA256') {
    if ($Algorithm -ne 'SHA256') { throw 'ONLY SHA256 IS ALLOWED' }
    $stream = [IO.File]::OpenRead($LiteralPath)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [pscustomobject]@{Hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','')} }
    finally { $sha.Dispose(); $stream.Dispose() }
}
function Read-RunnerJson([string]$Path) {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}
function Write-RunnerLog([string]$Message) {
    $line = [DateTimeOffset]::Now.ToString('o') + ' ' + $Message
    [IO.File]::AppendAllText((Join-Path $script:RunDirectory 'RUN_LOG.txt'), $line + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    Write-Host $Message
}
function Get-RunnerError($Record) {
    $chain = @()
    $exception = $Record.Exception
    while ($null -ne $exception) {
        $hr = '0x{0:X8}' -f ($exception.HResult -band 0xFFFFFFFFL)
        $chain += [pscustomobject]@{type=$exception.GetType().FullName; message=$exception.Message; hresult=$hr}
        $exception = $exception.InnerException
    }
    return [pscustomobject]@{time=[DateTimeOffset]::Now.ToString('o'); chain=$chain; position=$Record.InvocationInfo.PositionMessage}
}
function Get-ExcelDiscovery {
    $registrations = @()
    $paths = @()
    foreach ($keyPath in @(
        'Registry::HKEY_CLASSES_ROOT\Excel.Application\CLSID',
        'Registry::HKEY_CLASSES_ROOT\CLSID\{00024500-0000-0000-C000-000000000046}\LocalServer32',
        'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\excel.exe',
        'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\excel.exe',
        'Registry::HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\excel.exe'
    )) {
        if (Test-Path -LiteralPath $keyPath) {
            $value = [string](Get-Item -LiteralPath $keyPath).GetValue('')
            $registrations += [pscustomobject]@{key=$keyPath; value=$value}
            if ($value -match '(?i)^"?(.+?EXCEL\.EXE)"?(?:\s.*)?$') {
                $candidate = $Matches[1]
                if (Test-Path -LiteralPath $candidate -PathType Leaf) { $paths += $candidate }
            }
        }
    }
    return [pscustomobject]@{registrations=$registrations; paths=@($paths | Select-Object -Unique)}
}
function Assert-PackageHash($Manifest) {
    foreach ($entry in $Manifest.files.PSObject.Properties) {
        $path = Join-Path $PSScriptRoot $entry.Name
        if ((Get-RunnerFileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $entry.Value) { throw ('PACKAGE HASH MISMATCH: ' + $entry.Name) }
    }
}
function Release-OwnedCom($Value) {
    if ($null -ne $Value -and [Runtime.InteropServices.Marshal]::IsComObject($Value)) {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Value)
    }
}
