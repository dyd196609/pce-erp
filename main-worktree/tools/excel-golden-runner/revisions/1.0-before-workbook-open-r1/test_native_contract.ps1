param([Parameter(Mandatory=$true)][string]$RunDirectory)
# Only serialization/control fixtures. No Excel.Application creation or calculation.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'runner_common.ps1')
$checks = [Collections.Generic.List[object]]::new()
function Assert-Contract([bool]$Value, [string]$Name) {
    if (-not $Value) { throw ('POWERSHELL CONTRACT FAILED: ' + $Name) }
    $checks.Add([pscustomobject]@{name=$Name;status='PASS'})
}
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'native_excel_runner.ps1'), [ref]$tokens, [ref]$errors)
Assert-Contract (@($errors).Count -eq 0) 'Native script parses under delivered PowerShell'
$functions = $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]}, $false)
foreach ($function in $functions) {
    if ($function.Name -in @('Read-ExcelCell','Set-CaseValue')) { . ([scriptblock]::Create($function.Extent.Text)) }
}
$worksheetFunction = [pscustomobject]@{}
$worksheetFunction | Add-Member -MemberType ScriptMethod -Name IsError -Value {param($cell) return $cell.Error}
foreach ($fixture in @(
    @{value=$null;expected='blank';display='';error=$false},
    @{value=$false;expected='boolean';display='FALSE';error=$false},
    @{value=0.0;expected='number';display='0';error=$false},
    @{value='';expected='text';display='';error=$false},
    @{value='#REF!';expected='text';display='#REF!';error=$false},
    @{value=-2146826265;expected='error';display='#REF!';error=$true}
)) {
    $cell = [pscustomobject]@{Value2=$fixture.value;Text=$fixture.display;Error=$fixture.error;NumberFormat='General';Formula='=fixture';HasFormula=$true}
    $captured = Read-ExcelCell $cell
    Assert-Contract ($captured.excel_raw_value.type -eq $fixture.expected) ('Variant type: ' + $fixture.expected)
    $json = ConvertTo-Json -InputObject $captured -Depth 10
    $roundtrip = $json | ConvertFrom-Json
    Assert-Contract ($roundtrip.excel_raw_value.type -eq $fixture.expected) ('JSON variant roundtrip: ' + $fixture.expected)
}
$target = [pscustomobject]@{Value2=$null;Formula=$null}
$target | Add-Member -MemberType ScriptMethod -Name ClearContents -Value {$this.Value2=$null; $this.Formula=$null}
Set-CaseValue $target 'text' ''
Assert-Contract ($target.Formula -ceq '=""') 'Empty text override is not a blank'
Set-CaseValue $target 'text' 'a"b'
Assert-Contract ($target.Formula -ceq '="a""b"') 'Literal quotes escaped'
Set-CaseValue $target 'number' 0
Assert-Contract ($target.Value2 -is [double] -and $target.Value2 -eq 0) 'Zero remains numeric'
Set-CaseValue $target 'boolean' $false
Assert-Contract ($target.Value2 -is [bool] -and $target.Value2 -eq $false) 'False remains boolean'
Set-CaseValue $target 'blank' $null
Assert-Contract ($null -eq $target.Value2 -and $null -eq $target.Formula) 'Blank override clears only cell contents'
try { throw [Runtime.InteropServices.COMException]::new('SYNTHETIC SESSION TEST ONLY', -2147023584) }
catch { $detail = Get-RunnerError $_ }
Assert-Contract (@($detail.chain | Where-Object hresult -eq '0x80070520').Count -eq 1) 'Session HRESULT retained'
$addType = $ast.FindAll({param($n) $n -is [Management.Automation.Language.CommandAst] -and $n.GetCommandName() -eq 'Add-Type'}, $false)
Assert-Contract ($addType.Count -eq 1) 'Exactly one declared PID identity interop'
. ([scriptblock]::Create($addType[0].Extent.Text))
Assert-Contract ($null -ne ('PceExcelProcessIdentity' -as [type])) 'PID identity declaration compiles without creating Excel'
$report = @{status='PASS';native_excel_executed=$false;fixture_kind='SYNTHETIC_CONTRACT_TEST_ONLY';checks=$checks.ToArray();count=$checks.Count;powershell=$PSVersionTable.PSVersion.ToString()}
Write-RunnerJson (Join-Path $RunDirectory 'POWERSHELL_CONTRACT_TEST.json') $report
Write-Host ('PowerShell 合同预检通过：' + $checks.Count + ' 项；未启动 Excel。')
