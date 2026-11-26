param(
    [ValidateRange(1,5)][int]$Level = 1,
    [string]$EvidenceDirectory = (Join-Path $PSScriptRoot '../../docs/evidence/excel_formula_parity')
)
$ErrorActionPreference = 'Stop'
$evidenceRoot = [IO.Path]::GetFullPath($EvidenceDirectory)
$sourceManifest = Get-Content -LiteralPath (Join-Path $evidenceRoot 'SOURCE_WORKBOOK_FREEZE.json') -Raw | ConvertFrom-Json
$caseManifest = Get-Content -LiteralPath (Join-Path $evidenceRoot 'EXCEL_GOLDEN_CASES.json') -Raw | ConvertFrom-Json
$runId = [guid]::NewGuid().ToString()
$execution = [ordered]@{ run_id=$runId; level=$Level; engine='Microsoft Excel'; source_sha=$sourceManifest.sha256; case_manifest_sha=(Get-FileHash -LiteralPath (Join-Path $evidenceRoot 'EXCEL_GOLDEN_CASES.json')).Hash; status='BLOCKED'; started_at=[DateTimeOffset]::Now.ToString('o'); update_links=0; original_saved=$false; workbook_copy=$null; results=@(); error=$null }
$privateExcel = $null
$workingBook = $null
try {
    if ((Get-FileHash -LiteralPath $sourceManifest.source).Hash -ne $sourceManifest.sha256) { throw 'SOURCE SHA MISMATCH' }
    if ($Level -gt 1) {
        $gates = Get-Content -LiteralPath (Join-Path $evidenceRoot 'PARITY_GATES.json') -Raw | ConvertFrom-Json
        $previous = $gates.levels | Where-Object level -eq ($Level-1)
        if ($previous.status -ne 'PASS' -or $gates.source_sha -ne $sourceManifest.sha256) { throw 'PREVIOUS LEVEL NOT PASS; execution forbidden' }
    }
    # A new private COM instance only. Never attach to/close a user's workbook.
    $privateExcel = New-Object -ComObject Excel.Application
    $privateExcel.Visible = $false
    $privateExcel.DisplayAlerts = $false
    $privateExcel.AskToUpdateLinks = $false
    $privateExcel.EnableEvents = $false
    $privateExcel.AutomationSecurity = 3
    $execution.excel_version = $privateExcel.Version
    $copyDirectory = Join-Path $evidenceRoot ('oracle-copy-' + $runId)
    [void](New-Item -Path $copyDirectory -ItemType Directory)
    $copyPath = Join-Path $copyDirectory 'source-parity-copy.xlsx'
    Copy-Item -LiteralPath $sourceManifest.source -Destination $copyPath
    $execution.workbook_copy = $copyPath
    # Reject auto-refresh connections before opening; never refresh external data.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($copyPath)
    try {
        foreach ($entry in $archive.Entries) {
            if ($entry.FullName -match '^xl/(connections|queryTables/).*\.xml$') {
                $reader = [IO.StreamReader]::new($entry.Open())
                try { $xml = $reader.ReadToEnd() } finally { $reader.Dispose() }
                if ($xml -match 'refreshOnLoad="(1|true)"') { throw ('AUTOMATIC CONNECTION REFRESH BLOCKED: ' + $entry.FullName) }
            }
        }
    } finally { $archive.Dispose() }
    $workingBook = $privateExcel.Workbooks.Open($copyPath, 0, $true)
    $privateExcel.Calculation = -4135
    $privateExcel.CalculateFullRebuild()
    $allResults = [Collections.Generic.List[object]]::new()
    foreach ($case in @($caseManifest.cases | Where-Object level -eq $Level)) {
        $savedCells = [Collections.Generic.List[object]]::new()
        try {
            foreach ($change in $case.overrides) {
                $range = $workingBook.Worksheets.Item($change.sheet).Range($change.cell)
                $savedCells.Add([pscustomobject]@{ sheet=$change.sheet; cell=$change.cell; formula=$range.Formula; value=$range.Value2; has_formula=$range.HasFormula })
                if ($change.type -eq 'blank') { $range.ClearContents() }
                elseif ($change.type -eq 'text') { $range.Formula = ('="' + ([string]$change.value).Replace('"','""') + '"') }
                else { $range.Value2 = $change.value }
                [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($range)
            }
            $privateExcel.CalculateFull()
            $outputs = [Collections.Generic.List[object]]::new()
            foreach ($output in $case.derived_outputs) {
                $split = $output.cell.LastIndexOf('!')
                $sheetName = $output.cell.Substring(0,$split)
                $cellAddress = $output.cell.Substring($split+1)
                $range = $workingBook.Worksheets.Item($sheetName).Range($cellAddress)
                $raw = $range.Value2
                $displayed = [string]$range.Text
                $valueType = if ($displayed -match '^#(REF!|VALUE!|N/A|DIV/0!|NAME\?|NUM!|NULL!)$') { 'error' } elseif ($null -eq $raw) { 'blank' } elseif ($raw -is [bool]) { 'boolean' } elseif ($raw -is [string]) { 'text' } else { 'number' }
                $value = if ($valueType -eq 'error') { $displayed } else { $raw }
                $outputs.Add([pscustomobject]@{ cell=$output.cell; excel_raw_value=[pscustomobject]@{type=$valueType;value=$value}; excel_displayed_value=$displayed; number_format=$range.NumberFormat; formula=$range.Formula })
                [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($range)
            }
            $allResults.Add([pscustomobject]@{ case_id=$case.case_id; outputs=@($outputs) })
        } finally {
            foreach ($saved in $savedCells) {
                $range = $workingBook.Worksheets.Item($saved.sheet).Range($saved.cell)
                if ($saved.has_formula) { $range.Formula = $saved.formula }
                elseif ($null -eq $saved.value) { $range.ClearContents() }
                else { $range.Value2 = $saved.value }
                [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($range)
            }
        }
    }
    $execution.results = @($allResults)
    $execution.status = 'PASS'
} catch {
    $execution.error = $_.Exception.Message
    $execution.status = 'BLOCKED'
} finally {
    if ($null -ne $workingBook) { $workingBook.Close($false); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($workingBook) }
    if ($null -ne $privateExcel) { $privateExcel.Quit(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($privateExcel) }
    $execution.source_sha_after = (Get-FileHash -LiteralPath $sourceManifest.source).Hash
    $execution.original_unchanged = $execution.source_sha_after -eq $sourceManifest.sha256
    $execution.finished_at = [DateTimeOffset]::Now.ToString('o')
    $execution | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $evidenceRoot ('EXCEL_NATIVE_LEVEL_' + $Level + '.json')) -Encoding utf8
    [pscustomobject]$execution | Select-Object run_id,level,status,error,original_unchanged,started_at,finished_at | ConvertTo-Json -Depth 4
}
if ($execution.status -ne 'PASS') { exit 2 }
