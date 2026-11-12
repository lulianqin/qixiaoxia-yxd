$Root = "D:\wwwroot\qw.qixiaoxia.com\yxd"
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" | Where-Object { $_.CommandLine -like "*$Root*server.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host "YXD stopped."
