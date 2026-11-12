<#
.SYNOPSIS
    安全重启 yxd 报价服务（Windows PowerShell 5.1 兼容）。

.DESCRIPTION
    流程：预检 -> 备份 -> 校验 engine.py -> 按 PID 停服 -> 调 start-yxd.ps1 启动 -> 健康检查 -> quote-compare 自测。
    任一步失败立即停止并打印诊断与回滚命令。
    不调用 deploy-now.ps1，不使用 taskkill /IM python.exe。

    端口检测策略（三重兜底）：
      1) Get-NetTCPConnection（部分系统无此 cmdlet 或查询会失败，失败后不再短路）
      2) netstat -ano 解析：只看本地地址端口，PID 取行尾，不依赖本地化的状态列
      3) Win32_Process 命令行匹配 server.py（仅当命令行含本目录时才允许自动停止，避免误杀另一套系统）
    若“端口无监听但健康检查 200”，视为异常：先打印诊断，再中止，绝不叠起第二个进程。
    若同一端口出现多个监听进程（Windows SO_REUSEADDR 叠加），预检告警、停服时全部结束、启动后再出现多个即判失败。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File D:\wwwroot\qw.qixiaoxia.com\yxd\scripts\restart-yxd.ps1
#>
[CmdletBinding()]
param(
    [string]$Root = 'D:\wwwroot\qw.qixiaoxia.com\yxd',
    [string]$Data = 'D:\wwwroot\qw.qixiaoxia.com\yxd-data',
    [int]$Port = 8787,
    [int]$HealthTimeoutSec = 45
)

$ErrorActionPreference = 'Stop'
$BaseUrl = 'http://127.0.0.1:' + $Port
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$EngineFile = Join-Path $Root 'core\engine.py'
$StartScript = Join-Path $Root 'scripts\start-yxd.ps1'
$ServerFile = Join-Path $Root 'server.py'
$ErrLog = Join-Path $Data 'stderr.log'
$EngineBackup = ''

$script:PortDiag = @()
$script:NetRaw = @()
$script:CimAvailable = $true

# ------------------------------------------------------------------ 输出辅助
function Write-Step([string]$Text) {
    Write-Host ''
    Write-Host ('== ' + $Text) -ForegroundColor Cyan
}
function Write-Ok([string]$Text) {
    Write-Host ('   [OK] ' + $Text) -ForegroundColor Green
}
function Write-Note([string]$Text) {
    Write-Host ('   [..] ' + $Text)
}
function Write-WarnNote([string]$Text) {
    Write-Host ('   [WARN] ' + $Text) -ForegroundColor Yellow
}
function Format-Time($Value) {
    if ($null -eq $Value) { return '未知' }
    try { return ([datetime]$Value).ToString('yyyy-MM-dd HH:mm:ss') } catch { return [string]$Value }
}

# 失败即停：打印诊断为与回滚命令后退出，绝不静默继续
function Exit-Fail([string]$Text) {
    Write-Host ('   [FAIL] ' + $Text) -ForegroundColor Red
    Write-Host ''
    Write-Host '已中止。恢复步骤（复制粘贴执行，先确认 PID 再杀）：' -ForegroundColor Yellow
    Write-Host ('  netstat -ano | findstr :' + $script:Port)
    if ($script:EngineBackup -and (Test-Path $script:EngineBackup)) {
        Write-Host ('  Copy-Item "' + $script:EngineBackup + '" "' + $script:EngineFile + '" -Force')
    }
    Write-Host ('  Get-Process -Id <PID> | Select-Object Id,StartTime,Path   # 确认是要停的 python')
    Write-Host ('  Stop-Process -Id <PID> -Force')
    Write-Host ('  powershell -NoProfile -ExecutionPolicy Bypass -File "' + $script:StartScript + '"')
    if (Test-Path $script:ErrLog) {
        Write-Host ''
        Write-Host ('stderr.log 最后 30 行：' + $script:ErrLog)
        Get-Content $script:ErrLog -Tail 30
    }
    exit 1
}

