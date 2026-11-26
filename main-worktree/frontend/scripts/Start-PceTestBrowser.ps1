param(
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
  [string]$ProfileDir = 'D:\Dev-PCE\TestBrowserProfile',
  [int]$Port = 5173,
  [int]$DebugPort = 9222
)

$ErrorActionPreference = 'Stop'

function T {
  param([string]$Base64)
  return [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($Base64))
}

function Test-PortOpen {
  param([int]$TargetPort)
  $lines = netstat -ano | Select-String ":$TargetPort\s+.*LISTENING"
  return [bool]$lines
}

function Resolve-ChromePath {
  $candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
  )
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) {
      return $candidate
    }
  }
  $command = Get-Command chrome.exe -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Source
  }
  throw 'Chrome not found. Install local Chrome before starting the PCE test browser.'
}

if (-not (Test-PortOpen -TargetPort $Port)) {
  $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
  $npmCmd = if ($npmCommand) { $npmCommand.Source } else { $null }
  if (-not $npmCmd) {
    throw 'npm.cmd not found. Cannot start Vite dev server.'
  }
  Start-Process -FilePath $npmCmd -ArgumentList @('run', 'dev') -WorkingDirectory $ProjectRoot -WindowStyle Hidden
  $deadline = (Get-Date).AddSeconds(30)
  while (-not (Test-PortOpen -TargetPort $Port)) {
    if ((Get-Date) -gt $deadline) {
      throw "Vite dev server did not start on port $Port."
    }
    Start-Sleep -Milliseconds 500
  }
}

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null

$chromePath = Resolve-ChromePath
$targetUrl = "http://localhost:$Port/#/finance/payable-prepares"
$chromeArgs = @(
  "--remote-debugging-port=$DebugPort",
  "--user-data-dir=$ProfileDir",
  '--no-first-run',
  '--no-default-browser-check',
  $targetUrl
)

Start-Process -FilePath $chromePath -ArgumentList $chromeArgs -WindowStyle Normal

Write-Host (T 'UENF5rWL6K+V5rWP6KeI5Zmo5bey57uP5ZCv5Yqo44CC')
Write-Host "$(T '5LiT55So5rWP6KeI5Zmo5pWw5o2u55uu5b2V77ya')$ProfileDir"
Write-Host "$(T '5omT5byA6aG16Z2i77ya')$targetUrl"
Write-Host (T '5pyq5L2/55So55So5oi35pmu6YCaIENocm9tZSDphY3nva7nm67lvZXjgII=')
