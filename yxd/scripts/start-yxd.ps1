$ErrorActionPreference = "Stop"
$Root = "D:\wwwroot\qw.qixiaoxia.com\yxd"
$Data = "D:\wwwroot\qw.qixiaoxia.com\yxd-data"
New-Item -ItemType Directory -Force -Path $Data | Out-Null

$candidates = @(
  (Get-Command python.exe -ErrorAction SilentlyContinue).Source,
  (Get-Command py.exe -ErrorAction SilentlyContinue).Source,
  "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
  "C:\Program Files\Python312\python.exe",
  "C:\Program Files\Python311\python.exe"
) | Where-Object { $_ -and (Test-Path $_) }
$python = $candidates | Select-Object -First 1
if (-not $python) { throw "Python 3 not found. Install Python 3.12 x64 and enable Add to PATH." }

$env:HOST = "127.0.0.1"
$env:PORT = "8787"
$env:YXD_DATA_DIR = $Data
$env:PYTHONUNBUFFERED = "1"
Set-Location $Root

$existing = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" | Where-Object { $_.CommandLine -like "*$Root*server.py*" }
if ($existing) { $existing | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }

Start-Process -FilePath $python -ArgumentList "server.py" -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput "$Data\stdout.log" -RedirectStandardError "$Data\stderr.log"
Start-Sleep -Seconds 3

try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:8787/api/health" -UseBasicParsing -TimeoutSec 10
  Write-Host "YXD OK:" $r.Content
} catch {
  Write-Host "YXD FAILED:" $_.Exception.Message
  if (Test-Path "$Data\stderr.log") { Get-Content "$Data\stderr.log" -Tail 40 }
  exit 1
}

# 只有进程健康后才切换 IIS 代理，避免站点直接 502
$config = "D:\wwwroot\qw.qixiaoxia.com\web.config"
if (Test-Path $config) {
  if (-not (Test-Path "$config.yxd-backup")) { Copy-Item $config "$config.yxd-backup" -Force }
  $text = Get-Content $config -Raw
  if ($text -match "127\.0\.0\.1:8774") {
    $text.Replace("127.0.0.1:8774", "127.0.0.1:8787") | Set-Content $config -Encoding UTF8
    Write-Host "IIS web.config: 8774 -> 8787"
  }
}
Write-Host "启动成功：http://127.0.0.1:8787/"
