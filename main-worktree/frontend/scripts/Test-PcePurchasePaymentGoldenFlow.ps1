$ErrorActionPreference = 'Stop'
$frontendRoot = Split-Path -Parent $PSScriptRoot
Push-Location $frontendRoot
try {
  & 'D:\nodejs\npm.cmd' run verify:pce-purchase-payment-golden-flow
  exit $LASTEXITCODE
}
finally {
  Pop-Location
}
