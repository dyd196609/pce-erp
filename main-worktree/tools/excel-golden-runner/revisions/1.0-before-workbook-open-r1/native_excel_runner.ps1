param([Parameter(Mandatory=$true)][string]$RunDirectory)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'runner_common.ps1')
$script:RunDirectory = $RunDirectory
$runPath = Join-Path $RunDirectory 'NATIVE_EXCEL_RUN.json'
$run = Read-RunnerJson $runPath
$planPath = Join-Path $RunDirectory 'RUN_CASE_PLAN.json'
$plan = Read-RunnerJson $planPath
$manifest = Read-RunnerJson (Join-Path $PSScriptRoot 'RUNNER_MANIFEST.json')
$diagnostic = Read-RunnerJson (Join-Path $RunDirectory 'SESSION_DIAGNOSTIC.json')
$goldenPath = Join-Path $RunDirectory 'EXCEL_NATIVE_GOLDEN.json'
$golden = Read-RunnerJson $goldenPath
$privateExcel = $null
$workingBook = $null
$books = $null
$sheets = $null
$worksheetFunction = $null
$owned = $false
$results = [Collections.Generic.List[object]]::new()
$beforePids = @(Get-Process EXCEL -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
function Read-ExcelCell($Cell) {
    $raw = $Cell.Value2
    $displayed = [string]$Cell.Text
    $isError = [bool]$worksheetFunction.IsError($Cell)
    $type = if ($isError) { 'error' } elseif ($null -eq $raw) { 'blank' } elseif ($raw -is [bool]) { 'boolean' } elseif ($raw -is [string]) { 'text' } elseif ($raw -is [ValueType]) { 'number' } else { throw 'UNSUPPORTED EXCEL VARIANT TYPE' }
    $value = if ($isError) { $displayed } else { $raw }
    return [pscustomobject]@{excel_raw_value=[pscustomobject]@{type=$type;value=$value};excel_displayed_value=$displayed;number_format=[string]$Cell.NumberFormat;formula=[string]$Cell.Formula;has_formula=[bool]$Cell.HasFormula}
}
function Set-CaseValue($Cell, [string]$Type, $Value) {
    if ($Type -eq 'blank') { [void]$Cell.ClearContents() }
    elseif ($Type -eq 'text') {
        # A literal formula preserves Excel's empty-string vs empty-cell distinction.
        # Only the isolated, unsaved in-memory copy is changed for the frozen case.
        $Cell.Formula = '="' + ([string]$Value).Replace('"','""') + '"'
    } elseif ($Type -eq 'number') { $Cell.Value2 = [double]$Value }
    elseif ($Type -eq 'boolean') { $Cell.Value2 = [bool]$Value }
    else { throw ('UNSUPPORTED CASE TYPE ' + $Type) }
}
try {
    Assert-PackageHash $manifest
    if ($run.mode -ne 'USER_SESSION_NATIVE') { throw 'PRECHECK MAY NOT START EXCEL' }
    if ($run.plan_sha -ne (Get-RunnerFileHash -LiteralPath $planPath).Hash) { throw 'CASE PLAN HASH MISMATCH' }
    $resolvedCopy = [IO.Path]::GetFullPath($plan.workbook_copy)
    $expectedCopy = [IO.Path]::GetFullPath((Join-Path $RunDirectory 'source-readonly-copy.xlsx'))
    if ($resolvedCopy -ne $expectedCopy -or $resolvedCopy -eq [IO.Path]::GetFullPath($manifest.source)) { throw 'ISOLATED COPY PATH REQUIRED' }
    if ((Get-RunnerFileHash -LiteralPath $resolvedCopy).Hash -ne $manifest.source_sha) { throw 'COPY HASH MISMATCH' }
    if ((Get-RunnerFileHash -LiteralPath $manifest.source).Hash -ne $manifest.source_sha) { throw 'SOURCE HASH MISMATCH' }
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class PceExcelProcessIdentity { [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId); }'
    $privateExcel = New-Object -ComObject Excel.Application
    [uint32]$excelProcessId = 0
    [void][PceExcelProcessIdentity]::GetWindowThreadProcessId([IntPtr]$privateExcel.Hwnd, [ref]$excelProcessId)
    if ($excelProcessId -eq 0 -or $beforePids -contains [int]$excelProcessId) { throw 'EXCEL INSTANCE OWNERSHIP NOT PROVEN; USER INSTANCE WILL NOT BE CHANGED OR CLOSED' }
    $owned = $true
    $run.excel_pid = [int]$excelProcessId
    $excelProcess = Get-Process -Id $excelProcessId
    if ($excelProcess.SessionId -ne $run.session_id) { throw 'EXCEL SESSION DOES NOT MATCH RUNNER SESSION' }
    $run.excel_version = [string]$privateExcel.Version
    $diagnostic | Add-Member -NotePropertyName excel_process -NotePropertyValue @{pid=[int]$excelProcessId;session=$excelProcess.SessionId;started=$excelProcess.StartTime.ToString('o')} -Force
    Write-RunnerJson (Join-Path $RunDirectory 'SESSION_DIAGNOSTIC.json') $diagnostic
    Write-RunnerJson $runPath $run
    $privateExcel.Visible = $false
    $privateExcel.DisplayAlerts = $false
    $privateExcel.AskToUpdateLinks = $false
    $privateExcel.EnableEvents = $false
    $privateExcel.AutomationSecurity = 3
    $books = $privateExcel.Workbooks
    if ($books.Count -ne 0) { throw 'PRIVATE EXCEL ALREADY HAS A WORKBOOK; STOP WITHOUT OPENING SOURCE' }
    $missing = [Type]::Missing
    # Explicit empty passwords prevent a password prompt. UpdateLinks=0, ReadOnly=true,
    # IgnoreReadOnlyRecommended=true, Notify=false, AddToMru=false, CorruptLoad=normal.
    $workingBook = $books.Open($resolvedCopy,0,$true,$missing,'','',$true,$missing,$missing,$false,$false,$missing,$false,$true,0)
    if (-not $workingBook.ReadOnly -or [IO.Path]::GetFullPath($workingBook.FullName) -ne $expectedCopy) { throw 'WORKBOOK READ-ONLY/COPY CONTRACT VIOLATED' }
    $privateExcel.Calculation = -4135
    $sheets = $workingBook.Worksheets
    $worksheetFunction = $privateExcel.WorksheetFunction
    $run.calculation_start = [DateTimeOffset]::Now.ToString('o')
    Write-RunnerJson $runPath $run
    $privateExcel.CalculateFullRebuild()
    if ($privateExcel.CalculationState -ne 0) { throw 'EXCEL INITIAL CALCULATION INCOMPLETE' }
    $golden.engine = 'Microsoft Excel Calculation Engine'
    $golden.source_sha = $manifest.source_sha
    $golden.plan_sha = $run.plan_sha
    $golden.status = 'CAPTURING'
    foreach ($case in $plan.cases) {
        $savedCells = [Collections.Generic.List[object]]::new()
        $inputs = [Collections.Generic.List[object]]::new()
        $outputs = [Collections.Generic.List[object]]::new()
        $started = [DateTimeOffset]::Now.ToString('o')
        try {
            foreach ($change in $case.overrides) {
                $sheet = $sheets.Item($change.sheet)
                $cell = $sheet.Range($change.cell)
                try {
                    $savedCells.Add([pscustomobject]@{sheet=$change.sheet;cell=$change.cell;formula=$cell.Formula;value=$cell.Value2;has_formula=[bool]$cell.HasFormula;number_format=$cell.NumberFormat})
                    Set-CaseValue $cell $change.type $change.value
                    $inputs.Add([pscustomobject]@{sheet=$change.sheet;cell=$change.cell;requested_type=$change.type;requested_value=$change.value})
                } finally { Release-OwnedCom $cell; Release-OwnedCom $sheet }
            }
            $privateExcel.CalculateFull()
            if ($privateExcel.CalculationState -ne 0) { throw 'EXCEL CASE CALCULATION INCOMPLETE' }
            foreach ($input in $inputs) {
                $sheet = $sheets.Item($input.sheet)
                $cell = $sheet.Range($input.cell)
                try { $input | Add-Member -NotePropertyName actual -NotePropertyValue (Read-ExcelCell $cell).excel_raw_value }
                finally { Release-OwnedCom $cell; Release-OwnedCom $sheet }
            }
            foreach ($output in $case.derived_outputs) {
                $split = $output.cell.LastIndexOf('!')
                $sheet = $sheets.Item($output.cell.Substring(0,$split))
                $cell = $sheet.Range($output.cell.Substring($split+1))
                try {
                    $captured = Read-ExcelCell $cell
                    $captured | Add-Member -NotePropertyName cell -NotePropertyValue $output.cell
                    $captured | Add-Member -NotePropertyName formula_family -NotePropertyValue $output.formula_family
                    $outputs.Add($captured)
                } finally { Release-OwnedCom $cell; Release-OwnedCom $sheet }
            }
        } finally {
            foreach ($saved in $savedCells) {
                $sheet = $sheets.Item($saved.sheet)
                $cell = $sheet.Range($saved.cell)
                try {
                    if ($saved.has_formula) { $cell.Formula = $saved.formula }
                    elseif ($null -eq $saved.value) { [void]$cell.ClearContents() }
                    elseif ($saved.value -is [string]) { $cell.NumberFormat = '@'; $cell.Value2 = [string]$saved.value; $cell.NumberFormat = $saved.number_format }
                    else { $cell.Value2 = $saved.value }
                    if ([bool]$cell.HasFormula -ne $saved.has_formula) { throw 'CASE RESTORE FORMULA TYPE MISMATCH' }
                    if ($saved.has_formula -and [string]$cell.Formula -cne [string]$saved.formula) { throw 'CASE RESTORE FORMULA MISMATCH' }
                    if (-not $saved.has_formula -and $cell.Value2 -cne $saved.value) { throw 'CASE RESTORE VALUE MISMATCH' }
                } finally { Release-OwnedCom $cell; Release-OwnedCom $sheet }
            }
        }
        $results.Add([pscustomobject]@{case_id=$case.case_id;calculation_start=$started;calculation_end=[DateTimeOffset]::Now.ToString('o');overrides=$inputs.ToArray();outputs=$outputs.ToArray();restored=$true})
        $golden.results = $results.ToArray()
        $run.result_count = $results.Count
        Write-RunnerJson $goldenPath $golden
        Write-RunnerJson $runPath $run
        if ($results.Count % 10 -eq 0 -or $results.Count -eq $plan.cases.Count) { Write-RunnerLog ('Excel 原生计算：' + $results.Count + ' / ' + $plan.cases.Count) }
    }
    $run.calculation_end = [DateTimeOffset]::Now.ToString('o')
    $run.execution_status = 'PASS'
    $golden.status = 'CAPTURED'
} catch {
    $run.error = Get-RunnerError $_
    $diagnostic.errors += $run.error
    $run.execution_status = 'BLOCKED'
    $golden.status = 'BLOCKED'
    Write-RunnerLog ('原生计算已阻断，诊断已保存：' + $_.Exception.Message)
} finally {
    # Never Save; never attach to an existing instance; never kill EXCEL by name.
    try { if ($null -ne $workingBook) { $workingBook.Close($false) } }
    catch { $run.cleanup_errors += Get-RunnerError $_; $run.execution_status='BLOCKED'; $golden.status='BLOCKED' }
    Release-OwnedCom $worksheetFunction
    Release-OwnedCom $sheets
    Release-OwnedCom $workingBook
    Release-OwnedCom $books
    try { if ($owned -and $null -ne $privateExcel) { $privateExcel.Quit() } }
    catch { $run.cleanup_errors += Get-RunnerError $_; $run.execution_status='BLOCKED'; $golden.status='BLOCKED' }
    Release-OwnedCom $privateExcel
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    try {
        $run.source_sha_after = (Get-RunnerFileHash -LiteralPath $manifest.source).Hash
        $run.run_copy_sha_after = (Get-RunnerFileHash -LiteralPath $plan.workbook_copy).Hash
        $run.original_unchanged = $run.source_sha_after -eq $manifest.source_sha
        if (-not $run.original_unchanged -or $run.run_copy_sha_after -ne $manifest.source_sha) { throw 'SOURCE/COPY PROTECTION FAILED' }
    } catch { $run.cleanup_errors += Get-RunnerError $_; $run.execution_status='BLOCKED'; $golden.status='BLOCKED' }
    $golden.results = $results.ToArray()
    Write-RunnerJson $runPath $run
    Write-RunnerJson $goldenPath $golden
    Write-RunnerJson (Join-Path $RunDirectory 'SESSION_DIAGNOSTIC.json') $diagnostic
}
