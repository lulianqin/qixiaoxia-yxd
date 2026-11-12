$ErrorActionPreference = "Stop"
$task = "YXD-Quote"
$script = "D:\wwwroot\qw.qixiaoxia.com\yxd\scripts\start-yxd.ps1"
schtasks /Create /TN $task /SC ONSTART /DELAY 0001:00 /RU SYSTEM /RL HIGHEST /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`"" /F
schtasks /Run /TN $task
Write-Host "Autostart installed and started: $task"
