$ErrorActionPreference = 'Stop'

Write-Host 'V1.14.2.8.4.7 purchase-payable slice minimal gate'
& node "$PSScriptRoot/verifyPurchasePayableSliceStability.mjs"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'PASS: canonical name, selected context, three states, native fixed-column contract, and capability guard.'