# 取监听指定端口的 PID：cmdlet + netstat 双通道合并；失败不短路
# 用 CmdletBinding + ValidateRange：参数名写错会立刻报错，而不是被静默塞进 $args（曾导致 Port=0）
function Get-ListeningPid {
    [CmdletBinding()]
    param(
        [ValidateRange(1, 65535)][int]$ListenPort,
        [switch]$Quiet
    )
    if (-not $Quiet) { $script:PortDiag = @(); $script:NetRaw = @() }
    $found = @()

    # 通道一：Get-NetTCPConnection（Win8/2012+ 才有；部分机器存在但查询会报错）
    $cmd = Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            $items = @(Get-NetTCPConnection -LocalPort $ListenPort -ErrorAction Stop)
            foreach ($item in $items) {
                if ([string]$item.State -eq 'Listen') { $found += [int]$item.OwningProcess }
            }
            if (-not $Quiet) { $script:PortDiag += ('Get-NetTCPConnection: 返回 ' + $items.Count + ' 条') }
        } catch {
            if (-not $Quiet) { $script:PortDiag += ('Get-NetTCPConnection 查询失败: ' + $_.Exception.Message) }
        }
    } else {
        if (-not $Quiet) { $script:PortDiag += 'Get-NetTCPConnection: 本机不存在该 cmdlet' }
    }

    # 通道二：netstat（不依赖状态列文字；本地地址匹配端口，PID 固定取行尾，兼容 IPv4/IPv6/[::1]）
    $netLines = @()
    try {
        $netLines = @(& netstat -ano 2>$null)
    } catch {
        if (-not $Quiet) { $script:PortDiag += ('netstat 执行失败: ' + $_.Exception.Message) }
    }
    if (-not $Quiet) {
        $script:PortDiag += ('netstat: 共 ' + $netLines.Count + ' 行')
        foreach ($line in $netLines) {
            # 精确匹配“本地地址”列以该端口结尾，避免 :0 命中全表（远端列常见 0.0.0.0:0）
            if ($line -match ('^\s*TCP\s+\S+:' + $ListenPort + '\s')) { $script:NetRaw += $line }
        }
    }

    $strictPattern = '^\s*TCP\s+\S+:' + $ListenPort + '\s+\S+:0\s+.*?(\d+)\s*$'
    $loosePattern = '^\s*TCP\s+\S+:' + $ListenPort + '\s+\S+\s+.*?(\d+)\s*$'
    foreach ($line in $netLines) {
        $linePid = 0
        if ($line -match $strictPattern) {
            $linePid = [int]($Matches[1])
        } elseif ($line -match $loosePattern) {
            $linePid = [int]($Matches[1])
        }
        # PID 0 是 TIME_WAIT/已关闭连接的占位，不是监听进程，必须排除
        if ($linePid -gt 0) { $found += $linePid }
    }

    $found = @($found | Sort-Object -Unique)
    if (-not $Quiet) { $script:PortDiag += ('合并解析到 PID: ' + ($found -join ', ')) }
    return $found
}

# 列出 python 跑 server.py 的进程；IsUnderRoot 表示命令行含本目录（可安全停止）
function Get-PythonServerProcesses {
    $list = @()
    try {
        $all = @(Get-CimInstance Win32_Process -Filter "name = 'python.exe'" -ErrorAction Stop)
    } catch {
        $script:CimAvailable = $false
        $script:PortDiag += ('Win32_Process 查询失败: ' + $_.Exception.Message)
        return @()
    }
    foreach ($proc in $all) {
        $cmdLine = [string]$proc.CommandLine
        if (-not $cmdLine) { continue }
        if ($cmdLine -notlike '*server.py*') { continue }
        $created = $null
        try { $created = [datetime]$proc.CreationDate } catch { }
        $list += [pscustomobject]@{
            ProcessId = [int]$proc.ProcessId
            CreationDate = $created
            CommandLine = $cmdLine
            IsUnderRoot = ($cmdLine -like ('*' + $Root + '*'))
        }
    }
    return $list
}

