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
    if ($function.Name -in @('Read-ExcelCell','Set-CaseValue','Restore-CaseCell','Open-ValidationCopy','Initialize-TechnicalSheet')) { . ([scriptblock]::Create($function.Extent.Text)) }
}
$openFixture = [pscustomobject]@{Calls=0;Arguments=$null;Fail=$false;Result=[pscustomobject]@{ReadOnly=$true}}
$openFixture | Add-Member -MemberType ScriptMethod -Name Open -Value {
    $this.Calls++
    $this.Arguments = @($args)
    if ($this.Fail) { throw [Runtime.InteropServices.COMException]::new('SYNTHETIC OPEN FAILURE ONLY', -2146827284) }
    return $this.Result
}
$openedFixture = Open-ValidationCopy $openFixture 'D:\isolated-fixture\source-readonly-copy.xlsx'
Assert-Contract ($openFixture.Calls -eq 1 -and $openFixture.Arguments.Count -eq 3) 'Normal Open uses exactly three arguments; no repair fallback'
Assert-Contract ($openFixture.Arguments[0] -ceq 'D:\isolated-fixture\source-readonly-copy.xlsx') 'Open uses unchanged isolated path'
Assert-Contract ($openFixture.Arguments[1] -eq 0 -and $openFixture.Arguments[1] -is [int]) 'Open disables external link update'
Assert-Contract ($openFixture.Arguments[2] -is [bool] -and $openFixture.Arguments[2]) 'Open requires ReadOnly true'
Assert-Contract ([object]::ReferenceEquals($openedFixture, $openFixture.Result)) 'Open returns actual workbook object'
$openFixture.Fail = $true
$openFailed = $false
try { [void](Open-ValidationCopy $openFixture 'D:\isolated-fixture\source-readonly-copy.xlsx') }
catch { $openFailed=$true; $openError=Get-RunnerError $_ }
Assert-Contract ($openFailed -and $openFixture.Calls -eq 2) 'Open failure propagates without repair or repeated attempts'
Assert-Contract (@($openError.chain | Where-Object hresult -eq '0x800A03EC').Count -eq 1) 'Workbooks.Open native HRESULT retained'
$nativeText = $ast.Extent.Text
Assert-Contract ($nativeText.IndexOf("Set-NativeStage 'INITIAL_NATIVE_CALCULATION'") -gt $nativeText.IndexOf('$workingBook = Open-ValidationCopy')) 'Calculation stage follows workbook open'
Assert-Contract ($nativeText -notmatch 'foreach \(\$input in') 'Automatic input variable is not repurposed'
Assert-Contract ($nativeText -notmatch '\.Save\(' -and $nativeText -notmatch '\.SaveAs\(') 'No workbook save path'
Assert-Contract ($nativeText.Contains("'PCE_NATIVE_PROBES'")) 'Technical sheet has one fixed isolated identity'
$probeFixture = [pscustomobject]@{Name='PCE_NATIVE_PROBES'}
$collisionRejected = $false
try { Initialize-TechnicalSheet @($probeFixture) ([pscustomobject]@{name='PCE_NATIVE_PROBES';persistence='UNSAVED_ISOLATED_COPY_ONLY';cells=@()}) }
catch { $collisionRejected = $_.Exception.Message -match 'NAME COLLISION' }
Assert-Contract $collisionRejected 'Never reuse or overwrite an existing source sheet for probes'
$wrongProbeRejected = $false
try { Initialize-TechnicalSheet @() ([pscustomobject]@{name='SOURCE_SHEET';persistence='UNSAVED_ISOLATED_COPY_ONLY';cells=@()}) }
catch { $wrongProbeRejected = $_.Exception.Message -match 'INVALID TECHNICAL SHEET CONTRACT' }
Assert-Contract $wrongProbeRejected 'Reject arbitrary source sheet target'
Assert-Contract ($nativeText.Contains("$" + "workingBook.Close($" + "false)")) 'Owned workbook closed without saving'
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
foreach ($errorCase in @(@{code=2007;text='#DIV/0!'},@{code=2015;text='#VALUE!'},@{code=2023;text='#REF!'})) {
    $variant = [int](-2146828288 + $errorCase.code)
    $narrow = [pscustomobject]@{Value2=$variant;Text='######';Error=$true;NumberFormat='0';Formula='=fixture';HasFormula=$true}
    $captured = Read-ExcelCell $narrow
    Assert-Contract ($captured.excel_raw_value.value -ceq $errorCase.text) ('Narrow column CVError identity: ' + $errorCase.text)
    Assert-Contract ($captured.native_variant_value -eq $variant -and $captured.excel_displayed_value -ceq '######') 'Raw variant and displayed hashes both retained'
}
$unsupportedErrorRejected = $false
try { [void](Read-ExcelCell ([pscustomobject]@{Value2='######';Text='######';Error=$true;NumberFormat='0';Formula='=fixture';HasFormula=$true})) }
catch { $unsupportedErrorRejected = $true }
Assert-Contract $unsupportedErrorRejected 'Missing native error identity never falls back to display text'
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
Add-Type -TypeDefinition @'
using System;
public class PceRestoreContractCell {
    private object value;
    private string formula;
    public bool HasFormula { get; private set; }
    public string NumberFormat { get; set; }
    public PceRestoreContractCell() { NumberFormat = "General"; }
    public int Writes { get; private set; }
    public bool CorruptBool { get; set; }
    public object Value2 {
        get { return value; }
        set {
            if (value != null && value.GetType() != typeof(double) && value.GetType() != typeof(bool) && value.GetType() != typeof(string))
                throw new InvalidCastException("Fixture rejects untyped/non-primitive COM-like argument");
            this.value = CorruptBool && value is bool ? (object)0.0 : value;
            HasFormula = false; formula = null; Writes++;
        }
    }
    public string Formula { get { return formula; } set { formula=value; HasFormula=true; Writes++; } }
    public void ClearContents() { value=null; formula=null; HasFormula=false; Writes++; }
}
'@
foreach ($v in @([double]100,[int]100,[long]100,[decimal]0.2,[single]1.5,[double]0,$false,$true,$null,'001','=not-a-formula','a"b')) {
    $restoreCell = [PceRestoreContractCell]::new()
    $state = [pscustomobject]@{has_formula=$false;formula=$null;value=$v;number_format='General'}
    Restore-CaseCell $restoreCell $state
    Assert-Contract ($restoreCell.Writes -eq 1 -and -not $restoreCell.HasFormula) ('Typed saved-state restore: ' + $(if ($null -eq $v) {'blank'} else {$v.GetType().Name + ':' + [string]$v}))
    Assert-Contract ($restoreCell.NumberFormat -ceq 'General') 'Restore preserves original number format'
}
$formulaRestore = [PceRestoreContractCell]::new()
Restore-CaseCell $formulaRestore ([pscustomobject]@{has_formula=$true;formula='=""';value='';number_format='General'})
Assert-Contract ($formulaRestore.HasFormula -and $formulaRestore.Formula -ceq '=""') 'Empty-string source formula restored as formula'
$badRestore = [PceRestoreContractCell]::new()
$badRestore.CorruptBool = $true
$restoreRejected = $false
try { Restore-CaseCell $badRestore ([pscustomobject]@{has_formula=$false;formula=$null;value=$false;number_format='General'}) }
catch { $restoreRejected = $_.Exception.Message -match 'BOOLEAN TYPE MISMATCH' }
Assert-Contract $restoreRejected 'Restore rejects FALSE silently coerced to numeric zero'
Assert-Contract (-not $nativeText.Contains('$cell.Value2 = $saved.value')) 'Native restoration never passes an untyped saved object to COM setter'
Assert-Contract ($nativeText.Contains('Restore-CaseCell $cell $saved')) 'Actual Native case loop uses tested restoration function'
Assert-Contract ($nativeText.IndexOf('Restore-CaseCell $cell $saved') -lt $nativeText.IndexOf('$results.Add(')) 'Native case commits only after verified restoration'
Assert-Contract ($nativeText.Contains("'COMMITTED_RESTORED_CASE'")) 'Native failure diagnostics expose case phase'
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
