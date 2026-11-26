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
    $value = $raw
    if ($isError) {
        # Cell.Text can be ##### in a narrow column. Preserve the actual COM
        # VARIANT and decode only documented Excel CVError identities.
        # https://learn.microsoft.com/en-us/office/vba/api/excel.xlcverror
        $errors = @{2000='#NULL!';2007='#DIV/0!';2015='#VALUE!';2023='#REF!';2029='#NAME?';2036='#NUM!';2042='#N/A';2045='#SPILL!'}
        if ($raw -isnot [int] -and $raw -isnot [long]) { throw 'NATIVE ERROR VARIANT TYPE UNAVAILABLE; NEVER USE DISPLAY TEXT AS ORACLE' }
        $cvError = [int]([long]$raw -band 65535)
        if (-not $errors.ContainsKey($cvError)) { throw ('UNSUPPORTED NATIVE CVERROR ' + $cvError) }
        $value = $errors[$cvError]
    }
    return [pscustomobject]@{excel_raw_value=[pscustomobject]@{type=$type;value=$value};native_variant_value=$raw;excel_displayed_value=$displayed;number_format=[string]$Cell.NumberFormat;formula=[string]$Cell.Formula;has_formula=[bool]$Cell.HasFormula}
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
function Restore-CaseCell($Cell, $Saved) {
    # COM setters require primitive arguments, not an untyped property from a
    # PowerShell saved-state object. Preserve bool, number, text and blank.
    if ($Saved.has_formula) { $Cell.Formula = [string]$Saved.formula }
    elseif ($null -eq $Saved.value) { [void]$Cell.ClearContents() }
    elseif ($Saved.value -is [string]) {
        $Cell.NumberFormat = '@'
        try { $Cell.Value2 = [string]$Saved.value }
        finally { $Cell.NumberFormat = [string]$Saved.number_format }
    }
    elseif ($Saved.value -is [bool]) { $Cell.Value2 = [bool]$Saved.value }
    elseif ($Saved.value -is [double] -or $Saved.value -is [int] -or $Saved.value -is [long] -or $Saved.value -is [decimal] -or $Saved.value -is [single]) { $Cell.Value2 = [double]$Saved.value }
    else { throw ('UNSUPPORTED RESTORE VARIANT: ' + $Saved.value.GetType().FullName) }
    if ([bool]$Cell.HasFormula -ne [bool]$Saved.has_formula) { throw 'CASE RESTORE FORMULA TYPE MISMATCH' }
    if ($Saved.has_formula -and [string]$Cell.Formula -cne [string]$Saved.formula) { throw 'CASE RESTORE FORMULA MISMATCH' }
    if (-not $Saved.has_formula) {
        $restored = $Cell.Value2
        if (($Saved.value -is [bool]) -ne ($restored -is [bool])) { throw 'CASE RESTORE BOOLEAN TYPE MISMATCH' }
        if (($null -eq $Saved.value) -ne ($null -eq $restored)) { throw 'CASE RESTORE BLANK TYPE MISMATCH' }
        if (($Saved.value -is [string]) -ne ($restored -is [string])) { throw 'CASE RESTORE TEXT TYPE MISMATCH' }
        if ($restored -cne $Saved.value) { throw 'CASE RESTORE VALUE MISMATCH' }
    }
    if ([string]$Cell.NumberFormat -cne [string]$Saved.number_format) { throw 'CASE RESTORE FORMAT MISMATCH' }
}
function Open-ValidationCopy($Books, [string]$Path) {
    # Use Excel's documented optional-argument defaults, not a 15-position COM
    # call. Normal Open only: no repair/extract, trust change, links or saving.
    # This compatibility change still requires a real user-session recheck.
    return $Books.Open($Path, 0, $true)
}
function Initialize-TechnicalSheet($SheetCollection, $Definition) {
    if ($Definition.name -ne 'PCE_NATIVE_PROBES' -or $Definition.persistence -ne 'UNSAVED_ISOLATED_COPY_ONLY') { throw 'INVALID TECHNICAL SHEET CONTRACT' }
    foreach ($existingName in @($SheetCollection | ForEach-Object Name)) {
        if ($existingName -eq $Definition.name) { throw 'TECHNICAL SHEET NAME COLLISION; NEVER REUSE SOURCE SHEET' }
    }
    $technicalSheet = $null
    try {
        $technicalSheet = $SheetCollection.Add()
        $technicalSheet.Name = $Definition.name
        foreach ($definitionCell in $Definition.cells) {
            $technicalCell = $technicalSheet.Range($definitionCell.cell)
            try {
                if ($definitionCell.type -eq 'formula') { $technicalCell.Formula = [string]$definitionCell.formula }
                else { Set-CaseValue $technicalCell $definitionCell.type $definitionCell.value }
                if ($definitionCell.type -eq 'formula' -and -not [bool]$technicalCell.HasFormula) { throw 'TECHNICAL FORMULA NOT SET' }
            } finally { Release-OwnedCom $technicalCell }
        }
    } finally { Release-OwnedCom $technicalSheet }
}
function Set-NativeStage([string]$Stage) {
    $run.native_stage = $Stage
    $diagnostic | Add-Member -NotePropertyName native_stage -NotePropertyValue $Stage -Force
    Write-RunnerJson $runPath $run
    Write-RunnerJson (Join-Path $RunDirectory 'SESSION_DIAGNOSTIC.json') $diagnostic
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
    Set-NativeStage 'CREATE_PRIVATE_EXCEL'
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
    $openDiagnostic = [ordered]@{
        status='OPENING'; method='Workbooks.Open(FileName, UpdateLinks=0, ReadOnly=true)';
        file=$resolvedCopy; bytes=(Get-Item -LiteralPath $resolvedCopy).Length;
        omitted_optional_arguments='EXCEL_DEFAULTS; NORMAL_OPEN_NO_REPAIR';
        macros_disabled=($privateExcel.AutomationSecurity -eq 3);
        display_alerts=[bool]$privateExcel.DisplayAlerts; events_enabled=[bool]$privateExcel.EnableEvents;
        ask_to_update_links=[bool]$privateExcel.AskToUpdateLinks;
        culture=[Globalization.CultureInfo]::CurrentCulture.Name;
        ui_culture=[Globalization.CultureInfo]::CurrentUICulture.Name;
        excel_build=[string]$privateExcel.Build; protected_view_count=$null; error=$null
    }
    $diagnostic | Add-Member -NotePropertyName workbook_open -NotePropertyValue $openDiagnostic -Force
    Set-NativeStage 'OPEN_READONLY_COPY'
    Write-RunnerLog '正在打开 Excel 只读验证副本……（尚未开始公式计算）'
    try {
        $workingBook = Open-ValidationCopy $books $resolvedCopy
        $openDiagnostic.status = 'OPENED'
    } catch {
        $openDiagnostic.status = 'BLOCKED'
        $openDiagnostic.error = Get-RunnerError $_
        # Diagnostic only, on our owned instance. Do not leave Protected View,
        # disable FileValidation or change any Office trust/security settings.
        $protectedViews = $null
        try { $protectedViews = $privateExcel.ProtectedViewWindows; $openDiagnostic.protected_view_count = $protectedViews.Count }
        catch { $openDiagnostic['diagnostic_error'] = Get-RunnerError $_ }
        finally { Release-OwnedCom $protectedViews }
        throw
    }
    if (-not $workingBook.ReadOnly -or [IO.Path]::GetFullPath($workingBook.FullName) -ne $expectedCopy) { throw 'WORKBOOK READ-ONLY/COPY CONTRACT VIOLATED' }
    $privateExcel.Calculation = -4135
    $sheets = $workingBook.Worksheets
    $worksheetFunction = $privateExcel.WorksheetFunction
    if ($plan.PSObject.Properties.Name -contains 'probe_sheet') {
        Set-NativeStage 'INITIALIZE_UNSAVED_TECHNICAL_PROBES'
        Write-RunnerLog '正在准备隔离技术探针与候选验证……（不修改来源工作表，不保存）'
        Initialize-TechnicalSheet $sheets $plan.probe_sheet
        $golden | Add-Member -NotePropertyName technical_sheet_initialized -NotePropertyValue $plan.probe_sheet.name -Force
        $golden | Add-Member -NotePropertyName original_source_sheets_unmodified -NotePropertyValue $false -Force
    }
    $run.calculation_start = [DateTimeOffset]::Now.ToString('o')
    Set-NativeStage 'INITIAL_NATIVE_CALCULATION'
    Write-RunnerLog '正在使用 Microsoft Excel 原生计算……'
    $privateExcel.CalculateFullRebuild()
    if ($privateExcel.CalculationState -ne 0) { throw 'EXCEL INITIAL CALCULATION INCOMPLETE' }
    $golden.engine = 'Microsoft Excel Calculation Engine'
    $golden.source_sha = $manifest.source_sha
    $golden.plan_sha = $run.plan_sha
    $golden.status = 'CAPTURING'
    Set-NativeStage 'CAPTURE_NATIVE_CASES'
    foreach ($case in $plan.cases) {
        $run | Add-Member -NotePropertyName active_case -NotePropertyValue $case.case_id -Force
        $run | Add-Member -NotePropertyName active_cell -NotePropertyValue $null -Force
        $run | Add-Member -NotePropertyName case_phase -NotePropertyValue 'APPLY_INPUTS' -Force
        $savedCells = [Collections.Generic.List[object]]::new()
        $inputs = [Collections.Generic.List[object]]::new()
        $outputs = [Collections.Generic.List[object]]::new()
        $observations = [Collections.Generic.List[object]]::new()
        $started = [DateTimeOffset]::Now.ToString('o')
        try {
            foreach ($change in $case.overrides) {
                $run.active_cell = $change.sheet + '!' + $change.cell
                $sheet = $sheets.Item($change.sheet)
                $cell = $sheet.Range($change.cell)
                try {
                    $savedCells.Add([pscustomobject]@{sheet=$change.sheet;cell=$change.cell;formula=$cell.Formula;value=$cell.Value2;has_formula=[bool]$cell.HasFormula;number_format=$cell.NumberFormat})
                    Set-CaseValue $cell $change.type $change.value
                    $inputs.Add([pscustomobject]@{sheet=$change.sheet;cell=$change.cell;requested_type=$change.type;requested_value=$change.value})
                } finally { Release-OwnedCom $cell; Release-OwnedCom $sheet }
            }
            $privateExcel.CalculateFull()
            $run.case_phase = 'CAPTURE_OUTPUTS'
            if ($privateExcel.CalculationState -ne 0) { throw 'EXCEL CASE CALCULATION INCOMPLETE' }
            foreach ($caseInput in $inputs) {
                $sheet = $sheets.Item($caseInput.sheet)
                $cell = $sheet.Range($caseInput.cell)
                try { $caseInput | Add-Member -NotePropertyName actual -NotePropertyValue (Read-ExcelCell $cell).excel_raw_value }
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
            if ($case.PSObject.Properties.Name -contains 'observations') {
                foreach ($observation in $case.observations) {
                    $sheet = $sheets.Item($observation.sheet)
                    $cell = $sheet.Range($observation.cell)
                    try {
                        $capturedObservation = Read-ExcelCell $cell
                        $capturedObservation | Add-Member -NotePropertyName sheet -NotePropertyValue $observation.sheet
                        $capturedObservation | Add-Member -NotePropertyName cell -NotePropertyValue $observation.cell
                        $observations.Add($capturedObservation)
                    } finally { Release-OwnedCom $cell; Release-OwnedCom $sheet }
                }
            }
        } finally {
            $run.case_phase = 'RESTORE_INPUTS'
            foreach ($saved in $savedCells) {
                $run.active_cell = $saved.sheet + '!' + $saved.cell
                $sheet = $sheets.Item($saved.sheet)
                $cell = $sheet.Range($saved.cell)
                try {
                    Restore-CaseCell $cell $saved
                } finally { Release-OwnedCom $cell; Release-OwnedCom $sheet }
            }
        }
        $results.Add([pscustomobject]@{case_id=$case.case_id;calculation_start=$started;calculation_end=[DateTimeOffset]::Now.ToString('o');overrides=$inputs.ToArray();outputs=$outputs.ToArray();observations=$observations.ToArray();restored=$true})
        $run.case_phase = 'COMMITTED_RESTORED_CASE'
        $golden.results = $results.ToArray()
        $run.result_count = $results.Count
        Write-RunnerJson $goldenPath $golden
        Write-RunnerJson $runPath $run
        if ($results.Count % 10 -eq 0 -or $results.Count -eq $plan.cases.Count) { Write-RunnerLog ('Excel 原生计算：' + $results.Count + ' / ' + $plan.cases.Count) }
    }
    $run.calculation_end = [DateTimeOffset]::Now.ToString('o')
    $run.execution_status = 'PASS'
    $golden.status = 'CAPTURED'
    if ($plan.PSObject.Properties.Name -contains 'probe_sheet') {
        # Only input overrides touched source sheets, and every one was restored
        # and checked above. Candidate formulas exist solely on the new sheet.
        $golden.original_source_sheets_unmodified = $true
    }
    Set-NativeStage 'NATIVE_CAPTURE_COMPLETE'
} catch {
    $run.error = Get-RunnerError $_
    $diagnostic.errors += $run.error
    $run.execution_status = 'BLOCKED'
    $golden.status = 'BLOCKED'
    Write-RunnerLog ('Excel 验证已阻断；阶段=' + $run.native_stage + '；诊断已保存：' + $_.Exception.Message)
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