# 健康检查：临时禁用系统代理，避免把 200 误判成本地服务
function Test-Health([string]$Url) {
    $savedProxy = [System.Net.WebRequest]::DefaultWebProxy
    try {
        [System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            return [int]$resp.StatusCode
        } catch {
            return 0
        }
    } finally {
        [System.Net.WebRequest]::DefaultWebProxy = $savedProxy
    }
}

# POST JSON，返回 Code/Body（5.1 下 4xx/5xx 会抛异常，需要从响应流取正文）
function Invoke-PostJson([string]$Url, [string]$JsonBody) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($JsonBody)
    $savedProxy = [System.Net.WebRequest]::DefaultWebProxy
    try {
        [System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy
        try {
            $resp = Invoke-WebRequest -Uri $Url -Method Post -ContentType 'application/json; charset=utf-8' `
                -Body $bytes -UseBasicParsing -TimeoutSec 30
            return [pscustomobject]@{ Code = [int]$resp.StatusCode; Body = [string]$resp.Content }
        } catch {
            $code = 0
            $bodyText = $_.Exception.Message
            if ($_.Exception.Response) {
                try { $code = [int]$_.Exception.Response.StatusCode } catch { }
            }
            if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
                $bodyText = $_.ErrorDetails.Message
            } elseif ($_.Exception.Response) {
                try {
                    $stream = $_.Exception.Response.GetResponseStream()
                    if ($stream) {
                        $reader = New-Object System.IO.StreamReader($stream)
                        $bodyText = $reader.ReadToEnd()
                        $reader.Close()
                    }
                } catch { }
            }
            return [pscustomobject]@{ Code = $code; Body = [string]$bodyText }
        }
    } finally {
        [System.Net.WebRequest]::DefaultWebProxy = $savedProxy
    }
}

# 诊断：netstat 原始行 + 所有 python 进程 + 健康状态
function Show-Diagnostics {
    Write-Host ''
    Write-Host '---- 诊断信息 ----' -ForegroundColor Yellow
    foreach ($item in $script:PortDiag) { Write-Host ('  ' + $item) }
    if ($script:NetRaw.Count -gt 0) {
        Write-Host ('  netstat 中含 :' + $Port + ' 的原始行：')
        foreach ($line in $script:NetRaw) { Write-Host ('    ' + $line) }
    } else {
        Write-Host ('  netstat 中没有含 :' + $Port + ' 的行')
    }
    Write-Host '  python.exe 进程（PID / 启动时间 / 命令行）：'
    $procs = @(Get-Process -Name python -ErrorAction SilentlyContinue)
    if ($procs.Count -eq 0) { Write-Host '    (无 python 进程)' }
    foreach ($proc in $procs) {
        $cmdLine = ''
        try {
            $wmi = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $proc.Id) -ErrorAction Stop
            $cmdLine = [string]$wmi.CommandLine
        } catch { }
        $startTime = ''
        try { $startTime = $proc.StartTime.ToString('yyyy-MM-dd HH:mm:ss') } catch { $startTime = '未知' }
        Write-Host ('    PID ' + $proc.Id + '  ' + $startTime + '  ' + $cmdLine)
    }
    Write-Host ('  健康检查（绕过代理）：HTTP ' + (Test-Health ($BaseUrl + '/api/health')))
    Write-Host ('  手工确认命令：netstat -ano | findstr :' + $Port)
    Write-Host '------------------' -ForegroundColor Yellow
}

# 打印监听指定端口的全部进程（多进程叠加时用于逐个定位）
function Show-ListenerInfo {
    [CmdletBinding()]
    param([ValidateRange(1, 65535)][int]$ListenPort)
    $pids = @(Get-ListeningPid -ListenPort $ListenPort -Quiet)
    if ($pids.Count -eq 0) {
        Write-Note '  （没有解析到监听进程）'
        return
    }
    foreach ($procId in $pids) {
        $startTime = '未知'
        $procObj = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($procObj) {
            try { $startTime = $procObj.StartTime.ToString('yyyy-MM-dd HH:mm:ss') } catch { }
        }
        $cmdLine = ''
        try {
            $wmi = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $procId) -ErrorAction Stop
            $cmdLine = [string]$wmi.CommandLine
        } catch { }
        Write-Note ('  PID ' + $procId + '  启动 ' + $startTime + '  ' + $cmdLine)
    }
}

# ================================================================== 1 预检
Write-Step ('1/7 预检（Root=' + $Root + '，Data=' + $Data + '，Port=' + $Port + '）')

if (-not (Test-Path $ServerFile)) { Exit-Fail ('缺少文件：' + $ServerFile + '（路径不对或 yxd 未部署）') }
if (-not (Test-Path $StartScript)) { Exit-Fail ('缺少启动脚本：' + $StartScript) }
if (-not (Test-Path $EngineFile)) { Exit-Fail ('缺少文件：' + $EngineFile) }
if (-not (Test-Path $Data)) { Exit-Fail ('数据目录不存在：' + $Data) }
Write-Ok '必要文件与目录均存在'

$py = Get-Command python.exe -ErrorAction SilentlyContinue
if ($py) {
    Write-Ok ('PATH 中的解释器：' + $py.Source)
    if ($py.Source -like '*\WindowsApps\*') {
        Write-WarnNote '这是应用商店占位程序，start-yxd.ps1 会启动失败；请把真实 python.exe 放到 PATH 前面'
    }
    try {
        $pyVer = (& $py.Source -V 2>&1 | Out-String).Trim()
        Write-Note ('版本：' + $pyVer)
    } catch {
        Write-WarnNote ('读不到版本：' + $_.Exception.Message)
    }
} else {
    Write-WarnNote 'PATH 中找不到 python.exe；start-yxd.ps1 会尝试 Python312/311 固定路径，仍失败则启动会报错'
}

$healthBefore = Test-Health ($BaseUrl + '/api/health')
$oldPortPids = @(Get-ListeningPid -ListenPort $Port)
$serverProcs = @(Get-PythonServerProcesses)
$underRootPids = @($serverProcs | Where-Object { $_.IsUnderRoot } | ForEach-Object { $_.ProcessId })

# 端口检测可靠性探针：135 是 Windows 常驻 RPC 端口
$probePids = @(Get-ListeningPid -ListenPort 135 -Quiet)
$portDetectReliable = ($probePids.Count -gt 0)
if ($portDetectReliable) {
    Write-Note '端口检测可用（135 探针命中）'
} else {
    Write-WarnNote '端口检测不可靠（135 探针也为空）：后续以进程创建时间/PID 为准，不硬依赖端口'
}

if ($oldPortPids.Count -gt 0) {
    Write-Ok ('解析到监听 ' + $Port + ' 的 PID：' + ($oldPortPids -join ', '))
} else {
    Write-WarnNote ('没有解析到监听 ' + $Port + ' 的 PID')
}
if ($oldPortPids.Count -gt 1) {
    Write-WarnNote ('多进程叠加：' + $oldPortPids.Count + ' 个进程同时监听 ' + $Port + '。' +
        'Windows 下 allow_reuse_address/SO_REUSEADDR 允许重复绑定同一端口，请求会随机落到任一进程（命中旧进程即 500）')
    Show-ListenerInfo -ListenPort $Port
}
if ($serverProcs.Count -gt 1 -and $oldPortPids.Count -le 1) {
    Write-WarnNote ('发现 ' + $serverProcs.Count + ' 个 python server.py 进程（可能包含另一套系统）：请用 netstat 确认哪个在监听 ' + $Port)
}

if ($serverProcs.Count -gt 0) {
    foreach ($sp in $serverProcs) {
        $flag = '（命令行不含本目录：仅作诊断，不作为补充停止目标；若它监听端口，仍会按端口 PID 停止）'
        if ($sp.IsUnderRoot) { $flag = '（命令行含本目录：作为补充停止目标）' }
        Write-Note ('python server.py：PID ' + $sp.ProcessId + '，启动 ' + (Format-Time $sp.CreationDate) + $flag)
    }
} else {
    Write-Note '未发现 server.py 进程'
}

if ($healthBefore -eq 200) {
    Write-Ok '健康检查：HTTP 200'
    if ($oldPortPids.Count -eq 0 -and $underRootPids.Count -eq 0) {
        Write-WarnNote '异常：健康 200 但定位不到监听进程，先打印诊断（停服阶段会再校验一次）'
        Show-Diagnostics
    }
} else {
    Write-WarnNote ('健康检查未通过（HTTP ' + $healthBefore + '），服务可能已停')
}

$taskName = 'YXD-Quote'
$null = schtasks /Query /TN $taskName 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Ok ('计划任务存在：' + $taskName)
} else {
    Write-WarnNote ('计划任务不存在：' + $taskName + '（不影响本次重启；需要开机自启请另行执行 install-autostart.ps1）')
}

# ================================================================== 2 备份
Write-Step ('2/7 备份（时间戳 ' + $Stamp + '，已存在则不覆盖）')

if (Test-Path $ErrLog) {
    $logBak = Join-Path $Data ('stderr.log.bak-' + $Stamp)
    if (Test-Path $logBak) {
        Write-WarnNote ('备份已存在，跳过：' + $logBak)
    } else {
        try { Copy-Item $ErrLog $logBak -Force } catch { Exit-Fail ('备份 stderr.log 失败：' + $_.Exception.Message) }
        Write-Ok ('日志已备份：' + $logBak)
    }
} else {
    Write-WarnNote '没有 stderr.log，跳过日志备份'
}

$EngineBackup = Join-Path $Root ('core\engine.py.bak-' + $Stamp)
if (Test-Path $EngineBackup) {
    Write-WarnNote ('备份已存在，跳过：' + $EngineBackup)
} else {
    try { Copy-Item $EngineFile $EngineBackup -Force } catch { Exit-Fail ('备份 engine.py 失败：' + $_.Exception.Message) }
    Write-Ok ('代码已备份：' + $EngineBackup)
}

# ================================================================== 3 校验
Write-Step '3/7 校验 engine.py 是否为低版本兼容写法'

$bad = @(Select-String -Path $EngineFile -Pattern '\|\s*\{' -AllMatches -ErrorAction SilentlyContinue)
if ($bad.Count -gt 0) {
    $badLines = ($bad | ForEach-Object { $_.LineNumber }) -join ', '
    Exit-Fail ('engine.py 仍有 dict | 合并（行号 ' + $badLines + '）：当前文件不是修复版，请先同步再重启')
}
Write-Ok '未发现 "| {...}" 形式的字典合并'

$good = @(Select-String -Path $EngineFile -Pattern '\*\*self\._logistics_conf' -ErrorAction SilentlyContinue)
if ($good.Count -eq 0) {
    Exit-Fail '未找到 {**self._logistics_conf(...)}：engine.py 可能未同步完成或被旧文件覆盖'
}
Write-Ok ('已确认修复行存在（第 ' + $good[0].LineNumber + ' 行）')

try {
    $hash = (Get-FileHash $EngineFile -Algorithm SHA256).Hash
    Write-Note ('engine.py SHA256：' + $hash)
} catch {
    Write-WarnNote ('计算哈希失败：' + $_.Exception.Message)
}

# ================================================================== 4 停服
Write-Step ('4/7 停止服务（按 PID 停止，端口 ' + $Port + '）')

# 端口解析出的监听 PID 是权威依据：无论其命令行是否含目录，一律纳入停止目标；
# 目录匹配只用于补充“命令行确实指向本目录、但当前没在监听”的残留进程
$portPids = @(Get-ListeningPid -ListenPort $Port)
$procs = @(Get-PythonServerProcesses)
$rootPids = @($procs | Where-Object { $_.IsUnderRoot } | ForEach-Object { $_.ProcessId })
$targetPids = @(@($portPids) + @($rootPids) | Sort-Object -Unique)
$healthNow = Test-Health ($BaseUrl + '/api/health')

if ($targetPids.Count -eq 0) {
    if ($healthNow -eq 200) {
        Write-WarnNote '“端口无监听但健康 200”的矛盾状态：为避免再叠起一个进程造成端口冲突，已停止操作'
        Show-Diagnostics
        Exit-Fail ('无法定位正在服务 ' + $Port + ' 的进程，不能安全停服。请按诊断中的 PID 执行 Stop-Process -Id <PID> -Force，确认端口释放后重跑本脚本')
    }
    Write-WarnNote ('未发现监听进程（当前健康 HTTP ' + $healthNow + '），跳过停止')
} else {
    Write-Note ('待停止 PID：' + ($targetPids -join ', '))
    if ($targetPids.Count -gt 1) {
        Write-WarnNote ('命中 ' + $targetPids.Count + ' 个进程（多进程叠加），将全部停止')
    }
    foreach ($procId in $targetPids) {
        $procObj = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if (-not $procObj) {
            Write-WarnNote ('PID ' + $procId + ' 已不存在')
            continue
        }
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Ok ('已结束 PID ' + $procId)
        } catch {
            Exit-Fail ('结束 PID ' + $procId + ' 失败：' + $_.Exception.Message + '（请用管理员身份运行）')
        }
    }
}

$released = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    $alive = @($targetPids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
    $stillListen = @(Get-ListeningPid -ListenPort $Port)
    $portOk = ($stillListen.Count -eq 0) -or (-not $portDetectReliable)
    if ($alive.Count -eq 0 -and $portOk) { $released = $true; break }
}
if (-not $released) {
    Show-Diagnostics
    Exit-Fail ('目标进程/端口在 10 秒内未完全释放，可能权限不足或被其它程序占用')
}
Write-Ok ('停止完成' + $(if ($portDetectReliable) { ('，端口 ' + $Port + ' 已释放') } else { '（端口检测不可用，按进程已退出判定）' }))

# ================================================================== 5 启动
Write-Step '5/7 启动（调用 start-yxd.ps1，不使用 deploy-now.ps1）'

$startedAt = Get-Date
$watch = [System.Diagnostics.Stopwatch]::StartNew()
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript
if ($LASTEXITCODE -ne 0) {
    $watch.Stop()
    Exit-Fail ('start-yxd.ps1 退出码 ' + $LASTEXITCODE + '，服务未起来')
}
Write-Ok 'start-yxd.ps1 执行完成'

# ================================================================== 6 健康检查 + 进程身份确认
Write-Step ('6/7 等待健康检查（最长 ' + $HealthTimeoutSec + ' 秒）并确认是新进程')

$healthy = $false
$deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
while ((Get-Date) -lt $deadline) {
    if ((Test-Health ($BaseUrl + '/api/health')) -eq 200) { $healthy = $true; break }
    Start-Sleep -Milliseconds 800
}
if (-not $healthy) {
    $watch.Stop()
    Exit-Fail ('健康检查在 ' + $HealthTimeoutSec + ' 秒内未通过：' + $BaseUrl + '/api/health')
}
Write-Ok ('健康检查通过：' + $BaseUrl + '/api/health')

$stalePids = @($targetPids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
if ($stalePids.Count -gt 0) {
    $watch.Stop()
    Exit-Fail ('旧进程仍在运行：PID ' + ($stalePids -join ', ') + '，健康 200 来自旧进程')
}

$newPortPids = @(Get-ListeningPid -ListenPort $Port)
if ($newPortPids.Count -gt 1) {
    Show-ListenerInfo -ListenPort $Port
    $watch.Stop()
    Exit-Fail ('启动后仍有 ' + $newPortPids.Count + ' 个进程监听 ' + $Port + '（PID ' + ($newPortPids -join ', ') +
        '）：多进程叠加未清理干净，请求会随机命中旧进程')
}
$newProcs = @(Get-PythonServerProcesses)
$freshProcs = @($newProcs | Where-Object { $null -ne $_.CreationDate -and ([datetime]$_.CreationDate) -ge $startedAt.AddSeconds(-5) })

if ($newPortPids.Count -gt 0) {
    $overlap = @($targetPids | Where-Object { $newPortPids -contains $_ })
    if ($overlap.Count -gt 0) {
        $watch.Stop()
        Exit-Fail ('监听 ' + $Port + ' 的 PID 仍是旧进程：' + ($overlap -join ', '))
    }
    Write-Ok ('新监听 PID：' + ($newPortPids -join ', '))
} elseif ($portDetectReliable) {
    $watch.Stop()
    Show-Diagnostics
    Exit-Fail ('端口检测可用但 ' + $Port + ' 无监听：健康 200 可能来自代理或其它服务，服务状态异常')
}

if ($freshProcs.Count -gt 0) {
    Write-Ok ('启动后新建的 server.py 进程：PID ' + (($freshProcs | ForEach-Object { $_.ProcessId }) -join ', ') +
        '，启动时间 ' + (Format-Time $freshProcs[0].CreationDate))
} elseif ($script:CimAvailable) {
    $watch.Stop()
    Show-Diagnostics
    Exit-Fail '未发现启动后新建的 server.py 进程：健康 200 极可能来自旧进程（假成功），请按诊断手工处理'
} else {
    Write-WarnNote 'WMI 不可用，跳过“进程创建时间”校验；请用 netstat 人工确认 PID 已变化'
}

$displayPids = @($newPortPids)
if ($displayPids.Count -eq 0) { $displayPids = @($freshProcs | ForEach-Object { $_.ProcessId }) }

# ================================================================== 7 自测
Write-Step '7/7 quote-compare 自测（bag-kraft 请求体）'

$testBody = '{"product_id":"bag-kraft","config":{"mode":"custom","qty":100,"dims":{"L":300,"W":120,"H":400},"material_id":"mat-kraft120","aux":{"handle":"aux-rope-paper"},"colors":2,"processes":[],"packaging_id":"pkg-standard"}}'
$result = Invoke-PostJson ($BaseUrl + '/api/admin/quote-compare') $testBody

if ($result.Code -eq 200) {
    $json = $null
    try {
        $json = $result.Body | ConvertFrom-Json
    } catch {
        Exit-Fail ('接口返回不是合法 JSON：' + $result.Body)
    }
    if ($json.ok -ne $true) {
        Exit-Fail ('接口 ok 不为 true：' + $result.Body)
    }
    if ($null -eq $json.quote) {
        Exit-Fail ('接口返回缺少 quote 字段：' + $result.Body)
    }
    $sourceCount = 0
    if ($null -ne $json.sources) { $sourceCount = @($json.sources).Count }
    $recId = '(无)'
    if ($null -ne $json.recommended -and $json.recommended.id) { $recId = [string]$json.recommended.id }
    Write-Ok ('quote-compare 通过：sources=' + $sourceCount + '，recommended=' + $recId + '，retail=' + $json.quote.totals.retail)
} elseif ($result.Code -eq 401 -or $result.Code -eq 403) {
    Write-WarnNote ('接口需要登录（HTTP ' + $result.Code + '），跳过内容校验；请在浏览器点一次「工厂比价」确认')
} elseif ($result.Body -like '*unsupported operand type*') {
    Exit-Fail ('quote-compare 报 dict | dict：当前仍是旧代码进程（HTTP ' + $result.Code + '）：' + $result.Body)
} else {
    Exit-Fail ('quote-compare 返回 HTTP ' + $result.Code + '：' + $result.Body)
}

$watch.Stop()
$elapsed = [math]::Round($watch.Elapsed.TotalSeconds, 1)
Write-Host ''
Write-Host ('重启完成：耗时 ' + $elapsed + ' 秒，监听 PID ' + ($displayPids -join ', ') + '，端口 ' + $Port) -ForegroundColor Green
if (-not $portDetectReliable) {
    Write-Host '注意：本机端口检测不可靠，上面的 PID 来自 netstat/进程列表，请再用 netstat -ano | findstr :8787 复核一次。' -ForegroundColor Yellow
}
exit 0
