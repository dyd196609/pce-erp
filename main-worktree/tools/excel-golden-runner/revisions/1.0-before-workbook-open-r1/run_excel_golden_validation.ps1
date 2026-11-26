param([switch]$PrecheckOnly, [switch]$NoDelay)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONDONTWRITEBYTECODE = '1'
. (Join-Path $PSScriptRoot 'runner_common.ps1')
$runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$mode = if ($PrecheckOnly) { 'PACKAGE_PRECHECK' } else { 'USER_SESSION_NATIVE' }
$area = if ($PrecheckOnly) { 'prechecks' } else { 'runs' }
$script:RunDirectory = Join-Path (Join-Path $PSScriptRoot $area) $runId
[void](New-Item -Path $script:RunDirectory -ItemType Directory)
$session = (Get-Process -Id $PID).SessionId
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$run = [ordered]@{
    run_id=$runId; mode=$mode; execution_status='NOT_EXECUTED'; validation_status='PENDING';
    source_sha=$null; source_sha_after=$null; run_copy_sha=$null; run_copy_sha_after=$null;
    original_unchanged=$false; windows_user=$user; session_id=$session;
    excel_pid=$null; excel_version=$null; calculation_start=$null; calculation_end=$null;
    result_count=0; exit_code=2; started_at=[DateTimeOffset]::Now.ToString('o'); finished_at=$null;
    workbook_copy=$null; update_links=0; macros_disabled=$true; original_saved=$false;
    package_manifest_sha=$null; plan_sha=$null; error=$null; cleanup_errors=@()
}
$golden = [ordered]@{run_id=$runId; engine=$null; status='NOT_EXECUTED'; source_sha=$null; plan_sha=$null; results=@()}
$diagnostic = [ordered]@{
    run_id=$runId; windows_user=$user; runner_pid=$PID; runner_session=$session;
    explorer_processes=@(Get-Process explorer -ErrorAction SilentlyContinue | Select-Object Id,SessionId);
    excel_registration=@(); excel_paths=@(); errors=@(); elevated=([Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
}
$manifest = $null
$sourceGuard = $null
$pythonReady = $false
$exitCode = 2
Write-RunnerJson (Join-Path $script:RunDirectory 'NATIVE_EXCEL_RUN.json') $run
Write-RunnerJson (Join-Path $script:RunDirectory 'EXCEL_NATIVE_GOLDEN.json') $golden
Write-RunnerJson (Join-Path $script:RunDirectory 'DIFFERENTIAL_RESULTS.json') @{run_id=$runId;status='NOT_EXECUTED';results=@();families=@()}
Write-RunnerJson (Join-Path $script:RunDirectory 'SESSION_DIAGNOSTIC.json') $diagnostic
Write-RunnerJson (Join-Path $script:RunDirectory 'RUN_MANIFEST.json') @{run_id=$runId;mode=$mode;package_manifest_sha=$null;source_sha=$null;run_copy_sha=$null;files=@{}}
Write-RunnerLog '正在检查 Microsoft Excel……'
try {
    $discovery = Get-ExcelDiscovery
    $diagnostic.excel_registration = $discovery.registrations
    $diagnostic.excel_paths = $discovery.paths
    Write-RunnerJson (Join-Path $script:RunDirectory 'SESSION_DIAGNOSTIC.json') $diagnostic
    if ($discovery.paths.Count -eq 0) { throw 'MICROSOFT EXCEL INSTALLATION NOT FOUND' }
    $manifestPath = Join-Path $PSScriptRoot 'RUNNER_MANIFEST.json'
    $manifest = Read-RunnerJson $manifestPath
    Assert-PackageHash $manifest
    $syntax = @()
    foreach ($psFile in @('runner_common.ps1','run_excel_golden_validation.ps1','native_excel_runner.ps1','test_native_contract.ps1')) {
        $parseTokens = $null
        $parseErrors = $null
        [void][Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $psFile), [ref]$parseTokens, [ref]$parseErrors)
        if (@($parseErrors).Count -ne 0) { throw ('POWERSHELL SYNTAX FAILED: ' + $psFile) }
        $syntax += [pscustomobject]@{file=$psFile;status='PASS';error_count=0}
    }
    Write-RunnerJson (Join-Path $script:RunDirectory 'POWERSHELL_PRECHECK.json') @{version=$PSVersionTable.PSVersion.ToString();files=$syntax;status='PASS'}
    $run.package_manifest_sha = (Get-RunnerFileHash -LiteralPath $manifestPath).Hash
    if (-not (Test-Path -LiteralPath $manifest.python -PathType Leaf)) { throw 'BUNDLED PYTHON NOT FOUND' }
    $pythonReady = $true
    Write-RunnerLog '正在验证原始工作簿……'
    # Read sharing only: hold the source against writers until all checks finish.
    $sourceGuard = [IO.File]::Open($manifest.source, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $run.source_sha = (Get-RunnerFileHash -LiteralPath $manifest.source).Hash
    if ($run.source_sha -ne $manifest.source_sha) { throw 'SOURCE SHA MISMATCH' }
    Write-RunnerLog '正在创建只读验证副本……'
    & $manifest.python -E -B (Join-Path $PSScriptRoot 'package_support.py') prepare --run-directory $script:RunDirectory
    if ($LASTEXITCODE -ne 0) { throw 'PACKAGE PRECHECK FAILED; see PACKAGE_PRECHECK.json' }
    $plan = Read-RunnerJson (Join-Path $script:RunDirectory 'RUN_CASE_PLAN.json')
    $run.workbook_copy = $plan.workbook_copy
    $run.run_copy_sha = (Get-RunnerFileHash -LiteralPath $run.workbook_copy).Hash
    $run.plan_sha = (Get-RunnerFileHash -LiteralPath (Join-Path $script:RunDirectory 'RUN_CASE_PLAN.json')).Hash
    Write-RunnerJson (Join-Path $script:RunDirectory 'NATIVE_EXCEL_RUN.json') $run
    if ($PrecheckOnly) {
        & (Join-Path $PSScriptRoot 'test_native_contract.ps1') -RunDirectory $script:RunDirectory
        & $manifest.python -E -B (Join-Path $PSScriptRoot 'package_support.py') precheck --run-directory $script:RunDirectory
        if ($LASTEXITCODE -ne 0) { throw 'REFERENCE/PARSER/COMPARATOR PRECHECK FAILED' }
        $run.execution_status = 'NOT_EXECUTED'
        $run.validation_status = 'NOT_EXECUTED'
        $exitCode = 0
        Write-RunnerLog '程序包预检通过；没有启动 Excel，原生验证尚未执行。'
    } else {
        $sessionMatches = @($diagnostic.explorer_processes | Where-Object SessionId -eq $session)
        if ($session -eq 0 -or $sessionMatches.Count -eq 0) { throw 'RUNNER MUST RUN IN THE CURRENT EXPLORER SESSION; no policy changes will be made' }
        Write-RunnerLog '正在使用 Microsoft Excel 原生计算……'
        & (Join-Path $PSScriptRoot 'native_excel_runner.ps1') -RunDirectory $script:RunDirectory
        $run = Read-RunnerJson (Join-Path $script:RunDirectory 'NATIVE_EXCEL_RUN.json')
        if ($run.execution_status -ne 'PASS') { throw 'NATIVE EXCEL EXECUTION BLOCKED; diagnostics saved' }
        Write-RunnerLog '正在进行 Excel 与代码结果比对……'
        & $manifest.python -E -B (Join-Path $PSScriptRoot 'package_support.py') compare --run-directory $script:RunDirectory
        if ($LASTEXITCODE -notin @(0,3)) { throw 'COMPARISON EVIDENCE INVALID' }
        $diff = Read-RunnerJson (Join-Path $script:RunDirectory 'DIFFERENTIAL_RESULTS.json')
        $run.validation_status = $diff.status
        $exitCode = if ($diff.status -eq 'PASS') { 0 } else { 3 }
    }
} catch {
    $run.validation_status = 'BLOCKED'
    if ($run.execution_status -ne 'PASS') { $run.execution_status = if ($PrecheckOnly) { 'NOT_EXECUTED' } else { 'BLOCKED' } }
    $run.error = Get-RunnerError $_
    $diagnostic.errors += $run.error
    $exitCode = 2
    Write-RunnerLog ('EXCEL GOLDEN VALIDATION = BLOCKED. ' + $_.Exception.Message)
} finally {
    if ($null -ne $manifest) {
        try {
            $run.source_sha_after = (Get-RunnerFileHash -LiteralPath $manifest.source).Hash
            $run.original_unchanged = $run.source_sha_after -eq $manifest.source_sha
            if (-not $run.original_unchanged) { throw 'SOURCE WORKBOOK MUTATION DETECTED' }
            if ($null -ne $run.workbook_copy) {
                $run.run_copy_sha_after = (Get-RunnerFileHash -LiteralPath $run.workbook_copy).Hash
                if ($run.run_copy_sha_after -ne $manifest.source_sha) { throw 'RUN COPY SAVED OR MODIFIED ON DISK' }
            }
            Assert-PackageHash $manifest
        } catch {
            $diagnostic.errors += Get-RunnerError $_
            $run.validation_status = 'BLOCKED'
            $exitCode = 2
        }
    }
    if ($null -ne $sourceGuard) { $sourceGuard.Dispose() }
    $run.exit_code = $exitCode
    $run.finished_at = [DateTimeOffset]::Now.ToString('o')
    Write-RunnerJson (Join-Path $script:RunDirectory 'NATIVE_EXCEL_RUN.json') $run
    # Preserve native exception details collected by the private instance runner.
    $nativeDiagnostic = Read-RunnerJson (Join-Path $script:RunDirectory 'SESSION_DIAGNOSTIC.json')
    $diagnostic.errors = @($nativeDiagnostic.errors) + @($diagnostic.errors)
    if ($nativeDiagnostic.PSObject.Properties.Name -contains 'excel_process') { $diagnostic['excel_process'] = $nativeDiagnostic.excel_process }
    Write-RunnerJson (Join-Path $script:RunDirectory 'SESSION_DIAGNOSTIC.json') $diagnostic
    Write-RunnerLog ('完成。结果目录：' + $script:RunDirectory)
    if ($pythonReady) {
        & $manifest.python -E -B (Join-Path $PSScriptRoot 'package_support.py') finalize --run-directory $script:RunDirectory
        if ($LASTEXITCODE -ne 0) {
            $exitCode = 2
            $run.exit_code = 2
            $run.validation_status = 'BLOCKED'
            Write-RunnerJson (Join-Path $script:RunDirectory 'NATIVE_EXCEL_RUN.json') $run
            Write-RunnerLog 'EVIDENCE FINALIZATION = BLOCKED'
        }
    }
    if (-not $PrecheckOnly -and $exitCode -eq 0) { Write-Host 'EXCEL GOLDEN VALIDATION = PASS' }
    elseif (-not $PrecheckOnly -and $exitCode -eq 3) { Write-Host 'EXCEL GOLDEN VALIDATION = REVIEW_REQUIRED；原生结果已保留，Codex 将先分析差异。' }
    elseif ($exitCode -eq 2) { Write-Host 'EXCEL GOLDEN VALIDATION = BLOCKED；详细信息已保存。' }
    if (-not $PrecheckOnly) { [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'LAST_RUN.txt'), $script:RunDirectory, [Text.UTF8Encoding]::new($false)) }
    if (-not $NoDelay) { Start-Sleep -Seconds 15 }
}
exit $exitCode
