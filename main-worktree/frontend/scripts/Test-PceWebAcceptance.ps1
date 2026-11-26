$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendRoot = Split-Path -Parent $scriptRoot
Set-Location -LiteralPath $frontendRoot
& npm.cmd run gate:pce-web-acceptance:all
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
exit 0
