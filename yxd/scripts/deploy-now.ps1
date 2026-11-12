$ErrorActionPreference = "Stop"
$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $python) {
  $python = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "C:\Program Files\Python312\python.exe"
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $python) {
  if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
    Write-Host "Python not found. Installing Python 3.12 via winget..."
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
  } else {
    throw "Python 3 not found, and winget is unavailable. Install Python 3.12 x64 manually, enable Add to PATH, then rerun this script."
  }
}
& "D:\wwwroot\qw.qixiaoxia.com\yxd\scripts\start-yxd.ps1"
& "D:\wwwroot\qw.qixiaoxia.com\yxd\scripts\install-autostart.ps1"
